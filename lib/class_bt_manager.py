import threading
import subprocess
import json
import time
from pathlib import Path

from lib.class_config import Config
from lib.class_logging import Logger
from lib.class_socket import SocketManager


class BluetoothManager:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        raise RuntimeError("Use get_instance() to access BluetoothManager")

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = object.__new__(cls)
                    cls._instance._init_internal()
        return cls._instance

    def _init_internal(self):
        self._paired_devices = {}
        self._discovered_devices = {}
        self._connected_device = None
        self._scan_active = False
        self._scan_thread = None
        self._data_lock = threading.Lock()
        self._device_file = Path(Config.config_path("bt_devices.json"))
        self._load_devices()

    def _load_devices(self):
        if self._device_file.exists():
            try:
                with self._device_file.open("r") as f:
                    self._paired_devices = json.load(f)
            except Exception as e:
                Logger.warning(f"Failed to load paired devices: {e}", category="bluetooth")

    def _save_devices(self):
        try:
            with self._device_file.open("w") as f:
                json.dump(self._paired_devices, f, indent=2)
        except Exception as e:
            Logger.warning(f"Failed to save paired devices: {e}", category="bluetooth")

    def start_scan(self):
        if self._scan_active:
            return
        self._scan_active = True
        self._scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self._scan_thread.start()
        Logger.info("Bluetooth scan started", category="bluetooth")

    def stop_scan(self):
        self._scan_active = False
        Logger.info("Bluetooth scan stopped", category="bluetooth")

    def _scan_loop(self):
        while self._scan_active:
            try:
                result = subprocess.run(["bluetoothctl", "devices"], capture_output=True, text=True)
                devices = self._parse_scan_output(result.stdout)
                with self._data_lock:
                    self._discovered_devices = devices
                SocketManager.emit("bt-discovered", list(devices.values()))
            except Exception as e:
                Logger.error(f"Bluetooth scan error: {e}", category="bluetooth")
            time.sleep(10)

    def _parse_scan_output(self, output: str) -> dict:
        devices = {}
        for line in output.strip().splitlines():
            if line.startswith("Device"):
                parts = line.split(" ", 2)
                if len(parts) == 3:
                    addr, name = parts[1], parts[2]
                    devices[addr] = {"mac": addr, "name": name}
        return devices

    def get_status(self) -> dict:
        with self._data_lock:
            return {
                "connected": self._connected_device,
                "paired_count": len(self._paired_devices),
                "discovered_count": len(self._discovered_devices),
                "scan_active": self._scan_active
            }

    def get_discovered(self) -> list:
        with self._data_lock:
            return list(self._discovered_devices.values())

    def get_paired(self) -> list:
        with self._data_lock:
            return list(self._paired_devices.values())

    def connect(self, mac: str) -> bool:
        try:
            subprocess.run(["bluetoothctl", "pair", mac], check=True)
            subprocess.run(["bluetoothctl", "connect", mac], check=True)
            with self._data_lock:
                self._connected_device = mac
                self._paired_devices[mac] = self._discovered_devices.get(mac, {"mac": mac, "name": "Unknown"})
                self._save_devices()
            Logger.info(f"Connected to {mac}", category="bluetooth")
            return True
        except subprocess.CalledProcessError as e:
            Logger.error(f"Failed to connect to {mac}: {e}", category="bluetooth")
            return False

    def disconnect(self) -> bool:
        if not self._connected_device:
            return False
        try:
            subprocess.run(["bluetoothctl", "disconnect", self._connected_device], check=True)
            Logger.info(f"Disconnected from {self._connected_device}", category="bluetooth")
            with self._data_lock:
                self._connected_device = None
            return True
        except subprocess.CalledProcessError as e:
            Logger.error(f"Failed to disconnect: {e}", category="bluetooth")
            return False
