<p align="center">
  <img src="docs/assets/motscope_logo_rect.png" alt="MOTScope logo" width="720">
</p>

# MOTScope

A lightweight visual inspection tool for multi-object tracking datasets, detections, and tracker outputs.

![MOTScope demo](docs/assets/mot_viewer.png)



## Table of Contents

- [Overview](#overview)
- [Installation](#installation)
- [Usage](#run)
- [Dataset Setup](#dataset-configuration)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)



## Overview

MOTScope provides a simple browser interface for inspecting tracking datasets without writing custom visualization scripts. It is designed for quick validation of dataset structure, annotation quality, and sequence-level consistency.

The viewer supports common MOT-style datasets such as SoccerNet-Tracking and DanceTrack, and can be easily extended to custom datasets through a configuration file or the web interface.



## Features

- Browse MOT image sequences frame by frame  
- Visualize multiple annotation layers with independent colors
- Show GT, detections, tracker results, or custom MOT-style files together
- Toggle layers, IDs, scores, and score thresholds in the browser
- Use smooth video playback through a cached MP4 with canvas overlays
- Export frames, image-sequence ZIPs, and MP4 videos
- Use a light default theme with a persistent dark mode option
- Trigger export downloads automatically, with a `Download again` fallback link
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

Use **File -> Add Dataset...**. The dataset form opens as a modal dialog instead of occupying the navigation sidebar. Provide:

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


## Application Layout

MOTScope uses a draw.io-style application layout:

* top menu bar for high-level commands
* File menu for Add Dataset, Export, config location, and refresh
* compact top toolbar for playback mode, previous/play/stop/next, speed, theme toggle, and refresh
* left sidebar for dataset navigation, Layers, Annotation Source, Display, and review jumps
* central viewer workspace for frame canvas or smooth video playback
* floating viewer controls for fit, zoom, pan, and rectangle zoom
* right inspector reserved for selected box details and sequence metadata
* modal dialogs for Add Dataset, Export, and long-running progress states

The app opens in light mode by default. Use **View -> Theme: Dark** or the toolbar theme button to switch modes. The selected theme is stored in local browser storage.


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

Layer cards live in the left sidebar. Each card has a header with the layer color, name, type badge, and color swatch; a master **Show this layer** switch; display options for bounding boxes, IDs, and scores; and a per-layer score threshold.

Click a layer swatch to edit color. The color picker previews immediately, stays open while you choose a color, supports manual hex values such as `#00ff00`, and offers Apply, Cancel, and Reset default actions.


## Smooth Video Playback

The viewer has two playback modes:

* **Frame Inspection Mode** keeps precise image-by-image navigation, stepping, zoom, hover, and locked-box inspection.
* **Smooth Video Mode** generates a cached MP4 under `instance/video_cache/`, plays it in a `<video>` element, and draws selected annotation layers on a canvas overlay.

Smooth playback requires `ffmpeg` on the system path. If `ffmpeg` is missing or video generation fails, the API returns a clear error and frame inspection remains usable.

Smooth videos are cached under `instance/video_cache/` with a sequence signature based on dataset, split, sequence, image directory, frame count, FPS, and first/last frame names. The viewer checks cached MP4 duration with `ffprobe`; stale or too-short cache files are regenerated.

The V3 UI keeps the V2 full-duration smooth-video fix and only changes the surrounding controls/progress behavior.

## Viewer Shortcuts

| Shortcut | Action |
| --- | --- |
| Ctrl + mouse wheel | Zoom around cursor |
| Ctrl + + | Zoom in |
| Ctrl + - | Zoom out |
| Ctrl + 0 | Fit/reset view |
| Shift + left drag | Pan/drag image |


## Exporting

Use **File -> Export...**. The export workflow opens as a modal dialog where you choose a target, annotation mode, selected layers, and format. Generated files are written under `instance/exports/`, the browser download starts automatically after completion, and a `Download again` link remains available if the browser blocks the automatic download.

Smooth video generation and exports run through background jobs. The browser shows a progress modal with percentage and messages such as `Preparing frame 315 / 750`, `Rendering frame 450 / 750`, or `Encoding MP4`.

Supported formats:

| Export Target | Formats |
| --- | --- |
| Current Frame | `jpg`, `jpeg`, `png`, `svg` |
| Whole Sequence as Images ZIP | `jpg`, `jpeg`, `png`, `svg` |
| Whole Sequence as Video | `mp4` |

SVG exports embed the original frame image and draw boxes/text as real SVG elements.


## Troubleshooting

### Smooth video only plays briefly

If smooth video only plays for a couple of seconds:

1. Delete the relevant file under `instance/video_cache/`.
2. Regenerate smooth video from the viewer.
3. Check duration with:

```bash
ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 instance/video_cache/<video>.mp4
```

4. Confirm expected duration is `frame_count / fps`.
5. Confirm `seqinfo.ini` has the intended `frameRate`.

The V2 cache uses a signature and duration validation to avoid reusing stale short videos.

### GT and detections do not appear together

Confirm both layers are present in `annotation_layers` or that the sequence contains both `gt/gt.txt` and `det/det.txt`. In the left sidebar, layer visibility uses independent **Show this layer** switches, so multiple layers can stay enabled at the same time.



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
