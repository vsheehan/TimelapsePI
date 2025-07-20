from flask import Blueprint, render_template
from lib.class_config import Config
from lib.class_status import Status
from lib.class_camera import Camera
from lib.class_session import Session
from lib.class_temp import TempZip
from lib.class_logging import Logger
from pathlib import Path

ui_bp = Blueprint("ui", __name__)


@ui_bp.route("/")
def index():

    raw_config = Config.get_all()

    # Convert Path objects and other non-serializables to strings
    safe_config = {k: str(v) if isinstance(v, Path) else v for k, v in raw_config.items()}

    return render_template(
        "index.html",
        config=safe_config,
        resolutions=Camera.get_supported_resolutions(),
        status=Status.build(),
        sessions=Session.list_all(),
        temp=TempZip.get_instance().list(),
        log=Logger.get_recent_log(100)
    )
