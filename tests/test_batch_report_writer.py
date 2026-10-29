"""Unit tests for batch report writing and atomic persistence."""

import json
from pathlib import Path

from play_visualizer.batch_models import (
    BatchRenderStatus,
    BatchRunSummary,
    ClipBatchResult,
    PreflightStatus,
)
from play_visualizer.batch_report_writer import (
    BatchReportWriter,
    atomic_write_json,
    atomic_write_text,
)


def test_atomic_write_json(tmp_path: Path):
    target = tmp_path / "subdir" / "data.json"
    data = {"status": "ok", "value": 42}
    atomic_write_json(target, data)

    assert target.exists()
    with open(target, encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded == data


def test_atomic_write_text(tmp_path: Path):
    target = tmp_path / "subdir" / "summary.md"
    content = "# Title\n\nSome text."
    atomic_write_text(target, content)

    assert target.exists()
    assert target.read_text(encoding="utf-8") == content


def test_write_clip_report(tmp_path: Path):
    writer = BatchReportWriter(output_root=tmp_path)
    res = ClipBatchResult(
        clip_name="Power_3",
        play_name="Power",
        source_video="/path/to/Power_3.mp4",
        source_annotations="/path/to/annotations.json",
        render_status=BatchRenderStatus.SUCCESS,
        rendered_frames=250,
        output_video=str(tmp_path / "Power" / "Power_3.mp4"),
        output_report=str(tmp_path / "Power" / "Power_3.report.json"),
    )
    report_path = writer.write_clip_report(res)
    assert report_path.exists()
    assert report_path == tmp_path / "Power" / "Power_3.report.json"

    with open(report_path, encoding="utf-8") as f:
        d = json.load(f)
    assert d["clip_name"] == "Power_3"
    assert d["render_status"] == "SUCCESS"


def test_write_batch_summary(tmp_path: Path):
    writer = BatchReportWriter(output_root=tmp_path)
    summary = BatchRunSummary(
        run_id="batch_test_001",
        start_time="2026-10-29T12:00:00Z",
        end_time="2026-10-29T12:05:00Z",
        selected_count=2,
        expected_full_showcase_count=50,
        status_counts={"SUCCESS": 1, "FAILED": 1},
        unresolved_errors=[
            {"clip_name": "Bad_1", "stage": "render", "message": "Corrupted frame"}
        ],
        clip_results=[
            ClipBatchResult(
                clip_name="Good_1",
                play_name="PlayA",
                render_status=BatchRenderStatus.SUCCESS,
                rendered_frames=100,
                output_video=str(tmp_path / "PlayA" / "Good_1.mp4"),
                elapsed_seconds=5.2,
            ),
            ClipBatchResult(
                clip_name="Bad_1",
                play_name="PlayB",
                render_status=BatchRenderStatus.FAILED,
                errors=["Corrupted frame"],
                elapsed_seconds=1.1,
            ),
        ],
        elapsed_seconds=6.3,
    )

    json_path, md_path = writer.write_batch_summary(summary)
    assert json_path.exists()
    assert md_path.exists()
    assert json_path.name == "showcase_batch_summary.json"
    assert md_path.name == "showcase_batch_summary.md"

    md_text = md_path.read_text(encoding="utf-8")
    assert "# Play-Visualizer Showcase Batch Summary" in md_text
    assert "batch_test_001" in md_text
    assert "| **SUCCESS** | 1 |" in md_text
    assert "| **FAILED** | 1 |" in md_text
    assert "Corrupted frame" in md_text
    assert "`Good_1`" in md_text

