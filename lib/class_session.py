import os
import json
import shutil
from datetime import datetime
from pathlib import Path
from PIL import Image
from threading import Timer
import threading

from lib.class_config import Config
from lib.class_logging import Logger
from lib.class_socket import SocketManager

class Session:
    _sessions_cache = None
    _session_file = Config.config_path("sessions.json")
    _capture_dir  = Config.get("storage_path")
    _download_dir = Config.get("download_path")
    _remove_buffer = {}
    _emit_buffer = {}
    _emit_lock = threading.Lock()
    _emit_delay = 0.2  # seconds

    def __init__(self, session_id=None):
        if session_id is None:
            self.session = self._start_new_session()
        else:
            self.session = self._get_by_id(session_id)
            if self.session is None:
                raise ValueError(f"Session '{session_id}' not found.")

    def __repr__(self):
        return f"<Session {self.session_id()} ({self.session.get('status')})>"

    def session_id(self):
        return self.session.get("session_id")

    def uptime(self) -> str:
        started = self.session.get("started_at")
        ended = self.session.get("ended_at")
        if not started:
            return None
        try:
            start_time = datetime.fromisoformat(started)
            end_time = datetime.fromisoformat(ended) if ended else datetime.now()
            delta = end_time - start_time
            return str(delta).split(".")[0]
        except Exception:
            return None


    def save_thumbnail(self, image_path: Path = None):
        target_height = 170  # internal UI-driven constant

        try:
            # Determine aspect ratio from configured resolution
            resolution = Config.get("resolution")
            original_width, original_height = map(int, resolution.lower().split("x"))
            target_width = round(original_width / original_height * target_height)

            if not image_path:
                jpgs = sorted((Config.get("storage_path") / self.session_id()).glob("*.jpg"))
                if not jpgs:
                    Logger.warning("No images found to generate thumbnail", category="session")
                    return
                image_path = jpgs[0]

            Logger.debug(f"Generating thumbnail {target_width}x{target_height} from {image_path}", category="session")

            with Image.open(image_path) as img:
                img.thumbnail((target_width, target_height))
                session_folder = Config.get("storage_path") / self.session_id()
                thumb_path = session_folder / "thumbnail.jpg"
                img.save(thumb_path, "JPEG")

            Logger.info(f"Thumbnail saved to {thumb_path}", category="session")

        except Exception as e:
            Logger.warning(f"Failed to generate thumbnail: {e}", category="session")

    

        


    def get_thumbnail_path(self) -> Path:
        return Config.get("storage_path") / self.session_id() / "thumbnail.jpg"


    def _start_new_session(self):
        now = datetime.now()
        session_id = now.strftime("%Y%m%d-%H%M")

        session = {
            "session_id": session_id,
            "status": "active",
            "started_at": now.isoformat(),
            "ended_at": None,
            "interval": Config.get("interval"),
            "resolution": Config.get("resolution"),
            "file_count": 0,
            "tags": [],
            "notes": "",
            "zip_file": None,
            "zip_size": None
        }

        self._get_sessions().append(session)
        self._save_sessions()
        SocketManager.emit("add-session", session)
        Logger.info(f"Started new session: {session_id}", category="session")
        return session

    def save(self):
        """Persist changes to this session in sessions.json."""
        sessions = self._get_sessions()
        for i, s in enumerate(sessions):
            if s.get("session_id") == self.session_id():
                sessions[i] = self.session
                break
        else:
            sessions.append(self.session)
        self._save_sessions()

    def delete(self):
        """Delete session and its associated capture folder and zip."""
        session_id = self.session_id()
        self.delete_zip()

        capture_dir = self._capture_dir / session_id
        if capture_dir.exists():
            try:
                shutil.rmtree(capture_dir)
            except Exception as e:
                Logger.error(f"Error deleting capture directory for session {session_id}: {e}", category="session")

        Session._sessions_cache = [
            s for s in self._get_sessions() if s.get("session_id") != session_id
        ]
        self._save_sessions()
        
        Logger.info(f"Deleted session: {session_id}", category="session")
        Session._sessions_cache = self._load_sessions()
        self.emit_remove()
        return True

    def delete_zip(self):
        """Delete associated zip file if present."""
        zip_file = self.session.get("zip_file")
        if zip_file:
            zip_path = self._download_dir / zip_file
            if zip_path.exists():
                try:
                    zip_path.unlink()
                    self.update({"zip_file": None, "zip_size": None})
                    Logger.info(f"Deleted ZIP for: {self.session_id()}", category="session")
                except Exception as e:
                    Logger.error(f"Error deleting ZIP for session {self.session_id()}: {e}", category="session")

    def add_zip(self, zip_file):
        """Attach a zip file to this session with size tracking."""
        zip_path = self._download_dir / zip_file
        zip_size = zip_path.stat().st_size
        self.update({"zip_file": zip_file, "zip_size": zip_size})

    def end(self):
        """Mark session as ended and update timestamp."""
        if self.get("status") == "idle":
            return
        
        self.update({
            "ended_at": self._get_end_dt(),
            "status": "idle"
        })
        Logger.info(f"Session {self.session_id()} marked as ended.", category="session")

    def increment_file_count(self):
        """Increment file counter and save."""
        self.session["file_count"] = self.session.get("file_count", 0) + 1
        self.save()
        if self.session["file_count"] == 1:
            self.save_thumbnail()
        self.emit_update()


    def update_tags(self, tags, add=True):
        """Add or remove tags from session."""
        tag_list = self.session.get("tags", [])
        tags = tags if isinstance(tags, list) else [tags]

        if add:
            for tag in tags:
                if tag not in tag_list:
                    tag_list.append(tag)
        else:
            tag_list = [t for t in tag_list if t not in tags]

        self.session["tags"] = tag_list
        self.save()

    def update_notes(self, notes):
        self.session["notes"] = notes
        self.save()


    def update(self, key, value=None):
        if isinstance(key, dict):
            for k in key:
                if k not in self.session:
                    return False
            self.session.update(key)
        else:
            if key not in self.session:
                return False
            self.session[key] = value
            
        self.save()
        # Debounced emit
        self.emit_update()

        return True



    def get_session(self):
        if not self.session:
            return None

        result = self.session.copy()
        result["uptime"] = self.uptime()
        return result
    

    def refresh(self):
        """Reload session from file."""
        updated = self._get_by_id(self.session_id())
        if updated:
            self.session = updated

    def get(self, key, default=None):
        return self.session.get(key, default)

    def _get_end_dt(self):
        ended = self.get('ended_at', None)
        if (ended):
            return ended

        session_folder = Config.get("storage_path") / self.session_id()
        jpgs = sorted(session_folder.glob("*.jpg"))
        
        if jpgs:
            filename = jpgs[-1].stem  # Remove .jpg
            try:
                dt = datetime.strptime(filename, "%Y%m%d-%H%M%S")
                return dt.isoformat()
            except ValueError:
                Logger.warning(f"Could not parse timestamp from {filename}", category="session")
        
        return datetime.now().isoformat()

    # ------------------ Class Helpers ------------------

    @classmethod
    def list_all(cls, filters: dict = None):
        """Return all sessions, optionally filtered by dict."""
        results = cls._get_sessions()
        if filters:
            for key, val in filters.items():
                results = [s for s in results if s.get(key) == val]
        return results

    @classmethod
    def get_active_session(cls):
        """Return the first active session or None."""
        s = next((s for s in cls._get_sessions() if s.get("status") == "active"), None)
        return Session(s["session_id"]) if s else None

    @classmethod
    def session_exists(cls, session_id):
        """Return True if a session with the given ID exists."""
        return any(s.get("session_id") == session_id for s in cls._get_sessions())

    @classmethod
    def count(cls, status=None):
        """Return count of sessions, optionally filtered by status."""
        if status:
            return sum(1 for s in cls._get_sessions() if s.get("status") == status)
        return len(cls._get_sessions())

    @staticmethod
    def clean_invalid_sessions():
        """Remove sessions with missing capture folders from the session file."""
        if not os.path.exists(Session._session_file):
            return 0

        with open(Session._session_file, "r") as f:
            sessions = json.load(f)

        valid_sessions = [
            s for s in sessions if (Session._capture_dir / s["session_id"]).exists()
        ]

        removed = len(sessions) - len(valid_sessions)
        if removed:
            with open(Session._session_file, "w") as f:
                json.dump(valid_sessions, f, indent=2)
            Session._sessions_cache = valid_sessions
        return removed


    @classmethod
    def end_orphaned_sessions(cls):
        count = 0
        for s in cls.list_all():
            if s.get("status") == "active":
                Logger.warning(f"Orphaned session found on boot: {s['session_id']}", category="session")
                try:
                    session = cls(s["session_id"])
                    session.end()
                    count += 1
                except Exception as e:
                    Logger.error(f"Failed to end orphaned session {s['session_id']}: {e}", category="session")
        if count:
            Logger.info(f"Ended {count} orphaned sessions on boot", category="session")


    @staticmethod
    def _calculate_uptime(session):
        started = session.get("started_at")
        ended = session.get("ended_at")
        if not started:
            return "—"
        start_dt = datetime.fromisoformat(started)
        end_dt = datetime.fromisoformat(ended) if ended else datetime.now()
        return str(end_dt - start_dt).split(".")[0]


    # ------------------ Internal Helpers ------------------

    @classmethod
    def _get_sessions(cls):
        if cls._sessions_cache is None:
            cls._sessions_cache = cls._load_sessions()
        return cls._sessions_cache

    @classmethod
    def _save_sessions(cls, sessions=None):
        data = sessions if sessions is not None else cls._sessions_cache
        with open(cls._session_file, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def _load_sessions(cls):
        if not os.path.exists(cls._session_file):
            return []

        with open(cls._session_file, "r") as f:
            sessions = json.load(f)

        valid_sessions = [
            s for s in sessions if (cls._capture_dir / s["session_id"]).exists()
        ]

        if len(valid_sessions) != len(sessions):
            cls._save_sessions(valid_sessions)

        return valid_sessions

    @classmethod
    def _get_by_id(cls, session_id):
        return next((s for s in cls._get_sessions() if s.get("session_id") == session_id), None)

    @classmethod
    def get_latest_session(cls):
        sessions = cls._get_sessions()
        if not sessions:
            return None
        latest = sorted(sessions, key=lambda s: s["started_at"], reverse=True)[0]
        return Session(latest.get("session_id"))

    @classmethod
    def by_id(cls, session_id):
        """Return a Session object if found, otherwise None."""
        try:
            return cls(session_id)
        except Exception:
            return None

    @staticmethod
    def total_size(human=False):
        capture_dir = Config.get("storage_path")
        zip_dir = Config.get("download_path")

        def get_size(path):
            return sum(f.stat().st_size for f in path.rglob("*.jpg"))

        def get_zips(path):
            return sum(f.stat().st_size for f in path.rglob("*.zip"))

        def human_readable(size_bytes):
            for unit in ["B", "KB", "MB", "GB", "TB"]:
                if size_bytes < 1024:
                    return f"{size_bytes:.2f} {unit}"
                size_bytes /= 1024
            return f"{size_bytes:.2f} PB"

        captures = get_size(capture_dir)
        zips = get_zips(zip_dir)
        total = captures + zips

        result = {
            "captures_size": captures,
            "zips_size": zips,
            "total_size": total
        }

        if human:
            result.update({
                "captures_human": human_readable(captures),
                "zips_human": human_readable(zips),
                "total_human": human_readable(total)
            })

        return result
    

    # ------------------ Socket Debounce ------------------

    def emit_update(self):
        """Debounced update-session emit for this session."""
        session_id = self.session_id()
        Logger.debug(f"Debounce Update Session Called for: ${session_id}")

        with Session._emit_lock:
            if session_id in Session._emit_buffer:
                Session._emit_buffer[session_id].cancel()

            def _send():
                session = Session.by_id(session_id)
                if session:
                    SocketManager.emit("update-session", session.get_session())
                    Logger.debug(f"Sending Update Session {session_id}")
                with Session._emit_lock:
                    Session._emit_buffer.pop(session_id, None)

            t = Timer(Session._emit_delay, _send)
            t.start()
            Session._emit_buffer[session_id] = t

    def emit_remove(self):
        """Debounced remove-session emit for this session."""
        session_id = self.session_id()

        with Session._emit_lock:
            if session_id in Session._remove_buffer:
                Session._remove_buffer[session_id].cancel()

            def _send():
                SocketManager.emit("remove-session", {"session_id": session_id})
                with Session._emit_lock:
                    Session._remove_buffer.pop(session_id, None)
                Logger.debug(f"Debounced emit: remove-session {session_id}", category="session")

            t = Timer(Session._emit_delay, _send)
            t.start()
            Session._remove_buffer[session_id] = t
