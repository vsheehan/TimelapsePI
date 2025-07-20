import os
import json
from pathlib import Path

class Config:
    _root_dir = Path(__file__).resolve().parent.parent
    _config_path = _root_dir / "data/config"
    _config_file = _config_path / "config.json"
    _config_cache = None

    _defaults = {
        "developer": True,
        "debug": True,
        "video_device": "/dev/video0",
        "log_level": "DEBUG",
        "interval": 30,
        "auto_stop_enabled": False,
        "auto_stop_after_idle_minutes": 60,
        "change_detection_enabled": True,
        "change_threshold": 10.0,
        "camera_type": "libcamera",
        "autofocus_mode": "normal",
        "resolution": "1600x1200",
        "preview_resolution": "320x240",
        "storage_path": "ROOT_DIR/data/sessions",
        "download_path": "ROOT_DIR/data/downloads",
        "log_path": "ROOT_DIR/data/logs",
        "latest_symlink": "ROOT_DIR/data/latest.jpg",
        "storage_threshold": 500,
        "network_mode": "wifi",
        "temp_retention_minutes": 15,
        "bt_enabled": True,
        "bt_autoconnect": True,
        "bt_device_name": "TimelapsePi"
        
    }

    _types = {
        str:   ['resolution', 'preview_resolution', 'network_mode', 'log_level', 'video_device', 'bt_device_name', "camera_type", "autofocus_mode"],
        Path:  ['storage_path', 'download_path', 'log_path', 'latest_symlink'],
        int:   ['interval', 'auto_stop_after_idle_minutes', 'storage_threshold', 'temp_retention_minutes'],
        float: ['change_threshold'],
        bool:  ['auto_stop_enabled', 'change_detection_enabled', 'debug', 'bt_enabled', 'bt_autoconnect', "developer"],
    }

    _type_map = {k: t for t, keys in _types.items() for k in keys}

    def __new__(cls, *args, **kwargs):
        raise RuntimeError("Do not instantiate Config — use classmethods only")

    # ---- Load and initialize the config ----
    @classmethod
    def load(cls):
        file_exists = cls._config_file.exists()
        loaded = cls._load_config()
        updated = False

        for key, default in cls._defaults.items():
            if key not in loaded:
                loaded[key] = default
                updated = True

        cls._config_cache = loaded

        if not file_exists or updated:
            cls.save()

    @classmethod
    def reload(cls):
        cls._config_cache = None
        cls.load()

    @classmethod
    def is_loaded(cls):
        return cls._config_cache is not None

    # ---- Type casting and schema helpers ----
    @classmethod
    def _get_expected_type(cls, key):
        return cls._type_map.get(key)

    @classmethod
    def _cast(cls, key, value):
        expected = cls._get_expected_type(key)
        if expected:
            try:
                if expected == Path:
                    return Path(str(value).replace("ROOT_DIR", str(cls._root_dir))).expanduser()
                if expected == bool:
                    return str(value).strip().lower() in ("true", "1", "yes")
                return expected(value)
            except Exception:
                pass
        return value

    # ---- Config load/save helpers ----
    @classmethod
    def _load_config(cls):
        if not cls._config_file.exists():
            return cls._defaults.copy()
        with open(cls._config_file, "r") as f:
            raw = json.load(f)
        return {k: cls._cast(k, raw.get(k, cls._defaults.get(k))) for k in cls._defaults}

    @classmethod
    def _get_config(cls):
        if cls._config_cache is None:
            cls.load()
        return cls._config_cache

    @classmethod
    def save(cls):
        cls.sanitize(save_on_change=False)
        config = cls._get_config()
        to_save = {}

        for k, v in config.items():
            if isinstance(v, Path):
                to_save[k] = str(v).replace(str(cls._root_dir), "ROOT_DIR")
            else:
                to_save[k] = v

        cls._config_path.mkdir(parents=True, exist_ok=True)
        with open(cls._config_file, "w") as f:
            json.dump(to_save, f, indent=2)

    # ---- Public access methods ----
    @classmethod
    def get(cls, key, fallback=None):
        config = cls._get_config()
        if key not in config:
            fallback = fallback if fallback is not None else cls._defaults.get(key)
            return cls._cast(key, fallback)
        return config[key]

    @classmethod
    def get_all(cls):
        return cls._get_config().copy()

    @classmethod
    def set(cls, key, value=None, strict=False):
        config = cls._get_config()

        def apply(k, v):
            if k not in cls._defaults:
                raise ValueError(f"Invalid config key: {k}")
            expected = cls._get_expected_type(k)
            if strict and expected and not isinstance(v, expected):
                raise TypeError(f"{k} should be {expected.__name__}, got {type(v).__name__}")
            return cls._cast(k, v)

        if isinstance(key, dict):
            for k in key:
                config[k] = apply(k, key[k])
        else:
            config[key] = apply(key, value)

        cls.save()
        return True

    @classmethod
    def config_path(cls, filename):
        path = cls._config_path / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)

    # ---- Validation / sanitization ----
    @classmethod
    def validate(cls):
        issues = []
        config = cls._get_config()

        for key, expected in cls._type_map.items():
            val = config.get(key)
            if val is None:
                issues.append(f"Missing key: {key}")
            elif expected == Path:
                if not isinstance(val, (str, Path)):
                    issues.append(f"{key} should be Path (or str), got {type(val).__name__}")
            elif not isinstance(val, expected):
                issues.append(f"{key} should be {expected.__name__}, got {type(val).__name__}")
        return issues

    @classmethod
    def sanitize(cls, save_on_change=True):
        config = cls._get_config()
        changed = False

        for key in cls._defaults:
            raw = config.get(key, cls._defaults.get(key))
            casted = cls._cast(key, raw)
            if config.get(key) != casted:
                config[key] = casted
                changed = True

        if changed and save_on_change:
            cls.save()
        return changed

    @classmethod
    def print(cls):
        for k, v in cls._get_config().items():
            print(f"{k:30} = {v}")
