# PLAN_MOT_VIEWER_FIX_UI_V2.md

# MOT Viewer Fix + UI Redesign Plan

## Goal

This is a second-stage improvement plan for the MOT Viewer project at:

```bash
/home/junja/mot_viewer
```

The previous upgrade added multi-layer annotations, smooth video mode, export tools, and dataset registration, but the current implementation has several issues:

1. Smooth video mode only plays or displays correctly for about 2 seconds.
2. Video generation/rendering takes a long time but has no progress bar.
3. GT and detection overlays still do not appear together correctly. Only one layer appears at a time.
4. Add Dataset and Export Video controls are making the left sidebar too crowded.
5. The current UI layout feels cramped. Redesign it toward a draw.io-style layout:

   * top menu / toolbar
   * left sidebar for sequence/navigation tools
   * large central viewer canvas/video area
   * right-side inspector/properties panel
   * modals for larger workflows like Add Dataset and Export

Do not rewrite the whole project blindly. First inspect the current implementation, identify why these bugs happen, then fix them cleanly.

---

# Phase 0 — Inspect Current Repo and Current Implementation

Before editing, inspect the current repository:

```bash
cd /home/junja/mot_viewer
git status
git branch --show-current
find . -maxdepth 3 -type f | sort
```

Inspect especially:

```text
app.py
templates/
static/
static/js/
static/css/
motviewer/
instance/datasets.json
README.md
PLAN_MOT_VIEWER_UPGRADE.md
```

Identify:

* current smooth video route
* current video cache module
* current frontend video player logic
* current annotation loading API
* current annotation layer data structure
* current layer checkbox/control logic
* current canvas overlay drawing logic
* current export UI
* current add dataset UI
* current CSS layout

Before coding, summarize:

1. Why smooth video stops or only shows around 2 seconds.
2. Whether the generated MP4 itself is only 2 seconds, or whether the frontend stops drawing/playing after 2 seconds.
3. Why GT and detections are mutually exclusive instead of being drawn together.
4. Why the layout is crowded.
5. Files that need modification.

---

# Phase 1 — Fix Smooth Video Duration / Playback Bug

## Problem

Smooth video mode only shows about 2 seconds, even when the sequence should be longer.

## Required debugging

Check whether the problem is backend or frontend.

### Backend checks

Check generated video duration using:

```bash
ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 <cached_video_path>
```

Compare:

* number of image frames
* expected FPS
* expected duration
* actual MP4 duration

Expected:

```text
duration = frame_count / fps
```

If the sequence has 750 frames at 25 FPS, the video should be around 30 seconds.

Possible backend causes:

* ffmpeg input pattern only includes first few frames
* natural frame ordering is wrong
* frame list file is incomplete
* ffmpeg command is using wrong image pattern
* image filenames are not continuous
* video cache reused an old broken 2-second MP4
* FPS metadata is wrong
* frame_count is computed incorrectly

### Frontend checks

If MP4 duration is correct, inspect:

* video `loadedmetadata`
* video `duration`
* currentTime update
* canvas overlay loop
* requestAnimationFrame loop
* whether drawing stops early
* whether frame index calculation becomes invalid
* whether annotation frames only exist for first few seconds
* whether a stale video URL is being loaded

## Required fixes

1. Ensure cached video duration matches the full sequence length.
2. If a cached MP4 is invalid or too short, regenerate it.
3. Include cache invalidation using a hash/signature based on:

   * dataset
   * split
   * sequence
   * image directory path
   * frame count
   * FPS
   * first/last frame filename
4. Frontend should use actual video duration from metadata.
5. Overlay drawing should continue for the whole video.
6. Clamp frame index safely:

```javascript
frameIndex = Math.min(
  lastFrame,
  Math.max(firstFrame, Math.floor(video.currentTime * fps) + firstFrame)
);
```

7. Do not stop requestAnimationFrame until video is paused, ended, or mode is changed.

---

# Phase 2 — Add Progress Bar for Video Generation

## Problem

Video generation/rendering takes a long time but there is no progress indicator.

## Target

When generating smooth playback video or exporting annotated video, show a progress bar.

## Recommended design

Use an asynchronous job-style API.

### Start video generation

```text
POST /api/video/render
```

Request:

```json
{
  "dataset": "SportsMOT",
  "split": "train",
  "sequence": "seq001"
}
```

Response:

```json
{
  "job_id": "abc123",
  "status": "queued"
}
```

### Poll progress

```text
GET /api/jobs/<job_id>
```

Response:

```json
{
  "job_id": "abc123",
  "status": "running",
  "progress": 42,
  "message": "Rendering frame 315 / 750"
}
```

