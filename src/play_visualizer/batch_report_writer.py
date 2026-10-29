"""Report writer for Google Colab Showcase Batch-Rendering Workflow.

Generates atomic JSON and Markdown summaries persisted to Google Drive.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .batch_models import BatchRunSummary, ClipBatchResult

logger = logging.getLogger("play_visualizer.batch")


def atomic_write_json(path: Path, data: dict) -> None:
    """Atomically write JSON data to target path using a temp file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.parent / f".tmp_{path.name}"
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
        temp_path.replace(path)
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        raise e


def atomic_write_text(path: Path, text: str) -> None:
    """Atomically write text data to target path using a temp file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.parent / f".tmp_{path.name}"
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
        temp_path.replace(path)
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        raise e


class BatchReportWriter:
    """Handles writing per-clip reports, batch summaries, and Markdown audit logs."""

    def __init__(self, output_root: Path):
        self.output_root = output_root

    def write_clip_report(self, result: ClipBatchResult) -> Path:
        """Write single clip execution report."""
        report_path = self.output_root / result.play_name / f"{result.clip_name}.report.json"
        atomic_write_json(report_path, result.model_dump())
        return report_path

    def write_batch_summary(self, summary: BatchRunSummary) -> tuple[Path, Path]:
        """Write both showcase_batch_summary.json and showcase_batch_summary.md.

        Returns (json_path, markdown_path).
        """
        json_path = self.output_root / "showcase_batch_summary.json"
        md_path = self.output_root / "showcase_batch_summary.md"

        atomic_write_json(json_path, summary.model_dump())

        md_content = self.generate_markdown_summary(summary)
        atomic_write_text(md_path, md_content)

        return json_path, md_path

    def generate_markdown_summary(self, summary: BatchRunSummary) -> str:
        """Format a human-readable Markdown batch summary table and audit report."""
        mode_label = "DRY-RUN (Validation Only)" if summary.dry_run else "BATCH RENDER"

        lines = [
            f"# Play-Visualizer Showcase Batch Summary — {mode_label}",
            "",
            f"- **Run ID:** `{summary.run_id}`",
            f"- **Start Time:** {summary.start_time}",
            f"- **End Time:** {summary.end_time or 'In Progress'}",
            f"- **Elapsed Time:** {summary.elapsed_seconds:.2f} seconds",
            f"- **Selected Clips:** {summary.selected_count} (Full Showcase Target: {summary.expected_full_showcase_count})",
            "",
            "## 1. Status Counts",
            "",
            "| Status | Count |",
            "| :--- | :--- |",
        ]

        for status, count in summary.status_counts.items():
            lines.append(f"| **{status}** | {count} |")

        # Unresolved errors section
        if summary.unresolved_errors:
            lines.extend([
                "",
                "## 2. Unresolved Errors",
                "",
                "| Clip | Stage | Error Details |",
                "| :--- | :--- | :--- |",
            ])
            for err in summary.unresolved_errors:
                clip = err.get("clip_name", "UNKNOWN")
                stage = err.get("stage", "UNKNOWN")
                msg = err.get("message", "").replace("|", "\\|")
                lines.append(f"| `{clip}` | `{stage}` | {msg} |")

        # Per-clip results table
        lines.extend([
            "",
            "## 3. Clip Results",
            "",
            "| # | Clip Name | Play Name | Preflight | Render Status | Frames | Output Video | Time (s) |",
            "| :---: | :--- | :--- | :---: | :---: | :---: | :--- | :---: |",
        ])

        for idx, cr in enumerate(summary.clip_results, start=1):
            out_disp = f"`{Path(cr.output_video).name}`" if cr.output_video else "—"
            lines.append(
                f"| {idx} | `{cr.clip_name}` | {cr.play_name} | `{cr.preflight_status.value}` | "
                f"**`{cr.render_status.value}`** | {cr.rendered_frames} | {out_disp} | {cr.elapsed_seconds:.2f} |"
            )

        lines.extend([
            "",
            "---",
            "*Report generated automatically by Play-Visualizer Batch Orchestrator.*",
        ])

        return "\n".join(lines) + "\n"

