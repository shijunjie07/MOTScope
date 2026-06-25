# PLAN_MOTSCOPE_UI_REFINEMENT_V3.md

# MOTScope UI Refinement V3

## Goal

Refine and rebrand the existing Flask-based MOT Viewer into **MOTScope**.

Repository path inside WSL:

```bash
/home/junja/mot_viewer
```

This plan combines all pending V3 UI/UX changes and branding changes into one execution plan.

The app currently supports or is intended to support:

* multi-layer annotation visualization
* GT and detection display
* smooth video playback
* export/download support
* frame inspection mode
* dataset registration

This plan focuses on polishing the product UI and making the viewer feel like a real tool.

---

# Main Goals

1. Rebrand the app from **MOT Viewer** to **MOTScope**.
2. Add the MOTScope logo into the web app UI.
3. Add the rectangular MOTScope logo at the top of the README.
4. Design the UI theme to match the logo:

   * light mode default
   * clean white/gray interface
   * teal / blue / purple accent colors
   * dark mode still available
5. Make the top UI cleaner and closer to draw.io.
6. Move Add Dataset and Export into the File menu.
7. Move Layers, Annotation Source, and Display to the left sidebar.
8. Remove Pan / Rect / + / - from the top toolbar.
9. Preserve old pan / zoom / drag behavior.
10. Add Ctrl/Shift shortcuts for viewer interaction.
11. Redesign layer cards so `Visible` is clearly a master layer switch.
12. Fix color picker behavior:

    * preview color immediately
    * picker stays open until Apply / Cancel / Close
13. Make export start the download automatically after completion.
14. Keep a fallback `Download again` link.
15. Keep GT and detections drawing together.
16. Treat the smooth video full-duration issue as already fixed and only run regression checks.

---

# Phase 0 — Inspect Current Repository First

Before coding, inspect the current repository.

```bash
cd /home/junja/mot_viewer
pwd
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
static/assets/
docs/
docs/assets/
motviewer/
instance/datasets.json
README.md
PLAN_MOT_VIEWER_UPGRADE.md
```

Identify:

* current HTML layout structure
* current CSS layout system
* current top menu and toolbar implementation
* current left and right sidebar responsibilities
* current Add Dataset UI
* current Export UI
* current export API response handling
* current theme implementation
* current layer card implementation
* current color picker behavior
* current pan / zoom / drag implementation
* current keyboard/mouse event handlers
* current annotation layer rendering logic
* current GT + detection drawing behavior
* current smooth video playback implementation
* current logo / favicon / assets setup
* current README image references

Before editing, summarize:

1. Current UI layout structure.
2. Current branding/name usage.
3. Current asset folder structure.
4. Current top menu / toolbar structure.
5. Current left and right panel responsibilities.
6. Current Add Dataset and Export flow.
7. Current export download behavior.
8. Current theme implementation.
9. Current layer card structure.
10. Current color picker behavior.
11. Current pan / zoom / drag behavior.
12. Current GT + det rendering behavior.
13. Files that need modification.
14. Risks or assumptions.

Only begin implementation after this summary.

---

# Phase 1 — Branch Setup

Work on a new branch.

Recommended branch:

```bash
feature/motscope-ui-refinement-v3
```

Commands:

```bash
cd /home/junja/mot_viewer
git status
git checkout -b feature/motscope-ui-refinement-v3
```

If the branch already exists, create a safe alternative:

```bash
git checkout -b feature/motscope-ui-refinement-v3-fix
```

Do not merge into `master` or `main`.

---

# Phase 2 — Add MOTScope Branding Assets

## Target

Add MOTScope logo assets into the repo.

Expected asset names:

```text
static/assets/motscope_logo_square.png
static/assets/motscope_logo_rect.png
static/assets/motscope_logo_square.svg
static/assets/motscope_logo_rect.svg
static/assets/favicon.svg
static/assets/favicon.png
docs/assets/motscope_logo_rect.png
docs/assets/motscope_logo_square.png
```

Use available logo files if they already exist locally.

If only PNG files exist, add PNG first and create SVG later if feasible.

