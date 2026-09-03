"""Unit tests for annotation index."""

from pathlib import Path

from tapevision_visualizer.annotation_index import AnnotationIndex
from tapevision_visualizer.annotation_loader import load_annotation_file
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
