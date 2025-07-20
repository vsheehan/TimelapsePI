import json
import threading
import requests
from bluezero import peripheral
from lib.class_logging import Logger
import threading
from bluezero import adapter

# Static UUIDs for simplicity
UUID_SERVICE        = '12345678-1234-5678-1234-56789abcdef0'
UUID_COMMAND_WRITE  = '12345678-1234-5678-1234-56789abcdef1'
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
        command = value.decode("utf-8").strip()
        Logger.info(f"Received BLE command: {command}", category="bluetooth")
        result = self._dispatch_command(command)
        self._last_result = result
        if self._response_callback:
            self._response_callback(result.encode("utf-8"))

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
                r = requests.get("http://localhost:5000/status")
                return json.dumps(r.json(), indent=2)
            elif cmd == "set" and len(args) >= 2:
                key, value = args[0], " ".join(args[1:])
                r = requests.post("http://localhost:5000/settings", json={key: value})
            else:
                return "Unknown or invalid command"

            return f"Response {r.status_code}: {r.text.strip()}"
        except Exception as e:
            Logger.error(f"Dispatch error: {e}", category="bluetooth")
            return f"Error: {str(e)}"


# BLE Setup
def run_ble_gatt_server():
    handler = GattCommandHandler()

    cmd_characteristic = {
        'uuid': UUID_COMMAND_WRITE,
        'value': None,
        'write': handler.write_command,
        'notifying': False,
    }

    resp_characteristic = {
        'uuid': UUID_RESPONSE_NOTIFY,
        'value': handler.read_response,
        'notify': True
    }

    my_service = {
        'uuid': UUID_SERVICE,
        'characteristics': [cmd_characteristic, resp_characteristic]
    }

    device_name = "TimelapsePi"

    adapter_list = adapter.list_adapters()
    if not adapter_list:
        raise RuntimeError("No Bluetooth adapter found.")
    adapter_address = adapter_list[0]

    bt_adapter = adapter.Adapter()
    bt_adapter.powered = True
    bt_adapter.pairable = True
    bt_adapter.discoverable = True
    bt_adapter.advertise = True
    bt_adapter.alias = device_name  # Optional but nice for display
    Logger.info(f"Bluetooth MAC address: {bt_adapter.address}", category="bluetooth")
    peripheral_app = peripheral.Peripheral(
        adapter_address,              # adapter_addr → None to auto-select
        device_name,       # local_name
        [my_service]       # services
    )
    peripheral_app.advert._name = device_name
    Logger.debug(f"Advertising name: {peripheral_app.advert._name}", category="bluetooth")
    def notify_callback(value):
        try:
            peripheral_app.dman.characteristics[1].set_value(value)
        except Exception as e:
            Logger.warning(f"Notify callback error: {e}", category="bluetooth")

    peripheral_app.advert.local_name = device_name
    peripheral_app.advert.service_UUIDs = [UUID_SERVICE]


    handler.set_response_callback(notify_callback)

    Logger.info("Starting BLE GATT Command Server", category="bluetooth")
    peripheral_app.advert.start()
    peripheral_app.publish.start()


def start_ble_server_thread():
    global _gatt_thread
    if _gatt_thread and _gatt_thread.is_alive():
        return
    _gatt_thread = threading.Thread(target=run_ble_gatt_server, daemon=True)
    _gatt_thread.start()
