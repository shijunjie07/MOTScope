from __future__ import annotations

import base64
import copy
import html
import re
import shutil
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Callable

import cv2

IMAGE_FORMATS = {"jpg", "jpeg", "png", "svg"}
VIDEO_FORMATS = {"mp4"}
EXPORT_FORMATS = {
    "frame": IMAGE_FORMATS,
    "images": IMAGE_FORMATS,
    "video": VIDEO_FORMATS,
}


def validate_export_request(target: str, fmt: str) -> str:
    """Validate an export target/format combination."""
    target = (target or "").strip().lower()
    fmt = (fmt or "").strip().lower().lstrip(".")
    if target not in EXPORT_FORMATS:
        raise ValueError(f"Unsupported export target: {target}")
    if fmt not in EXPORT_FORMATS[target]:
        allowed = ", ".join(sorted(EXPORT_FORMATS[target]))
        raise ValueError(f"Invalid format '{fmt}' for {target}. Allowed: {allowed}")
    return fmt


def safe_name(value: str) -> str:
    """Return a filesystem-safe filename segment."""
    out = []
    for char in str(value):
        out.append(char if char.isalnum() or char in {"-", "_"} else "_")
    text = "".join(out).strip("_")
    return text or "item"


def selected_layer_names(payload: dict, request_payload: dict) -> list[str]:
    """Resolve export layer selection from request settings."""
    if not request_payload.get("include_annotations", True):
        return []
    mode = request_payload.get("annotation_mode", "visible")
    layers = payload.get("layers", [])
    if mode == "none":
        return []
    if mode == "custom":
        selected = {str(name) for name in request_payload.get("selected_layers", [])}
        known = {layer["name"] for layer in layers}
        missing = selected - known
        if missing:
            raise ValueError(f"Invalid layer name(s): {', '.join(sorted(missing))}")
        return [layer["name"] for layer in layers if layer["name"] in selected]
    return [layer["name"] for layer in layers if layer.get("visible", True)]


def apply_layer_overrides(annotation_payload: dict, request_payload: dict) -> dict:
    """Apply client-side layer display settings before export rendering."""
    overrides = request_payload.get("layer_overrides") or {}
    if not isinstance(overrides, dict):
        return annotation_payload
    known = {layer.get("name"): layer for layer in annotation_payload.get("layers", [])}
    for name, patch in overrides.items():
        layer = known.get(name)
        if not layer or not isinstance(patch, dict):
            continue
        color = str(patch.get("color") or "").strip()
        if re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            layer["color"] = color
        for key in ("visible", "draw_id", "draw_score"):
            if key in patch:
                layer[key] = bool(patch[key])
        if "score_threshold" in patch:
            try:
                layer["score_threshold"] = max(0.0, min(1.0, float(patch["score_threshold"])))
            except (TypeError, ValueError):
                pass
    return annotation_payload


def boxes_for_frame(payload: dict, frame_number: int, selected_layers: list[str]) -> list[dict]:
    """Flatten selected layer boxes for one MOT frame."""
    layer_settings = {layer["name"]: layer for layer in payload.get("layers", [])}
    frame_layers = payload.get("frames", {}).get(str(frame_number), {})
    boxes: list[dict] = []
    for layer_name in selected_layers:
        settings = layer_settings.get(layer_name)
        if not settings:
            continue
        threshold = float(settings.get("score_threshold", 0.0) or 0.0)
        for box in frame_layers.get(layer_name, []):
            if float(box.get("score", 1.0)) < threshold:
                continue
            item = dict(box)
            item["layer"] = layer_name
            item["color"] = settings.get("color", "#35e6fd")
            item["draw_id"] = bool(settings.get("draw_id", True))
            item["draw_score"] = bool(settings.get("draw_score", False))
            boxes.append(item)
    return boxes


