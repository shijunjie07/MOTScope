# PLAN_MOTSCOPE_CANVAS_REFINEMENT_V4.md

# MOTScope Canvas Refinement V4

## Goal

Refine the MOTScope main viewer canvas/workspace.

Repository path inside WSL:

```bash
/home/junja/mot_viewer
```

The previous UI refinement has already been executed. This follow-up plan focuses only on the viewer canvas/background and zoom behavior.

Main goals:

1. Add a clean grid background to the main viewer canvas/workspace.
2. Support both white-grid and black-grid canvas backgrounds.
3. Allow the user to switch canvas background mode.
4. Make image/video zoom-out work properly.
5. Preserve existing zoom-in, pan, drag, overlay alignment, and annotation drawing behavior.
6. Ensure the canvas background fits the MOTScope visual theme.

---

# Phase 0 — Inspect Current Implementation

Before editing, inspect the current repo:

```bash
cd /home/junja/mot_viewer
git status
git branch --show-current
find . -maxdepth 3 -type f | sort
```

Inspect especially:

```text
templates/
static/
static/js/
static/css/
app.py
README.md
```

Identify:

* current viewer stage HTML structure
* current canvas/image/video container structure
* current CSS for viewer workspace
* current background styling
* current zoom state variables
* current zoom-in and zoom-out functions
* current pan/drag transform logic
* current overlay canvas drawing logic
* current keyboard/mouse shortcut logic
* current theme logic

Before coding, summarize:

1. Current viewer workspace structure.
2. Current background implementation.
3. Current zoom implementation.
4. Why zoom-out is limited or broken.
5. Files to modify.
6. Risks or assumptions.

Only begin implementation after this summary.

---

# Phase 1 — Add Grid Background to Viewer Canvas

## Current problem

The main viewer/canvas background is visually plain.

The user wants a grid-style background similar to design tools.

## Target

The main viewer workspace should show a subtle grid background.

It should support:

```text
White grid background
Black grid background
```

The grid should look clean and designer-like, not distracting.

## Recommended white grid

Use a light neutral background with subtle grid lines:

```css
.viewer-workspace[data-canvas-bg="white-grid"] {
  background-color: #f8fafc;
  background-image:
    linear-gradient(to right, rgba(15, 23, 42, 0.08) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(15, 23, 42, 0.08) 1px, transparent 1px);
  background-size: 24px 24px;
}
```

## Recommended black grid

Use a dark background with subtle grid lines:

```css
.viewer-workspace[data-canvas-bg="black-grid"] {
  background-color: #020617;
  background-image:
    linear-gradient(to right, rgba(148, 163, 184, 0.16) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(148, 163, 184, 0.16) 1px, transparent 1px);
  background-size: 24px 24px;
}
```

## Optional dot grid

If the existing UI style looks better with dots, a dot grid is acceptable.

Example:

```css
.viewer-workspace[data-canvas-bg="white-dot-grid"] {
  background-color: #f8fafc;
  background-image: radial-gradient(rgba(15, 23, 42, 0.14) 1px, transparent 1px);
  background-size: 18px 18px;
}
```

But the preferred default should be a regular grid.

---

# Phase 2 — Add Canvas Background Controls

## Target

Add a user control to switch the viewer canvas background.

Recommended location:

```text
View → Canvas Background
  White Grid
  Black Grid
  Plain White
  Plain Black
```

Optional if there is already a Display section in the left sidebar:

```text
Display
  Canvas background: [White Grid ▼]
```

Preferred implementation:

* Put the main setting under `View → Canvas Background`.
* Also show it in the left `Display` section if that section already exists.

## Required options

Support at least:

```text
White Grid
Black Grid
Plain White
Plain Black
```

Optional:

```text
Dot Grid
```

## Default

Default canvas background should be:

```text
White Grid
```

This matches the MOTScope logo and light-mode default.

## Persistence

Persist selected canvas background using `localStorage`.

Recommended key:

```javascript
localStorage.setItem("motScopeCanvasBackground", value);
```

Default logic:

```javascript
const savedCanvasBg = localStorage.getItem("motScopeCanvasBackground");
const canvasBg = savedCanvasBg || "white-grid";
viewerWorkspace.dataset.canvasBg = canvasBg;
```

