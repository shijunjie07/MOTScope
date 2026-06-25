# PLAN_MOT_VIEWER_UPGRADE.md

# MOT Viewer Upgrade Plan

## Goal

Upgrade the MOT Viewer located at:

```bash
/home/junja/mot_viewer
```

inside WSL.

The upgraded viewer should support:

1. Displaying multiple MOT-style annotation files at the same time.
2. Showing `gt/gt.txt`, `det/det.txt`, tracker results, or other MOT-style files together with different colors.
3. Smooth video-style playback instead of laggy image-by-image playback.
4. Exporting/downloading:

   * current frame
   * whole sequence as image ZIP
   * whole sequence as video
5. Exporting with or without selected annotations.
6. User-selectable export formats:

   * image/frame formats: `jpg`, `jpeg`, `png`, `svg`
   * video format: `mp4`
7. Creating and using a new conda environment named:

```bash
motviewer
```

8. Implementing the changes on a new Git branch.
9. Committing and pushing the branch to GitHub.
10. Do not merge the branch into `master` or `main`.

---

# Phase 0 — Repository Inspection First

## Objective

Before editing anything, the Codex agent must inspect the entire repository and understand the current structure.

## Required actions

Go to the repo:

```bash
cd /home/junja/mot_viewer
```

Inspect:

```bash
pwd
ls -la
find . -maxdepth 3 -type f | sort
git status
git branch --show-current
```

Read important files if they exist:

```bash
README.md
requirements.txt
environment.yml
pyproject.toml
app.py
config files
templates
static JS/CSS files
instance/datasets.json
```

The agent should identify:

* current Flask app entrypoint
* current dataset config format
* current annotation loading logic
* current frame/image loading logic
* current frontend rendering logic
* current playback implementation
* current static/template structure
* current dependency management
* current Git remote

## Output before coding

After inspection, the agent should briefly summarize:

* current repository structure
* key files involved
* current annotation pipeline
* current frontend playback pipeline
* expected files to modify
* any risks or assumptions

Only then start implementation.

---

# Phase 1 — Environment Setup

## Objective

Create and use a clean conda environment named `motviewer`.

## Required commands

From WSL:

```bash
cd /home/junja/mot_viewer
```

Create the environment if it does not already exist:

```bash
conda create -n motviewer python=3.11 -y
```

Activate it:

```bash
conda activate motviewer
```

Install existing dependencies.

If `requirements.txt` exists:

```bash
pip install -r requirements.txt
```

If no dependency file exists, inspect imports first, then install the minimal required packages.

Likely required packages:

```bash
pip install flask pillow numpy opencv-python
```

For SVG export, either use:

```bash
pip install svgwrite
```

or implement SVG generation manually with XML.

For video encoding, use system `ffmpeg`.

Check ffmpeg:

```bash
ffmpeg -version
```

If ffmpeg is missing, the app should fail gracefully with a clear message. Do not silently crash.

## Dependency update

Update or create dependency files as appropriate:

* `requirements.txt`
* optionally `environment.yml`

Do not over-install unnecessary libraries.

---

# Phase 2 — Git Branch Setup

## Objective

Work on a new branch only.

## Required actions

Before editing:

```bash
git status
```

If there are existing uncommitted user changes, do not overwrite them. Report them clearly.

Create a feature branch:

```bash
git checkout -b feature/multilayer-video-export
```

If that branch already exists, use a safe alternative:

```bash
git checkout -b feature/multilayer-video-export-v2
```

Do not merge into `master` or `main`.

---

# Phase 3 — Multi-Layer Annotation Support

## Current problem

The viewer currently supports only one annotation source at a time.

## Target behavior

The viewer should support multiple annotation layers for one sequence.

Examples:

```text
gt/gt.txt
det/det.txt
results/bytetrack.txt
results/ours.txt
```

Each layer should be independently configurable and visible together.

## New annotation layer concept

Each sequence should support:

```json
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
```

## Backward compatibility

If the existing config only has one annotation path, convert it internally into one default annotation layer.

Do not break existing datasets.

## Annotation parser requirements

Support MOTChallenge-style text files.

Expected format:

```text
frame,id,x,y,w,h,conf,...
```

Parser rules:

* require at least 6 columns
* parse:

  * frame
  * id
  * x
  * y
  * w
  * h
* parse confidence score if available
* if confidence does not exist, default to `1.0`
* support detection files where id may be `-1`
* ignore malformed lines safely
* collect warnings for skipped lines
* report missing annotation files clearly
* do not crash the whole app because one optional layer is missing

