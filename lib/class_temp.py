import time
import threading
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

from lib.class_camera import Camera
from lib.class_config import Config
from lib.class_logging import Logger


class TempZip:
    _instance = None
    _singleton_lock = threading.Lock()

    def __init__(self):
        raise RuntimeError("Use get_instance() to access the TempZip singleton")

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._singleton_lock:
                if cls._instance is None:
                    cls._instance = object.__new__(cls)
                    cls._instance._init_internal()
        return cls._instance

    def _init_internal(self):
        self.temp_dir = Config.get("download_path") / "temp"
        self.temp_files = {}  # {filename: metadata}
        self.lock = threading.Lock()
        self._stop_flag = False
        self._cleanup_thread = None

        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self._initial_cleanup()
        self._start_cleanup_loop()

    def _initial_cleanup(self):
        Logger.info("Running initial cleanup of temp folder...", category="temp")
        for file in self.temp_dir.glob("*.zip"):
            try:
                file.unlink()
                Logger.debug(f"Deleted stale temp file on init: {file.name}", category="temp")
            except Exception as e:
                Logger.error(f"Failed to delete {file.name} during init cleanup: {e}", category="temp")

    def _start_cleanup_loop(self):
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            return
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()

    def _cleanup_loop(self):
        retention_minutes = Config.get("temp_retention_minutes")

        while not self._stop_flag:
            self.clean_expired()
            time.sleep(60)

    def clean_expired(self):
        now = datetime.now()
        expired = []

        with self.lock:
            for filename, entry in list(self.temp_files.items()):
                try:
                    created = datetime.fromisoformat(entry["created"])
                    if now - created > timedelta(minutes=Config.get("temp_retention_minutes")):
                        expired.append(filename)
                except Exception as e:
                    Logger.warning(f"Error checking expiration for {filename}: {e}", category="temp")

        for filename in expired:
            self.remove(filename)

    def add(self, filename: str, type: str, session_id: str = None):
        zip_path = self.temp_dir / filename
        if not zip_path.exists():
            Logger.warning(f"Tried to add nonexistent zip: {filename}", category="temp")
            return

        metadata = self._extract_metadata(zip_path, type, session_id)
        with self.lock:
            self.temp_files[filename] = metadata
        Logger.debug(f"Added temp zip: {filename}", category="temp")

    def _extract_metadata(self, zip_path: Path, type: str, session_id: str = None) -> dict:
        size = zip_path.stat().st_size
        dt_from = dt_to = None

        try:
            with zipfile.ZipFile(zip_path, 'r') as zipf:
                jpgs = sorted(f for f in zipf.namelist() if f.lower().endswith(".jpg"))
                if jpgs:
                    dt_from = Camera.timestamp_from_name(jpgs[0])
                    dt_to = Camera.timestamp_from_name(jpgs[-1])
        except Exception as e:
            Logger.warning(f"Failed to parse zip file {zip_path.name}: {e}", category="temp")

        return {
            "filename": zip_path.name,
            "size": size,
            "created": datetime.now().isoformat(),
            "session_id": session_id,
            "dt_from": dt_from.isoformat() if dt_from else None,
            "dt_to": dt_to.isoformat() if dt_to else None,
            "type": type
        }

    def remove(self, filename: str):
        zip_path = self.temp_dir / filename
        try:
            if zip_path.exists():
                zip_path.unlink()
            with self.lock:
                self.temp_files.pop(filename, None)
            Logger.debug(f"Removed temp zip: {filename}", category="temp")
        except Exception as e:
            Logger.error(f"Failed to remove temp zip {filename}: {e}", category="temp")

    def clear_all(self):
        with self.lock:
            for filename in list(self.temp_files.keys()):
                self.remove(filename)
            self.temp_files.clear()

    def destroy(self):
        Logger.info("Destroying TempZip state and cleaning up all temp zips...", category="temp")
        self._stop_flag = True
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=2)
        self.clear_all()

    def list(self) -> list:
        with self.lock:
            return list(self.temp_files.values())

    def get(self, filename: str) -> dict:
        with self.lock:
            return self.temp_files.get(filename)

    def count(self) -> int:
        with self.lock:
            return len(self.temp_files)

    def exists(self, filename: str) -> bool:
        with self.lock:
            return filename in self.temp_files

    @classmethod
    def get_temp_dir(cls) -> Path:
        return Config.get("download_path") / "temp"
