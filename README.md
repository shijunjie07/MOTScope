# MOT Viewer

A lightweight Flask-based viewer for inspecting Multi-Object Tracking (MOT) datasets.

![MOT Viewer demo](docs/assets/mot_viewer.png)



## Table of Contents

- [Overview](#overview)
- [Installation](#installation)
- [Usage](#run)
- [Dataset Setup](#dataset-configuration)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)



## Overview

MOT Viewer provides a simple browser interface for inspecting tracking datasets without writing custom visualization scripts. It is designed for quick validation of dataset structure, annotation quality, and sequence-level consistency.

The viewer supports common MOT-style datasets such as SoccerNet-Tracking and DanceTrack, and can be easily extended to custom datasets through a configuration file or the web interface.



## Features

- Browse MOT image sequences frame by frame  
- Visualize multiple annotation layers with independent colors
- Show GT, detections, tracker results, or custom MOT-style files together
- Toggle layers, IDs, scores, and score thresholds in the browser
- Use smooth video playback through a cached MP4 with canvas overlays
- Export frames, image-sequence ZIPs, and MP4 videos
- Switch between multiple datasets in the browser  
- Register new datasets without modifying source code  
- Configure dataset-specific layouts (splits, folders, filenames)  
- Store local dataset configurations separately via `instance/`  



## Supported Datasets

| Dataset | Description | URL |
| --- | --- | --- |
| SoccerNet-Tracking | Soccer broadcast video dataset for multi-object tracking (SoccerNet challenge) | https://github.com/SoccerNet/sn-tracking |
| DanceTrack | Multi-human tracking dataset with similar appearance and complex motion | https://dancetrack.github.io/ |

Other MOT-style datasets can be added as long as their structure and annotations are compatible.



## Installation

### 1. Clone the repository

```bash
git clone https://github.com/shijunjie07/mot-viewer.git
cd mot-viewer
````

### 2. Create environment

```bash
conda create -n motviewer python=3.11 -y
conda activate motviewer
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```



## Run

```bash
python app.py
```

Open in browser:

```
http://127.0.0.1:5000
```



## Dataset Configuration

By default, dataset definitions are stored in:

```
instance/datasets.json
```

This file is used for **local configuration only**.

To override the path:

```bash
export MOT_VIEWER_DATASETS_CONFIG=/path/to/datasets.json
```



## Adding Custom Datasets

### Option 1: Web UI

Use the **Add Dataset** button in the viewer and provide:

* Dataset root path
* Available splits
* Optional folder / filename settings

### Option 2: JSON Configuration

Edit `instance/datasets.json` manually:

```json
{
  "datasets": [
    {
      "name": "my_dataset",
      "root": "/path/to/my_dataset",
      "splits": ["train", "val", "test"],
      "image_dir": "img1",
      "gt_files": ["gt.txt"],
      "seqinfo_filename": "seqinfo.ini",
      "gameinfo_filename": "gameinfo.ini"
    }
  ]
}
```

Datasets are loaded at startup, and changes from the UI are written back to this file.


## Multiple Annotation Layers

Existing configs that only define `gt_files` still work. To show GT and detections together, add `annotation_layers` to a dataset entry:

```json
{
  "name": "sportsmot",
  "root": "/path/to/SportsMOT/dataset",
  "splits": ["train", "val", "test"],
  "image_dir": "img1",
  "gt_files": ["gt.txt"],
  "annotation_layers": [
    {
      "name": "Ground Truth",
      "type": "gt",
      "path": "gt/gt.txt",
      "color": "#00ff00",
      "visible": true,
      "draw_id": true,
      "draw_score": false
    },
    {
      "name": "Detections",
      "type": "det",
      "path": "det/det.txt",
      "color": "#ff9900",
      "visible": true,
      "draw_id": false,
      "draw_score": true,
      "score_threshold": 0.0
    }
  ]
}
```

Layer paths are relative to each sequence folder, such as `<dataset-root>/<split>/<sequence>/gt/gt.txt`. If `annotation_layers` is omitted, the viewer derives a Ground Truth layer from `gt_files` and, when present, a Detections layer from `det/det.txt`.


## Smooth Video Playback

The viewer has two playback modes:

* **Frame Inspection Mode** keeps precise image-by-image navigation, stepping, zoom, hover, and locked-box inspection.
* **Smooth Video Mode** generates a cached MP4 under `instance/video_cache/`, plays it in a `<video>` element, and draws selected annotation layers on a canvas overlay.

Smooth playback requires `ffmpeg` on the system path. If `ffmpeg` is missing or video generation fails, the API returns a clear error and frame inspection remains usable.


## Exporting

Use the Export panel to choose a target, annotation mode, selected layers, and format. Generated files are written under `instance/exports/` and returned as browser download links.

Supported formats:

| Export Target | Formats |
| --- | --- |
| Current Frame | `jpg`, `jpeg`, `png`, `svg` |
| Whole Sequence as Images ZIP | `jpg`, `jpeg`, `png`, `svg` |
| Whole Sequence as Video | `mp4` |

SVG exports embed the original frame image and draw boxes/text as real SVG elements.



## Expected Dataset Structure

Default MOT-style layout:

```
<dataset-root>/
  <split>/
    <sequence>/
      img1/
        000001.jpg
        000002.jpg
        ...
      gt/
        gt.txt
      seqinfo.ini       # optional
      gameinfo.ini      # optional
```

### Notes

* `img1/` is the default image directory
* `gt/` contains annotation files
* `seqinfo.ini` and `gameinfo.ini` are optional
* Ground-truth defaults to `gt.txt`
* Custom layouts can be configured during dataset registration



## Annotation Format

Expected format follows MOTChallenge style:

```
frame,id,x,y,w,h,confidence,class,unused
```

Key fields used by the viewer:

| Field      | Description    |
| ---------- | -------------- |
| frame      | Frame index    |
| id         | Track identity |
| x, y, w, h | Bounding box   |


## Use Cases

* Validate tracking annotations before training
* Check alignment between frames and labels
* Compare annotation quality across datasets
* Debug dataset conversion pipelines



## Roadmap

Planned improvements:

* [ ] Add support for more MOT datasets (e.g. MOT17, SportsMOT)
* [ ] Improve UI for sequence navigation and playback
* [ ] Add video export (annotated sequences)
* [ ] Support additional annotation formats (e.g. COCO-style tracking)


## Contributing

Contributions are welcome.

1. Fork the repository
2. Create a new branch (`feature/your-feature-name`)
3. Make your changes
4. Commit with clear messages
5. Open a Pull Request

For major changes, please open an issue first to discuss your ideas.



## Ideas & Feature Requests

Feel free to open an issue for:

* New dataset support
* UI/UX improvements
* Visualization features
* Workflow integrations



## Repository Notes

* `instance/` is for local configuration and should not be committed
* Documentation assets should be placed in `docs/assets/`



## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