## Backend annotation data structure

The backend should be able to return annotations grouped by frame and layer.

Example:

```json
{
  "fps": 25,
  "first_frame": 1,
  "frame_count": 750,
  "layers": [
    {
      "name": "Ground Truth",
      "type": "gt",
      "color": "#00ff00",
      "visible": true,
      "draw_id": true,
      "draw_score": false
    },
    {
      "name": "Detections",
      "type": "det",
      "color": "#ff9900",
      "visible": true,
      "draw_id": false,
      "draw_score": true,
      "score_threshold": 0.0
    }
  ],
  "frames": {
    "1": {
      "Ground Truth": [
        {
          "id": 3,
          "x": 100,
          "y": 120,
          "w": 40,
          "h": 90,
          "score": 1.0
        }
      ],
      "Detections": [
        {
          "id": -1,
          "x": 105,
          "y": 124,
          "w": 38,
          "h": 88,
          "score": 0.82
        }
      ]
    }
  }
}
```

## Frontend requirements

Add a layer control panel.

Each layer should have:

* checkbox for visibility
* color indicator
* layer name
* optional score threshold slider if scores exist
* option to show ID
* option to show score

GT and detections should be visible together.

Use different colors for different layers.

Avoid overlapping text labels too badly.

---

# Phase 4 — Smooth Video Playback

## Current problem

The current play function loads image frames one by one. At higher speed, image loading and bounding-box drawing can lag or freeze.

## Target behavior

Add a smooth playback mode using:

```html
<video>
<canvas>
```

The video element plays a generated MP4 proxy of the image sequence.

The canvas overlays selected annotation layers in sync with the current video time.

## Architecture

```text
Image sequence
    ↓
Backend generates cached MP4
    ↓
Frontend plays MP4 using <video>
    ↓
Canvas overlay draws selected boxes
    ↓
Frame index computed from video.currentTime and fps
```

## Keep two modes

The viewer should have two modes:

1. Frame Inspection Mode
2. Smooth Video Mode

### Frame Inspection Mode

Keep the existing precise frame-by-frame browsing.

Use this for:

* exact frame debugging
* stepping forward and backward
* checking annotations precisely

### Smooth Video Mode

Use video playback.

Use this for:

* natural playback
* fast sequence review
* demo recording
* smooth visual inspection

## Backend video cache

Add a video cache module, for example:

```text
video_cache.py
```

It should:

* locate the image sequence directory
* naturally sort image files
* support `.jpg`, `.jpeg`, `.png`
* generate MP4 if not already cached
* reuse cached MP4 when available
* store cached videos under:

```text
instance/video_cache/
```

* return video URL, FPS, first frame, and frame count
* fail gracefully if ffmpeg is unavailable

## Recommended endpoint

```text
GET /api/video/<dataset>/<split>/<sequence>
```

Response example:

```json
{
  "available": true,
  "video_url": "/video_cache/SportsMOT_train_seq001.mp4",
  "fps": 25,
  "first_frame": 1,
  "frame_count": 750
}
```

Failure example:

```json
{
  "available": false,
  "error": "ffmpeg not found or video generation failed"
}
```

## Frontend video sync

Use:

```javascript
frameIndex = Math.floor(video.currentTime * fps) + firstFrame;
```

Use `requestAnimationFrame` to draw overlays.

Do not create one DOM element per bounding box during playback.

Use canvas drawing only.

Do not request annotations frame-by-frame during playback.

Load annotations once per sequence.

## Playback speed

Support:

```text
0.25x
0.5x
1x
2x
4x
```

Use:

```javascript
video.playbackRate
```

Do not simulate speed by manually changing image frame intervals in smooth video mode.

---

# Phase 5 — Export and Download Support

## Target behavior

The viewer should allow exporting:

1. Current frame without annotations.
2. Current frame with selected annotations.
3. Whole sequence as raw images ZIP.
4. Whole sequence as annotated images ZIP.
5. Whole sequence as raw video.
6. Whole sequence as annotated video.

The user should be able to choose:

* export target
* include annotations or not
* use currently visible layers or custom selected layers
* output format
* selected layers
* score threshold behavior

## Export targets

```text
Current Frame
Whole Sequence as Images ZIP
Whole Sequence as Video MP4
```

## Annotation options

```text
No annotations
Use currently visible layers
Custom selected layers
```

The recommended default:

```text
Use currently visible layers
```

## Format support

Allowed format matrix:

