import json
import threading
import requests
from bluezero import peripheral, adapter
from lib.class_logging import Logger
from gi.repository import GLib

# UUIDs for BLE service and characteristics
UUID_SERVICE = '12345678-1234-5678-1234-56789abcdef0'
UUID_COMMAND_WRITE = '12345678-1234-5678-1234-56789abcdef1'
UUID_RESPONSE_NOTIFY = '12345678-1234-5678-1234-56789abcdef2'

_gatt_thread = None


class GattCommandHandler:
    def __init__(self):
        self._response_callback = None
        self._lock = threading.Lock()
        self._last_result = "Waiting for command..."

    def set_response_callback(self, callback):
        self._response_callback = callback

    def write_command(self, value, options):
        try:
            command = bytes(value).decode("utf-8").strip()
            Logger.info(f"Received BLE command: {command}", category="bluetooth")
            result = self._dispatch_command(command)
            with self._lock:
                self._last_result = result
            if self._response_callback:
                GLib.idle_add(lambda: self._response_callback(result.encode("utf-8")))
        except Exception as e:
            Logger.error(f"Write handler error: {e}", category="bluetooth")

    def read_response(self):
        with self._lock:
            return self._last_result.encode("utf-8")

    def _dispatch_command(self, command: str) -> str:
        parts = command.split()
        if not parts:
            return "Invalid command"

        cmd = parts[0].lower()
        args = parts[1:]

        try:
            if cmd == "stream_start":
                r = requests.post("http://localhost:5000/camera/stream/start")
            elif cmd == "stream_stop":
                r = requests.post("http://localhost:5000/camera/stream/stop")
            elif cmd == "capture_start":
                r = requests.post("http://localhost:5000/camera/capture/start")
            elif cmd == "capture_stop":
                r = requests.post("http://localhost:5000/camera/capture/stop")
            elif cmd == "status":
                r = requests.get("http://localhost:5000/system/status")
                return json.dumps(r.json(), indent=2)
            elif cmd == "set" and len(args) >= 2:
                key, value = args[0], " ".join(args[1:])
                r = requests.post("http://localhost:5000/settings", data={key: value})
            else:
                return "Unknown or invalid command"

            return f"Response {r.status_code}: {r.text.strip()}"
        except Exception as e:
            Logger.error(f"Dispatch error: {e}", category="bluetooth")
            return f"Error: {str(e)}"


def run_ble_gatt_server():
    handler = GattCommandHandler()

    adapter_list = adapter.list_adapters()
    if not adapter_list:
        raise RuntimeError("No Bluetooth adapter found.")

    app = peripheral.Peripheral(adapter_address=adapter_list[0], local_name="TimelapsePi")

    # Create service
    app.add_service(0, UUID_SERVICE, True)

    # Add characteristics with correct parameter order and types
    # Write characteristic
    app.add_characteristic(
        0, 0, UUID_COMMAND_WRITE, ['write', 'write-without-response'],
        read_callback=None,
        write_callback=handler.write_command,
        notify_callback=None,
        notifying=False
    )

    # Notify characteristic
    app.add_characteristic(
        0, 1, UUID_RESPONSE_NOTIFY, ['read', 'notify'],
        read_callback=handler.read_response,
        write_callback=None,
        notify_callback=None,
        notifying=True
    )

    def notify_callback(value):
        try:
            app.update_value(UUID_RESPONSE_NOTIFY, value)
        except Exception as e:
            Logger.warning(f"Notify error: {e}", category="bluetooth")

    handler.set_response_callback(notify_callback)

    app.advert.service_UUIDs = [UUID_SERVICE]
    Logger.info("Starting BLE GATT Command Server", category="bluetooth")

    app.advert.start()
    app.publish()


def start_ble_server_thread():
    global _gatt_thread
    if _gatt_thread and _gatt_thread.is_alive():
        return
    _gatt_thread = threading.Thread(target=run_ble_gatt_server, daemon=True)
    _gatt_thread.start()
