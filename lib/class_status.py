import threading
import time
import psutil
import shutil
from datetime import datetime

from lib.class_camera import Camera
from lib.class_session import Session
from lib.class_config import Config
from lib.class_socket import SocketManager
from lib.class_logging import Logger


class Status:
    _thread = None
    _lock = threading.Lock()
    _stop_flag = False
    _interval = 10
    _last_emit = 0

    @staticmethod
    def build() -> dict:
        camera = Camera.get_instance()
        mode = camera.get_mode()
        session = Session.get_active_session() if mode == "capture" else Session.get_latest_session()
        session_data = session.get_session() if session else False

        disk = Status.get_disk_usage()    
        cpu_load = Status.get_cpu_load()
        memory_usage = Status.get_memory_usage()
        uptime_str = Status.get_uptime(True)
        temperature_c = Status.get_temperature()
        libcamera = Status.is_libcamera_streaming()

        return {
            "mode": mode,
            "libcamera": libcamera,
            "latest_session": session_data,
            "system": {
                "cpu_load": cpu_load,
                "memory_usage": memory_usage,
                "disk": disk,
                "temperature_celsius": temperature_c
            },
            "uptime": uptime_str
        }

    @staticmethod
    def is_libcamera_streaming():
        return Camera.get_capture_mode() == "streaming" and Camera._using_libcamera()

    @staticmethod
    def get_uptime(string = False):
        try:
            uptime_seconds = time.time() - psutil.boot_time()
        except Exception:
            uptime_seconds = 0
        if string:
            return time.strftime("%Hh %Mm %Ss", time.gmtime(uptime_seconds))
        return uptime_seconds
        

    @staticmethod
    def get_memory_usage():
        try:
            memory = psutil.virtual_memory()
            memory_usage = round(memory.percent, 1)
        except Exception:
            memory_usage = None
        return memory_usage



    @staticmethod
    def get_cpu_load():
        try:
            cpu_load = round(psutil.getloadavg()[0], 2)
        except Exception:
            cpu_load = None
        return cpu_load

    @staticmethod
    def get_disk_usage():
        try:
            storage_path = Config.get("storage_path")
            total, used, free = shutil.disk_usage(storage_path)
            return {
                "total_mb": round(total / (1024 * 1024), 2),
                "used_mb": round(used / (1024 * 1024), 2),
                "free_mb": round(free / (1024 * 1024), 2),
                "percent_used": round((used / total) * 100, 1)
            }
        except Exception as e:
           return {"error": str(e)}

    @staticmethod
    def get_temperature():
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                # Use 'cpu-thermal' or first available sensor
                for key in temps:
                    if temps[key]:
                        temperature_c = round(temps[key][0].current, 1)
                        break
                else:
                    temperature_c = None
            else:
                raise RuntimeError("No temperature data from psutil")
        except Exception:
            # Fallback to direct read from thermal_zone0
            try:
                with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                    temperature_c = round(int(f.read()) / 1000, 1)
            except Exception:
                temperature_c = None
        return temperature_c


    @staticmethod
    def emit():
        SocketManager.emit("status-update", Status.build())

    @classmethod
    def start_emitter(cls):
        if cls._thread and cls._thread.is_alive():
            return
        cls._stop_flag = False
        cls._thread = threading.Thread(target=cls._run_loop, daemon=True)
        cls._thread.start()
        Logger.info("StatusEmitter started", category="status")

    @classmethod
    def _run_loop(cls):
        while not cls._stop_flag:
            now = time.time()
            if now - cls._last_emit >= cls._interval:
                cls.emit()
                cls._last_emit = now
            time.sleep(1)

    @classmethod
    def force_emit(cls):
        with cls._lock:
            cls.emit()
            cls._last_emit = time.time()
            Logger.debug("Forced status emit", category="status")

    @classmethod
    def stop_emitter(cls):
        cls._stop_flag = True
        if cls._thread:
            cls._thread.join(timeout=2)
            Logger.info("StatusEmitter stopped", category="status")
            cls._thread = None