Do not commit huge design source files unless necessary.

## Logo style

Use the selected MOTScope branding style:

* icon with bounding boxes / tracking dots
* teal → blue → purple color flow
* clean minimal design
* light background
* wordmark: `MOTScope`

Recommended brand colors:

```text
Teal:    #14B8A6
Blue:    #3B82F6
Violet:  #8B5CF6
Charcoal: #111827
Light background: #F8FAFC
Panel background: #FFFFFF
Border: #E5E7EB
```

## Important

If the current generated logo filename is different, copy/rename it into stable project paths.

Example:

```bash
mkdir -p static/assets docs/assets
cp /path/to/logo_rect.png static/assets/motscope_logo_rect.png
cp /path/to/logo_square.png static/assets/motscope_logo_square.png
cp static/assets/motscope_logo_rect.png docs/assets/motscope_logo_rect.png
cp static/assets/motscope_logo_square.png docs/assets/motscope_logo_square.png
```

The final app and README should not depend on temporary filenames.

---

# Phase 3 — Rename UI Branding from MOT Viewer to MOTScope

## Target

Use `MOTScope` as the product name in the UI.

Replace user-facing text:

```text
MOT Viewer
```

with:

```text
MOTScope
```

Apply to:

* browser title
* app header
* top menu brand
* README title
* navbar/logo area
* modal titles where relevant
* documentation references where appropriate

Do not rename repository folder unless explicitly required.

The repo can remain:

```text
mot_viewer
```

but the product UI should say:

```text
MOTScope
```

---

# Phase 4 — Add Logo to Web App Header

## Target

Add the MOTScope logo to the top-left of the app.

Recommended header structure:

```html
<div class="app-brand">
  <img src="/static/assets/motscope_logo_square.png" alt="MOTScope logo" class="app-logo" />
  <span class="app-title">MOTScope</span>
</div>
```

## Preferred layout

Top menu row should look like:

```text
[MOTScope logo] MOTScope     File     Dataset     View     Export     Help       Loaded frames=286
```

The logo should be compact and not make the top bar tall.

Recommended sizes:

```css
.app-logo {
  width: 28px;
  height: 28px;
}

.app-title {
  font-weight: 700;
  color: var(--text-main);
}
```

---

# Phase 5 — Add Logo to README Top

## Target

At the very top of `README.md`, show the rectangular MOTScope logo.

Add this before the main title:

```markdown
<p align="center">
  <img src="docs/assets/motscope_logo_rect.png" alt="MOTScope logo" width="720">
</p>

# MOTScope
```

Then update the short description:

```markdown
A lightweight visual inspection tool for multi-object tracking datasets, detections, and tracker outputs.
```

## README requirements

Update README references from:

```text
MOT Viewer
```

to:

```text
MOTScope
```

where user-facing.

Keep technical repo references if needed.

Update README sections to mention:

* light mode default
* dark mode option
* File → Add Dataset
* File → Export
* automatic export download
* layer card layout
* color picker behavior
* keyboard shortcuts

---

# Phase 6 — Design UI Theme to Fit MOTScope Logo

## Target

The UI should visually match the MOTScope logo.

Default theme should be light.

Style direction:

```text
clean
minimal
designer-like
white/gray panels
soft borders
teal/blue/purple accents
large central viewer
compact toolbar
draw.io-like layout
```

## Default light theme

Use CSS variables.

```css
:root,
:root[data-theme="light"] {
  --bg-app: #f8fafc;
  --bg-panel: #ffffff;
  --bg-toolbar: #ffffff;
  --bg-viewer: #eef2f7;
  --text-main: #111827;
  --text-muted: #6b7280;
  --border-main: #e5e7eb;
  --button-bg: #ffffff;
  --button-hover: #f3f4f6;
  --accent-teal: #14b8a6;
  --accent-blue: #3b82f6;
  --accent-violet: #8b5cf6;
  --accent-gradient: linear-gradient(90deg, #14b8a6, #3b82f6, #8b5cf6);
}
```

## Dark theme

Keep dark mode available:

