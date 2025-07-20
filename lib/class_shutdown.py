import os
import threading
from lib.class_session import Session
from lib.class_camera import Camera
from lib.class_logging import Logger
from lib.class_temp import TempZip
from lib.class_status import Status
from lib.class_config import Config

class ShutdownManager:
    _called = False

    @classmethod
    def clean_up(cls):
        if cls._called:
            return
        cls._called = True

        try:
            Status.stop_emitter()
            TempZip.get_instance().destroy()
            Logger.info("App exiting, TempZip destroyed", category="app")

            # Stop camera
            camera = Camera.get_instance()
            if camera.is_running():
                camera.stop()
                Logger.info("Camera capture stopped", category="camera")
            if camera.is_streaming():
                camera.stop_streamer()
                Logger.info("Streamer stopped", category="camera")
            Camera.remove_temp_images()

            # End sessions
            active = [s for s in Session.list_all() if s.get("status") == "active"]
            for s in active:
                try:
                    Session(s["session_id"]).end()
                    Logger.info(f"Ended active session: {s['session_id']}", category="session")
                except Exception as e:
                    Logger.error(f"Failed to end session {s['session_id']}: {e}", category="session")

            # Thread dump
            Logger.debug("Threads still alive at shutdown:", category="app")
            for t in threading.enumerate():
                Logger.debug(f"Thread: {t.name}, Daemon: {t.daemon}", category="app")

            Logger.destroy()

        except Exception as e:
            Logger.error(f"Cleanup error: {e}", category="app")
            Logger.destroy()

        finally:
            Logger.info("Exiting via os._exit(0)", category="app")
            os._exit(0)
