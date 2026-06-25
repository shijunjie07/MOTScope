# --------------------
# Page routes for rendering the viewer interface.
# @author: SHI JUNJIE
# 2026-04-25
# --------------------

from pathlib import Path

from flask import Blueprint, abort, current_app, render_template, send_from_directory

pages_bp = Blueprint("pages", __name__)


@pages_bp.get("/")
def index():
    """Render the main viewer page."""
    return render_template("index.html")


@pages_bp.get("/video_cache/<path:filename>")
def video_cache_file(filename: str):
    """Serve generated smooth-playback MP4 cache files."""
    directory = Path(current_app.instance_path) / "video_cache"
    if not (directory / filename).exists():
        abort(404)
    return send_from_directory(directory, filename, as_attachment=False)


@pages_bp.get("/downloads/exports/<path:filename>")
def export_download(filename: str):
    """Serve generated exports for browser download."""
    directory = Path(current_app.instance_path) / "exports"
    if not (directory / filename).exists():
        abort(404)
    return send_from_directory(directory, filename, as_attachment=True)