## Requirements

* Changing the canvas background should apply immediately.
* Selection should persist after refresh.
* It should work in both light and dark app themes.
* It should not affect annotation colors.
* It should not affect export rendering.
* It should not affect original image/video pixels.

---

# Phase 3 — Ensure Grid Background Is Behind Image/Video Only

## Important

The grid should be the background of the viewer workspace, not drawn into the image/video itself.

The hierarchy should be:

```text
Viewer workspace grid background
    ↓
Viewport transform container
    ↓
Image or video element
    ↓
Overlay canvas
    ↓
Floating viewer controls
```

Recommended structure:

```html
<main class="viewer-workspace" data-canvas-bg="white-grid">
  <div class="viewer-stage">
    <div class="viewport-layer">
      <img id="frameImage" />
      <video id="motVideo"></video>
      <canvas id="overlayCanvas"></canvas>
    </div>

    <div class="floating-viewer-controls">
      ...
    </div>
  </div>
</main>
```

The grid should remain visible around the image when the user zooms out.

The grid should not move unless intentionally tied to pan. Preferred first version:

* grid stays fixed relative to viewer workspace
* image/video pans and zooms above it

---

# Phase 4 — Fix Zoom-Out Behavior

## Current problem

The user wants the image to be able to zoom out.

Existing zoom may only allow zooming in or may clamp too early.

## Target

Allow the image/video to zoom out below fit size.

The user should be able to see the image/video smaller than the viewer workspace, with grid background around it.

## Required behavior

Support zoom range:

```text
minimum zoom: 0.10x or 10%
maximum zoom: 8.00x or 800%
default fit zoom: based on container size
```

Recommended constants:

```javascript
const MIN_ZOOM = 0.1;
const MAX_ZOOM = 8.0;
const ZOOM_STEP = 1.15;
```

Zoom controls should allow:

```text
Zoom In
Zoom Out
Fit / Reset
100%
Ctrl + mouse wheel
Ctrl + +
Ctrl + -
Ctrl + 0
```

## Important distinction

There should be two useful zoom states:

### Fit zoom

The image/video fits inside the available viewer area.

```text
Fit to screen
```

### Manual zoom

The user can zoom in or zoom out from fit.

This means:

```text
manual zoom can be smaller than fit zoom
manual zoom can be larger than fit zoom
```

Do not clamp minimum zoom to fit size.

## Recommended state design

Use:

```javascript
viewport = {
  scale: 1,
  offsetX: 0,
  offsetY: 0
};
```

Where:

```text
scale = actual rendered scale relative to original media size
```

Or if the existing system uses fit scale + user scale:

```javascript
viewport = {
  fitScale: 1,
  userScale: 1,
  offsetX: 0,
  offsetY: 0
};
```

Then:

```javascript
effectiveScale = fitScale * userScale;
```

If using this design, allow:

```javascript
userScale >= 0.1
```

so the user can zoom out below fit.

## Zoom-out requirements

* Zoom-out button should work.
* Ctrl + mouse wheel down should zoom out.
* Ctrl + - should zoom out.
* Zoom can go below fit size.
* Image/video should stay centered or zoom around cursor.
* Overlay boxes must remain aligned.
* Panning should still work after zooming out.
* Fit/reset should return to fit-to-screen.
* 100% should show original pixel scale if feasible.

---

# Phase 5 — Overlay Alignment After Zoom-Out

## Required behavior

Annotations must remain aligned with the image/video when zoomed out.

Check:

* frame inspection mode
* smooth video mode
* bounding boxes
* hover detection
* selected box display
* rectangle selection if implemented

## Drawing logic

Box coordinates should remain based on original image coordinates.

Rendering should map:

```text
original image coordinates → screen coordinates
```

using the same transform:

```javascript
screenX = imageOriginX + box.x * effectiveScale + offsetX;
screenY = imageOriginY + box.y * effectiveScale + offsetY;
screenW = box.w * effectiveScale;
screenH = box.h * effectiveScale;
```

If the implementation uses canvas transform:

```javascript
ctx.setTransform(effectiveScale, 0, 0, effectiveScale, offsetX, offsetY);
```

