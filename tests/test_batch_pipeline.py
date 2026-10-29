"""Unit and integration tests for BatchPipeline preflight, execution, and failure isolation."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from play_visualizer.batch_models import (
    BatchRenderStatus,
    PreflightStatus,
    ShowcaseClipManifestRecord,
)
from play_visualizer.batch_pipeline import (
    BatchPipeline,
    compute_file_sha256,
    compute_input_fingerprint,
    probe_video_metadata,
)
from play_visualizer.models import RenderReport
from tests.fixtures.synthetic_sample import create_synthetic_annotation


def test_compute_file_sha256(tmp_path: Path):
    f = tmp_path / "test.txt"
    f.write_text("hello world", encoding="utf-8")
    h = compute_file_sha256(f)
    assert len(h) == 64
    assert isinstance(h, str)


def test_compute_input_fingerprint(tmp_path: Path):
    v = tmp_path / "video.mp4"
    v.write_bytes(b"dummy video data")
    a = tmp_path / "ann.json"
    create_synthetic_annotation(a, num_frames=5)

    fp1 = compute_input_fingerprint(v, a)
    fp2 = compute_input_fingerprint(v, a)
    assert fp1.combined_hash == fp2.combined_hash

    # Modify annotation -> fingerprint must change
    create_synthetic_annotation(a, num_frames=10)
    fp3 = compute_input_fingerprint(v, a)
    assert fp1.combined_hash != fp3.combined_hash


def test_batch_pipeline_init_config_validation(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="Provided configuration file not found"):
        BatchPipeline(
            videos_root=tmp_path / "videos",
            annotations_root=tmp_path / "annotations",
            output_root=tmp_path / "outputs",
            config_path=tmp_path / "missing_config.yaml",
        )


def test_batch_pipeline_load_manifest_subset(tmp_path: Path):
    manifest_path = tmp_path / "manifest.json"
    manifest_data = [
        {"logical_clip_name": "Clip_A", "play_name": "PlayA", "video_id": "1"},
        {"logical_clip_name": "Clip_B", "play_name": "PlayB", "video_id": "2"},
    ]
    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

    pipeline = BatchPipeline(
        videos_root=tmp_path / "videos",
        annotations_root=tmp_path / "annotations",
        output_root=tmp_path / "outputs",
        manifest_path=manifest_path,
    )

    records = pipeline.load_manifest_records(clip_filter=["Clip_A"])
    assert len(records) == 1
    assert records[0].logical_clip_name == "Clip_A"

    with pytest.raises(ValueError, match="Requested clip.*not found"):
        pipeline.load_manifest_records(clip_filter=["NonExistentClip"])


def test_batch_pipeline_preflight_missing_files(tmp_path: Path):
    manifest_path = tmp_path / "manifest.json"
    manifest_data = [
        {"logical_clip_name": "Clip_A", "play_name": "PlayA", "video_id": "1"},
    ]
    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

    pipeline = BatchPipeline(
        videos_root=tmp_path / "videos",
        annotations_root=tmp_path / "annotations",
        output_root=tmp_path / "outputs",
        manifest_path=manifest_path,
    )

    records = pipeline.load_manifest_records(enforce_exact_count=False)
    preflight = pipeline.preflight_batch(records)

    assert len(preflight) == 1
    res = preflight[0]
    assert res.status == PreflightStatus.FAILED
    assert any("MISSING_VIDEO" in e for e in res.errors)
    assert any("MISSING_ANNOTATION" in e for e in res.errors)


def test_batch_pipeline_dry_run_success(tmp_path: Path):
    videos_root = tmp_path / "videos"
    videos_root.mkdir()
    v1 = videos_root / "Clip_1.mp4"
    v1.write_bytes(b"dummy")

    annotations_root = tmp_path / "annotations"
    a1 = annotations_root / "PlayA" / "Clip_1" / "annotations.json"
    create_synthetic_annotation(a1, num_frames=5)
    # Fix video_name in JSON to match Clip_1
    d = json.loads(a1.read_text(encoding="utf-8"))
    d["clip"]["video_name"] = "Clip_1"
    a1.write_text(json.dumps(d), encoding="utf-8")

    manifest_path = tmp_path / "manifest.json"
    manifest_data = [
        {"logical_clip_name": "Clip_1", "play_name": "PlayA", "video_id": "1"},
    ]
    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

    output_root = tmp_path / "outputs"

    pipeline = BatchPipeline(
        videos_root=videos_root,
        annotations_root=annotations_root,
        output_root=output_root,
        scratch_root=tmp_path / "scratch",
        manifest_path=manifest_path,
    )

    summary = pipeline.run_batch(dry_run=True, enforce_exact_count=False)
    assert summary.dry_run is True
    assert summary.selected_count == 1
    assert summary.clip_results[0].preflight_status == PreflightStatus.READY
    assert summary.clip_results[0].render_status == BatchRenderStatus.READY
    # In dry-run, output video should NOT be created
    dest_video = output_root / "PlayA" / "Clip_1.mp4"
    assert not dest_video.exists()


def test_batch_pipeline_failure_isolation(tmp_path: Path):
    videos_root = tmp_path / "videos"
    videos_root.mkdir()
    v2 = videos_root / "Clip_2.mp4"
    v2.write_bytes(b"dummy")

    annotations_root = tmp_path / "annotations"
    a2 = annotations_root / "PlayB" / "Clip_2" / "annotations.json"
    create_synthetic_annotation(a2, num_frames=5)
    d = json.loads(a2.read_text(encoding="utf-8"))
    d["clip"]["video_name"] = "Clip_2"
    a2.write_text(json.dumps(d), encoding="utf-8")

    manifest_path = tmp_path / "manifest.json"
    # Clip_1 is missing video/annotations; Clip_2 has them
    manifest_data = [
        {"logical_clip_name": "Clip_1", "play_name": "PlayA", "video_id": "1"},
        {"logical_clip_name": "Clip_2", "play_name": "PlayB", "video_id": "2"},
    ]
    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

    output_root = tmp_path / "outputs"

    pipeline = BatchPipeline(
        videos_root=videos_root,
        annotations_root=annotations_root,
        output_root=output_root,
        scratch_root=tmp_path / "scratch",
        manifest_path=manifest_path,
    )

    # In dry-run mode, both should be processed and reported without stopping at Clip_1
    summary = pipeline.run_batch(dry_run=True, enforce_exact_count=False)
    assert len(summary.clip_results) == 2
    assert summary.clip_results[0].clip_name == "Clip_1"
    assert summary.clip_results[0].preflight_status == PreflightStatus.FAILED
    assert summary.clip_results[1].clip_name == "Clip_2"
    assert summary.clip_results[1].preflight_status == PreflightStatus.READY