### Complete response

```json
{
  "job_id": "abc123",
  "status": "done",
  "progress": 100,
  "result": {
    "video_url": "/video_cache/xxx.mp4",
    "fps": 25,
    "first_frame": 1,
    "frame_count": 750
  }
}
```

### Failure response

```json
{
  "job_id": "abc123",
  "status": "failed",
  "progress": 0,
  "error": "ffmpeg failed: ..."
}
```

## Simpler acceptable first version

If a full async job system is too much for the current repo, implement a simpler progress modal:

* show “Generating video…”
* show spinner/progress state
* disable play button while generating
* show complete/error state clearly

But preferred implementation is real progress polling.

## UI requirements

Add a progress bar modal:

```text
Generating Smooth Video
[██████████----------] 52%
Rendering frame 390 / 750
Cancel
```

For export video, use a similar modal:

```text
Exporting Annotated Video
[████████████--------] 60%
Rendering frame 450 / 750
Cancel
```

---

# Phase 3 — Fix Multi-Layer Overlay: GT + Det Must Draw Together

## Problem

The viewer still only shows one annotation layer at a time.

## Target

The viewer must be able to draw multiple visible layers together.

Example:

* GT boxes: green
* Detection boxes: orange
* Tracker result boxes: blue

All visible checked layers should be drawn on the same frame/video overlay.

## Required debugging

Inspect:

* backend annotation JSON
* whether `frames[frameIndex]` contains both `Ground Truth` and `Detections`
* frontend layer state
* whether layer checkboxes behave like radio buttons
* whether selected layer state is a single string instead of an array/set
* whether draw function clears canvas between layers incorrectly
* whether only the last layer is passed to draw function
* whether API returns only one active layer

## Required backend behavior

The annotation endpoint should return all layers for each frame:

```json
{
  "frames": {
    "1": {
      "Ground Truth": [...],
      "Detections": [...]
    }
  },
  "layers": [
    {"name": "Ground Truth", "color": "#00ff00"},
    {"name": "Detections", "color": "#ff9900"}
  ]
}
```

Do not filter to only one active layer on the backend unless the API explicitly requests filtering.

## Required frontend behavior

Use a layer visibility map:

```javascript
visibleLayers = {
  "Ground Truth": true,
  "Detections": true,
  "ByteTrack": false
};
```

Drawing logic should be:

```javascript
clearCanvas();

for (const layer of layers) {
  if (!visibleLayers[layer.name]) continue;

  const boxes = frameData[layer.name] || [];
  drawBoxesForLayer(boxes, layer);
}
```

Important:

* clear the canvas once per frame, not once per layer
* loop through all visible layers
* do not overwrite `frameData`
* do not store only one selected layer globally
* checkboxes must allow multiple layers selected
* score threshold should apply per layer

## UI requirement

Layer panel should support multiple checked layers at the same time.

It should not behave like:

```text
radio button group
```

It should behave like:

```text
checkbox group
```

---

# Phase 4 — Move Add Dataset and Export to Separate Modal Views

## Problem

The left sidebar is too crowded because Add Dataset and Export controls are placed there directly.

## Target

Move larger workflows into modal dialogs.

## Add Dataset modal

Add Dataset should open as a modal/popup.

Trigger button location:

* top toolbar, or
* left sidebar compact button

Modal contents:

```text
Add Dataset
────────────────────────
Dataset name
Dataset root path
Splits
Image directory
GT files
Detection file
Annotation layers
Save / Cancel
```

Requirements:

* do not occupy permanent sidebar space
* validate required fields
* show success/error message
* after saving, refresh dataset list

## Export modal

Export should open as a modal/popup.

Trigger button location:

* top toolbar
* right inspector panel
* or viewer toolbar

Modal contents:

```text
Export
────────────────────────
Target:
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

[ Export ]
```

Requirements:

* dynamically update format options
* show progress for long exports
* show download link when done
* show errors clearly
* support current visible layers
* support custom selected layers

---

# Phase 5 — Redesign UI Toward draw.io-Style Layout

## Problem

Current left toolbar is crowded and the layout feels cramped.

## Target layout

Adopt a draw.io-style application layout.

Reference concept:

```text
┌────────────────────────────────────────────────────────────┐
│ Top Menu Bar                                                │
│ File  View  Dataset  Export  Help                           │
├────────────────────────────────────────────────────────────┤
│ Top Toolbar                                                 │
│ [Add Dataset] [Export] [Mode] [Play] [Speed] [Zoom] ...     │
├───────────────┬───────────────────────────────┬────────────┤
│ Left Sidebar  │ Main Viewer Area               │ Right Panel │
│ Dataset       │                               │ Layers      │
│ Split         │       Image/Video Canvas       │ Properties  │
│ Sequence      │                               │ Export info │
│ Frame list    │                               │ Metadata    │
└───────────────┴───────────────────────────────┴────────────┘
```

