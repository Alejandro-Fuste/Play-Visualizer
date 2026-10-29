"""Unit tests for batch resume, overwrite protection, and fingerprint verification."""

import json
from pathlib import Path

import pytest

from play_visualizer.batch_models import (
    BatchRenderStatus,
    ClipBatchResult,
    PreflightStatus,
    ShowcaseClipManifestRecord,
)
from play_visualizer.batch_pipeline import BatchPipeline, compute_input_fingerprint
from tests.fixtures.synthetic_sample import create_synthetic_annotation


def test_resume_skips_verified_identical_output(tmp_path: Path):
    videos_root = tmp_path / "videos"
    videos_root.mkdir()
    v1 = videos_root / "Clip_1.mp4"
    v1.write_bytes(b"dummy video content")

    annotations_root = tmp_path / "annotations"
    a1 = annotations_root / "PlayA" / "Clip_1" / "annotations.json"
    create_synthetic_annotation(a1, num_frames=5)
    d = json.loads(a1.read_text(encoding="utf-8"))
    d["clip"]["video_name"] = "Clip_1"
    a1.write_text(json.dumps(d), encoding="utf-8")

    output_root = tmp_path / "outputs"
    dest_video = output_root / "PlayA" / "Clip_1.mp4"
    dest_report = output_root / "PlayA" / "Clip_1.report.json"
    dest_video.parent.mkdir(parents=True, exist_ok=True)
    dest_video.write_bytes(b"rendered video content")

    fp = compute_input_fingerprint(v1, a1)
    rep_data = ClipBatchResult(
        clip_name="Clip_1",
        play_name="PlayA",
        render_status=BatchRenderStatus.SUCCESS,
        rendered_frames=5,
        output_video=str(dest_video),
        output_report=str(dest_report),
        input_fingerprint=fp.combined_hash,
    ).model_dump()
    dest_report.write_text(json.dumps(rep_data), encoding="utf-8")

    manifest_path = tmp_path / "manifest.json"
    manifest_data = [
        {"logical_clip_name": "Clip_1", "play_name": "PlayA", "video_id": "1"},
    ]
    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

    pipeline = BatchPipeline(
        videos_root=videos_root,
        annotations_root=annotations_root,
        output_root=output_root,
        scratch_root=tmp_path / "scratch",
        manifest_path=manifest_path,
    )

    can_skip, skipped_result = pipeline.check_resume_skip("Clip_1", "PlayA", fp.combined_hash)
    assert can_skip is True
    assert skipped_result is not None
    assert skipped_result.render_status == BatchRenderStatus.SKIPPED


def test_resume_does_not_skip_on_fingerprint_mismatch(tmp_path: Path):
    videos_root = tmp_path / "videos"
    videos_root.mkdir()
    v1 = videos_root / "Clip_1.mp4"
    v1.write_bytes(b"dummy video content")

    annotations_root = tmp_path / "annotations"
    a1 = annotations_root / "PlayA" / "Clip_1" / "annotations.json"
    create_synthetic_annotation(a1, num_frames=5)

    output_root = tmp_path / "outputs"
    dest_video = output_root / "PlayA" / "Clip_1.mp4"
    dest_report = output_root / "PlayA" / "Clip_1.report.json"
    dest_video.parent.mkdir(parents=True, exist_ok=True)
    dest_video.write_bytes(b"rendered video content")

    rep_data = ClipBatchResult(
        clip_name="Clip_1",
        play_name="PlayA",
        render_status=BatchRenderStatus.SUCCESS,
        rendered_frames=5,
        output_video=str(dest_video),
        output_report=str(dest_report),
        input_fingerprint="old_stale_fingerprint_123",
    ).model_dump()
    dest_report.write_text(json.dumps(rep_data), encoding="utf-8")

    pipeline = BatchPipeline(
        videos_root=videos_root,
        annotations_root=annotations_root,
        output_root=output_root,
    )

    # Current fingerprint is different from stale fingerprint in report
    fp = compute_input_fingerprint(v1, a1)
    can_skip, skipped_result = pipeline.check_resume_skip("Clip_1", "PlayA", fp.combined_hash)
    assert can_skip is False
    assert skipped_result is None


def test_resume_and_overwrite_mutually_exclusive(tmp_path: Path):
    pipeline = BatchPipeline(
        videos_root=tmp_path / "videos",
        annotations_root=tmp_path / "annotations",
        output_root=tmp_path / "outputs",
    )
    with pytest.raises(ValueError, match="mutually exclusive"):
        pipeline.run_batch(resume=True, overwrite=True)


def test_destination_exists_without_resume_or_overwrite(tmp_path: Path):
    videos_root = tmp_path / "videos"
    videos_root.mkdir()
    v1 = videos_root / "Clip_1.mp4"
    v1.write_bytes(b"dummy video")

    annotations_root = tmp_path / "annotations"
    a1 = annotations_root / "PlayA" / "Clip_1" / "annotations.json"
    create_synthetic_annotation(a1, num_frames=5)
    d = json.loads(a1.read_text(encoding="utf-8"))
    d["clip"]["video_name"] = "Clip_1"
    a1.write_text(json.dumps(d), encoding="utf-8")

    output_root = tmp_path / "outputs"
    dest_video = output_root / "PlayA" / "Clip_1.mp4"
    dest_video.parent.mkdir(parents=True, exist_ok=True)
    dest_video.write_bytes(b"existing video")

    manifest_path = tmp_path / "manifest.json"
    manifest_data = [
        {"logical_clip_name": "Clip_1", "play_name": "PlayA", "video_id": "1"},
    ]
    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

    pipeline = BatchPipeline(
        videos_root=videos_root,
        annotations_root=annotations_root,
        output_root=output_root,
        manifest_path=manifest_path,
    )

    # Running without resume or overwrite when dest exists must fail for that clip
    rec = ShowcaseClipManifestRecord(logical_clip_name="Clip_1", play_name="PlayA", video_id="1")
    preflight = pipeline.preflight_clip(rec, inventory={}, gen_statuses={})

    res = pipeline.execute_clip(
        record=rec,
        preflight=preflight,
        dry_run=False,
        resume=False,
        overwrite=False,
    )

    assert res.render_status == BatchRenderStatus.FAILED
    assert any("already exists" in e for e in res.errors)

