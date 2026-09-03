# TapeVision Annotation Video Visualizer (`tapevision-visualizer`)

`tapevision-visualizer` is a modular, high-performance Python application designed to render TapeVision football annotations onto source video clips. It generates polished broadcast-grade video demonstrations featuring thin action-colored player bounding boxes, persistent track IDs (`POSITION | TRACK_ID`), human-readable action labels, play metadata cards, a `LIVE ACTIONS` color legend panel, and play progress timelines with frame numbers.

---

## 1. Features

- **Modern Telestration Aesthetic**: Polished, clutter-free broadcast presentation featuring thin 1–2 px action-colored bounding boxes, single-line `{POSITION} | {TRACK_ID}` player labels, compact 2-line Play Information Cards, and a dynamic `LIVE ACTIONS` color legend.
- **Zero-Based Frame Alignment**: Accurate zero-indexed frame mapping ensuring frame-exact annotation overlay.
- **Timeline Frame Counters**: Bottom progress timeline displaying live frame status (`F: 192 / 329`) and exact frame numbers next to key event markers (`Snap (f:45)`, `Handoff (f:92)`, `Out of Bounds (f:329)`).
- **Frame Indexing**: Pre-indexed in-memory frame lookup (`dict[int, list[DenseFrameAnnotation]]`) for fast frame streaming.
- **Action Formatting & Color Mapping**: Automatic action color mapping from JSON (`action_labels.json`) with priority-based panel sorting.
- **FFmpeg Integration**: OpenCV intermediate frame rendering combined with FFmpeg H.264 (`libx264`, `yuv420p`, CRF 18) encoding and original source audio preservation.
- **Quality Warnings & Run Reports**: Automated validation checking for frame count mismatches, suspicious defense actions, and missing ball samples with machine-readable JSON run reports (`.report.json`).

---

## 2. Prerequisites & System Dependencies

### System Requirements
- **Python**: 3.11 or newer.
- **FFmpeg**: External system dependency required for final H.264 video encoding and audio muxing.

#### Installing FFmpeg

- **macOS**:
  ```bash
  brew install ffmpeg
  ```
- **Ubuntu/Debian**:
  ```bash
  sudo apt update && sudo apt install -y ffmpeg
  ```
- **Windows**: Download build from [FFmpeg Official Website](https://ffmpeg.org/download.html) and add to `PATH`.

---

## 3. Installation

Clone or locate the repository and install dependencies in your virtual environment:

```bash
cd /Users/alejandro/Desktop/Projects/FilmBreakdownAI/Utilities/Visualizer

# Create virtual environment (optional)
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies and package in editable mode
pip install -e .
```

To install development dependencies (testing and linting):
```bash
pip install -e ".[dev]"
```

---

## 4. Quick Start CLI Usage

### Basic CLI Command

```bash
tapevision-visualizer \
  --video path/to/JetSweep_1.mp4 \
  --annotations path/to/tapevision_annotations.json \
  --output output/JetSweep_1_TapeVision_Demo.mp4 \
  --overwrite
```

Or run via Python module:

```bash
python -m tapevision_visualizer \
  --video ./examples/JetSweep_1.mp4 \
  --annotations ./examples/tapevision_annotations.json \
  --output ./output/JetSweep_1_TapeVision_Demo.mp4 \
  --overwrite
```

### Dry Run (Validation Only)

Validate inputs and generate `.report.json` without rendering video:

```bash
python -m tapevision_visualizer \
  --video ./examples/JetSweep_1.mp4 \
  --annotations ./examples/tapevision_annotations.json \
  --output ./output/JetSweep_1_Test.mp4 \
  --dry-run
```

---

## 5. Command-Line Arguments Reference

| Argument | Short | Type | Default | Description |
|---|---|---|---|---|
| `--video` | `-v` | Path | *Required* | Path to source video MP4. |
| `--annotations` | `-a` | Path | *Required* | Path to TapeVision annotation JSON. |
| `--output` | `-o` | Path | *Required* | Path for output annotated MP4. |
| `--config` | `-c` | Path | Built-in | Custom YAML configuration path. |
| `--action-labels` | | Path | Built-in | Custom action labels JSON file path containing action colors. |
| `--start-frame` | | Int | Clip start | First frame to render (zero-based). |
| `--end-frame` | | Int | Clip end | Last frame to render (zero-based). |
| `--include-unannotated-tail` | | Flag | `false` | Keep video frames after the last annotated frame. |
| `--show-defense` | | Flag | `true` | Display defensive player bounding boxes. |
| `--show-offense` | | Flag | `true` | Display offensive player bounding boxes. |
| `--show-action-panel` | | Flag | `true` | Display top-right LIVE ACTIONS panel. |
| `--show-timeline` | | Flag | `true` | Display bottom progress timeline. |
| `--dry-run` | | Flag | `false` | Validate inputs without rendering video. |
| `--overwrite` | | Flag | `false` | Permit overwriting existing output files. |
| `--log-level` | | String | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |


---

## 6. Configuration

Visual styling, fonts, colors, panel limits, and FFmpeg encoding presets are controlled by `config/default_visualization.yaml`. You can copy and customize this YAML file:

```yaml
styles:
  offense:
    box_color: [46, 204, 113]       # BGR Green
  defense:
    box_color: [231, 76, 60]        # BGR Red
  active_highlight:
    box_color: [241, 196, 15]       # BGR Gold

hidden_actions:
  portfolio:
    - Action_None
    - Action_Unknown
    - Action_Defense_NotAnnotated

ffmpeg:
  crf: 18
  preset: medium
  pix_fmt: yuv420p
```

---

## 7. Frame Mismatches & Edge Cases

### Video vs. JSON Frame Mismatch
Source football clips may have unannotated frames at the tail end. For example:
- **Source Video**: 360 frames (0–359)
- **TapeVision JSON**: 330 frames (0–329)

**Default Behavior**: The visualizer calculates the intersection range (frames 0–329), renders those frames with annotations, and logs a frame mismatch warning in `output.report.json`. To include the unannotated tail frames, supply `--include-unannotated-tail`.

### Missing Ball Annotations
If `tracks.ball` is empty or lacks frame samples, the visualizer logs an informational warning and continues rendering player annotations without crashing.

---

## 8. Development & Testing

Run unit tests and end-to-end smoke tests using pytest:

```bash
pytest -v
```

Run code quality linting with Ruff:

```bash
ruff check .
```

Run static type checking with mypy:

```bash
mypy src/tapevision_visualizer
```

---

## 9. Extending for Future Play Types

To add support for new play types or action labels:
1. Add raw action label mappings to `EXPLICIT_ACTION_MAP` in `src/tapevision_visualizer/action_formatter.py`.
2. Update key action priority ranking in `config/default_visualization.yaml`.
3. The fallback formatter automatically splits PascalCase labels (`Action_RunAfterCatch` -> `Run After Catch`) for unlisted actions.