ensure both image/video positioning and canvas drawing use the same origin and scale.

---

# Phase 6 — Update Floating Viewer Controls

If floating controls already exist, update them.

They should include:

```text
Fit
100%
-
+
Pan
Rect
Canvas BG
```

The top toolbar should remain clean.

Do not move `+`, `-`, `Pan`, or `Rect` back to the top toolbar.

Recommended floating controls:

```text
[Fit] [100%] [-] [+] [Pan] [Rect] [BG]
```

Where `BG` can open a small menu:

```text
White Grid
Black Grid
Plain White
Plain Black
```

If `View → Canvas Background` already exists, this floating `BG` is optional.

---

# Phase 7 — Theme Compatibility

The canvas background setting is separate from app theme.

Examples:

```text
App theme: light
Canvas background: white-grid

App theme: light
Canvas background: black-grid

App theme: dark
Canvas background: white-grid

App theme: dark
Canvas background: black-grid
```

Do not force canvas background to follow app theme.

But the default should be:

```text
App theme default: light
Canvas background default: white-grid
```

---

# Phase 8 — Documentation Update

Update README or relevant docs.

Add a section:

```markdown
## Canvas Background

MOTScope supports multiple viewer canvas backgrounds:

- White Grid
- Black Grid
- Plain White
- Plain Black

The default is White Grid. The canvas background can be changed from `View → Canvas Background` and is saved in the browser.
```

Update shortcut table if needed:

| Shortcut           | Action                    |
| ------------------ | ------------------------- |
| Ctrl + mouse wheel | Zoom in/out around cursor |
| Ctrl + +           | Zoom in                   |
| Ctrl + -           | Zoom out                  |
| Ctrl + 0           | Fit/reset view            |
| Shift + left drag  | Pan/drag image            |

Add note:

```markdown
The image/video can be zoomed out below fit size, making the grid workspace visible around the sequence frame.
```

---

# Phase 9 — Verification Checklist

Run:

```bash
python -m compileall .
```

Run smoke checks if available:

```bash
python scripts/smoke_check.py
```

Start app if possible:

```bash
python app.py
```

Manual checks:

1. App opens successfully.
2. Viewer workspace shows white grid by default.
3. View menu has Canvas Background options.
4. Switching to black grid works immediately.
5. Switching to plain white works.
6. Switching to plain black works.
7. Canvas background choice persists after refresh.
8. App theme and canvas background are independent.
9. Zoom-out button works.
10. Ctrl + mouse wheel down zooms out.
11. Ctrl + - zooms out.
12. Image/video can become smaller than fit-to-screen.
13. Grid is visible around the image/video when zoomed out.
14. Fit returns image/video to fit-to-screen.
15. 100% view works if implemented.
16. Pan still works after zooming out.
17. Overlay boxes stay aligned after zooming out.
18. GT and detection layers still draw together.
19. Smooth video mode still works.
20. Export behavior is not affected.
21. Top toolbar remains clean.
22. Pan/Rect/+/- are not reintroduced to the top toolbar.

---

# Phase 10 — Commit and Push

Use a new branch:

```bash
feature/motscope-canvas-background-zoom
```

If it already exists, use:

```bash
feature/motscope-canvas-background-zoom-fix
```

Commit message:

```bash
Refine viewer canvas background and zoom behavior
```

Push:

```bash
git push -u origin feature/motscope-canvas-background-zoom
```

Do not merge into `master` or `main`.

---

# Final Report Required

At the end, provide:

1. Repository path.
2. Branch name.
3. Commit hash.
4. Files changed.
5. Summary of canvas background changes.
6. Available canvas background modes.
7. Confirmation default canvas background is white grid.
8. Confirmation black grid is available.
9. Confirmation setting persists after refresh.
10. Zoom-out behavior changes.
11. Minimum/maximum zoom used.
12. Confirmation image/video can zoom out below fit size.
13. Confirmation overlay alignment works after zoom-out.
14. Confirmation smooth video still works.
15. Confirmation export behavior is unaffected.
16. Tests/checks run.
17. Known limitations.
18. Whether branch was pushed to GitHub.
19. Confirmation that it was not merged into master/main.
