"""Data models for Play-Visualizer annotation visualizer."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class VideoMetadata(BaseModel):
    """Metadata extracted from the source video file."""
    fps: float
    width: int
    height: int
    num_frames: int
    duration_seconds: float
    has_audio: bool = False


class ClipMetadata(BaseModel):
    """Clip metadata from annotation JSON."""
    video_name: str
    frame_start: int
    frame_end: int
    num_frames: int


class PlayMetadata(BaseModel):
    """Play metadata from annotation JSON."""
    play_tag: str = "Play_Unknown"
    result_tag: str = "Result_Unknown"
    result_frame: int | None = None


class PlayerTrackSample(BaseModel):
    """Individual frame bounding box sample in a player track."""
    frame: int
    bbox_xyxy: tuple[float, float, float, float]
    bbox_xywh: tuple[float, float, float, float] | None = None


class PlayerTrack(BaseModel):
    """Player track metadata and frame samples."""
    xml_track_id: str = "0"
    actor_track_id: str
    position: str = "UNK"
    team_side: str = "unknown"
    samples: list[PlayerTrackSample] = Field(default_factory=list)


class BallTrackSample(BaseModel):
    """Individual frame bounding box sample in a ball track."""
    frame: int
    bbox_xyxy: tuple[float, float, float, float]
    bbox_xywh: tuple[float, float, float, float] | None = None


class BallTrack(BaseModel):
    """Ball track metadata and samples."""
    xml_track_id: str = "ball"
    samples: list[BallTrackSample] = Field(default_factory=list)


class ActionSegment(BaseModel):
    """Temporal action segment for an actor."""
    actor_track_id: str
    position: str = "UNK"
    team_side: str = "unknown"
    action: str
    frame_start: int
    frame_end: int
    duration_frames: int = 1


class DenseFrameAnnotation(BaseModel):
    """Dense player annotation for a single frame."""
    frame: int
    actor_track_id: str
    xml_track_id: str = "0"
    position: str = "UNK"
    team_side: str = "unknown"
    action: str = "Action_Unknown"
    bbox_xyxy: tuple[float, float, float, float]
    bbox_xywh: tuple[float, float, float, float] | None = None


class PlayVisualizerAnnotationPackage(BaseModel):
    """Complete parsed Play-Visualizer annotation file package."""
    schema_version: str
    source: dict[str, Any] = Field(default_factory=dict)
    clip: ClipMetadata
    play: PlayMetadata
    players: list[PlayerTrack] = Field(default_factory=list)
    ball: list[BallTrack] = Field(default_factory=list)
    action_segments: list[ActionSegment] = Field(default_factory=list)
    dense_annotations: list[DenseFrameAnnotation] = Field(default_factory=list)


# Backward compatibility alias
TapeVisionAnnotationPackage = PlayVisualizerAnnotationPackage


class ValidationWarning(BaseModel):
    """Warning item captured during input validation."""
    code: str
    message: str
    severity: str = "WARNING"  # INFO, WARNING, ERROR
    frame: int | None = None
    actor_id: str | None = None


class RenderReport(BaseModel):
    """Machine-readable JSON execution run report."""
    input_video: str
    input_annotations: str
    output_video: str
    mode: str = "standard"
    video_properties: dict[str, Any] = Field(default_factory=dict)
    annotation_properties: dict[str, Any] = Field(default_factory=dict)
    rendered_frame_start: int
    rendered_frame_end: int
    rendered_frames: int
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    skipped_annotations: int = 0
    ffmpeg_command: str = ""
    status: str = "success"

