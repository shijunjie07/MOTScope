# --------------------
# Dataset registry for built-in and user-defined datasets.
# @author: SHI JUNJIE
# 2026-04-25
# --------------------

import json
import re
from pathlib import Path

from .models import AnnotationLayer, DatasetDefinition


def _default_builtin_datasets() -> dict[str, DatasetDefinition]:
    """Build the built-in dataset definitions.

    Returns:
        dict[str, DatasetDefinition]: Built-in dataset registry entries.
    """
    return {
        "soccernet": DatasetDefinition(
            name="soccernet",
            root=Path(r"/mnt/f/soccer_tracking/sports_datasets/tracking-2023").resolve(),
            splits=["train", "test"],
            source="builtin",
        ),
        "dancetrack": DatasetDefinition(
            name="dancetrack",
            root=Path(r"/mnt/f/dancetrack").resolve(),
            splits=["train1", "train2", "val", "test1", "test2"],
            source="builtin",
        ),
    }


class DatasetRegistry:
    """Manage built-in and user-defined dataset definitions."""

    def _ensure_config_file(self) -> None:
        """Create an empty dataset config file if it does not exist.

        This makes the instance folder a user-editable place for custom
        dataset definitions instead of a hidden implementation detail.
        """
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.config_path.exists():
            self.config_path.write_text('{\n  "datasets": []\n}\n', encoding='utf-8')

    def __init__(self, config_path: Path, default_dataset: str):
        """Initialize the registry and load persisted custom datasets.

        Args:
            config_path: Path to the JSON file storing custom datasets.
            default_dataset: Preferred fallback dataset name.
        """
        self.config_path = config_path
        self.default_dataset = default_dataset
        self._builtin = _default_builtin_datasets()
        self._ensure_config_file()
        self._custom = self._load_custom_datasets()

    def _load_custom_datasets(self) -> dict[str, DatasetDefinition]:
        """Load custom datasets from disk.

        Returns:
            dict[str, DatasetDefinition]: Custom dataset definitions.
        """
        if not self.config_path.exists():
            return {}

        payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        datasets = {}
        for item in payload.get("datasets", []):
            dataset = self._from_payload(item, source="custom")
            datasets[dataset.name] = dataset
        return datasets

    def _write_custom_datasets(self) -> None:
        """Persist custom datasets to the registry JSON file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "datasets": [
                dataset.to_dict()
                for dataset in sorted(self._custom.values(), key=lambda item: item.name)
            ]
        }
        self.config_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _from_payload(self, payload: dict, source: str) -> DatasetDefinition:
        """Normalize a raw payload into a dataset definition.

        Args:
            payload: Raw dataset configuration dictionary.
            source: Dataset origin label such as ``"builtin"`` or
                ``"custom"``.

        Returns:
            DatasetDefinition: The parsed dataset definition.
        """
        gt_files = self._normalize_list(payload.get("gt_files", ["gt_vis.txt", "gt.txt"]))
        if not gt_files:
            gt_files = ["gt_vis.txt", "gt.txt"]
        return DatasetDefinition(
            name=self._validate_name(payload["name"]),
            root=Path(payload["root"]).expanduser().resolve(),
            splits=self._normalize_list(payload.get("splits", [])),
            image_dir=(payload.get("image_dir") or "img1").strip(),
            gt_files=gt_files,
            seqinfo_filename=(payload.get("seqinfo_filename") or "seqinfo.ini").strip(),
            gameinfo_filename=(payload.get("gameinfo_filename") or "gameinfo.ini").strip(),
            annotation_layers=self._normalize_annotation_layers(payload.get("annotation_layers", [])),
            source=source,
        )

    def _normalize_annotation_layers(self, value) -> list[AnnotationLayer]:
        """Normalize optional multi-layer annotation configuration.

        Args:
            value: Raw ``annotation_layers`` list from JSON.

        Returns:
            list[AnnotationLayer]: Valid layer definitions. Empty means the
            viewer should derive backward-compatible defaults from ``gt_files``.
        """
        if not isinstance(value, list):
            return []

        layers: list[AnnotationLayer] = []
        used_names: set[str] = set()
        for idx, item in enumerate(value, start=1):
            if not isinstance(item, dict):
                continue
            layer_type = str(item.get("type") or "gt").strip().lower()
            if layer_type not in {"gt", "det", "tracker", "result", "custom"}:
                layer_type = "custom"
            name = str(item.get("name") or f"Layer {idx}").strip()
            if not name:
                name = f"Layer {idx}"
            original = name
            suffix = 2
            while name in used_names:
                name = f"{original} {suffix}"
                suffix += 1
            used_names.add(name)

            raw_threshold = item.get("score_threshold", 0.0)
            try:
                score_threshold = float(raw_threshold)
            except (TypeError, ValueError):
                score_threshold = 0.0

            layers.append(
                AnnotationLayer(
                    name=name,
                    type=layer_type,
                    path=str(item.get("path") or "").strip(),
                    color=self._normalize_color(item.get("color"), idx),
                    visible=bool(item.get("visible", True)),
                    draw_id=bool(item.get("draw_id", layer_type != "det")),
                    draw_score=bool(item.get("draw_score", layer_type == "det")),
                    score_threshold=score_threshold,
                )
            )
        return layers

    def _normalize_color(self, value, idx: int) -> str:
        """Return a usable CSS hex color for a layer."""
        text = str(value or "").strip()
        if re.fullmatch(r"#[0-9a-fA-F]{6}", text):
            return text
        defaults = ["#00ff00", "#ff9900", "#35e6fd", "#ff4d4d", "#d8b4fe"]
        return defaults[(idx - 1) % len(defaults)]

    def _validate_name(self, value: str) -> str:
        """Validate and normalize a dataset name.

        Args:
            value: Raw dataset name string.

        Returns:
            str: The normalized dataset name.

        Raises:
            ValueError: If the name is empty or contains invalid characters.
        """
        name = (value or "").strip().lower()
        if not name:
            raise ValueError("Dataset name is required.")
        if not re.fullmatch(r"[a-z0-9_-]+", name):
            raise ValueError("Dataset name must use only letters, numbers, hyphen, or underscore.")
        return name

    def _normalize_list(self, value) -> list[str]:
        """Convert a CSV string or iterable into a cleaned list of strings.

        Args:
            value: String, iterable, or empty value.

        Returns:
            list[str]: Cleaned string items.
        """
        if isinstance(value, str):
            items = value.split(",")
        else:
            items = value or []
        out = []
        for item in items:
            text = str(item).strip()
            if text:
                out.append(text)
        return out

    def _all(self) -> dict[str, DatasetDefinition]:
        """Merge built-in and custom datasets into one mapping.

        Returns:
            dict[str, DatasetDefinition]: Combined dataset definitions.
        """
        merged = dict(self._builtin)
        merged.update(self._custom)
        return merged

    def resolve_name(self, name: str | None) -> str:
        """Resolve a requested dataset name to a valid registry key.

        Args:
            name: Requested dataset name or ``None``.

        Returns:
            str: The dataset name that should be used.
        """
        key = (name or self.default_dataset).strip().lower()
        if key in self._all():
            return key
        return self.default_dataset if self.default_dataset in self._all() else next(iter(self._all()))

    def get(self, name: str | None) -> DatasetDefinition:
        """Fetch a dataset definition by name.

        Args:
            name: Requested dataset name or ``None``.

        Returns:
            DatasetDefinition: The resolved dataset definition.
        """
        return self._all()[self.resolve_name(name)]

    def list_splits(self, name: str | None) -> list[str]:
        """List available splits for a dataset.

        Args:
            name: Requested dataset name or ``None``.

        Returns:
            list[str]: Existing split names on disk.
        """
        dataset = self.get(name)
        candidates = dataset.splits or self._discover_splits(dataset)
        return [split for split in candidates if (dataset.root / split).exists()]

    def list_datasets(self) -> list[dict]:
        """List all datasets as JSON-ready payloads.

        Returns:
            list[dict]: Dataset payloads for the frontend.
        """
        items = []
        for dataset in sorted(self._all().values(), key=lambda item: item.name):
            items.append(dataset.to_dict(resolved_splits=self.list_splits(dataset.name)))
        return items

    def add_dataset(self, payload: dict) -> DatasetDefinition:
        """Register and persist a custom dataset.

        Args:
            payload: Raw dataset configuration from the client.

        Returns:
            DatasetDefinition: The saved custom dataset definition.

        Raises:
            ValueError: If the payload is invalid or the dataset cannot be
                registered.
        """
        dataset = self._from_payload(payload, source="custom")
        if dataset.name in self._builtin:
            raise ValueError(f"Dataset name is reserved: {dataset.name}")
        if not dataset.root.exists():
            raise ValueError(f"Dataset root does not exist: {dataset.root}")

        if not dataset.splits:
            dataset.splits = self._discover_splits(dataset)
        if not dataset.splits:
            raise ValueError("Could not detect dataset splits. Please provide them explicitly.")

        self._custom[dataset.name] = dataset
        self._write_custom_datasets()
        return dataset

    def _discover_splits(self, dataset: DatasetDefinition) -> list[str]:
        """Infer split names from a dataset root directory.

        Args:
            dataset: Dataset definition whose root should be scanned.

        Returns:
            list[str]: Detected split names.
        """
        if not dataset.root.exists():
            return []

        splits = []
        for child in sorted(dataset.root.iterdir(), key=lambda path: path.name.lower()):
            if not child.is_dir():
                continue
            if any(grandchild.is_dir() for grandchild in child.iterdir()):
                splits.append(child.name)
        return splits