def draw_boxes(image, boxes: list[dict]):
    """Draw annotation boxes onto an OpenCV BGR image."""
    for box in boxes:
        color = hex_to_bgr(box.get("color", "#35e6fd"))
        x = int(round(float(box.get("x", box.get("x1", 0)))))
        y = int(round(float(box.get("y", box.get("y1", 0)))))
        w = int(round(float(box.get("w", box.get("x2", 0) - box.get("x1", 0)))))
        h = int(round(float(box.get("h", box.get("y2", 0) - box.get("y1", 0)))))
        cv2.rectangle(image, (x, y), (x + w, y + h), color, 2)
        labels = []
        if box.get("draw_id", True):
            labels.append(f"id:{box.get('id')}")
        if box.get("draw_score", False):
            labels.append(f"{float(box.get('score', 1.0)):.2f}")
        if labels:
            cv2.putText(
                image,
                " ".join(labels),
                (x, max(14, y - 5)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1,
                cv2.LINE_AA,
            )
    return image


def hex_to_bgr(value: str) -> tuple[int, int, int]:
    text = (value or "#35e6fd").strip().lstrip("#")
    if len(text) != 6:
        text = "35e6fd"
    r = int(text[0:2], 16)
    g = int(text[2:4], 16)
    b = int(text[4:6], 16)
    return b, g, r


def encode_raster(image, fmt: str) -> bytes:
    ext = ".jpg" if fmt == "jpeg" else f".{fmt}"
    params = [int(cv2.IMWRITE_JPEG_QUALITY), 92] if fmt in {"jpg", "jpeg"} else []
    ok, buf = cv2.imencode(ext, image, params)
    if not ok:
        raise RuntimeError(f"Failed to encode {fmt}")
    return buf.tobytes()


def render_svg(frame_path: Path, boxes: list[dict]) -> bytes:
    image = cv2.imread(str(frame_path), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"Failed to read image: {frame_path}")
    height, width = image.shape[:2]
    mime = "image/png" if frame_path.suffix.lower() == ".png" else "image/jpeg"
    embedded = base64.b64encode(frame_path.read_bytes()).decode("ascii")
    items = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<image href="data:{mime};base64,{embedded}" x="0" y="0" width="{width}" height="{height}"/>',
    ]
    for box in boxes:
        color = html.escape(box.get("color", "#35e6fd"))
        x = float(box.get("x", box.get("x1", 0)))
        y = float(box.get("y", box.get("y1", 0)))
        w = float(box.get("w", box.get("x2", 0) - box.get("x1", 0)))
        h = float(box.get("h", box.get("y2", 0) - box.get("y1", 0)))
        items.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" '
            f'stroke="{color}" fill="none" stroke-width="2"/>'
        )
        labels = []
        if box.get("draw_id", True):
            labels.append(f"ID {box.get('id')}")
        if box.get("draw_score", False):
            labels.append(f"{float(box.get('score', 1.0)):.2f}")
        if labels:
            label = html.escape(" ".join(labels))
            items.append(
                f'<text x="{x:.2f}" y="{max(14.0, y - 5):.2f}" '
                f'fill="{color}" stroke="black" stroke-width="0.5" font-size="14">{label}</text>'
            )
    items.append("</svg>")
    return "\n".join(items).encode("utf-8")


