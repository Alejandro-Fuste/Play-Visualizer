"""Unit tests for batch models and serialization."""

from play_visualizer.batch_models import (
    BatchRenderStatus,
    BatchRunSummary,
    ClipBatchResult,
    ClipPreflightResult,
    InputFingerprint,
    PreflightStatus,
)


def test_clip_preflight_result_serialization():
    res = ClipPreflightResult(
        clip_name="JetSweep_1",
        play_name="JetSweep",
        status=PreflightStatus.READY,
        source_video="/path/to/JetSweep_1.mp4",
        source_annotations="/path/to/annotations.json",
        video_file_id="fid_123",
        expected_frames=300,
        video_frames=300,
        warnings=["Nonfatal warning"],
    )
    d = res.model_dump()
    assert d["clip_name"] == "JetSweep_1"
    assert d["status"] == "READY"
    assert len(d["warnings"]) == 1
    assert len(d["errors"]) == 0


def test_clip_batch_result_serialization():
    res = ClipBatchResult(
        clip_name="JetSweep_1",
        play_name="JetSweep",
        video_file_id="fid_123",
        source_video="/path/to/JetSweep_1.mp4",
        source_annotations="/path/to/annotations.json",
        annotation_schema_version="tapevision_annotation_enrichment_v1.1",
        source_generation_status="WARNING",
        preflight_status=PreflightStatus.READY,
        render_status=BatchRenderStatus.SUCCESS,
        rendered_frames=300,
        output_video="/content/drive/outputs/JetSweep/JetSweep_1.mp4",
        output_report="/content/drive/outputs/JetSweep/JetSweep_1.report.json",
        input_fingerprint="abc123hash",
        elapsed_seconds=12.5,
    )
    d = res.model_dump()
    assert d["render_status"] == "SUCCESS"
    assert d["rendered_frames"] == 300
    assert d["input_fingerprint"] == "abc123hash"


def test_batch_run_summary_serialization():
    summary = BatchRunSummary(
        run_id="batch_20261029_120000",
        start_time="2026-10-29T12:00:00Z",
        end_time="2026-10-29T12:10:00Z",
        selected_count=50,
        expected_full_showcase_count=50,
        status_counts={"SUCCESS": 49, "WARNING": 1, "FAILED": 0, "SKIPPED": 0},
        elapsed_seconds=600.0,
    )
    d = summary.model_dump()
    assert d["run_id"] == "batch_20261029_120000"
    assert d["status_counts"]["SUCCESS"] == 49