| Export Target                | Allowed Formats             |
| ---------------------------- | --------------------------- |
| Current Frame                | `jpg`, `jpeg`, `png`, `svg` |
| Whole Sequence as Images ZIP | `jpg`, `jpeg`, `png`, `svg` |
| Whole Sequence as Video      | `mp4`                       |

Invalid combinations must be rejected.

Examples:

| Request                    | Valid? |
| -------------------------- | ------ |
| frame export as PNG        | yes    |
| frame export as SVG        | yes    |
| sequence images ZIP as JPG | yes    |
| sequence images ZIP as SVG | yes    |
| sequence video as MP4      | yes    |
| frame export as MP4        | no     |
| sequence video as PNG      | no     |
| sequence video as SVG      | no     |

## Backend export modules

Add reusable modules where appropriate:

```text
frame_renderer.py
svg_renderer.py
export_manager.py
video_exporter.py
zip_exporter.py
```

Actual filenames may follow the existing repo style.

## Frame renderer

The renderer should:

* load original frame
* draw selected annotation layers
* apply each layer color
* apply score thresholds
* draw track IDs if enabled
* draw confidence scores if enabled
* save to requested raster format
* support raw export with no annotations

This renderer should be reused by:

* current frame export
* annotated image ZIP export
* annotated video export

## SVG renderer

SVG export should be meaningful.

For SVG:

* preserve original frame width and height
* embed original image into SVG
* draw boxes as SVG `<rect>` elements
* draw IDs/scores as SVG `<text>` elements
* use selected layer colors
* support raw SVG export by embedding the image without annotations
* do not simply rasterize and rename as `.svg`

Recommended SVG structure:

```xml
<svg width="1920" height="1080">
  <image href="data:image/jpeg;base64,..." x="0" y="0" width="1920" height="1080"/>
  <rect x="100" y="120" width="40" height="90" stroke="#00ff00" fill="none"/>
  <text x="100" y="115">ID 3</text>
</svg>
```

## Video export

For raw video export:

* reuse smooth playback video cache if available
* otherwise generate MP4 from image sequence

For annotated video export:

* render frames with selected annotation layers
* encode to MP4
* preserve sequence FPS unless user overrides it
* use browser-compatible MP4 settings:

  * H.264
  * yuv420p
  * faststart if possible

## ZIP export

For raw image sequence ZIP:

* zip original frames in natural order

For annotated image sequence ZIP:

* render each frame with selected annotation layers
* write images into ZIP
* avoid keeping all rendered frames in memory

## Export storage

Store generated exports under:

```text
instance/exports/
```

Use safe filenames containing:

* dataset name
* split
* sequence
* export type
* selected layers
* format
* timestamp or hash

Examples:

```text
SportsMOT_train_seq001_frame_000120_gt_det.png
SportsMOT_train_seq001_frame_000120_gt.svg
SportsMOT_train_seq001_images_gt_det_png.zip
SportsMOT_train_seq001_images_raw_jpg.zip
SportsMOT_train_seq001_video_gt_det.mp4
SportsMOT_train_seq001_video_raw.mp4
```

## Recommended API endpoints

### Export current frame

```text
POST /api/export/frame
```

Request:

```json
{
  "dataset": "SportsMOT",
  "split": "train",
  "sequence": "seq001",
  "frame": 120,
  "include_annotations": true,
  "annotation_mode": "visible",
  "selected_layers": ["Ground Truth", "Detections"],
  "format": "png"
}
```

Response:

```json
{
  "available": true,
  "download_url": "/downloads/exports/SportsMOT_train_seq001_frame_000120_gt_det.png"
}
```

### Export whole sequence as images ZIP

```text
POST /api/export/sequence/images
```

Request:

```json
{
  "dataset": "SportsMOT",
  "split": "train",
  "sequence": "seq001",
  "include_annotations": true,
  "annotation_mode": "visible",
  "selected_layers": ["Ground Truth", "Detections"],
  "format": "jpg"
}
```

Response:

```json
{
  "available": true,
  "download_url": "/downloads/exports/SportsMOT_train_seq001_images_gt_det_jpg.zip"
}
```

### Export whole sequence as video

```text
POST /api/export/sequence/video
```

Request:

```json
{
  "dataset": "SportsMOT",
  "split": "train",
  "sequence": "seq001",
  "include_annotations": true,
  "annotation_mode": "visible",
  "selected_layers": ["Ground Truth", "Detections"],
  "format": "mp4",
  "fps": 25
}
```

Response:

```json
{
  "available": true,
  "download_url": "/downloads/exports/SportsMOT_train_seq001_video_gt_det.mp4"
}
```

