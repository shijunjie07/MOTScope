# --------------------
# REST API routes for dataset and viewer operations.
# @author: SHI JUNJIE
# 2026-04-25
# --------------------

from io import BytesIO

import cv2
from flask import Blueprint, abort, current_app, jsonify, request, send_file

api_bp = Blueprint("api", __name__)


def _viewer():
    """Return the shared viewer service from the Flask app."""
    return current_app.extensions["viewer_service"]


def _registry():
    """Return the shared dataset registry from the Flask app."""
    return current_app.extensions["dataset_registry"]


def _video_cache():
    """Return the shared video cache service."""
    return current_app.extensions["video_cache"]


def _export_manager():
    """Return the shared export manager."""
    return current_app.extensions["export_manager"]


def _job_manager():
    """Return the shared background job manager."""
    return current_app.extensions["job_manager"]


def _download_url(path):
    """Build a browser download URL for an exported file path."""
    return f"/downloads/exports/{path.name}"


def _public_video_payload(payload: dict) -> dict:
    """Hide local filesystem details from video payloads."""
    public_payload = dict(payload)
    public_payload.pop("path", None)
    return public_payload


@api_bp.get("/datasets")
def api_datasets():
    """Return dataset definitions for the frontend selector."""
    registry = _registry()
    return jsonify(
        {
            "datasets": registry.list_datasets(),
            "default": registry.resolve_name(current_app.config["DEFAULT_DATASET"]),
        }
    )


@api_bp.post("/datasets")
def api_add_dataset():
    """Create a new custom dataset entry from client-provided settings."""
    payload = request.get_json(silent=True) or {}
    try:
        dataset = _registry().add_dataset(payload)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"dataset": dataset.to_dict(resolved_splits=_registry().list_splits(dataset.name))}), 201


@api_bp.get("/splits")
def api_splits():
    """Return available splits for a dataset."""
    dataset = request.args.get("dataset")
    return jsonify(_registry().list_splits(dataset))


@api_bp.get("/sequences")
def api_sequences():
    """Return sequences for the requested dataset split."""
    dataset = request.args.get("dataset")
    split = request.args.get("split", "")
    return jsonify(_viewer().list_sequences(dataset, split))


@api_bp.get("/frame_info")
def api_frame_info():
    """Return frame count and frame range for a sequence."""
    dataset = request.args.get("dataset")
    split = request.args.get("split", "")
    seq = request.args.get("seq", "")
    return jsonify(_viewer().frame_info(dataset, split, seq))


@api_bp.get("/annotation_files")
def api_annotation_files():
    """Return available GT and DET files for a sequence."""
    dataset = request.args.get("dataset")
    split = request.args.get("split", "")
    seq = request.args.get("seq", "")
    return jsonify(_viewer().list_annotation_files(dataset, split, seq))


@api_bp.get("/annotations")
def api_annotations():
    """Return all sequence annotations grouped by frame and layer."""
    dataset = request.args.get("dataset")
    split = request.args.get("split", "")
    seq = request.args.get("seq", "")
    if not seq:
        return jsonify({"error": "Missing sequence"}), 400
    try:
        return jsonify(_viewer().annotation_payload(dataset, split, seq))
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:
        return jsonify({"error": f"annotation load failed: {exc}"}), 500


@api_bp.get("/video/<dataset>/<split>/<seq>")
def api_video(dataset: str, split: str, seq: str):
    """Create or return a cached MP4 proxy for smooth playback."""
    payload = _video_cache().ensure_video(dataset, split, seq)
    return jsonify(_public_video_payload(payload))


@api_bp.post("/video/render")
def api_video_render():
    """Start a background smooth-video generation job."""
    payload = request.get_json(silent=True) or {}
    dataset = payload.get("dataset")
    split = payload.get("split", "")
    seq = payload.get("sequence") or payload.get("seq", "")
    if not seq:
        return jsonify({"error": "Missing sequence"}), 400
    video_cache = _video_cache()

    def work(progress):
        result = video_cache.ensure_video(dataset, split, seq, progress=progress)
        if not result.get("available"):
            raise RuntimeError(result.get("error") or "video generation failed")
        return _public_video_payload(result)

    job = _job_manager().start("Generating Smooth Video", work)
    return jsonify({"job_id": job.job_id, "status": job.status}), 202


@api_bp.get("/jobs/<job_id>")
def api_job(job_id: str):
    """Return background job progress."""
    job = _job_manager().get(job_id)
    if job is None:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job.to_dict())


@api_bp.get("/vis_not1_frames")
def api_vis_not1_frames():
    """Return frames whose visibility differs from 1."""
    dataset = request.args.get("dataset")
    split = request.args.get("split", "")
    seq = request.args.get("seq", "")
    annotation_type = request.args.get("annotation_type", "gt")
    annotation_file = request.args.get("annotation_file", "").strip() or None
    return jsonify(
        _viewer().vis_not1_frames(
            dataset, split, seq, annotation_type=annotation_type, annotation_file=annotation_file
        )
    )


