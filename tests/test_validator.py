"""Unit tests for validator and coordinate clamping."""

from pathlib import Path

from play_visualizer.annotation_index import AnnotationIndex
from play_visualizer.annotation_loader import load_annotation_file
from play_visualizer.models import VideoMetadata
from play_visualizer.validator import InputValidator, clamp_bbox
from tests.fixtures.synthetic_sample import create_synthetic_annotation


def test_clamp_bbox_valid():
    box = (10.0, 20.0, 100.0, 200.0)
    clamped = clamp_bbox(box, width=640, height=480)
    assert clamped == (10.0, 20.0, 100.0, 200.0)


def test_clamp_bbox_out_of_bounds():
    box = (-10.0, -20.0, 700.0, 500.0)
    clamped = clamp_bbox(box, width=640, height=480)
    assert clamped == (0.0, 0.0, 640.0, 480.0)


def test_clamp_bbox_invalid_nan_inf():
    assert clamp_bbox((float("nan"), 10.0, 50.0, 50.0), 640, 480) is None
    assert clamp_bbox((10.0, float("inf"), 50.0, 50.0), 640, 480) is None


def test_input_validator(tmp_path: Path):
    json_path = tmp_path / "sample.json"
    create_synthetic_annotation(json_path, num_frames=30)
    pkg = load_annotation_file(json_path)
    index = AnnotationIndex(pkg)

    video_meta = VideoMetadata(
        fps=30.0,
        width=640,
        height=480,
        num_frames=30,
        duration_seconds=1.0,
        has_audio=False,
    )

    validator = InputValidator(video_meta=video_meta, pkg=pkg, index=index)
    start_frame, end_frame, warnings = validator.validate_all()

    assert start_frame == 0
    assert end_frame == 29
