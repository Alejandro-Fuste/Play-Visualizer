"""Data models for Google Colab Showcase Batch-Rendering Workflow."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class PreflightStatus(str, Enum):
    """Preflight check status for a clip."""
    READY = "READY"
    FAILED = "FAILED"


class BatchRenderStatus(str, Enum):
    """Render and persistence status for a clip in the batch."""
    READY = "READY"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class ShowcaseClipManifestRecord(BaseModel):
    """Individual record from the authoritative showcase_clips.json manifest."""
    logical_clip_name: str
    play_name: str
    video_id: str
    tracking_source: str | None = None
    key_actions_source: str | None = None
    player_tracks_source: str | None = None


class InventoryVideoRecord(BaseModel):
    """Provenance record from 1_Videos_Inventory.csv."""
    file_name: str
    size_mb: float | None = None
    date_modified: str | None = None
    file_id: str | None = None


class InputFingerprint(BaseModel):
    """Stable fingerprint for input reproducibility and resume verification."""
    video_size_bytes: int
    video_mtime: float
    annotation_sha256: str
    config_sha256: str
    tool_version: str
    combined_hash: str


class ClipPreflightResult(BaseModel):
    """Validation report generated prior to batch rendering."""
    clip_name: str
    play_name: str
    status: PreflightStatus
    source_video: str | None = None
    source_annotations: str | None = None
    video_file_id: str | None = None
    annotation_schema_version: str | None = None
    expected_frames: int | None = None
    video_frames: int | None = None
    source_generation_status: str = "UNKNOWN"
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ClipBatchResult(BaseModel):
    """Machine-readable execution result for a single showcase clip."""
    clip_name: str
    play_name: str
    video_file_id: str = ""
    source_video: str = ""
    source_annotations: str = ""
    annotation_schema_version: str = ""
    source_generation_status: str = "UNKNOWN"
    preflight_status: PreflightStatus = PreflightStatus.READY
    render_status: BatchRenderStatus = BatchRenderStatus.READY
    rendered_frames: int = 0
    rendered_frame_start: int | None = None
    rendered_frame_end: int | None = None
    output_video: str = ""
    output_report: str = ""
    input_fingerprint: str = ""
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    ffmpeg_command: str = ""
    elapsed_seconds: float = 0.0


class BatchRunSummary(BaseModel):
    """Comprehensive batch execution summary persisted to Google Drive."""
    schema_version: str = "play_visualizer_batch_summary_v1.0"
    run_id: str
    start_time: str
    end_time: str | None = None
    runtime_environment: dict[str, Any] = Field(default_factory=dict)
    selected_count: int
    expected_full_showcase_count: int = 50
    status_counts: dict[str, int] = Field(default_factory=dict)
    unresolved_errors: list[dict[str, Any]] = Field(default_factory=list)
    source_manifest_path: str = ""
    inventory_csv_path: str | None = None
    videos_root: str = ""
    annotations_root: str = ""
    output_root: str = ""
    scratch_root: str = ""
    dry_run: bool = False
    clip_results: list[ClipBatchResult] = Field(default_factory=list)
    elapsed_seconds: float = 0.0

