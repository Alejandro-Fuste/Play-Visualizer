"""Video I/O module wrapping OpenCV VideoCapture and VideoWriter with audio probe support."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Generator
from pathlib import Path

import cv2
import numpy as np

from .models import VideoMetadata


class VideoIOError(Exception):
    """Raised when video opening, reading, or writing fails."""


def check_audio_presence(video_path: Path) -> bool:
    """Use ffprobe to check if the source video file contains an audio stream."""
    ffprobe_cmd = shutil.which("ffprobe")
    if not ffprobe_cmd:
        for path in ("/opt/homebrew/bin/ffprobe", "/usr/local/bin/ffprobe"):
            if Path(path).exists():
                ffprobe_cmd = path
                break
    if not ffprobe_cmd:
        return False

    cmd = [
        ffprobe_cmd,
        "-v",
        "error",
        "-select_streams",
        "a",
        "-show_entries",
        "stream=codec_type",
        "-of",
        "csv=p=0",
        str(video_path),
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return "audio" in res.stdout.strip().lower()
    except Exception:
        return False


class VideoReader:
    """Stream frames and inspect metadata from a video file."""

    def __init__(self, video_path: Path):
        self.video_path = video_path
        if not self.video_path.exists():
            raise VideoIOError(f"Video file does not exist: {self.video_path}")

        self.cap = cv2.VideoCapture(str(self.video_path))
        if not self.cap.isOpened():
            raise VideoIOError(f"Failed to open video file with OpenCV: {self.video_path}")

        fps = float(self.cap.get(cv2.CAP_PROP_FPS) or 30.0)
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        num_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration = num_frames / fps if fps > 0 else 0.0
        has_audio = check_audio_presence(self.video_path)

        self.metadata = VideoMetadata(
            fps=fps,
            width=width,
            height=height,
            num_frames=num_frames,
            duration_seconds=duration,
            has_audio=has_audio,
        )

    def read_frame(self, frame_idx: int | None = None) -> np.ndarray | None:
        """Read a single frame by index or current position."""
        if frame_idx is not None:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)

        ret, frame = self.cap.read()
        if not ret or frame is None:
            return None
        return frame

    def stream_frames(
        self, start_frame: int = 0, end_frame: int | None = None
    ) -> Generator[tuple[int, np.ndarray], None, None]:
        """Generator yielding (frame_index, bgr_image_array) within the specified frame range."""
        max_frame = self.metadata.num_frames - 1 if self.metadata.num_frames > 0 else 0
        end_idx = end_frame if end_frame is not None else max_frame
        end_idx = min(end_idx, max_frame)

        self.cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        current_idx = start_frame

        while current_idx <= end_idx:
            ret, frame = self.cap.read()
            if not ret or frame is None:
                break
            yield current_idx, frame
            current_idx += 1

    def close(self) -> None:
        """Release VideoCapture resources."""
        if self.cap and self.cap.isOpened():
            self.cap.release()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class VideoWriter:
    """Write intermediate video frames using OpenCV."""

    def __init__(self, output_path: Path, width: int, height: int, fps: float):
        self.output_path = output_path
        self.width = width
        self.height = height
        self.fps = fps

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")  # type: ignore[attr-defined]
        self.writer = cv2.VideoWriter(
            str(self.output_path), fourcc, self.fps, (self.width, self.height)
        )
        if not self.writer.isOpened():
            raise VideoIOError(f"Failed to open OpenCV VideoWriter for {self.output_path}")

    def write_frame(self, frame: np.ndarray) -> None:
        """Write a single frame image array to the video file."""
        if frame.shape[0] != self.height or frame.shape[1] != self.width:
            frame = cv2.resize(frame, (self.width, self.height))
        self.writer.write(frame)

    def close(self) -> None:
        """Release VideoWriter resources."""
        if self.writer and self.writer.isOpened():
            self.writer.release()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
