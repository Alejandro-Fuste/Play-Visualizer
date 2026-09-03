"""Synthetic video and annotation generator for automated testing."""

import json
from pathlib import Path

import cv2
import numpy as np


def create_synthetic_video(video_path: Path, num_frames: int = 30, width: int = 640, height: int = 480, fps: float = 30.0) -> Path:
    """Create a synthetic MP4 video file with color-patterned frames."""
    video_path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(video_path), fourcc, fps, (width, height))

    for i in range(num_frames):
        # Create solid background with frame counter text
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:, :] = (40, 100, 40)  # Green turf background
        cv2.putText(
            frame,
            f"Synthetic Frame {i}",
            (50, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (255, 255, 255),
            2,
        )
        writer.write(frame)

    writer.release()
    return video_path


def create_synthetic_annotation(json_path: Path, num_frames: int = 30) -> Path:
    """Create a matching TapeVision annotation JSON file."""
    json_path.parent.mkdir(parents=True, exist_ok=True)

    dense_anns = []
    for f in range(num_frames):
        # Offense QB
        dense_anns.append(
            {
                "frame": f,
                "actor_track_id": "1",
                "xml_track_id": "10",
                "position": "QB",
                "team_side": "offense",
                "action": "Action_SnapReceive" if f < 10 else "Action_BallCarry",
                "bbox_xyxy": [100.0 + f, 200.0, 150.0 + f, 300.0],
                "bbox_xywh": [100.0 + f, 200.0, 50.0, 100.0],
            }
        )
        # Defense FS
        dense_anns.append(
            {
                "frame": f,
                "actor_track_id": "2",
                "xml_track_id": "20",
                "position": "FS",
                "team_side": "defense",
                "action": "Action_Defense_NotAnnotated",
                "bbox_xyxy": [400.0, 100.0, 450.0, 200.0],
                "bbox_xywh": [400.0, 100.0, 50.0, 100.0],
            }
        )

    data = {
        "schema_version": "tapevision_annotation_enrichment_v1.0",
        "source": {
            "xml_file": "synthetic.xml",
            "csv_file": "synthetic.csv",
        },
        "clip": {
            "video_name": "Synthetic_Clip",
            "frame_start": 0,
            "frame_end": num_frames - 1,
            "num_frames": num_frames,
        },
        "play": {
            "play_tag": "Play_Run_JetSweep",
            "result_tag": "Result_OutOfBounds",
            "result_frame": num_frames - 1,
        },
        "tracks": {
            "players": [
                {
                    "xml_track_id": "10",
                    "actor_track_id": "1",
                    "position": "QB",
                    "team_side": "offense",
                    "samples": [],
                },
                {
                    "xml_track_id": "20",
                    "actor_track_id": "2",
                    "position": "FS",
                    "team_side": "defense",
                    "samples": [],
                },
            ],
            "ball": [],
        },
        "actions": {
            "segments": [
                {
                    "actor_track_id": "1",
                    "position": "QB",
                    "team_side": "offense",
                    "action": "Action_BallSnap",
                    "frame_start": 0,
                    "frame_end": 5,
                    "duration_frames": 6,
                },
                {
                    "actor_track_id": "1",
                    "position": "QB",
                    "team_side": "offense",
                    "action": "Action_BallCarry",
                    "frame_start": 6,
                    "frame_end": num_frames - 1,
                    "duration_frames": num_frames - 6,
                },
            ],
            "dense_frame_annotations": dense_anns,
        },
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return json_path