```css
:root[data-theme="dark"] {
  --bg-app: #111827;
  --bg-panel: #161b22;
  --bg-toolbar: #0f172a;
  --bg-viewer: #020617;
  --text-main: #f9fafb;
  --text-muted: #9ca3af;
  --border-main: #334155;
  --button-bg: #1f2937;
  --button-hover: #374151;
  --accent-teal: #14b8a6;
  --accent-blue: #3b82f6;
  --accent-violet: #8b5cf6;
}
```

## Requirements

* app opens in light mode by default
* dark mode can be enabled from `View → Theme → Dark`
* selection persists with localStorage
* if no saved preference exists, use light mode
* do not force system dark mode on first load
* all modals and panels must be readable in both themes
* viewer stage can remain neutral gray or dark gray for video contrast

---

# Phase 7 — Make Top Menu and Toolbar Cleaner

## Current problem

The current top toolbar is too crowded.

It may contain large buttons such as:

```text
Add Dataset
Export
Frame Inspection
Prev
Play
Stop
Next
Speed
+
-
Pan
Rect
Refresh
```

## Target

Use a draw.io-style top structure:

```text
Row 1: Menu bar
[MOTScope logo] MOTScope | File | Dataset | View | Export | Help | Status

Row 2: Compact toolbar
Mode selector | Prev | Play/Pause | Next | Speed | Refresh
```

## Required changes

Remove these large permanent buttons from the top toolbar:

```text
Add Dataset
Export
+
-
Pan
Rect
```

Keep only compact viewer flow controls:

```text
Mode: [Frame Inspection ▼]   Prev   Play/Pause   Next   Speed: [0.25x ▼]   Refresh
```

Avoid large full-width buttons.

---

# Phase 8 — Move Add Dataset and Export into File Menu

## Target

Add Dataset and Export should be inside the File menu.

File menu structure:

```text
File
  Add Dataset...
  Export...
  Open Config Folder
  Refresh
```

## Add Dataset

Clicking:

```text
File → Add Dataset...
```

opens the Add Dataset modal.

## Export

Clicking:

```text
File → Export...
```

opens the Export modal.

Export modal should include:

* export target
* format
* annotation mode
* layer selection
* export button
* progress/status
* automatic download behavior
* fallback `Download again` link

---

# Phase 9 — Move Layers, Annotation Source, and Display to the Left

## Target left sidebar

The left sidebar should contain:

```text
Navigation
Layers
Annotation Source
Display
Review Jumps / Metadata if needed
```

Recommended order:

```text
LEFT SIDEBAR
├── Navigation
│   ├── Dataset
│   ├── Split
│   ├── Sequence
│   ├── Frame slider
│   └── Go to Frame
│
├── Layers
│   ├── Ground Truth card
│   └── Detections card
│
├── Annotation Source
│   ├── Legacy Type
│   └── Legacy File
│
├── Display
│   ├── Box base color
│   ├── Visibility color
│   └── Other display toggles
│
└── Review Jumps / Metadata
```

Right panel should be removed, collapsed by default, or reserved only for optional details.

Do not put Layers, Annotation Source, or Display on the right.

---

# Phase 10 — Redesign Layer Cards

## Current problem

`Visible` is a master switch but appears beside smaller drawing options.

## Target layer card

```text
┌────────────────────────────────────┐
│ ● Ground Truth        GT   [color] │
│                                    │
│ Layer visibility                   │
│ [✓] Show this layer                │
│                                    │
│ Display options                    │
│ [✓] Bounding box                   │
│ [✓] ID label                       │
│ [ ] Score label                    │
│                                    │
│ Score threshold                    │
│ Min score: 0.00                    │
│ [ slider ------------------ ]      │
└────────────────────────────────────┘
```

## Requirements

* rename `Visible` to `Show this layer`
* visually separate master visibility from display options
* group BBox / ID / Score under `Display options`
* put Min score slider under `Score threshold`
* hide or disable score threshold for GT if not useful
* header should show:

  * color dot
  * layer name
  * type badge such as `GT`, `DET`, `TRACK`
  * clickable color swatch

