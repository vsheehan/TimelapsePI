import os
import signal
import atexit
from flask import Flask
from flask_socketio import SocketIO
from lib.class_config import Config
from lib.class_logging import Logger
from lib.class_temp import TempZip
from lib.class_socket import SocketManager

from routes import blueprints
from lib.errors import register_error_handlers
from lib.class_shutdown import ShutdownManager
from lib.class_status import Status


# --- App Setup ---
app = Flask(__name__)


@app.template_filter("istrue")
def istrue(value):
    return str(value).lower() in ["1", "true", "yes", "on"]


socketio = SocketIO(app, async_mode="threading")
SocketManager.set_socketio(socketio)

# --- Config/Logger Init ---
Config.load()
Status.start_emitter()
Logger.info("App initialized", category="app")

# Warn if previous session still active

def sessionAndCameraCleanup():
    from lib.class_session import Session
    from lib.class_camera import Camera
    active = [s for s in Session.list_all() if s.get("status") == "active"]
    if active:
        Logger.warning(f"{len(active)} session(s) still marked active on startup", category="session")
    Session.clean_invalid_sessions()
    Session.end_orphaned_sessions()
    Camera.remove_temp_images()

sessionAndCameraCleanup()

# --- Initialize TempZip Singleton ---
TempZip.get_instance()

# --- Start Bluetooth Daemon ---
def doBluetooth():
    from lib.class_bt_daemon import BluetoothDaemon
    from lib.ble_gatt_server import start_ble_server_thread
    BluetoothDaemon.start()
    start_ble_server_thread()

if Config.get('bt_enabled'):
    doBluetooth()


# --- Register Blueprints ---
for bp in blueprints:
    app.register_blueprint(bp)

# --- Register Error Handlers ---
register_error_handlers(app)

# --- Cleanup Hook ---
atexit.register(ShutdownManager.clean_up)
signal.signal(signal.SIGINT, lambda sig, frame: ShutdownManager.clean_up())
signal.signal(signal.SIGTERM, lambda sig, frame: ShutdownManager.clean_up())

# --- App Entry Point ---
if __name__ == "__main__":
    Logger.tail_log()
    debug_mode = Config.get("debug", fallback=True)

    if debug_mode:
        socketio.run(
            app,
            host="0.0.0.0",
            port=5000,
            debug=True,
            use_debugger=True,
            use_reloader=False,
            allow_unsafe_werkzeug=True
        )
    else:
        import eventlet
        eventlet.monkey_patch()
        socketio.run(app, host="0.0.0.0", port=80, debug=False)
