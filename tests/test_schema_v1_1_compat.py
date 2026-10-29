"""Compatibility tests against real finalized v1.1 annotation JSON files."""

from pathlib import Path

import pytest

from play_visualizer.annotation_index import AnnotationIndex
from play_visualizer.annotation_loader import load_annotation_file
from play_visualizer.models import VideoMetadata
from play_visualizer.validator import InputValidator

REPO_ROOT = Path(__file__).resolve().parent.parent
ANNOTATIONS_DIR = REPO_ROOT / "annotations"

REAL_SHOWCASE_SAMPLES = [
    ("BootPass", "BootPass_1"),
    ("JetSweep", "JetSweep_1"),
    ("Power", "Power_3"),
    ("Power", "Power_4"),
    ("Post10to15", "Post10to15_1"),
    ("PuntBlock", "PuntBlock_1"),
    ("KickoffReturnTouchdown", "KickoffReturnTouchdown_17"),
]


@pytest.mark.parametrize("play_name,clip_name", REAL_SHOWCASE_SAMPLES)
def test_real_annotation_schema_v1_1_compatibility(play_name: str, clip_name: str):
    """Verify that real finalized v1.1 annotation JSONs load and index cleanly."""
    json_path = ANNOTATIONS_DIR / play_name / clip_name / "annotations.json"
    if not json_path.exists():
        pytest.skip(f"Annotation file not found: {json_path}")

    pkg = load_annotation_file(json_path)

    # Validate top-level schema and metadata
    assert pkg.schema_version == "tapevision_annotation_enrichment_v1.1"
    assert pkg.clip.video_name == clip_name
    assert pkg.clip.num_frames > 0
    assert pkg.clip.frame_end >= pkg.clip.frame_start

    # Verify tracks and action segments
    assert len(pkg.players) > 0
    assert len(pkg.dense_annotations) > 0

    # Build index and verify annotated frames can be retrieved
    index = AnnotationIndex(pkg)
    first_annotated_frame = pkg.dense_annotations[0].frame
    first_anns = index.for_frame(first_annotated_frame)
    assert len(first_anns) > 0

    # Verify validator works with this schema
    video_meta = VideoMetadata(
        fps=30.0,
        width=1920,
        height=1080,
        num_frames=pkg.clip.num_frames,
        duration_seconds=pkg.clip.num_frames / 30.0,
        has_audio=False,
    )
    validator = InputValidator(video_meta=video_meta, pkg=pkg, index=index)
    start_frame, end_frame, warnings = validator.validate_all()

    assert start_frame == pkg.clip.frame_start
    assert end_frame == min(video_meta.num_frames - 1, pkg.clip.frame_end)
