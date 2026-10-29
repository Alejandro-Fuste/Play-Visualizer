# Play-Visualizer

`Play-Visualizer` is a modular, high-performance Python application designed to render football annotations onto source video clips. It generates polished broadcast-grade video demonstrations featuring thin action-colored player bounding boxes, persistent track IDs (`POSITION | TRACK_ID`), human-readable action labels, play metadata cards, a `LIVE ACTIONS` color legend panel, and play progress timelines with frame numbers.

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
cd /Users/alejandro/Desktop/Projects/FilmBreakdownAI/Utilities/Play-Visualizer

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
play-visualizer \
  --video path/to/JetSweep_1.mp4 \
  --annotations path/to/annotations.json \
  --output output/JetSweep_1_PlayVisualizer_Demo.mp4 \
  --overwrite
```

Or run via Python module:

```bash
python -m play_visualizer \
  --video ./examples/JetSweep_1.mp4 \
  --annotations ./examples/annotations.json \
  --output ./output/JetSweep_1_PlayVisualizer_Demo.mp4 \
  --overwrite
```

### Dry Run (Validation Only)

Validate inputs and generate `.report.json` without rendering video:

```bash
python -m play_visualizer \
  --video ./examples/JetSweep_1.mp4 \
  --annotations ./examples/annotations.json \
  --output ./output/JetSweep_1_Test.mp4 \
  --dry-run
```

---

## 5. Google Colab Showcase Batch Workflow

`Play-Visualizer` provides a Google Colab-compatible batch-rendering pipeline that processes the **50 finalized showcase clips** sequentially with failure isolation, SHA-256 input fingerprinting, resume capabilities, and atomic persistence to Google Drive.

### 5.1 Colab Notebook

The notebook is located at [`notebooks/showcase_batch_colab.ipynb`](file:///Users/alejandro/Desktop/Projects/FilmBreakdownAI/Utilities/Play-Visualizer/notebooks/showcase_batch_colab.ipynb). It provides 8 numbered execution cells:
1. **Configuration**: Configures Drive paths, local scratch directory (`/content/play_visualizer_batch`), and overlay settings.
2. **Mount Google Drive**: Mounts `/content/drive` interactively.
3. **Clone & Install**: Installs `play-visualizer` in editable mode and verifies `ffmpeg` and `ffprobe`.
4. **Access Checks**: Confirms that `VIDEOS_ROOT`, `ANNOTATIONS_ROOT`, and sample showcase clips exist.
5. **Full Showcase Dry-Run**: Validates manifest, inventory, file existence, and schema v1.1 without rendering MP4s.
6. **Representative Test Batch**: Renders a 5–6 clip QA subset (`JetSweep_1`, `Post10to15_1`, `Power_3`, `PuntBlock_1`, `KickoffReturnTouchdown_17`, `Power_4`).
7. **Full 50-Clip Batch Render**: Sequentially renders all 50 showcase clips with `--resume` enabled.
8. **Results & In-Notebook Video Player**: Formats the final Markdown audit summary and embeds an HTML5 player to preview rendered clips.

### 5.2 Showcase Batch CLI (`play-visualizer-showcase-batch`)

The batch workflow can also be run directly from the command line:

```bash
# Full 50-clip dry-run preflight
play-visualizer-showcase-batch \
  --videos-root /content/drive/MyDrive/.../videos \
  --annotations-root /content/drive/MyDrive/.../Play-Visualizer/annotations \
  --output-root /content/drive/MyDrive/.../Play-Visualizer/outputs/showcase \
  --scratch-root /content/play_visualizer_batch \
  --manifest /content/Play-Visualizer/config/showcase_clips.json \
  --inventory /content/drive/MyDrive/.../Play-Visualizer/1_Videos_Inventory.csv \
  --dry-run

# Representative subset render (5 clips) with resume protection
play-visualizer-showcase-batch \
  --videos-root /content/drive/MyDrive/.../videos \
  --annotations-root /content/drive/MyDrive/.../Play-Visualizer/annotations \
  --output-root /content/drive/MyDrive/.../Play-Visualizer/outputs/showcase \
  --clips JetSweep_1,Post10to15_1,Power_3,PuntBlock_1,KickoffReturnTouchdown_17 \
  --resume

# Full 50-clip showcase rendering
play-visualizer-showcase-batch \
  --videos-root /content/drive/MyDrive/.../videos \
  --annotations-root /content/drive/MyDrive/.../Play-Visualizer/annotations \
  --output-root /content/drive/MyDrive/.../Play-Visualizer/outputs/showcase \
  --resume
```

### 5.3 Batch CLI Options Reference

| Argument | Description |
|---|---|
| `--videos-root` | Path to directory containing source football videos (`{ClipName}.mp4`). **Required**. |
| `--annotations-root` | Path to annotations directory (`{PlayName}/{ClipName}/annotations.json`). **Required**. |
| `--output-root` | Persistent Google Drive directory for output videos and reports. **Required**. |
| `--manifest` | Path to `showcase_clips.json` (defaults to bundled `config/showcase_clips.json`). |
| `--inventory` | Path to `1_Videos_Inventory.csv` for provenance and Google Drive File ID mapping. |
| `--scratch-root` | Fast local SSD directory for staging (`/content/play_visualizer_batch`). |
| `--clip` / `--clips` | Process specific clip(s) for quick verification (e.g. `--clips JetSweep_1,Power_3`). |
| `--dry-run` | Audits entire batch without producing MP4s. Writes validation summary. |
| `--resume` | Skips clips where output MP4 and report exist and match input SHA-256 fingerprint. |
| `--overwrite` | Replaces existing outputs using safe local staging and atomic commit. |
| `--show-timeline / --hide-timeline` | Toggle bottom progress timeline with frame markers (default: hidden). |
| `--show-offense / --hide-offense` | Toggle offensive player bounding boxes (default: shown). |
| `--show-defense / --hide-defense` | Toggle defensive player bounding boxes (default: shown). |
| `--show-action-panel / --hide-action-panel` | Toggle LIVE ACTIONS legend panel in upper-right (default: shown). |

---

## 6. Single-Video CLI Arguments Reference

| Argument | Short | Type | Default | Description |
|---|---|---|---|---|
| `--video` | `-v` | Path | *Required* | Path to source video MP4. |
| `--annotations` | `-a` | Path | *Required* | Path to annotation JSON. |
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

## 7. Configuration

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
    - Action_Unknown
    - Action_Defense_NotAnnotated

ffmpeg:
  crf: 18
  preset: medium
  pix_fmt: yuv420p
```

---

## 8. Frame Mismatches & Edge Cases

### Video vs. JSON Frame Mismatch
Source football clips may have unannotated frames at the tail end. For example:
- **Source Video**: 360 frames (0–359)
- **Annotation JSON**: 330 frames (0–329)

**Default Behavior**: The visualizer calculates the intersection range (frames 0–329), renders those frames with annotations, and logs a frame mismatch warning in `output.report.json`. To include the unannotated tail frames, supply `--include-unannotated-tail`.

### Missing Ball Annotations
If `tracks.ball` is empty or lacks frame samples, the visualizer logs an informational warning and continues rendering player annotations without crashing.

---

## 9. Development & Testing

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
mypy src/play_visualizer
```

---

## 10. Extending for Future Play Types

To add support for new play types or action labels:
1. Add raw action label mappings to `EXPLICIT_ACTION_MAP` in `src/play_visualizer/action_formatter.py`.
2. Update key action priority ranking in `config/default_visualization.yaml`.
3. The fallback formatter automatically splits PascalCase labels (`Action_RunAfterCatch` -> `Run After Catch`) for unlisted actions.