---

# Phase 11 — Fix Color Picker UX

## Target behavior

The color should update immediately as a live preview.

The color picker should remain open until:

```text
Apply
Cancel
Close / X
```

## Required behavior

When clicking a layer color swatch:

1. Open a sticky color picker popover or modal.
2. Store the original color.
3. Allow picking a new color.
4. Apply new color immediately as preview on overlay.
5. Keep picker open.
6. Apply commits and closes.
7. Cancel restores original and closes.
8. Reset restores default and keeps picker open.
9. Close / X behaves like Cancel.

## Manual hex input

Support valid hex input:

```text
#00ff00
#ff9900
#3b82f6
```

Invalid values should:

* not apply
* show a clear error
* keep picker open

Committed color should be used by:

* frame inspection mode
* smooth video mode
* export rendering
* layer panel color dot
* layer panel swatch

---

# Phase 12 — Move Pan / Rect / Zoom Controls Out of Top Toolbar

## Target

Remove these from top toolbar:

```text
+
-
Pan
Rect
```

Preserve pan / zoom / drag / selection behavior.

Move controls to:

```text
Floating viewer controls inside the main viewer
```

Preferred:

```text
[Fit] [100%] [+] [-] [Pan] [Rect]
```

Recommended placement:

```text
bottom-left of viewer stage
```

or:

```text
top-left inside viewer stage
```

Controls should be compact and not block important content.

---

# Phase 13 — Add Keyboard and Mouse Shortcuts

Implement:

```text
Ctrl + mouse wheel     zoom in/out around cursor
Ctrl + +               zoom in
Ctrl + -               zoom out
Ctrl + 0               fit/reset view
Shift + left drag      pan/drag image
Space + left drag      optional pan shortcut
```

Requirements:

* prevent browser page zoom when Ctrl+wheel is used inside viewer
* zoom around mouse cursor if possible
* pan and zoom work in frame inspection mode
* pan and zoom work in smooth video mode if possible
* overlay boxes stay aligned

Use shared viewport transform:

```javascript
viewport = {
  scale: 1,
  offsetX: 0,
  offsetY: 0
};
```

Apply the same transform to:

```text
image element
video element
canvas overlay
mouse coordinate conversion
box drawing
hover detection
```

---

# Phase 14 — Preserve Multi-Layer Drawing

All visible layers should draw together.

Correct logic:

```javascript
clearCanvas();

for (const layer of layers) {
  if (!visibleLayers[layer.name]) continue;

  const boxes = frameData[layer.name] || [];
  drawBoxesForLayer(boxes, layer);
}
```

Rules:

* clear canvas once per frame
* do not clear canvas once per layer
* do not store selected layer as a single string
* use visibility map or set
* score threshold applies per layer
* GT and Det must appear together with different colors

---

# Phase 15 — Export Auto-Download

## Target

After export completes, download should start automatically.

The user should not need to click:

```text
Download export
```

## Required behavior

When export succeeds:

1. Receive `download_url`.
2. Automatically trigger browser download.
3. Show message:

```text
Export complete. Download started.
```

4. Keep fallback link:

```text
Download again
```

5. If browser blocks automatic download, fallback link remains available.

## Recommended helper

```javascript
function triggerDownload(downloadUrl, filename = null) {
  const link = document.createElement("a");
  link.href = downloadUrl;
  if (filename) {
    link.download = filename;
  }
  document.body.appendChild(link);
  link.click();
  link.remove();
}
```

During export:

* disable Export button
* show exporting status
* prevent duplicate jobs from double-clicks
* re-enable after success or failure

---

# Phase 16 — Video Generation / Export Progress

For long operations, show progress.

Applies to:

* smooth video generation if triggered manually
* annotated video export
* whole sequence ZIP export if slow

Preferred UI:

```text
Exporting Annotated Video
[████████████--------] 60%
Rendering frame 450 / 750
Cancel
```

If real progress is difficult, provide at least:

* modal loading state
* spinner
* operation message
* disabled button
* complete/error state

---