## Layout responsibilities

### Top menu bar

Contains high-level commands:

```text
File
Dataset
View
Export
Help
```

### Top toolbar

Contains common action buttons:

```text
Add Dataset
Export
Frame Mode / Smooth Video Mode
Play / Pause
Playback Speed
Previous Frame
Next Frame
Zoom In
Zoom Out
Fit to Screen
```

### Left sidebar

Only for navigation:

* dataset selector
* split selector
* sequence selector
* frame number input / slider
* sequence metadata summary

Do not put large forms in the left sidebar.

### Main viewer area

Large central display area.

Must support:

* frame image view
* smooth video view
* canvas overlay
* responsive scaling
* black/dark stage background
* no unnecessary UI overlap on the video/image

### Right inspector panel

Use this for properties and layer controls:

* annotation layers
* layer visibility checkboxes
* layer colors
* draw ID toggle
* draw score toggle
* score threshold slider
* selected frame info
* selected sequence info

### Modals

Use modals for:

* Add Dataset
* Export
* Video generation progress
* Export progress
* Error details

## CSS requirements

Use a stable grid/flex layout.

Suggested structure:

```html
<div class="app-shell">
  <header class="app-menu-bar"></header>
  <div class="app-toolbar"></div>
  <div class="app-body">
    <aside class="left-sidebar"></aside>
    <main class="viewer-workspace"></main>
    <aside class="right-inspector"></aside>
  </div>
</div>
```

Suggested CSS concept:

```css
.app-shell {
  height: 100vh;
  display: grid;
  grid-template-rows: 36px 48px 1fr;
}

.app-body {
  min-height: 0;
  display: grid;
  grid-template-columns: 280px 1fr 320px;
}

.viewer-workspace {
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.viewer-stage {
  position: relative;
  width: 100%;
  height: 100%;
}

.video-stage,
.frame-stage {
  position: relative;
}

.overlay-canvas {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
```

## Visual design requirements

* reduce clutter
* use consistent spacing
* use icons or compact buttons where helpful
* keep the central viewer large
* avoid overlapping controls with video/image
* support smaller screens reasonably
* right panel can collapse if needed
* left panel can collapse if needed

---

# Phase 6 — Update Documentation

Update README with:

* new draw.io-style layout explanation
* Add Dataset modal
* Export modal
* progress bar behavior
* GT + detection overlay behavior
* troubleshooting for short generated videos

Add troubleshooting section:

```text
If smooth video only plays for 2 seconds:
1. Delete instance/video_cache for that sequence.
2. Regenerate the video.
3. Check ffmpeg and ffprobe duration.
4. Confirm FPS and frame count.
```

---

# Phase 7 — Verification

Run:

```bash
python -m compileall .
```

Run smoke checks if available:

```bash
python scripts/smoke_check.py
```

Start app:

```bash
python app.py
```

Manual verification checklist:

1. Open a sequence.
2. Enable both Ground Truth and Detections.
3. Confirm both appear together with different colors.
4. Switch to smooth video mode.
5. Generate video.
6. Confirm progress indicator appears.
7. Confirm video duration matches expected sequence length.
8. Confirm overlay continues after 2 seconds.
9. Open Add Dataset modal.
10. Confirm the left sidebar is not crowded.
11. Open Export modal.
12. Export current frame.
13. Export annotated video if possible.
14. Confirm layout resembles draw.io-style structure.

---

# Phase 8 — Commit and Push

Commit on a new branch or the current feature branch.

Recommended branch:

```bash
feature/fix-video-overlay-ui-v2
```

Commit message:

```bash
Fix smooth playback, multilayer overlays, and redesign UI layout
```

Push to GitHub:

```bash
git push -u origin feature/fix-video-overlay-ui-v2
```

Do not merge into `master` or `main`.

---

# Final Report Required

Provide:

1. Branch name.
2. Commit hash.
3. Files changed.
4. Root cause of 2-second smooth video issue.
5. How video generation progress works.
6. Root cause of single-layer-only overlay issue.
7. How GT + detection drawing was fixed.
8. Description of new draw.io-style layout.
9. How Add Dataset modal works.
10. How Export modal works.
11. Tests/checks run.
12. Known limitations.
13. Whether pushed to GitHub.
14. Confirmation that it was not merged into master/main.
