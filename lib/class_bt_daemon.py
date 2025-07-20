import threading
import time
import pexpect

from lib.class_logging import Logger
from lib.class_bt_manager import BluetoothManager
from lib.class_config import Config


class BluetoothDaemon:
    _thread = None
    _stop_flag = False

    @classmethod
    def start(cls):
        if cls._thread and cls._thread.is_alive():
            return
        cls._stop_flag = False
        cls._thread = threading.Thread(target=cls._run, daemon=True)
        cls._thread.start()
        Logger.info("Bluetooth daemon started", category="bluetooth")

    @classmethod
    def stop(cls):
        cls._stop_flag = True
        if cls._thread:
            cls._thread.join(timeout=3)
        Logger.info("Bluetooth daemon stopped", category="bluetooth")

    @classmethod
    def _run(cls):
        try:
            bt = pexpect.spawn("bluetoothctl", echo=False, encoding="utf-8", timeout=5)
            bt.expect(["Discoverable: yes", "Controller .* Discoverable: yes", "Controller .* Pairable: yes"], timeout=5)
            bt.sendline("agent on")
            bt.expect(["Agent registered", "Agent is already registered"], timeout=5)
            bt.sendline("default-agent")
            bt.expect("Default agent request successful")
            bt.sendline("scan on")
            Logger.info("Bluetooth scanning enabled (interactive)", category="bluetooth")

            manager = BluetoothManager.get_instance()

            while not cls._stop_flag:
                try:
                    idx = bt.expect(["Device ([0-9A-F:]{17}) (.+)", pexpect.TIMEOUT, pexpect.EOF], timeout=5)
                    if idx == 0:
                        mac = bt.match.group(1)
                        name = bt.match.group(2)
                        Logger.debug(f"Discovered device: {mac} {name}", category="bluetooth")
                        with manager._data_lock:
                            manager._discovered_devices[mac] = {"mac": mac, "name": name}
                    time.sleep(0.1)
                except Exception as e:
                    Logger.warning(f"Scan loop error: {e}", category="bluetooth")
                    time.sleep(1)

            bt.sendline("scan off")
            bt.expect("Discovery stopped")
            bt.sendline("exit")
        except Exception as e:
            Logger.error(f"Bluetooth daemon failed: {e}", category="bluetooth")