class ExportManager:
    """Create frame, image ZIP, and MP4 exports."""

    def __init__(self, viewer, export_dir: Path, video_cache):
        self.viewer = viewer
        self.export_dir = export_dir
        self.video_cache = video_cache

    def _ensure_dir(self) -> None:
        self.export_dir.mkdir(parents=True, exist_ok=True)
        if not self.export_dir.is_dir():
            raise RuntimeError(f"Export directory is not writable: {self.export_dir}")

    def _context(self, payload: dict) -> tuple[dict, list[str]]:
        annotation_payload = self.viewer.annotation_payload(
            payload.get("dataset"),
            payload.get("split", ""),
            payload.get("sequence", ""),
        )
        annotation_payload = copy.deepcopy(annotation_payload)
        annotation_payload = apply_layer_overrides(annotation_payload, payload)
        return annotation_payload, selected_layer_names(annotation_payload, payload)

    def export_frame(self, payload: dict, progress: Callable[[int, str], None] | None = None) -> Path:
        if progress:
            progress(10, "Rendering frame")
        fmt = validate_export_request("frame", payload.get("format", "png"))
        annotation_payload, selected_layers = self._context(payload)
        frame_number = int(payload.get("frame", annotation_payload.get("first_frame", 1)))
        frame_path = self.viewer.frame_path_for_mot_frame(
            payload.get("dataset"), payload.get("split", ""), payload.get("sequence", ""), frame_number
        )
        boxes = boxes_for_frame(annotation_payload, frame_number, selected_layers)
        self._ensure_dir()
        layer_key = "raw" if not selected_layers else safe_name("_".join(selected_layers))
        filename = (
            f"{safe_name(payload.get('dataset'))}_{safe_name(payload.get('split'))}_"
            f"{safe_name(payload.get('sequence'))}_frame_{frame_number:06d}_{layer_key}.{fmt}"
        )
        out_path = self._unique_path(filename)
        if fmt == "svg":
            out_path.write_bytes(render_svg(frame_path, boxes))
            if progress:
                progress(100, "Frame export ready")
            return out_path
        image = cv2.imread(str(frame_path), cv2.IMREAD_COLOR)
        if image is None:
            raise FileNotFoundError(f"Failed to read image: {frame_path}")
        if selected_layers:
            draw_boxes(image, boxes)
        out_path.write_bytes(encode_raster(image, fmt))
        if progress:
            progress(100, "Frame export ready")
        return out_path

    def export_images_zip(self, payload: dict, progress: Callable[[int, str], None] | None = None) -> Path:
        fmt = validate_export_request("images", payload.get("format", "png"))
        annotation_payload, selected_layers = self._context(payload)
        files = self.viewer.sequence_frame_files(
            payload.get("dataset"), payload.get("split", ""), payload.get("sequence", "")
        )
        self._ensure_dir()
        layer_key = "raw" if not selected_layers else safe_name("_".join(selected_layers))
        filename = (
            f"{safe_name(payload.get('dataset'))}_{safe_name(payload.get('split'))}_"
            f"{safe_name(payload.get('sequence'))}_images_{layer_key}_{fmt}.zip"
        )
        out_path = self._unique_path(filename)
        total = len(files)
        with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for idx, frame_path in enumerate(files, start=1):
                frame_number = self.viewer.parse_frame_num_from_name(frame_path.name) or 1
                boxes = boxes_for_frame(annotation_payload, frame_number, selected_layers)
                arcname = f"{frame_path.stem}.{fmt}"
                if fmt == "svg":
                    archive.writestr(arcname, render_svg(frame_path, boxes))
                elif selected_layers:
                    image = cv2.imread(str(frame_path), cv2.IMREAD_COLOR)
                    if image is None:
                        raise FileNotFoundError(f"Failed to read image: {frame_path}")
                    archive.writestr(arcname, encode_raster(draw_boxes(image, boxes), fmt))
                else:
                    if fmt in {"jpg", "jpeg"} and frame_path.suffix.lower() in {".jpg", ".jpeg"}:
                        archive.write(frame_path, arcname)
                    elif fmt == "png" and frame_path.suffix.lower() == ".png":
                        archive.write(frame_path, arcname)
                    else:
                        image = cv2.imread(str(frame_path), cv2.IMREAD_COLOR)
                        if image is None:
                            raise FileNotFoundError(f"Failed to read image: {frame_path}")
                        archive.writestr(arcname, encode_raster(image, fmt))
                if progress and (idx == 1 or idx == total or idx % 25 == 0):
                    progress(int((idx / total) * 100), f"Rendering frame {idx} / {total}")
        return out_path

    def export_video(self, payload: dict, progress: Callable[[int, str], None] | None = None) -> Path:
        validate_export_request("video", payload.get("format", "mp4"))
        annotation_payload, selected_layers = self._context(payload)
        self._ensure_dir()
        layer_key = "raw" if not selected_layers else safe_name("_".join(selected_layers))
        filename = (
            f"{safe_name(payload.get('dataset'))}_{safe_name(payload.get('split'))}_"
            f"{safe_name(payload.get('sequence'))}_video_{layer_key}.mp4"
        )
        out_path = self._unique_path(filename)
        fps = float(payload.get("fps") or annotation_payload.get("fps") or 25)
        if not selected_layers:
            cache = self.video_cache.ensure_video(
                payload.get("dataset"),
                payload.get("split", ""),
                payload.get("sequence", ""),
                progress=progress,
            )
            if cache.get("available") and cache.get("path"):
                shutil.copyfile(cache["path"], out_path)
                if progress:
                    progress(100, "Video export ready")
                return out_path
        files = self.viewer.sequence_frame_files(
            payload.get("dataset"), payload.get("split", ""), payload.get("sequence", "")
        )
        self._encode_rendered_video(files, annotation_payload, selected_layers, fps, out_path, progress)
        return out_path

    def _encode_rendered_video(
        self,
        files: list[Path],
        annotation_payload: dict,
        selected_layers: list[str],
        fps: float,
        out_path: Path,
        progress: Callable[[int, str], None] | None = None,
    ) -> None:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("ffmpeg not found")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            total = len(files)
            for idx, frame_path in enumerate(files, start=1):
                image = cv2.imread(str(frame_path), cv2.IMREAD_COLOR)
                if image is None:
                    raise FileNotFoundError(f"Failed to read image: {frame_path}")
                frame_number = self.viewer.parse_frame_num_from_name(frame_path.name) or idx
                boxes = boxes_for_frame(annotation_payload, frame_number, selected_layers)
                if selected_layers:
                    draw_boxes(image, boxes)
                cv2.imwrite(str(tmp_dir / f"{idx:06d}.jpg"), image)
                if progress and (idx == 1 or idx == total or idx % 25 == 0):
                    percent = max(1, min(85, int((idx / total) * 85)))
                    progress(percent, f"Rendering frame {idx} / {total}")
            if progress:
                progress(90, "Encoding MP4")
            command = [
                ffmpeg,
                "-y",
                "-framerate",
                str(fps),
                "-i",
                str(tmp_dir / "%06d.jpg"),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(out_path),
            ]
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg video export failed: {result.stderr.strip()}")
            if progress:
                progress(100, "Video export ready")

    def _unique_path(self, filename: str) -> Path:
        stem = Path(filename).stem
        suffix = Path(filename).suffix
        candidate = self.export_dir / filename
        if not candidate.exists():
            return candidate
        return self.export_dir / f"{stem}_{int(time.time())}{suffix}"
