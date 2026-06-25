# --------------------
# Dataset data models used by the viewer.
# @author: SHI JUNJIE
# 2026-04-25
# --------------------

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class AnnotationLayer:
    """Configurable MOT annotation source shown as one visual layer."""
    name: str
    type: str = "gt"
    path: str = ""
    color: str = "#35e6fd"
    visible: bool = True
    draw_id: bool = True
    draw_score: bool = False
    score_threshold: float = 0.0

    def to_dict(self) -> dict:
        """Convert the layer into a JSON-ready dictionary."""
        return {
            "name": self.name,
            "type": self.type,
            "path": self.path,
            "color": self.color,
            "visible": self.visible,
            "draw_id": self.draw_id,
            "draw_score": self.draw_score,
            "score_threshold": self.score_threshold,
        }


@dataclass(slots=True)
class DatasetDefinition:
    """Store normalized dataset settings for the viewer."""
    name: str
    root: Path
    splits: list[str] = field(default_factory=list)
    image_dir: str = "img1"
    gt_files: list[str] = field(default_factory=lambda: ["gt_vis.txt", "gt.txt"])
    seqinfo_filename: str = "seqinfo.ini"
    gameinfo_filename: str = "gameinfo.ini"
    annotation_layers: list[AnnotationLayer] = field(default_factory=list)
    source: str = "custom"

    def to_dict(self, resolved_splits: list[str] | None = None) -> dict:
        """Convert the dataset definition into a JSON-ready dictionary.

        Args:
            resolved_splits: Optional split list to expose instead of stored
                splits.

        Returns:
            dict: A serializable dataset payload.
        """
        return {
            "name": self.name,
            "root": str(self.root),
            "splits": resolved_splits if resolved_splits is not None else list(self.splits),
            "image_dir": self.image_dir,
            "gt_files": list(self.gt_files),
            "seqinfo_filename": self.seqinfo_filename,
            "gameinfo_filename": self.gameinfo_filename,
            "annotation_layers": [layer.to_dict() for layer in self.annotation_layers],
            "source": self.source,
        }
