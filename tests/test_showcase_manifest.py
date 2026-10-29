"""Unit tests for showcase manifest loading, inventory parsing, and path resolution."""

import json
from pathlib import Path

import pytest

from play_visualizer.showcase_manifest import (
    InventoryError,
    ManifestError,
    PathResolver,
    load_showcase_manifest,
    load_source_generation_statuses,
    load_video_inventory,
)


def test_load_showcase_manifest_default_packaged():
    """Verify that the packaged config/showcase_clips.json loads exactly 50 records."""
    records = load_showcase_manifest()
    assert len(records) == 50
    assert records[0].logical_clip_name == "BootPass_1"
    assert records[0].play_name == "BootPass"
    assert records[0].video_id == "1"

    # Verify no duplicates
    names = [r.logical_clip_name for r in records]
    assert len(names) == len(set(names))


def test_load_manifest_non_existent(tmp_path: Path):
    with pytest.raises(ManifestError, match="not found"):
        load_showcase_manifest(tmp_path / "missing.json")


def test_load_manifest_invalid_json(tmp_path: Path):
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("not json", encoding="utf-8")
    with pytest.raises(ManifestError, match="Failed to parse manifest"):
        load_showcase_manifest(bad_json)


def test_load_manifest_not_list(tmp_path: Path):
    bad_root = tmp_path / "dict_root.json"
    bad_root.write_text('{"records": []}', encoding="utf-8")
    with pytest.raises(ManifestError, match="must be a JSON array"):
        load_showcase_manifest(bad_root)


def test_load_manifest_duplicate_clip_names(tmp_path: Path):
    dup_manifest = tmp_path / "dups.json"
    data = [
        {"logical_clip_name": "Clip_1", "play_name": "PlayA", "video_id": "1"},
        {"logical_clip_name": "Clip_1", "play_name": "PlayA", "video_id": "2"},
    ]
    dup_manifest.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ManifestError, match="Duplicate logical_clip_name"):
        load_showcase_manifest(dup_manifest, enforce_exact_count=False)


def test_load_manifest_count_enforcement(tmp_path: Path):
    partial = tmp_path / "partial.json"
    data = [
        {"logical_clip_name": "Clip_1", "play_name": "PlayA", "video_id": "1"},
    ]
    partial.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ManifestError, match="Expected exactly 50"):
        load_showcase_manifest(partial, enforce_exact_count=True)

    records = load_showcase_manifest(partial, enforce_exact_count=False)
    assert len(records) == 1


def test_load_video_inventory(tmp_path: Path):
    csv_path = tmp_path / "inventory.csv"
    csv_content = """File Name,Google Drive File Path,Size (MB),Date Modified,File ID
Video Count=5132,Total Size=22.82 GB,,,"videos"
JetSweep_1.mp4,,4.67,2026-08-01 19:43:00,id_jetsweep_1
Power_3.mp4,,5.12,2026-08-01 19:45:00,id_power_3
"""
    csv_path.write_text(csv_content, encoding="utf-8")
    inventory = load_video_inventory(csv_path)

    assert "JetSweep_1.mp4" in inventory
    assert inventory["JetSweep_1.mp4"].file_id == "id_jetsweep_1"
    assert inventory["JetSweep_1.mp4"].size_mb == 4.67
    assert "Power_3.mp4" in inventory
    assert inventory["Power_3.mp4"].file_id == "id_power_3"
    # Summary row excluded
    assert not any("video count" in k.lower() for k in inventory)


def test_load_video_inventory_missing(tmp_path: Path):
    with pytest.raises(InventoryError, match="not found"):
        load_video_inventory(tmp_path / "missing_inv.csv")

    assert load_video_inventory(None) == {}


def test_path_resolver(tmp_path: Path):
    videos_root = tmp_path / "videos"
    annotations_root = tmp_path / "annotations"
    output_root = tmp_path / "outputs"
    scratch_root = tmp_path / "scratch"

    resolver = PathResolver(
        videos_root=videos_root,
        annotations_root=annotations_root,
        output_root=output_root,
        scratch_root=scratch_root,
    )

    v_path = resolver.resolve_video_path("JetSweep_1")
    assert v_path == videos_root / "JetSweep_1.mp4"

    a_path = resolver.resolve_annotation_path("JetSweep", "JetSweep_1")
    assert a_path == annotations_root / "JetSweep" / "JetSweep_1" / "annotations.json"

    o_video = resolver.resolve_output_video_path("JetSweep", "JetSweep_1")
    assert o_video == output_root / "JetSweep" / "JetSweep_1.mp4"

    o_report = resolver.resolve_output_report_path("JetSweep", "JetSweep_1")
    assert o_report == output_root / "JetSweep" / "JetSweep_1.report.json"

    staging = resolver.resolve_staging_dir("JetSweep_1")
    assert staging == scratch_root / "staging" / "JetSweep_1"


def test_path_resolver_traversal_detection(tmp_path: Path):
    resolver = PathResolver(
        videos_root=tmp_path / "videos",
        annotations_root=tmp_path / "annotations",
        output_root=tmp_path / "outputs",
    )
    with pytest.raises(ValueError, match="Path traversal"):
        resolver.resolve_video_path("../escape")
    with pytest.raises(ValueError, match="Path traversal"):
        resolver.resolve_annotation_path("..", "clip")


def test_load_source_generation_statuses(tmp_path: Path):
    summary_path = tmp_path / "showcase_summary.json"
    data = [
        {
            "clip_name": "Clip_1",
            "status": "WARNING",
            "errors_count": 0,
            "warnings_count": 2,
            "warnings": ["warn 1", "warn 2"],
        }
    ]
    summary_path.write_text(json.dumps(data), encoding="utf-8")
    statuses = load_source_generation_statuses(tmp_path)
    assert "Clip_1" in statuses
    assert statuses["Clip_1"]["status"] == "WARNING"
    assert statuses["Clip_1"]["warnings_count"] == 2

