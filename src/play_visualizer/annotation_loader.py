"""Loader and parser for TapeVision JSON annotation files."""

from __future__ import annotations

import json
from pathlib import Path

from .models import (
    ActionSegment,
    BallTrack,
    BallTrackSample,
    ClipMetadata,
    DenseFrameAnnotation,
    PlayerTrack,
    PlayerTrackSample,
    PlayMetadata,
    TapeVisionAnnotationPackage,
)

EXPECTED_SCHEMA_VERSION = "tapevision_annotation_enrichment_v1.0"


class AnnotationLoadError(Exception):
    """Raised when an annotation file cannot be parsed or validated."""


def load_annotation_file(file_path: Path) -> TapeVisionAnnotationPackage:
    """Read, parse, and validate a TapeVision JSON annotation file."""
    if not file_path.exists():
        raise AnnotationLoadError(f"Annotation file not found: {file_path}")

    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        raise AnnotationLoadError(f"Failed to parse JSON file {file_path}: {e}") from e

    if not isinstance(data, dict):
        raise AnnotationLoadError("Top-level JSON structure must be an object.")

    # Validate top-level schema version
    schema_version = str(data.get("schema_version", ""))
    if not schema_version:
        raise AnnotationLoadError("Missing 'schema_version' field in annotation JSON.")

    source_info = data.get("source", {}) if isinstance(data.get("source"), dict) else {}

    # Parse clip metadata
    clip_data = data.get("clip", {})
    if not isinstance(clip_data, dict):
        raise AnnotationLoadError("'clip' section must be a dictionary.")

    try:
        clip_meta = ClipMetadata(
            video_name=str(clip_data.get("video_name", "unknown")),
            frame_start=int(clip_data.get("frame_start", 0)),
            frame_end=int(clip_data.get("frame_end", 0)),
            num_frames=int(clip_data.get("num_frames", 0)),
        )
    except Exception as e:
        raise AnnotationLoadError(f"Invalid 'clip' metadata: {e}") from e

    # Parse play metadata
    play_data = data.get("play", {})
    if not isinstance(play_data, dict):
        play_data = {}

    result_frame = play_data.get("result_frame")
    play_meta = PlayMetadata(
        play_tag=str(play_data.get("play_tag", "Play_Unknown")),
        result_tag=str(play_data.get("result_tag", "Result_Unknown")),
        result_frame=int(result_frame) if result_frame is not None else None,
    )

    # Parse tracks
    tracks_data = data.get("tracks", {})
    if not isinstance(tracks_data, dict):
        tracks_data = {}

    # Player tracks
    players_list: list[PlayerTrack] = []
    raw_players = tracks_data.get("players", [])
    if isinstance(raw_players, list):
        for item in raw_players:
            if not isinstance(item, dict):
                continue
            samples = []
            for sample in item.get("samples", []):
                if isinstance(sample, dict) and "frame" in sample and "bbox_xyxy" in sample:
                    samples.append(
                        PlayerTrackSample(
                            frame=int(sample["frame"]),
                            bbox_xyxy=tuple(sample["bbox_xyxy"]),
                            bbox_xywh=tuple(sample["bbox_xywh"]) if "bbox_xywh" in sample else None,
                        )
                    )
            players_list.append(
                PlayerTrack(
                    xml_track_id=str(item.get("xml_track_id", "0")),
                    actor_track_id=str(item.get("actor_track_id", "")),
                    position=str(item.get("position", "UNK")),
                    team_side=str(item.get("team_side", "unknown")),
                    samples=samples,
                )
            )

    # Ball tracks
    ball_list: list[BallTrack] = []
    raw_ball = tracks_data.get("ball", [])
    if isinstance(raw_ball, list):
        for item in raw_ball:
            if not isinstance(item, dict):
                continue
            ball_samples: list[BallTrackSample] = []
            for b_sample in item.get("samples", []):
                if isinstance(b_sample, dict) and "frame" in b_sample and "bbox_xyxy" in b_sample:
                    ball_samples.append(
                        BallTrackSample(
                            frame=int(b_sample["frame"]),
                            bbox_xyxy=tuple(b_sample["bbox_xyxy"]),
                            bbox_xywh=tuple(b_sample["bbox_xywh"]) if "bbox_xywh" in b_sample else None,
                        )
                    )
            ball_list.append(
                BallTrack(
                    xml_track_id=str(item.get("xml_track_id", "ball")),
                    samples=ball_samples,
                )
            )

    # Parse actions
    actions_data = data.get("actions", {})
    if not isinstance(actions_data, dict):
        actions_data = {}

    action_segments: list[ActionSegment] = []
    raw_segments = actions_data.get("segments", [])
    if isinstance(raw_segments, list):
        for item in raw_segments:
            if isinstance(item, dict) and "actor_track_id" in item and "action" in item:
                action_segments.append(
                    ActionSegment(
                        actor_track_id=str(item.get("actor_track_id", "")),
                        position=str(item.get("position", "UNK")),
                        team_side=str(item.get("team_side", "unknown")),
                        action=str(item.get("action", "")),
                        frame_start=int(item.get("frame_start", 0)),
                        frame_end=int(item.get("frame_end", 0)),
                        duration_frames=int(item.get("duration_frames", 1)),
                    )
                )

    dense_annotations: list[DenseFrameAnnotation] = []
    raw_dense = actions_data.get("dense_frame_annotations", [])
    if isinstance(raw_dense, list):
        for item in raw_dense:
            if isinstance(item, dict) and "frame" in item and "actor_track_id" in item and "bbox_xyxy" in item:
                dense_annotations.append(
                    DenseFrameAnnotation(
                        frame=int(item["frame"]),
                        actor_track_id=str(item["actor_track_id"]),
                        xml_track_id=str(item.get("xml_track_id", "0")),
                        position=str(item.get("position", "UNK")),
                        team_side=str(item.get("team_side", "unknown")),
                        action=str(item.get("action", "Action_Unknown")),
                        bbox_xyxy=tuple(item["bbox_xyxy"]),
                        bbox_xywh=tuple(item["bbox_xywh"]) if "bbox_xywh" in item else None,
                    )
                )

    return TapeVisionAnnotationPackage(
        schema_version=schema_version,
        source=source_info,
        clip=clip_meta,
        play=play_meta,
        players=players_list,
        ball=ball_list,
        action_segments=action_segments,
        dense_annotations=dense_annotations,
    )
