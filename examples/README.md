# TapeVision Visualizer Examples

This directory contains example input files and instructions for running the visualizer.

## Usage Example

Place your video file (`JetSweep_1.mp4`) in this directory or reference it directly from another path.

Run Portfolio Mode:
```bash
python -m tapevision_visualizer \
  --video ./examples/JetSweep_1.mp4 \
  --annotations ./examples/tapevision_annotations.json \
  --output ./output/JetSweep_1_TapeVision_Demo.mp4 \
  --mode portfolio \
  --overwrite
```


