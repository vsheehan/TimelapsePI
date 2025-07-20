import os
import zipfile
import threading
from datetime import datetime
from pathlib import Path
from threading import Thread

from lib.class_config import Config
from lib.class_logging import Logger
from lib.class_session import Session
from lib.class_temp import TempZip
from lib.class_socket import SocketManager


class ZipTask:
    _lock = threading.Lock()
    _thread = None
    _cancel_requested = False

    def __new__(cls):
        raise RuntimeError("Use classmethods only — do not instantiate ZipTask")

    @classmethod
    def run_job(cls, job):
        if cls._thread and cls._thread.is_alive():
            Logger.warning("ZIP job already in progress", category="zip")
            return

        cls._cancel_requested = False
        cls._thread = Thread(target=cls._dispatch, args=(job,), daemon=True)
        cls._thread.start()

    @classmethod
    def cancel(cls):
        if not cls._thread or not cls._thread.is_alive():
            return False
        cls._cancel_requested = True
        cls._thread.join(timeout=3)
        Logger.info("ZIP task cancelled by user", category="zip")
        SocketManager.emit("zip-cancelled", {})
        return True

    @classmethod
    def is_running(cls):
        return cls._thread and cls._thread.is_alive()

    @classmethod
    def _dispatch(cls, job):
        if isinstance(job, dict) and "from_dt" in job and "to_dt" in job:
            Logger.info("Starting zip by datetime range", category="zip")
            from_dt, to_dt = cls._parse_range(job["from_dt"], job["to_dt"])
            cls._emit("zip-started", {"type": "range-precise", "from": from_dt.isoformat(), "to": to_dt.isoformat()})
            results = cls._zip_by_range(from_dt, to_dt)
            if results:
                cls._emit("zip-complete", {"type": "range-precise", "results": results})
            return

        if isinstance(job, list):
            Logger.info(f"Starting multi-session zip for {len(job)} sessions", category="zip")
            cls._emit("zip-started", {"type": "sessions-multi", "session_ids": job, "total": len(job)})
            results = cls._zip_multi_session(job)
            cls._emit("zip-complete", {"type": "sessions-multi", "results": results, "count": len(results)})
            return

        if isinstance(job, str):
            Logger.info(f"Starting single session zip: {job}", category="zip")
            cls._emit("zip-started", {"type": "session-single", "session_id": job})
            try:
                results = cls._zip_single_session(job)
                if results:
                    cls._emit("zip-complete", {"type": "session-single", "result": results})
            except Exception as e:
                Logger.error(f"ZIP error: {e}", category="zip")
                cls._emit("zip-error", {"message": str(e)})
            return

        Logger.error("ZIP job input was invalid", category="zip")
        cls._emit("zip-error", {"message": "Invalid zip job format."})

    @classmethod
    def _parse_range(cls, from_str, to_str):
        try:
            from_dt = datetime.fromisoformat(from_str).replace(second=0)
        except Exception:
            from_dt = datetime.min
        try:
            to_dt = datetime.fromisoformat(to_str).replace(second=59)
        except Exception:
            to_dt = datetime.max
        return from_dt, to_dt

    @classmethod
    def _zip_single_session(cls, session_id):
        if not cls._lock.acquire(blocking=False):
            cls._emit("zip-error", {"message": "Another ZIP task is already running."})
            return

        try:
            session = Session.by_id(session_id)
            if not session:
                raise ValueError(f"Session {session_id} not found")

            is_idle = session.get("status") == "idle"
            zip_name = f"session_{session_id}.zip"
            zip_dir = Config.get("download_path") / ("temp" if not is_idle else "")
            zip_path = zip_dir / zip_name
            session_dir = Config.get("storage_path") / session_id
            
            if is_idle and session.get("zip_file") and (zip_dir / session.get("zip_file")).exists():
                return {
                    "session_id": session_id,
                    "zip_file": session.get("zip_file"),
                    "zip_size": session.get("zip_size")
                }
            
            jpgs = sorted([f for f in session_dir.iterdir() if f.suffix.lower() == ".jpg"])
            if not jpgs:
                raise RuntimeError(f"No JPGs found for session {session_id}")
            
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for i, file_path in enumerate(jpgs, 1):
                    if cls._cancel_requested:
                        zip_path.unlink(missing_ok=True)
                        return None
                    zipf.write(file_path, arcname=file_path.name)
                    cls._emit_progress(i, len(jpgs), session_id=session_id)
            
            zip_size = zip_path.stat().st_size
            
            if is_idle:
                Logger.debug(f"[DEBUG] Emitting session update with: {type(session)} {type(zip_name)} / {type(zip_size)} Is Idle: {is_idle}", category="zip")
                session.update({"zip_file": zip_name, "zip_size": zip_size})
                
                session.emit_update()
                
                
            else:
                TempZip.get_instance().add(zip_name, "session", session_id)

            Logger.info(f"Finished zipping session {session_id}", category="zip")
            return {"session_id": session_id, "zip_file": zip_name, "zip_size": zip_size, "temp": not is_idle}

        finally:
            cls._lock.release()

    @classmethod
    def _zip_multi_session(cls, session_ids):
        results = []
        total = len(session_ids)
        for idx, session_id in enumerate(session_ids, 1):
            if cls._cancel_requested:
                break
            result = cls._zip_single_session(session_id)
            if result:
                results.append(result)
            cls._emit_progress(idx, total, bar="overall")
        return results

    @classmethod
    def _zip_by_range(cls, from_dt, to_dt):
        if not cls._lock.acquire(blocking=False):
            cls._emit("zip-error", {"message": "Another ZIP task is already running."})
            return None

        try:
            name = f"images_{from_dt.strftime('%Y%m%d-%H%M')}_{to_dt.strftime('%Y%m%d-%H%M')}.zip"
            output_path = Config.get("download_path") / "temp" / name
            capture_root = Config.get("storage_path")
            matched = []

            for root, _, files in os.walk(capture_root):
                for file in files:
                    if file.lower().endswith(".jpg"):
                        try:
                            ts = datetime.strptime(Path(file).stem, "%Y%m%d-%H%M%S")
                            if from_dt <= ts <= to_dt:
                                matched.append(Path(root) / file)
                        except ValueError:
                            continue

            if not matched:
                Logger.warning("No images found in range", category="zip")
                cls._emit("zip-error", {"message": "No images found in specified datetime range."})
                return None

            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for idx, path in enumerate(matched):
                    if cls._cancel_requested:
                        output_path.unlink(missing_ok=True)
                        return None
                    arcname = path.relative_to(capture_root)
                    zipf.write(path, arcname)
                    if idx % 10 == 0 or idx == len(matched) - 1:
                        cls._emit_progress(idx + 1, len(matched), bar="single")

            TempZip.get_instance().add(name, "range-precise")
            Logger.info("Finished zipping image range", category="zip")
            return {"filename": name, "path": str(output_path), "count": len(matched), "sessions": []}

        finally:
            cls._lock.release()

    @classmethod
    def _emit(cls, event, data):
        SocketManager.emit(event, data)

    @classmethod
    def _emit_progress(cls, current, total, bar="session", session_id=None):
        data = {
            "bar": bar,
            "current": current,
            "total": total,
            "percent": int((current / total) * 100)
        }
        if session_id:
            data["session_id"] = session_id
        cls._emit("zip-progress", data)
