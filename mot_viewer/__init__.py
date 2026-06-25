# --------------------
# App factory and Flask application wiring.
# @author: SHI JUNJIE
# 2026-04-25
# --------------------

from pathlib import Path

from flask import Flask

from .config import AppConfig
from .datasets.registry import DatasetRegistry
from .routes.api import api_bp
from .routes.pages import pages_bp
from .services.export_manager import ExportManager
from .services.jobs import JobManager
from .services.viewer import ViewerService
from .services.video_cache import VideoCache


def create_app(config: type[AppConfig] = AppConfig) -> Flask:
    """Create and configure the Flask application.

    Args:
        config: Configuration class used to populate ``app.config``.

    Returns:
        Flask: The configured Flask application instance.
    """
    base_dir = Path(__file__).resolve().parent.parent
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder=str(base_dir / "templates"),
        static_folder=str(base_dir / "static"),
    )
    app.config.from_object(config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    registry = DatasetRegistry(
        config_path=Path(app.config["DATASETS_CONFIG_PATH"]),
        default_dataset=app.config["DEFAULT_DATASET"],
    )
    viewer_service = ViewerService(registry)
    video_cache = VideoCache(viewer_service, Path(app.instance_path) / "video_cache")
    job_manager = JobManager()
    export_manager = ExportManager(
        viewer_service,
        Path(app.instance_path) / "exports",
        video_cache,
    )

    app.extensions["dataset_registry"] = registry
    app.extensions["viewer_service"] = viewer_service
    app.extensions["video_cache"] = video_cache
    app.extensions["job_manager"] = job_manager
    app.extensions["export_manager"] = export_manager

    app.register_blueprint(pages_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    return app