@api_bp.get("/seq_meta")
def api_seq_meta():
    """Return selected metadata fields for a sequence."""
    dataset = request.args.get("dataset")
    split = request.args.get("split", "")
    seq = request.args.get("seq", "")
    return jsonify(_viewer().sequence_meta(dataset, split, seq))


@api_bp.get("/render_raw")
def api_render_raw():
    """Render a raw frame image for the requested sequence position."""
    dataset = request.args.get("dataset")
    split = request.args.get("split", "")
    seq = request.args.get("seq", "")
    if not seq:
        abort(400, "Missing seq")

    frame_idx = int(request.args.get("frame_idx", "0"))
    frame_mode = request.args.get("frame_mode", "idx")
    frame_value = request.args.get("frame_value", "").strip()

    try:
        image = _viewer().render_raw(dataset, split, seq, frame_idx, frame_mode, frame_value)
    except FileNotFoundError as exc:
        abort(404, str(exc))
    if image is None:
        abort(404, "failed to read image")

    ok, buf = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        abort(500, "encode failed")
    return send_file(BytesIO(buf.tobytes()), mimetype="image/jpeg")


@api_bp.get("/frame_boxes")
def api_frame_boxes():
    """Return detection boxes for one selected frame."""
    dataset = request.args.get("dataset")
    split = request.args.get("split", "")
    seq = request.args.get("seq", "")
    if not seq:
        abort(400, "Missing seq")

    frame_idx = int(request.args.get("frame_idx", "0"))
    frame_mode = request.args.get("frame_mode", "idx")
    frame_value = request.args.get("frame_value", "").strip()
    annotation_type = request.args.get("annotation_type", "gt")
    annotation_file = request.args.get("annotation_file", "").strip() or None
    try:
        payload = _viewer().frame_boxes(
            dataset,
            split,
            seq,
            frame_idx,
            frame_mode,
            frame_value,
            annotation_type=annotation_type,
            annotation_file=annotation_file,
        )
    except FileNotFoundError as exc:
        abort(404, str(exc))
    return jsonify(payload)


@api_bp.post("/export/frame")
def api_export_frame():
    """Export the current frame in a selected image format."""
    payload = request.get_json(silent=True) or {}
    try:
        out_path = _export_manager().export_frame(payload)
    except ValueError as exc:
        return jsonify({"available": False, "error": str(exc)}), 400
    except FileNotFoundError as exc:
        return jsonify({"available": False, "error": str(exc)}), 404
    except Exception as exc:
        return jsonify({"available": False, "error": f"frame export failed: {exc}"}), 500
    return jsonify({"available": True, "download_url": _download_url(out_path)})


@api_bp.post("/export/sequence/images")
def api_export_sequence_images():
    """Export a sequence as a ZIP of images."""
    payload = request.get_json(silent=True) or {}
    try:
        out_path = _export_manager().export_images_zip(payload)
    except ValueError as exc:
        return jsonify({"available": False, "error": str(exc)}), 400
    except FileNotFoundError as exc:
        return jsonify({"available": False, "error": str(exc)}), 404
    except Exception as exc:
        return jsonify({"available": False, "error": f"image ZIP export failed: {exc}"}), 500
    return jsonify({"available": True, "download_url": _download_url(out_path)})


@api_bp.post("/export/sequence/video")
def api_export_sequence_video():
    """Export a sequence as an MP4 video."""
    payload = request.get_json(silent=True) or {}
    try:
        out_path = _export_manager().export_video(payload)
    except ValueError as exc:
        return jsonify({"available": False, "error": str(exc)}), 400
    except FileNotFoundError as exc:
        return jsonify({"available": False, "error": str(exc)}), 404
    except Exception as exc:
        return jsonify({"available": False, "error": f"video export failed: {exc}"}), 500
    return jsonify({"available": True, "download_url": _download_url(out_path)})


@api_bp.post("/export/start")
def api_export_start():
    """Start an export job and report progress via /api/jobs/<job_id>."""
    payload = request.get_json(silent=True) or {}
    target = (payload.get("target") or "frame").strip().lower()
    titles = {
        "frame": "Exporting Frame",
        "images": "Exporting Image Sequence",
        "video": "Exporting Annotated Video",
    }
    if target not in titles:
        return jsonify({"error": f"Unsupported export target: {target}"}), 400
    export_manager = _export_manager()

    def work(progress):
        if target == "frame":
            out_path = export_manager.export_frame(payload, progress=progress)
        elif target == "images":
            out_path = export_manager.export_images_zip(payload, progress=progress)
        else:
            out_path = export_manager.export_video(payload, progress=progress)
        return {"available": True, "download_url": _download_url(out_path)}

    job = _job_manager().start(titles[target], work)
    return jsonify({"job_id": job.job_id, "status": job.status}), 202
