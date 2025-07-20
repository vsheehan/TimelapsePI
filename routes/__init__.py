from .camera   import camera_bp
from .settings import settings_bp
from .sessions import sessions_bp
from .system   import system_bp
from .temp     import temp_bp
from .ui       import ui_bp
from .bt       import bt_bp


blueprints = [
    bt_bp,
    camera_bp,
    settings_bp,
    sessions_bp,
    system_bp,
    temp_bp,
    ui_bp
]