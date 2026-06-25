# --------------------
# Core viewer service for sequence, frame, and box loading.
# @author: SHI JUNJIE
# 2026-04-25
# --------------------

import re
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from ..datasets.models import DatasetDefinition
from ..datasets.registry import DatasetRegistry
from .annotations import (
    clone_layer,
    default_layers_for_sequence,
    layer_payload,
    parse_annotation_file,
    resolve_layer_path,
)

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


class ViewerService:
    """Load sequence assets, metadata, and annotations for the viewer."""

    def __init__(self, registry: DatasetRegistry):
        """Initialize the viewer service and in-memory caches.

        Args:
            registry: Dataset registry service.
        """
        self.registry = registry
        self.vis_frames_cache: dict[tuple[str, float], list[int]] = {}
        self.meta_cache: dict[tuple[str, float, float], dict] = {}
        self.annotation_payload_cache: dict[tuple, dict] = {}

    def natural_key(self, value: str):
        """Build a natural-sort key for mixed text and digits.

        Args:
            value: String to tokenize for sorting.

        Returns:
            list: Sort key list suitable for natural ordering.
        """
        return [int(token) if token.isdigit() else token.lower() for token in re.split(r"(\d+)", value)]

    def list_sequences(self, dataset_name: str | None, split: str) -> list[str]:
        """List sequence folders under a dataset split.

        Args:
            dataset_name: Dataset name or ``None`` for the default dataset.
            split: Dataset split name.

        Returns:
            list[str]: Sorted sequence names.
        """
        dataset = self.registry.get(dataset_name)
        split_dir = dataset.root / split
        if not split_dir.exists():
            return []

        sequences = [path.name for path in split_dir.iterdir() if path.is_dir()]
        sequences.sort(key=self.natural_key)
        return sequences

    def get_seq_dir(self, dataset_name: str | None, split: str, seq: str) -> tuple[DatasetDefinition, Path]:
        """Resolve the dataset definition and sequence directory path.

        Args:
            dataset_name: Dataset name or ``None``.
            split: Split name.
            seq: Sequence name.

        Returns:
            tuple[DatasetDefinition, Path]: Dataset definition and sequence
                path.
        """
        dataset = self.registry.get(dataset_name)
        return dataset, (dataset.root / split / seq).resolve()

    def get_img_dir(self, dataset: DatasetDefinition, seq_dir: Path) -> Path | None:
        """Resolve the image directory inside a sequence.

        Args:
            dataset: Dataset definition.
            seq_dir: Sequence directory path.

        Returns:
            Path | None: Image directory path if it exists.
        """
        img_dir = seq_dir / dataset.image_dir
        return img_dir if img_dir.exists() else None

    def parse_frame_num_from_name(self, name: str):
        """Extract the first numeric frame id from a filename.

        Args:
            name: Filename or stem string.

        Returns:
            int | None: Parsed frame number if present.
        """
        stem = Path(name).stem
        match = re.search(r"(\d+)", stem)
        return int(match.group(1)) if match else None

    def list_frame_files(self, img_dir: Path):
        """List frame image files in natural order.

        Args:
            img_dir: Directory containing frame images.

        Returns:
            list[Path]: Sorted frame image paths.
        """
        files = [path for path in img_dir.iterdir() if path.suffix.lower() in IMG_EXTS]

        def key(path: Path):
            frame_num = self.parse_frame_num_from_name(path.name)
            return (frame_num if frame_num is not None else 10**18, path.name)

        files.sort(key=key)
        return files

    def sequence_frame_files(self, dataset_name: str | None, split: str, seq: str) -> list[Path]:
        """Return all image files for a sequence in natural frame order."""
        _, _, img_dir, files = self.get_files_and_idx(dataset_name, split, seq)
        if not img_dir:
            raise FileNotFoundError("image directory not found")
        if not files:
            raise FileNotFoundError("no image frames found")
        return files

    def frame_path_for_mot_frame(
        self,
        dataset_name: str | None,
        split: str,
        seq: str,
        frame_number: int,
    ) -> Path:
        """Resolve a MOT frame number or 1-based index to an image path."""
        files = self.sequence_frame_files(dataset_name, split, seq)
        for path in files:
            if self.parse_frame_num_from_name(path.name) == int(frame_number):
                return path
        idx = int(frame_number) - 1
        if 0 <= idx < len(files):
            return files[idx]
        raise ValueError(f"Invalid frame index: {frame_number}")

    def get_gt_path(self, dataset: DatasetDefinition, seq_dir: Path) -> Path | None:
        """Resolve the first available GT file for a sequence.

        Args:
            dataset: Dataset definition with GT filename priority.
            seq_dir: Sequence directory path.

        Returns:
            Path | None: Existing GT file path if found.
        """
        for gt_name in dataset.gt_files:
            path = seq_dir / "gt" / gt_name
            if path.exists():
                return path
        return None

    def list_annotation_files(self, dataset_name: str | None, split: str, seq: str) -> dict:
        """List selectable GT and DET files for a sequence.

        Args:
            dataset_name: Dataset name or ``None``.
            split: Split name.
            seq: Sequence name.

        Returns:
            dict: Annotation file options grouped by source type.
        """
        if not seq:
            return {"sources": {"gt": [], "det": []}, "default_type": "gt", "default_file": ""}

        dataset, seq_dir = self.get_seq_dir(dataset_name, split, seq)
        gt_files = self._list_annotation_dir(seq_dir / "gt")
        det_files = self._list_annotation_dir(seq_dir / "det")

        default_gt = self.get_gt_path(dataset, seq_dir)
        default_gt_name = default_gt.name if default_gt else (gt_files[0] if gt_files else "")
        default_det_name = "det.txt" if "det.txt" in det_files else (det_files[0] if det_files else "")

        if default_gt_name:
            default_type = "gt"
            default_file = default_gt_name
        elif default_det_name:
            default_type = "det"
            default_file = default_det_name
        else:
            default_type = "gt"
            default_file = ""

        return {
            "sources": {
                "gt": gt_files,
                "det": det_files,
            },
            "defaults": {
                "gt": default_gt_name,
                "det": default_det_name,
            },
            "default_type": default_type,
            "default_file": default_file,
        }

    def _list_annotation_dir(self, directory: Path) -> list[str]:
        """List annotation filenames inside a directory.

        Args:
            directory: Annotation directory path.

        Returns:
            list[str]: Sorted annotation filenames.
        """
        if not directory.exists():
            return []

        files = [path.name for path in directory.iterdir() if path.is_file()]
        files.sort(key=self.natural_key)
        return files

    def resolve_annotation_path(
        self,
        dataset_name: str | None,
        split: str,
        seq: str,
        annotation_type: str | None,
        annotation_file: str | None,
    ) -> Path | None:
        """Resolve a selected annotation source and filename to a safe path.

        Args:
            dataset_name: Dataset name or ``None``.
            split: Split name.
            seq: Sequence name.
            annotation_type: ``"gt"`` or ``"det"``.
            annotation_file: Requested annotation filename.

        Returns:
            Path | None: Resolved annotation file path if available.

        Raises:
            FileNotFoundError: If the requested annotation file is invalid.
        """
        if not seq:
            return None

        dataset, seq_dir = self.get_seq_dir(dataset_name, split, seq)
        annotation_type = (annotation_type or "gt").strip().lower()
        if annotation_type not in {"gt", "det"}:
            annotation_type = "gt"

        if annotation_type == "gt" and not annotation_file:
            return self.get_gt_path(dataset, seq_dir)

        available = self.list_annotation_files(dataset_name, split, seq)["sources"][annotation_type]
        if not available:
            return None

        if not annotation_file:
            defaults = self.list_annotation_files(dataset_name, split, seq)["defaults"]
            annotation_file = defaults.get(annotation_type) or available[0]

        if annotation_file not in available:
            raise FileNotFoundError(f"{annotation_type} file not found: {annotation_file}")

        return (seq_dir / annotation_type / annotation_file).resolve()

    def load_annotations(self, annotation_path: Path | None):
        """Load and normalize an annotation file into a DataFrame.

        Args:
            annotation_path: Annotation file path.

        Returns:
            pandas.DataFrame | None: Normalized annotations.
        """
        if annotation_path is None:
            return None

        df = pd.read_csv(annotation_path, header=None)
        if df.shape[1] < 6:
            return None

        columns = ["frame", "id", "x", "y", "w", "h", "conf", "cls", "unused", "vis"]
        df = df.iloc[:, : min(len(columns), df.shape[1])]
        df.columns = columns[: df.shape[1]]

        for col in ["frame", "id", "x", "y", "w", "h"]:
            if col not in df.columns:
                return None

        if "vis" not in df.columns:
            df["vis"] = -1.0

        df["frame"] = pd.to_numeric(df["frame"], errors="coerce").fillna(0).astype(int)
        df["id"] = pd.to_numeric(df["id"], errors="coerce").fillna(0).astype(int)
        for col in ["x", "y", "w", "h", "vis"]:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        return df

    def get_files_and_idx(self, dataset_name: str | None, split: str, seq: str):
        """Resolve dataset, sequence, image directory, and frame files.

        Args:
            dataset_name: Dataset name or ``None``.
            split: Split name.
            seq: Sequence name.

        Returns:
            tuple: Dataset, sequence dir, image dir, and frame file list.
        """
        dataset, seq_dir = self.get_seq_dir(dataset_name, split, seq)
        img_dir = self.get_img_dir(dataset, seq_dir)
        if not img_dir:
            return dataset, seq_dir, None, []
        return dataset, seq_dir, img_dir, self.list_frame_files(img_dir)

    def resolve_frame_idx(self, files, frame_idx: int, frame_mode: str, frame_value: str):
        """Resolve a slider/frame request into a valid file index.

        Args:
            files: Frame file list.
            frame_idx: Slider-based frame index.
            frame_mode: ``"idx"`` or ``"mot"``.
            frame_value: Optional direct frame input from the UI.

        Returns:
            int: Clamped frame file index.
        """
        idx = int(frame_idx)
        if frame_value.strip():
            try:
                value = int(frame_value)
                if frame_mode == "mot":
                    numbers = [self.parse_frame_num_from_name(path.name) for path in files]
                    idx = numbers.index(value) if value in numbers else value
                else:
                    idx = value
            except Exception:
                pass
        return max(0, min(len(files) - 1, idx))

    def read_kv_ini(self, path: Path):
        """Read simple key=value metadata files without section parsing.

        Args:
            path: Metadata file path.

        Returns:
            dict: Parsed key-value pairs.
        """
        if not path or not path.exists():
            return {}

        out = {}
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            text = line.strip()
            if not text or text.startswith("#") or text.startswith(";") or "=" not in text:
                continue
            key, value = text.split("=", 1)
            out[key.strip()] = value.strip()
        return out

    def load_meta(self, dataset: DatasetDefinition, seq_dir: Path):
        """Load cached sequence metadata from seqinfo and gameinfo files.

        Args:
            dataset: Dataset definition.
            seq_dir: Sequence directory path.

        Returns:
            dict: Metadata payload with ``gameinfo`` and ``seqinfo`` sections.
        """
        gameinfo = seq_dir / dataset.gameinfo_filename
        seqinfo = seq_dir / dataset.seqinfo_filename

        gameinfo_mtime = gameinfo.stat().st_mtime if gameinfo.exists() else 0
        seqinfo_mtime = seqinfo.stat().st_mtime if seqinfo.exists() else 0
        cache_key = (str(seq_dir), gameinfo_mtime, seqinfo_mtime)
        if cache_key in self.meta_cache:
            return self.meta_cache[cache_key]

        gameinfo_data = self.read_kv_ini(gameinfo)
        seqinfo_data = self.read_kv_ini(seqinfo)

        gameinfo_keys = ["gameID", "actionPosition", "actionClass", "num_tracklets"]
        seqinfo_keys = ["frameRate", "imWidth", "imHeight", "imExt"]

        payload = {
            "gameinfo": {key: gameinfo_data.get(key, "") for key in gameinfo_keys if key in gameinfo_data},
            "seqinfo": {key: seqinfo_data.get(key, "") for key in seqinfo_keys if key in seqinfo_data},
        }
        self.meta_cache[cache_key] = payload
        return payload

    def frame_info(self, dataset_name: str | None, split: str, seq: str) -> dict:
        """Compute frame count and MOT frame range for a sequence.

        Args:
            dataset_name: Dataset name or ``None``.
            split: Split name.
            seq: Sequence name.

        Returns:
            dict: Frame count and min/max frame information.
        """
        if not seq:
            return {"count": 0}

        _, _, img_dir, files = self.get_files_and_idx(dataset_name, split, seq)
        if not img_dir or not files:
            return {"count": 0}

        frame_numbers = [self.parse_frame_num_from_name(path.name) for path in files]
        frame_numbers = [num for num in frame_numbers if num is not None]
        return {
            "count": len(files),
            "min_frame": int(frame_numbers[0]) if frame_numbers else 1,
            "max_frame": int(frame_numbers[-1]) if frame_numbers else len(files),
        }

    def vis_not1_frames(
        self,
        dataset_name: str | None,
        split: str,
        seq: str,
        annotation_type: str | None = "gt",
        annotation_file: str | None = None,
        eps: float = 1e-6,
    ) -> list[int]:
        """List frames where visibility is present and not equal to 1.

        Args:
            dataset_name: Dataset name or ``None``.
            split: Split name.
            seq: Sequence name.
            annotation_type: Annotation source type, ``"gt"`` or ``"det"``.
            annotation_file: Selected annotation filename.
            eps: Numeric tolerance for equality checks.

        Returns:
            list[int]: Sorted MOT frame IDs.
        """
        if not seq:
            return []

        annotation_path = self.resolve_annotation_path(
            dataset_name, split, seq, annotation_type, annotation_file
        )
        if annotation_path is None:
            return []

        cache_key = (str(annotation_path), annotation_path.stat().st_mtime)
        if cache_key in self.vis_frames_cache:
            return self.vis_frames_cache[cache_key]

        df = self.load_annotations(annotation_path)
        if df is None or "vis" not in df.columns:
            self.vis_frames_cache[cache_key] = []
            return []

        visible = df[df["vis"] >= 0].copy()
        bad = visible[np.abs(visible["vis"] - 1.0) > eps]
        frames = sorted(bad["frame"].unique().astype(int).tolist())
        self.vis_frames_cache[cache_key] = frames
        return frames

    def sequence_meta(self, dataset_name: str | None, split: str, seq: str) -> dict:
        """Return metadata for a single sequence.

        Args:
            dataset_name: Dataset name or ``None``.
            split: Split name.
            seq: Sequence name.

        Returns:
            dict: Metadata payload.
        """
        if not seq:
            return {"gameinfo": {}, "seqinfo": {}}
        dataset, seq_dir = self.get_seq_dir(dataset_name, split, seq)
        return self.load_meta(dataset, seq_dir)

    def sequence_fps(self, dataset_name: str | None, split: str, seq: str) -> float:
        """Return sequence FPS from seqinfo.ini, falling back to 25."""
        meta = self.sequence_meta(dataset_name, split, seq)
        value = (meta.get("seqinfo") or {}).get("frameRate", "")
        try:
            fps = float(value)
        except (TypeError, ValueError):
            fps = 25.0
        return fps if fps > 0 else 25.0

    def configured_annotation_layers(
        self,
        dataset: DatasetDefinition,
        seq_dir: Path,
    ) -> list:
        """Resolve configured layers or derive backward-compatible defaults."""
        if dataset.annotation_layers:
            return [clone_layer(layer) for layer in dataset.annotation_layers]
        det_files = self._list_annotation_dir(seq_dir / "det")
        return default_layers_for_sequence(dataset, seq_dir, self.get_gt_path(dataset, seq_dir), det_files)

    def annotation_payload(self, dataset_name: str | None, split: str, seq: str) -> dict:
        """Load all configured annotation layers once and group boxes by frame."""
        if not seq:
            return {"fps": 25, "first_frame": 1, "frame_count": 0, "layers": [], "frames": {}, "warnings": []}

        dataset, seq_dir, img_dir, files = self.get_files_and_idx(dataset_name, split, seq)
        if not img_dir:
            raise FileNotFoundError("image directory not found")
        frame_numbers = [self.parse_frame_num_from_name(path.name) for path in files]
        frame_numbers = [num for num in frame_numbers if num is not None]
        first_frame = int(frame_numbers[0]) if frame_numbers else 1
        layer_defs = self.configured_annotation_layers(dataset, seq_dir)
        layer_mtimes = []
        for layer in layer_defs:
            try:
                path = resolve_layer_path(seq_dir, layer)
                layer_mtimes.append((str(path), path.stat().st_mtime if path.exists() else 0))
            except FileNotFoundError:
                layer_mtimes.append((layer.path, 0))
        cache_key = (dataset.name, split, seq, len(files), tuple(layer_mtimes))
        if cache_key in self.annotation_payload_cache:
            return self.annotation_payload_cache[cache_key]

        layers = []
        grouped: dict[str, dict[str, list[dict]]] = {}
        warnings: list[str] = []
        for layer in layer_defs:
            layers.append(layer_payload(layer))
            try:
                path = resolve_layer_path(seq_dir, layer)
            except FileNotFoundError as exc:
                warnings.append(str(exc))
                continue
            frames, layer_warnings = parse_annotation_file(path, layer.name)
            warnings.extend(layer_warnings)
            for frame, boxes in frames.items():
                grouped.setdefault(str(frame), {})[layer.name] = boxes

        payload = {
            "fps": self.sequence_fps(dataset_name, split, seq),
            "first_frame": first_frame,
            "frame_count": len(files),
            "layers": layers,
            "frames": grouped,
            "warnings": warnings,
        }
        self.annotation_payload_cache[cache_key] = payload
        return payload

    def render_raw(self, dataset_name: str | None, split: str, seq: str, frame_idx: int, frame_mode: str, frame_value: str):
        """Load one raw image frame from disk.

        Args:
            dataset_name: Dataset name or ``None``.
            split: Split name.
            seq: Sequence name.
            frame_idx: Slider-based frame index.
            frame_mode: ``"idx"`` or ``"mot"``.
            frame_value: Optional direct frame input from the UI.

        Returns:
            numpy.ndarray: OpenCV image array.

        Raises:
            FileNotFoundError: If the image directory or frame files are
                missing.
        """
        _, _, img_dir, files = self.get_files_and_idx(dataset_name, split, seq)
        if not img_dir:
            raise FileNotFoundError("img1 not found")
        if not files:
            raise FileNotFoundError("no images")

        idx = self.resolve_frame_idx(files, frame_idx, frame_mode, frame_value)
        img = cv2.imread(str(files[idx]), cv2.IMREAD_COLOR)
        return img

    def frame_boxes(
        self,
        dataset_name: str | None,
        split: str,
        seq: str,
        frame_idx: int,
        frame_mode: str,
        frame_value: str,
        annotation_type: str | None = "gt",
        annotation_file: str | None = None,
    ) -> dict:
        """Return the boxes attached to one selected frame.

        Args:
            dataset_name: Dataset name or ``None``.
            split: Split name.
            seq: Sequence name.
            frame_idx: Slider-based frame index.
            frame_mode: ``"idx"`` or ``"mot"``.
            frame_value: Optional direct frame input from the UI.
            annotation_type: Annotation source type, ``"gt"`` or ``"det"``.
            annotation_file: Selected annotation filename.

        Returns:
            dict: MOT frame ID and normalized box list.

        Raises:
            FileNotFoundError: If the image directory is missing.
        """
        dataset, seq_dir, img_dir, files = self.get_files_and_idx(dataset_name, split, seq)
        if not img_dir:
            raise FileNotFoundError("img1 not found")
        if not files:
            return {"mot_frame": None, "boxes": []}

        idx = self.resolve_frame_idx(files, frame_idx, frame_mode, frame_value)
        img_path = files[idx]
        mot_frame = self.parse_frame_num_from_name(img_path.name)
        if mot_frame is None:
            mot_frame = idx + 1

        annotation_path = self.resolve_annotation_path(
            dataset_name, split, seq, annotation_type, annotation_file
        )
        df = self.load_annotations(annotation_path)
        if df is None:
            return {"mot_frame": int(mot_frame), "boxes": []}

        rows = df[df["frame"] == int(mot_frame)]
        boxes = []
        for _, row in rows.iterrows():
            x, y, w, h = float(row["x"]), float(row["y"]), float(row["w"]), float(row["h"])
            boxes.append(
                {
                    "id": int(row["id"]),
                    "x1": x,
                    "y1": y,
                    "x2": x + w,
                    "y2": y + h,
                    "vis": float(row.get("vis", -1.0)),
                }
            )
        return {"mot_frame": int(mot_frame), "boxes": boxes}
