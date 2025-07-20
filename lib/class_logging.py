import logging
import threading
import time
import re
from datetime import datetime
from pathlib import Path
from collections import deque
from logging.handlers import TimedRotatingFileHandler
from lib.class_config import Config
from lib.class_socket import SocketManager

import inspect
import os

class Logger:
    _logger = None
    _log_level = None
    _tail_thread = None
    _stop_tail = False

    _level_order = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    _colors = {
        "DEBUG": "\033[90m",
        "INFO": "\033[92m",
        "WARNING": "\033[93m",
        "ERROR": "\033[91m",
        "CRITICAL": "\033[95m",
        "RESET": "\033[0m",
    }

    def __new__(cls, *args, **kwargs):
        raise RuntimeError("Use classmethods only — do not instantiate Logger")

    @classmethod
    def _get_logger(cls) -> logging.Logger:
        if cls._logger is not None:
            return cls._logger

        log_path: Path = Config.get("log_path") / "timelapse.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        logger = logging.getLogger("timelapse")
        logger.setLevel(logging.DEBUG)

        if not logger.handlers:
            handler = TimedRotatingFileHandler(log_path, when="midnight", backupCount=7)
            formatter = logging.Formatter(
                fmt="%(asctime)s [%(category)s] %(levelname)s: %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.propagate = False

        cls._logger = logger
        return logger

    @classmethod
    def get_logger(cls) -> logging.Logger:
        return cls._get_logger()

    @classmethod
    def _get_log_level(cls) -> str:
        if cls._log_level is None:
            cls._log_level = Config.get("log_level", fallback="INFO").upper()
        return cls._log_level

    @classmethod
    def log(cls, message: str, category: str = "app", level: str = "INFO", console: bool = True):



        level = level.upper()
        current_level = cls._get_log_level()

        if level not in cls._level_order:
            level = "INFO"

        if cls._level_order.index(level) < cls._level_order.index(current_level):
            return

        # Get the previous frame in the stack (the caller of Logger.log)

        frame = inspect.currentframe().f_back
        filename = os.path.basename(frame.f_code.co_filename)

        # If the caller is class_logging.py, go one frame higher
        if filename == "class_logging.py":
            frame = frame.f_back
            filename = os.path.basename(frame.f_code.co_filename)

        lineno = frame.f_lineno

        # Optional: format with padding or alignment
        location = f"{filename}:{lineno}"

        message += f" ({location})"

        logger = cls._get_logger()
        log_method = getattr(logger, level.lower(), logger.info)
        log_method(message, extra={"category": category})

        if console:
            color = cls._colors.get(level, "")
            reset = cls._colors["RESET"]
            print(f"{color}[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}][{category.upper()}][{level}] {message}{reset}")

    # --- Convenience wrappers ---
    @classmethod
    def debug(cls, message: str, category: str = "app", console: bool = True):
        cls.log(message, category, level="DEBUG", console=console)

    @classmethod
    def info(cls, message: str, category: str = "app", console: bool = True):
        cls.log(message, category, level="INFO", console=console)

    @classmethod
    def warning(cls, message: str, category: str = "app", console: bool = True):
        cls.log(message, category, level="WARNING", console=console)

    @classmethod
    def error(cls, message: str, category: str = "app", console: bool = True):
        cls.log(message, category, level="ERROR", console=console)

    @classmethod
    def critical(cls, message: str, category: str = "app", console: bool = True):
        cls.log(message, category, level="CRITICAL", console=console)

    @classmethod
    def tail_log(cls):
        socketio = SocketManager.get_socketio()
        path: Path = Config.get("log_path") / "timelapse.log"
        cls._stop_tail = False  # Reset if re-called

        def _run():
            current_inode = None
            f = None
            while not cls._stop_tail:
                try:
                    if not path.exists():
                        time.sleep(1)
                        continue

                    inode = path.stat().st_ino
                    if inode != current_inode:
                        current_inode = inode
                        if f:
                            f.close()
                        f = path.open("r")
                        f.seek(0, 2)

                    line = f.readline()
                    if line:
                        parsed = cls.parse_log_line(line.strip())
                        socketio.emit("log_line", parsed)
                    else:
                        time.sleep(0.5)

                except Exception as e:
                    print(f"\033[91m[LOGGER] Tail error: {e}\033[0m")
                    time.sleep(1)

        cls._tail_thread = threading.Thread(target=_run, daemon=True)
        cls._tail_thread.start()

    @staticmethod
    def parse_log_line(line: str) -> dict:
        pattern = re.compile(
            r"""^(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\s+      # timestamp
                \[(?P<category>\w+)]\s+                                    # [category]
                (?P<level>\w+):\s+                                        # LEVEL:
                (?P<message>.+?)                                          # message (non-greedy)
                \s+\((?P<file>[\w\.]+):(?P<line>\d+)\)$                   # (filename.py:123)
            """, re.VERBOSE
        )

        match = pattern.match(line.strip())
        if match:
            return {
                "timestamp": datetime.fromisoformat(match.group("timestamp")).strftime("%H:%M:%S"),
                "level": match.group("level"),
                "category": match.group("category").lower(),
                "message": match.group("message"),
                "file": match.group("file"),
                "line": int(match.group("line")),
            }

        # Fallback if log is malformed
        return {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "level": "UNKNOWN",
            "category": "unknown",
            "message": line.strip(),
            "file": None,
            "line": None,
        }

    @classmethod
    def get_recent_log(cls, max_lines: int = 100) -> list:
        """
        Return the last `max_lines` entries from the log file as parsed dicts.
        """
        path: Path = Config.get("log_path") / "timelapse.log"
        if not path.exists():
            return []

        from collections import deque
        lines = deque(maxlen=max_lines)
        with path.open("r") as f:
            for line in f:
                lines.append(line.strip())

        return [cls.parse_log_line(line) for line in lines]


    @classmethod
    def destroy(cls):
        cls._stop_tail = True
        if cls._tail_thread:
            cls._tail_thread.join(timeout=2)
            cls._tail_thread = None
        Logger.info("Logger tail_log thread stopped", category="logger")