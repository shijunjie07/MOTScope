from __future__ import annotations

import json
import time
import tempfile
from pathlib import Path

import cv2
import numpy as np

from mot_viewer import create_app
from mot_viewer.config import AppConfig
from mot_viewer.datasets.registry import DatasetRegistry
from mot_viewer.services.export_manager import apply_layer_overrides, validate_export_request
from mot_viewer.services.viewer import ViewerService


def write_image(path: Path, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = np.zeros((48, 64, 3), dtype=np.uint8)
    image[:, :] = color
    ok = cv2.imwrite(str(path), image)
    assert ok, f"failed to write {path}"


def build_fixture(root: Path) -> Path:
    dataset_root = root / "dataset"
    seq_dir = dataset_root / "train" / "seq001"
    for idx in range(1, 4):
        write_image(seq_dir / "img1" / f"{idx:06d}.jpg", (idx * 30, idx * 20, idx * 10))

    (seq_dir / "gt").mkdir(parents=True, exist_ok=True)
    (seq_dir / "det").mkdir(parents=True, exist_ok=True)
    (seq_dir / "gt" / "gt.txt").write_text(
        "1,7,10,11,20,21,1,1,1,0.5\n"
        "bad,line\n"
        "2,8,12,13,22,23\n",
        encoding="utf-8",
    )
    (seq_dir / "det" / "det.txt").write_text(
        "1,-1,14,15,24,25,0.82\n"
        "3,-1,16,17,26,27,0.25\n",
        encoding="utf-8",
    )
    (seq_dir / "seqinfo.ini").write_text("frameRate=25\nimWidth=64\nimHeight=48\n", encoding="utf-8")

    config_path = root / "datasets.json"
    config_path.write_text(
        json.dumps(
            {
                "datasets": [
                    {
                        "name": "fixture",
                        "root": str(dataset_root),
                        "splits": ["train"],
                        "image_dir": "img1",
                        "gt_files": ["gt.txt"],
                        "annotation_layers": [
                            {
                                "name": "Ground Truth",
                                "type": "gt",
                                "path": "gt/gt.txt",
                                "color": "#00ff00",
                                "visible": True,
                                "draw_id": True,
                                "draw_score": False,
                            },
                            {
                                "name": "Detections",
                                "type": "det",
                                "path": "det/det.txt",
                                "color": "#ff9900",
                                "visible": True,
                                "draw_id": False,
                                "draw_score": True,
                                "score_threshold": 0.5,
                            },
                        ],
                    }
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return config_path


def assert_download(client, url: str, suffix: str) -> None:
    response = client.get(url)
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.data, f"empty download for {suffix}"


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        config_path = build_fixture(root)
        registry = DatasetRegistry(config_path=config_path, default_dataset="fixture")
        viewer = ViewerService(registry)

        class TestConfig(AppConfig):
            DATASETS_CONFIG_PATH = str(config_path)
            DEFAULT_DATASET = "fixture"

        app = create_app(TestConfig)

        assert registry.list_splits("fixture") == ["train"]
        dataset = registry.get("fixture")
        assert len(dataset.annotation_layers) == 2

        payload = viewer.annotation_payload("fixture", "train", "seq001")
        assert payload["fps"] == 25
        assert payload["first_frame"] == 1
        assert payload["frame_count"] == 3
        assert [layer["name"] for layer in payload["layers"]] == ["Ground Truth", "Detections"]
        assert payload["frames"]["1"]["Ground Truth"][0]["id"] == 7
        assert payload["frames"]["1"]["Detections"][0]["score"] == 0.82
        assert payload["warnings"], "bad annotation line should be reported"

        assert validate_export_request("frame", "png") == "png"
        assert validate_export_request("frame", "svg") == "svg"
        assert validate_export_request("images", "jpg") == "jpg"
        assert validate_export_request("video", "mp4") == "mp4"
        overridden = apply_layer_overrides(
            {"layers": [{"name": "Detections", "color": "#ff9900", "score_threshold": 0.0}]},
            {"layer_overrides": {"Detections": {"color": "#3b82f6", "score_threshold": 0.75}}},
        )
        assert overridden["layers"][0]["color"] == "#3b82f6"
        assert overridden["layers"][0]["score_threshold"] == 0.75
        for target, fmt in [("frame", "mp4"), ("video", "svg"), ("images", "mp4")]:
            try:
                validate_export_request(target, fmt)
            except ValueError:
                pass
            else:
                raise AssertionError(f"{target}/{fmt} should be invalid")

        client = app.test_client()
        page = client.get("/")
        assert page.status_code == 200, page.get_data(as_text=True)
        html = page.get_data(as_text=True)
        assert "MOTScope" in html
        assert "/static/assets/motscope_logo_square.png" in html
        assert 'id="fileMenuBtn"' in html
        assert 'id="themeToggleBtn"' in html
        assert 'id="layerControls"' in html
        assert "Download again" in Path("static/app.js").read_text(encoding="utf-8")
        assert Path("docs/assets/motscope_logo_rect.png").exists()
        assert 'data-canvas-bg="white-grid"' in html
        assert 'id="canvasBackgroundSelect"' in html
        assert 'id="canvasBgMenu"' in html

        css = Path("static/style.css").read_text(encoding="utf-8")
        for mode in ["white-grid", "black-grid", "plain-white", "plain-black"]:
            assert f'[data-canvas-bg="{mode}"]' in css

        js = Path("static/app.js").read_text(encoding="utf-8")
        assert 'localStorage.setItem("motScopeCanvasBackground"' in js
        assert "const MIN_ZOOM = 0.1" in js
        assert "const MAX_ZOOM = 8.0" in js
        assert "const ZOOM_STEP = 1.15" in js

        response = client.get("/api/annotations?dataset=fixture&split=train&seq=seq001")
        assert response.status_code == 200, response.get_data(as_text=True)
        assert response.get_json()["frames"]["1"]["Ground Truth"]

        response = client.get("/api/video/fixture/train/seq001")
        assert response.status_code == 200, response.get_data(as_text=True)
        video_payload = response.get_json()
        assert "available" in video_payload
        assert video_payload["available"] is True
        assert video_payload["frame_count"] == 3
        assert video_payload["expected_duration"] == 3 / 25
        assert video_payload["duration"] >= 0.08
        assert "signature" in video_payload

        response = client.post(
            "/api/video/render",
            json={"dataset": "fixture", "split": "train", "sequence": "seq001"},
        )
        assert response.status_code == 202, response.get_data(as_text=True)
        job_id = response.get_json()["job_id"]
        video_job = wait_for_job(client, job_id)
        assert video_job["status"] == "done", video_job
        assert video_job["progress"] == 100
        assert video_job["result"]["frame_count"] == 3

        for fmt in ["jpg", "jpeg", "png", "svg"]:
            response = client.post(
                "/api/export/frame",
                json={
                    "dataset": "fixture",
                    "split": "train",
                    "sequence": "seq001",
                    "frame": 1,
                    "include_annotations": True,
                    "annotation_mode": "custom",
                    "selected_layers": ["Ground Truth", "Detections"],
                    "format": fmt,
                },
            )
            assert response.status_code == 200, response.get_data(as_text=True)
            assert_download(client, response.get_json()["download_url"], fmt)

        for fmt in ["jpg", "png", "svg"]:
            response = client.post(
                "/api/export/sequence/images",
                json={
                    "dataset": "fixture",
                    "split": "train",
                    "sequence": "seq001",
                    "include_annotations": True,
                    "annotation_mode": "custom",
                    "selected_layers": ["Ground Truth"],
                    "format": fmt,
                },
            )
            assert response.status_code == 200, response.get_data(as_text=True)
            assert_download(client, response.get_json()["download_url"], fmt)

        response = client.post(
            "/api/export/sequence/video",
            json={
                "dataset": "fixture",
                "split": "train",
                "sequence": "seq001",
                "include_annotations": False,
                "annotation_mode": "none",
                "selected_layers": [],
                "format": "mp4",
            },
        )
        assert response.status_code == 200, response.get_data(as_text=True)
        assert_download(client, response.get_json()["download_url"], "mp4")

        response = client.post(
            "/api/export/start",
            json={
                "target": "video",
                "dataset": "fixture",
                "split": "train",
                "sequence": "seq001",
                "include_annotations": True,
                "annotation_mode": "custom",
                "selected_layers": ["Ground Truth", "Detections"],
                "format": "mp4",
            },
        )
        assert response.status_code == 202, response.get_data(as_text=True)
        export_job = wait_for_job(client, response.get_json()["job_id"])
        assert export_job["status"] == "done", export_job
        assert export_job["progress"] == 100
        assert_download(client, export_job["result"]["download_url"], "mp4")

        invalid = client.post(
            "/api/export/frame",
            json={
                "dataset": "fixture",
                "split": "train",
                "sequence": "seq001",
                "frame": 1,
                "format": "mp4",
            },
        )
        assert invalid.status_code == 400

    create_app()
    print("smoke_check passed")


def wait_for_job(client, job_id: str) -> dict:
    for _ in range(120):
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200, response.get_data(as_text=True)
        payload = response.get_json()
        if payload["status"] in {"done", "failed"}:
            return payload
        time.sleep(0.05)
    raise AssertionError(f"job did not finish: {job_id}")


if __name__ == "__main__":
    main()
