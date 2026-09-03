"""Unit tests for annotation loader."""

from pathlib import Path

import pytest

from tapevision_visualizer.annotation_loader import AnnotationLoadError, load_annotation_file
from tests.fixtures.synthetic_sample import create_synthetic_annotation


def test_load_valid_annotation(tmp_path: Path):
    json_path = tmp_path / "sample.json"
    create_synthetic_annotation(json_path, num_frames=10)

    pkg = load_annotation_file(json_path)

    assert pkg.schema_version == "tapevision_annotation_enrichment_v1.0"
    assert pkg.clip.num_frames == 10
    assert pkg.play.play_tag == "Play_Run_JetSweep"
    assert len(pkg.players) == 2
    assert len(pkg.dense_annotations) == 20


def test_load_non_existent_file(tmp_path: Path):
    json_path = tmp_path / "does_not_exist.json"
    with pytest.raises(AnnotationLoadError, match="not found"):
        load_annotation_file(json_path)


def test_load_invalid_json(tmp_path: Path):
    json_path = tmp_path / "bad.json"
    json_path.write_text("not json content", encoding="utf-8")

    with pytest.raises(AnnotationLoadError, match="Failed to parse JSON"):
        load_annotation_file(json_path)