# Phase 17 — Smooth Video Regression Check Only

The smooth video full-duration issue is already fixed.

Do not rework this feature unless a regression is found.

Regression check:

1. Smooth video still plays full duration.
2. Overlay remains synchronized.
3. Video cache still works.
4. Progress behavior does not break playback.
5. Do not reintroduce the old 2-second bug.

---

# Phase 18 — Documentation Update

Update README with MOTScope branding.

At the top, add:

```markdown
<p align="center">
  <img src="docs/assets/motscope_logo_rect.png" alt="MOTScope logo" width="720">
</p>

# MOTScope

A lightweight visual inspection tool for multi-object tracking datasets, detections, and tracker outputs.
```

Update sections for:

* MOTScope name
* logo assets
* File → Add Dataset
* File → Export
* automatic export download
* light mode default
* dark mode option
* layer card structure
* color picker behavior
* pan/zoom shortcuts
* GT + det overlay
* smooth video regression note

Add shortcut table:

| Shortcut           | Action              |
| ------------------ | ------------------- |
| Ctrl + mouse wheel | Zoom around cursor  |
| Ctrl + +           | Zoom in             |
| Ctrl + -           | Zoom out            |
| Ctrl + 0           | Fit/reset view      |
| Shift + left drag  | Pan/drag image      |
| Space + left drag  | Pan, if implemented |

---

# Phase 19 — Verification Checklist

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

1. App shows MOTScope branding.
2. Logo appears in the top-left app header.
3. README shows `docs/assets/motscope_logo_rect.png` at the top.
4. README title is MOTScope.
5. UI theme matches logo colors.
6. App opens in light mode when no saved theme exists.
7. Dark mode can be selected.
8. Theme persists after refresh.
9. Top menu looks cleaner and closer to draw.io.
10. Add Dataset is under File menu.
11. Export is under File menu.
12. Add Dataset opens a modal.
13. Export opens a modal.
14. Layers are on the left.
15. Annotation Source is on the left.
16. Display is on the left.
17. Layer card has clear sections.
18. `Show this layer` clearly acts as master switch.
19. Color picker stays open while selecting colors.
20. Color preview updates immediately.
21. Apply commits color.
22. Cancel restores old color.
23. Reset restores default color.
24. Pan/Rect/+/- are not on top toolbar.
25. Floating viewer controls exist.
26. Ctrl + wheel zooms in viewer.
27. Shift + drag pans image.
28. Overlay boxes stay aligned after zoom/pan.
29. GT and detections display together.
30. Export download starts automatically after completion.
31. Fallback link appears as `Download again`.
32. Export button is disabled during export.
33. Smooth video still plays full duration.
34. Video overlay stays synchronized.
35. App does not crash.

---

# Phase 20 — Commit and Push

Commit changes:

```bash
git status
git add .
git commit -m "Rebrand to MOTScope and refine UI experience"
```

Push branch:

```bash
git push -u origin feature/motscope-ui-refinement-v3
```

If a different branch is used, push that branch.

Do not merge into `master` or `main`.

---

# Final Report Required

At the end, provide:

1. Repository path.
2. Branch name.
3. Commit hash.
4. Files changed.
5. Logo asset paths added.
6. Confirmation app is rebranded as MOTScope.
7. Confirmation logo appears in app header.
8. Confirmation README has rectangular logo at top.
9. Summary of theme changes.
10. Confirmation light mode is default.
11. Confirmation dark mode remains available.
12. Top menu / toolbar changes.
13. Confirmation Add Dataset and Export are under File menu.
14. Confirmation Layers / Annotation Source / Display are on the left.
15. Layer card layout changes.
16. Color picker behavior.
17. Export download behavior.
18. Keyboard shortcuts implemented.
19. Pan / zoom / drag behavior.
20. Whether overlay alignment works after zoom/pan.
21. Whether GT + det display together.
22. Smooth video full-duration regression result.
23. Progress bar behavior.
24. Tests/checks run.
25. Known limitations.
26. Whether branch was pushed to GitHub.
27. Confirmation that it was not merged into master/main.