---

# Phase 6 — Export UI

Add an export panel to the frontend.

## Required controls

```text
Export Target:
[ Current Frame ▼ ]

Format:
[ PNG ▼ ]

Annotations:
( ) No annotations
(o) Use currently visible layers
( ) Custom selected layers

Layers:
[x] Ground Truth
[x] Detections
[ ] Tracker Result

Options:
[x] Draw IDs
[x] Draw scores

[ Export ]
```

## Dynamic format dropdown

If target is `Current Frame`, show:

```text
JPG
JPEG
PNG
SVG
```

If target is `Whole Sequence as Images ZIP`, show:

```text
JPG
JPEG
PNG
SVG
```

If target is `Whole Sequence as Video`, show:

```text
MP4
```

The UI should not show invalid options.

## Export feedback

The UI should show:

* exporting status
* success message
* download link
* clear error message if failed

For long exports, it is acceptable to use a synchronous first version, but the UI should not fail silently.

---

# Phase 7 — Error Handling

Add useful error messages for:

* missing dataset
* missing split
* missing sequence
* missing image directory
* missing annotation file
* malformed annotation line
* invalid layer name
* invalid frame index
* invalid export format
* invalid export target/format combination
* ffmpeg missing
* video generation failure
* ZIP generation failure
* export directory not writable

Do not crash the whole app if one optional layer fails.

---

# Phase 8 — Performance Requirements

## Playback performance

* Do not use DOM elements for each box in smooth playback.
* Use canvas overlay.
* Use `requestAnimationFrame`.
* Load annotations once per sequence.
* Avoid per-frame backend requests during video playback.

## Export performance

* Parse annotations once per sequence.
* Cache parsed annotations where reasonable.
* Use natural frame ordering.
* Do not load all frames into memory.
* Stream/write frame outputs incrementally where possible.
* Reuse cached raw MP4 video for raw video export.

---

# Phase 9 — Smoke Checks / Tests

Add tests or smoke scripts depending on the existing repo style.

If there is no test structure, add a simple script such as:

```text
scripts/smoke_check.py
```

The smoke check should verify:

1. App imports successfully.
2. Config loads successfully.
3. Multi-layer annotation config parses.
4. `gt/gt.txt` and `det/det.txt` can be loaded together.
5. Annotations are grouped by frame and layer.
6. Missing/malformed annotation lines are handled safely.
7. Export format validation works.
8. Current frame export works for:

   * jpg
   * jpeg
   * png
   * svg
9. Sequence image ZIP export works for:

   * jpg
   * png
   * svg
10. Sequence video export validates `mp4`.
11. Invalid combinations are rejected, for example:

* frame export as mp4
* video export as svg

12. Video cache path can be resolved.
13. Flask app starts without crashing.

Run available tests or smoke checks before committing.

---

# Phase 10 — Documentation

Update documentation.

At minimum, update or create:

```text
README.md
```

Add sections explaining:

* how to create the conda environment
* how to run the viewer
* how to configure multiple annotation layers
* how to show GT and detections together
* how smooth video playback works
* how export works
* supported export formats
* ffmpeg requirement
* known limitations

Example environment instructions:

```bash
conda create -n motviewer python=3.11 -y
conda activate motviewer
pip install -r requirements.txt
python app.py
```

---

# Phase 11 — Final Verification

Before committing, run:

```bash
git status
python --version
python -m compileall .
```

Run the app or available smoke check:

```bash
python app.py
```

or:

```bash
python scripts/smoke_check.py
```

Also check ffmpeg:

```bash
ffmpeg -version
```

If the app cannot be fully run due to missing dataset or missing ffmpeg, explain clearly in the final report.

---

# Phase 12 — Commit and Push

After verification, commit changes.

```bash
git status
git add .
git commit -m "Add multilayer annotations, smooth playback, and export support"
```

Push the new branch:

```bash
git push -u origin feature/multilayer-video-export
```

If the branch name is different, push that branch.

Do not merge into `master` or `main`.

---

# Final Report Required

After finishing, provide a final report containing:

1. Branch name.
2. Commit hash.
3. Files changed.
4. Summary of implemented features.
5. How to activate the conda environment.
6. How to run the viewer.
7. How to configure GT and detections together.
8. How to use smooth playback.
9. How to export frame/image sequence/video.
10. Supported export formats.
11. Tests or smoke checks run.
12. Any limitations or issues.
13. Whether the branch was pushed to GitHub.
14. Confirmation that it was not merged into master/main.
