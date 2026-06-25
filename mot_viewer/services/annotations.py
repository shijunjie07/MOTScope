from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from ..datasets.models import AnnotationLayer, DatasetDefinition


DEFAULT_COLORS = {
    "gt": "#00ff00",
    "det": "#ff9900",
    "tracker": "#35e6fd",
    "result": "#35e6fd",
    "custom": "#d8b4fe",
}


def layer_payload(layer: AnnotationLayer) -> dict:
    """Return the public settings for an annotation layer."""
    return layer.to_dict()


def default_layers_for_sequence(
    dataset: DatasetDefinition,
    seq_dir: Path,
    gt_path: Path | None,
    det_files: list[str],
) -> list[AnnotationLayer]:
    """Build backward-compatible layers when config has no layer list."""
    layers: list[AnnotationLayer] = []
    if gt_path is not None:
        layers.append(
            AnnotationLayer(
                name="Ground Truth",
                type="gt",
                path=str(gt_path.relative_to(seq_dir)),
                color=DEFAULT_COLORS["gt"],
                visible=True,
                draw_id=True,
                draw_score=False,
                score_threshold=0.0,
            )
        )
    elif dataset.gt_files:
        layers.append(
            AnnotationLayer(
                name="Ground Truth",
                type="gt",
                path=f"gt/{dataset.gt_files[0]}",
                color=DEFAULT_COLORS["gt"],
                visible=True,
                draw_id=True,
                draw_score=False,
                score_threshold=0.0,
            )
        )

    if "det.txt" in det_files:
        det_name = "det.txt"
    elif det_files:
        det_name = det_files[0]
    else:
        det_name = ""

    if det_name:
        layers.append(
            AnnotationLayer(
                name="Detections",
                type="det",
                path=f"det/{det_name}",
                color=DEFAULT_COLORS["det"],
                visible=True,
                draw_id=False,
                draw_score=True,
                score_threshold=0.0,
            )
        )
    return layers


def resolve_layer_path(seq_dir: Path, layer: AnnotationLayer) -> Path:
    """Resolve a layer path safely within a sequence directory."""
    raw_path = (layer.path or "").strip()
    if not raw_path:
        raw_path = f"{layer.type}/{layer.type}.txt"
    path = (seq_dir / raw_path).resolve()
    if seq_dir.resolve() not in path.parents and path != seq_dir.resolve():
        raise FileNotFoundError(f"annotation path escapes sequence directory: {layer.path}")
    return path


def parse_annotation_file(path: Path, layer_name: str) -> tuple[dict[int, list[dict]], list[str]]:
    """Parse a MOTChallenge-style annotation file.

    Malformed lines are skipped and reported as warnings instead of raising.
    """
    warnings: list[str] = []
    frames: dict[int, list[dict]] = {}
    if not path.exists():
        return frames, [f"{layer_name}: annotation file missing: {path}"]

    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
        text = raw_line.strip()
        if not text:
            continue
        parts = [part.strip() for part in text.split(",")]
        if len(parts) < 6:
            warnings.append(f"{layer_name}: line {line_no} skipped, expected at least 6 columns")
            continue
        try:
            frame = int(float(parts[0]))
            obj_id = int(float(parts[1]))
            x = float(parts[2])
            y = float(parts[3])
            w = float(parts[4])
            h = float(parts[5])
            score = float(parts[6]) if len(parts) > 6 and parts[6] != "" else 1.0
            vis = float(parts[9]) if len(parts) > 9 and parts[9] != "" else -1.0
        except ValueError:
            warnings.append(f"{layer_name}: line {line_no} skipped, non-numeric MOT value")
            continue
        if frame <= 0 or w < 0 or h < 0:
            warnings.append(f"{layer_name}: line {line_no} skipped, invalid frame or box size")
            continue
        frames.setdefault(frame, []).append(
            {
                "id": obj_id,
                "x": x,
                "y": y,
                "w": w,
                "h": h,
                "x1": x,
                "y1": y,
                "x2": x + w,
                "y2": y + h,
                "score": score,
                "vis": vis,
            }
        )
    return frames, warnings


def clone_layer(layer: AnnotationLayer) -> AnnotationLayer:
    """Return a copy so callers can adjust transient defaults safely."""
    return replace(layer)
