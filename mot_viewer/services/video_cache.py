from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import cv2


class VideoCache:
    """Generate and reuse MP4 proxies for smooth playback."""

    def __init__(self, viewer, cache_dir: Path):
        self.viewer = viewer
        self.cache_dir = cache_dir

    def ensure_video(self, dataset_name: str | None, split: str, seq: str) -> dict:
        """Return a cached MP4 proxy, generating it with ffmpeg if needed."""
        try:
            files = self.viewer.sequence_frame_files(dataset_name, split, seq)
            info = self.viewer.frame_info(dataset_name, split, seq)
            fps = self.viewer.sequence_fps(dataset_name, split, seq)
        except Exception as exc:
            return {"available": False, "error": str(exc)}

        if not files:
            return {"available": False, "error": "no image frames found"}
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            return {"available": False, "error": "ffmpeg not found"}

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{safe_name(dataset_name)}_{safe_name(split)}_{safe_name(seq)}.mp4"
        out_path = self.cache_dir / filename
        newest_frame = max(path.stat().st_mtime for path in files)
        if out_path.exists() and out_path.stat().st_mtime >= newest_frame:
            return self._payload(out_path, fps, info)

        try:
            self._generate(ffmpeg, files, fps, out_path)
        except Exception as exc:
            return {"available": False, "error": f"ffmpeg not found or video generation failed: {exc}"}
        return self._payload(out_path, fps, info)

    def _payload(self, out_path: Path, fps: float, info: dict) -> dict:
        return {
            "available": True,
            "video_url": f"/video_cache/{out_path.name}",
            "path": out_path,
            "fps": fps,
            "first_frame": int(info.get("min_frame") or 1),
            "frame_count": int(info.get("count") or 0),
        }

    def _generate(self, ffmpeg: str, files: list[Path], fps: float, out_path: Path) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            for idx, frame_path in enumerate(files, start=1):
                image = cv2.imread(str(frame_path), cv2.IMREAD_COLOR)
                if image is None:
                    raise FileNotFoundError(f"Failed to read image: {frame_path}")
                ok = cv2.imwrite(str(tmp_dir / f"{idx:06d}.jpg"), image)
                if not ok:
                    raise RuntimeError(f"Failed to prepare frame for video: {frame_path}")
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
                raise RuntimeError(result.stderr.strip() or "ffmpeg failed")


def safe_name(value) -> str:
    text = str(value or "default")
    out = [char if char.isalnum() or char in {"-", "_"} else "_" for char in text]
    return "".join(out).strip("_") or "default"
