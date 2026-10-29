"""Unit tests for annotation index."""

from pathlib import Path

from play_visualizer.annotation_index import AnnotationIndex
from play_visualizer.annotation_loader import load_annotation_file
from tests.fixtures.synthetic_sample import create_synthetic_annotation


def test_annotation_index_lookup(tmp_path: Path):
    json_path = tmp_path / "sample.json"
    create_synthetic_annotation(json_path, num_frames=5)

    pkg = load_annotation_file(json_path)
    index = AnnotationIndex(pkg)

    # Verify frame 0 lookup returns 2 player annotations
    frame0_anns = index.for_frame(0)
    assert len(frame0_anns) == 2

    # Verify actor metadata lookup
    actor1_info = index.get_actor_info("1")
    assert actor1_info["position"] == "QB"
    assert actor1_info["team_side"] == "offense"


def test_annotation_index_deduplication(tmp_path: Path):
    json_path = tmp_path / "sample.json"
    create_synthetic_annotation(json_path, num_frames=2)

    pkg = load_annotation_file(json_path)
    # Add a duplicate annotation manually
    pkg.dense_annotations.append(pkg.dense_annotations[0].model_copy())

    index = AnnotationIndex(pkg)
    assert index.duplicate_count == 1
    assert len(index.for_frame(0)) == 2


def test_annotation_index_fallback_when_dense_empty(tmp_path: Path):
    """Verify fallback indexing when dense_annotations is empty (tests p_sample.frame fix)."""
    json_path = tmp_path / "sample.json"
    create_synthetic_annotation(json_path, num_frames=3)

    pkg = load_annotation_file(json_path)
    pkg.dense_annotations.clear()

    index = AnnotationIndex(pkg)
    assert index.is_fallback is True
    # Should index samples by player track samples
    frame0_anns = index.for_frame(0)
    assert len(frame0_anns) == 2
    assert frame0_anns[0].frame == 0
    assert frame0_anns[0].action == "Action_Unknown"
    frame1_anns = index.for_frame(1)
    assert len(frame1_anns) == 2
    assert frame1_anns[0].frame == 1
