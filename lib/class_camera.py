import os
import time
import shutil
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageChops
import psutil
import re

from lib.class_session import Session
from lib.class_config import Config
from lib.class_logging import Logger
from lib.class_socket import SocketManager




class Camera:
    _instance = None
    _preview_path = Path("/tmp/preview.jpg")
    _compare_path = Path("/tmp/prev_compare.jpg")

    def __init__(self):
        raise RuntimeError("Use get_instance() to access the Camera singleton")

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = object.__new__(cls)
            cls._instance._init_internal()
        return cls._instance

    def _init_internal(self):
        self.session = None
        self.capture_thread = None
        self.running = False
        self._stream_proc = None
        self._lock = threading.Lock()

    @staticmethod
    def _using_libcamera() -> bool:
        return Config.get("camera_type", "usb") == "libcamera"

    def is_running(self) -> bool:
        return self.running

    @staticmethod
    def is_streaming() -> bool:
        for proc in psutil.process_iter(["cmdline"]):
            cmd = " ".join(proc.info["cmdline"] or [])
            if "mjpg_streamer" in cmd:
                return True
            if "libcamera-vid" in cmd and "streamer_relay.py" in cmd:
                return True
        return False

    def get_mode(self) -> str:
        if self.is_running():
            return "capture"
        if self.is_streaming():
            return "streaming"
        return "idle"

    def get_stream_url(self) -> str:
        if self._using_libcamera:
            return f"http://localhost:8080/"
        else:
            return f"http://localhost:8080/?action=stream"

    def start(self):
        with self._lock:
            if self.is_running() or self.is_streaming():
                Logger.warning("Cannot start capture — another mode is active", category="camera")
                return

            self.session = Session()
            self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.capture_thread.start()
            from lib.class_status import Status
            Status.force_emit()

    def stop(self):
        with self._lock:
            self.running = False


    def start_streamer(self):
        with self._lock:
            if self.is_running() or self.is_streaming():
                Logger.warning("Cannot start streamer — another mode is active", category="camera")
                return

            resolution = Config.get("resolution")
            try:
                if self._using_libcamera():
                    width, height = resolution.split("x")
                    self._stream_proc = subprocess.Popen([
                        "bash", "-c",
                        f"libcamera-vid --codec mjpeg -t 0 --inline --framerate 15 --width {width} --height {height} -o - "
                        f"| python3 lib/streamer_relay.py"
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    self._stream_proc = subprocess.Popen([
                        "mjpg_streamer",
                        "-i", f"input_uvc.so -r {resolution} -f 15",
                        "-o", "output_http.so -w ./www -p 8080"
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                Logger.info("Streamer started", category="camera")

            except Exception as e:
                Logger.error(f"Failed to start streamer: {e}", category="camera")
            finally:
                from lib.class_status import Status
                Status.force_emit()

    def stop_streamer(self):
        with self._lock:
            if self._stream_proc:
                try:
                    self._stream_proc.terminate()
                    self._stream_proc.wait(timeout=3)
                    Logger.info("Streamer stopped (via tracked process)", category="camera")
                except Exception as e:
                    Logger.warning(f"Failed to terminate streamer cleanly: {e}", category="camera")
                finally:
                    self._stream_proc = None

            # Fallback: kill by name depending on backend
            if self._using_libcamera():
                subprocess.call(["pkill", "-f", "libcamera-vid"])
                subprocess.call(["pkill", "-f", "streamer_relay.py"])
                Logger.debug("Streamer not tracked — used pkill fallback (libcamera)", category="camera")
            else:
                subprocess.call(["pkill", "-f", "mjpg_streamer"])
                Logger.debug("Streamer not tracked — used pkill fallback (mjpg_streamer)", category="camera")

            from lib.class_status import Status
            Status.force_emit()

    def capture_once(self, path: Path = None, resolution: str = None) -> bool:
        path = path or Path("/tmp/test_capture.jpg")
        resolution = resolution or Config.get("resolution")
        return self._capture_image(path, resolution)



    def _compare_images(self) -> float:
        try:
            with Image.open(self._preview_path).convert("L") as im1, Image.open(self._compare_path).convert("L") as im2:
                if im1.size != im2.size:
                    im2 = im2.resize(im1.size)
                diff = ImageChops.difference(im1, im2)
                rms = (sum(p**2 for p in diff.getdata()) / (im1.size[0] * im1.size[1])) ** 0.5
                return rms
        except Exception as e:
            Logger.error(f"Image comparison error: {e}", category="camera")
            return float("inf")

    def _get_output_path(self) -> Path:
        session_id = self.session.session_id()
        folder = Config.get("storage_path") / session_id
        folder.mkdir(parents=True, exist_ok=True)
        filename = datetime.now().strftime("%Y%m%d-%H%M%S.jpg")
        return folder / filename

    def _capture_loop(self):
        interval     = Config.get("interval")
        resolution   = Config.get("resolution")
        preview_res  = Config.get("preview_resolution")
        threshold    = Config.get("change_threshold")
        detect_change = Config.get("change_detection_enabled")
        auto_stop    = Config.get("auto_stop_enabled")
        stop_minutes = int(Config.get("auto_stop_after_idle_minutes"))
        latest_path  = Config.get("latest_symlink")

        self.running = True
        Logger.info(f"--- Starting capture session: {self.session.session_id()} ---", category="camera")

        idle_start = None
        
        try:
            while self.running:
                loop_start = time.time()
                if not self._capture_image(self._preview_path, preview_res):
                    Logger.warning("Preview capture failed.", category="camera")
                    self._log_and_sleep(loop_start, interval)
                    continue
                if not detect_change:
                    self._full_capture(resolution, latest_path)
                    self._log_and_sleep(loop_start, interval)
                    continue

                if not self._compare_path.exists():
                    shutil.copy2(self._preview_path, self._compare_path)
                    Logger.debug("Initialized comparison baseline.", category="camera")
                    idle_start = None
                    self._full_capture(resolution,latest_path)
                    self._log_and_sleep(loop_start, interval)
                    continue

                rms = self._compare_images()
                Logger.debug(f"Change RMS: {rms:.2f} (Threshold: {threshold})", category="camera")


                if rms < threshold:
                    if idle_start is None:
                        idle_start = time.time()
                    elif auto_stop and (time.time() - idle_start > stop_minutes * 60):
                        Logger.info("Auto-stop triggered by inactivity.", category="camera")
                        break
                    self._log_and_sleep(loop_start, interval)
                    continue

                idle_start = None
                os.replace(self._preview_path, self._compare_path)
                self._full_capture(resolution, latest_path)
                self._log_and_sleep(loop_start, interval)

        except Exception as e:
            Logger.error(f"Unexpected error in capture loop: {e}", category="camera")
        finally:
            self.running = False

            if self.session:
                self.session.end()
                Logger.info(f"Session {self.session.session_id()} ended", category="camera")
                self.session = None

            Camera.remove_temp_images()

            from lib.class_status import Status
            Status.force_emit()


    def _full_capture(self, resolution, latest_path):
        full_path = self._get_output_path()
        if self._capture_image(full_path, resolution):
            Logger.info(f"Captured {full_path}", category="camera")
            try:
                shutil.copy2(full_path, latest_path)
            except Exception as e:
                Logger.warning(f"Failed to update latest symlink: {e}", category="camera")
            data = { 
                "filename": full_path.name,
                "session_id": self.session.session_id()
            }
            SocketManager.emit('image-updated', data)
            self.session.increment_file_count()
        else:
            Logger.error("Full capture failed.", category="camera")



    def _log_and_sleep(self, start_time, interval):
        duration = time.time() - start_time
        sleep_time = interval - duration
        if duration > interval:
            Logger.warning(f"Capture Loop processing time {duration:.2f}s exceeded interval of {interval}s", category="camera")
        else:
            Logger.debug(f"Capture Loop processing time {duration:.2f}s", category="camera")

        if sleep_time > 0:
            time.sleep(sleep_time)



    def _capture_image(self, path: Path, resolution: str) -> bool:
        if self._using_libcamera():
            return self._capture_libcamera(path, resolution)
        return self._capture_usb(path, resolution)


    def _capture_usb(self, path: Path, resolution: str) -> bool:
        cmd = [
            "fswebcam",
            "--no-banner",
            "-d", Config.get("video_device", "/dev/video0"),
            "-r", resolution,
            str(path)
        ]
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return result.returncode == 0

    def _capture_libcamera(self, path: Path, resolution: str) -> bool:
        try:
            width, height = resolution.split("x")
        except Exception:
            width, height = "1920", "1080"

        cmd = [
            "libcamera-still",
            "--autofocus-mode", "auto",
            "--autofocus-range", "normal",
            "--lens-position", "0.0",
            "--width", width,
            "--height", height,
            "--timeout", "3000",
            "-o", str(path)
        ]

        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return result.returncode == 0



    @staticmethod
    def _aspect_ratio(res):
        try:
            w, h = map(int, res.split("x"))
            ratio = w / h
            return {
                4/3: "4:3",
                16/9: "16:9",
                3/2: "3:2",
                5/4: "5:4"
            }.get(ratio, f"{ratio:.2f}:1")
        except:
            return "unknown"


    @staticmethod
    def get_supported_resolutions(aspect_ratio: str = None):
        if Camera._using_libcamera():
            return Camera.get_libcamera_resolutions(aspect_ratio)

        try:
            output = subprocess.check_output([
                "v4l2-ctl", "--list-formats-ext",
                "-d", Config.get("video_device", "/dev/video0")
            ], text=True)

            resolutions = {
                line.split()[2]
                for line in output.splitlines()
                if line.strip().startswith("Size: Discrete")
            }

            result = []
            for r in resolutions:
                ratio = Camera._aspect_ratio(r)
                if aspect_ratio and ratio.lower() != aspect_ratio.lower():
                    continue
                result.append({"resolution": r, "aspect_ratio": ratio})

            return sorted(result, key=lambda r: tuple(map(int, r["resolution"].split("x"))))

        except Exception as e:
            Logger.error(f"Error listing resolutions: {e}", category="camera")
            return []

    @staticmethod
    def get_libcamera_resolutions(aspect_ratio: str = None):
        """
        Returns a sorted list of available libcamera resolutions (known + parsed),
        each with its aspect ratio. Optionally filters by aspect ratio.
        """
        try:
            known = [ 
                "1280x720", 
                "640x360", 
                "320x180", 
                "1024x768" 
            ]

            output = subprocess.check_output(["libcamera-hello", "--list-cameras"], text=True)
            resolutions = set()

            resolutions.update(known)

            for line in output.splitlines():
                match = re.search(r"(\d{3,5}x\d{3,5})", line)
                if match:
                    resolutions.add(match.group(1))

            result = []
            for res in resolutions:
                ar = Camera._aspect_ratio(res)
                if aspect_ratio and ar.lower() != aspect_ratio.lower():
                    continue
                result.append({"resolution": res, "aspect_ratio": ar})

            return sorted(result, key=lambda r: tuple(map(int, r["resolution"].split("x"))))

        except Exception as e:
            Logger.warning(f"Failed to list libcamera resolutions: {e}", category="camera")
            return []


    @staticmethod
    def get_capture_mode():
        for proc in psutil.process_iter(["cmdline"]):
            cmd = " ".join(proc.info["cmdline"] or [])
            if "capture.py" in cmd:
                return "capture"
            if "mjpg_streamer" in cmd:
                return "streaming"
            if "libcamera-vid" in cmd and "streamer_relay.py" in cmd:
                return "streaming"
        return "none"

    @staticmethod
    def timestamp_from_name(filename):
        try:
            name = Path(filename).stem
            return datetime.strptime(name, "%Y%m%d-%H%M%S")
        except Exception as e:
            Logger.warning(f"Invalid filename timestamp: {filename} ({e})", category="camera")
            return None

    @staticmethod
    def remove_temp_images():
        # Remove Temp Paths
        for path in [Camera._preview_path, Camera._compare_path, Config.get("latest_symlink")]:
            try:
                if path.exists():
                    path.unlink()
                    Logger.debug(f"Deleted stale file: {path}", category="camera")
            except Exception as e:
                Logger.warning(f"Failed to clean up temp file {path}: {e}", category="camera")
