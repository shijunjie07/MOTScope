from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

import cv2


class VideoCache:
    """Generate and reuse MP4 proxies for smooth playback."""

    def __init__(self, viewer, cache_dir: Path):
        self.viewer = viewer
        self.cache_dir = cache_dir

    def ensure_video(
        self,
        dataset_name: str | None,
        split: str,
        seq: str,
        progress: Callable[[int, str], None] | None = None,
    ) -> dict:
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
        signature = self._signature(dataset_name, split, seq, files, fps)
        filename = f"{safe_name(dataset_name)}_{safe_name(split)}_{safe_name(seq)}_{signature}.mp4"
        out_path = self.cache_dir / filename
        expected_duration = len(files) / fps
        if out_path.exists() and self._duration_is_valid(out_path, expected_duration):
            if progress:
                progress(100, "Using cached video")
            return self._payload(out_path, fps, info, signature, expected_duration)

        try:
            self._generate(ffmpeg, files, fps, out_path, progress)
        except Exception as exc:
            return {"available": False, "error": f"ffmpeg not found or video generation failed: {exc}"}
        if not self._duration_is_valid(out_path, expected_duration):
            actual = self.probe_duration(out_path)
            return {
                "available": False,
                "error": f"generated video duration mismatch: expected {expected_duration:.2f}s, got {actual:.2f}s",
            }
        return self._payload(out_path, fps, info, signature, expected_duration)

    def _payload(self, out_path: Path, fps: float, info: dict, signature: str, expected_duration: float) -> dict:
        duration = self.probe_duration(out_path)
        return {
            "available": True,
            "video_url": f"/video_cache/{out_path.name}?v={signature}",
            "path": out_path,
            "fps": fps,
            "first_frame": int(info.get("min_frame") or 1),
            "frame_count": int(info.get("count") or 0),
            "last_frame": int(info.get("max_frame") or info.get("count") or 0),
            "duration": duration,
            "expected_duration": expected_duration,
            "signature": signature,
        }

    def _generate(
        self,
        ffmpeg: str,
        files: list[Path],
        fps: float,
        out_path: Path,
        progress: Callable[[int, str], None] | None = None,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            total = len(files)
            for idx, frame_path in enumerate(files, start=1):
                image = cv2.imread(str(frame_path), cv2.IMREAD_COLOR)
                if image is None:
                    raise FileNotFoundError(f"Failed to read image: {frame_path}")
                ok = cv2.imwrite(str(tmp_dir / f"{idx:06d}.jpg"), image)
                if not ok:
                    raise RuntimeError(f"Failed to prepare frame for video: {frame_path}")
                if progress and (idx == 1 or idx == total or idx % 25 == 0):
                    percent = max(1, min(85, int((idx / total) * 85)))
                    progress(percent, f"Preparing frame {idx} / {total}")
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
                raise RuntimeError(result.stderr.strip() or "ffmpeg failed")
            if progress:
                progress(100, "Video ready")

    def _signature(self, dataset_name: str | None, split: str, seq: str, files: list[Path], fps: float) -> str:
        first = files[0]
        last = files[-1]
        data = "|".join(
            [
                str(dataset_name or ""),
                split,
                seq,
                str(first.parent.resolve()),
                str(len(files)),
                f"{fps:.6f}",
                first.name,
                last.name,
                str(first.stat().st_mtime_ns),
                str(last.stat().st_mtime_ns),
            ]
        )
        return hashlib.sha1(data.encode("utf-8")).hexdigest()[:12]

    def _duration_is_valid(self, path: Path, expected_duration: float) -> bool:
        duration = self.probe_duration(path)
        if duration <= 0:
            return False
        tolerance = max(0.5, expected_duration * 0.02)
        return abs(duration - expected_duration) <= tolerance

    def probe_duration(self, path: Path) -> float:
        ffprobe = shutil.which("ffprobe")
        if not ffprobe or not path.exists():
            return 0.0
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=nw=1:nk=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return 0.0
        try:
            return float(result.stdout.strip())
        except ValueError:
            return 0.0


def safe_name(value) -> str:
    text = str(value or "default")
    out = [char if char.isalnum() or char in {"-", "_"} else "_" for char in text]
    return "".join(out).strip("_") or "default"
