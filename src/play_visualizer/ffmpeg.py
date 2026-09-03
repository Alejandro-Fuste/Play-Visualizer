"""FFmpeg post-processing for H.264 encoding and audio muxing."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger("play_visualizer")


class FFmpegError(Exception):
    """Raised when FFmpeg transcoding fails."""


def find_ffmpeg_executable() -> str | None:
    """Locate ffmpeg binary in system PATH or standard install locations."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    for path in ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"):
        if Path(path).exists():
            return path
    return None


def run_ffmpeg_encode(
    intermediate_path: Path,
    final_output_path: Path,
    source_video_path: Path | None = None,
    has_audio: bool = False,
    crf: int = 18,
    preset: str = "medium",
    pix_fmt: str = "yuv420p",
    movflags: str = "+faststart",
    keep_intermediate: bool = False,
) -> str:
    """Encode intermediate MP4 to final H.264 video with optional audio muxing.

    Returns the executed command string.
    """
    ffmpeg_cmd = find_ffmpeg_executable()
    if not ffmpeg_cmd:
        raise FFmpegError("FFmpeg command not found in system PATH.")

    final_output_path.parent.mkdir(parents=True, exist_ok=True)

    # Base command for video transcode
    cmd = [
        ffmpeg_cmd,
        "-y",
        "-i",
        str(intermediate_path),
    ]

    # Include audio stream from source if available
    if has_audio and source_video_path and source_video_path.exists():
        cmd.extend(["-i", str(source_video_path)])
        cmd.extend(["-c:v", "libx264"])
        cmd.extend(["-preset", preset])
        cmd.extend(["-crf", str(crf)])
        cmd.extend(["-pix_fmt", pix_fmt])
        cmd.extend(["-movflags", movflags])
        cmd.extend(["-timecode", "00:00:00:00"])
        cmd.extend(["-write_tmcd", "1"])
        cmd.extend(["-c:a", "aac"])
        cmd.extend(["-map", "0:v:0"])
        cmd.extend(["-map", "1:a:0?"])
    else:
        cmd.extend(["-c:v", "libx264"])
        cmd.extend(["-preset", preset])
        cmd.extend(["-crf", str(crf)])
        cmd.extend(["-pix_fmt", pix_fmt])
        cmd.extend(["-movflags", movflags])
        cmd.extend(["-timecode", "00:00:00:00"])
        cmd.extend(["-write_tmcd", "1"])
        cmd.extend(["-an"])  # No audio

    cmd.append(str(final_output_path))
    cmd_str = " ".join(cmd)

    logger.info(f"Running FFmpeg encoding command: {cmd_str}")

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode != 0:
            logger.error(f"FFmpeg failed with return code {res.returncode}: {res.stderr}")
            raise FFmpegError(f"FFmpeg encoding failed: {res.stderr}")
    except Exception as e:
        if not isinstance(e, FFmpegError):
            raise FFmpegError(f"Error executing FFmpeg: {e}") from e
        raise

    logger.info(f"FFmpeg encoding successful. Output saved to: {final_output_path}")

    # Remove temporary intermediate video file unless configured to keep
    if not keep_intermediate and intermediate_path.exists():
        try:
            intermediate_path.unlink()
            logger.info(f"Removed intermediate video file: {intermediate_path}")
        except Exception as e:
            logger.warning(f"Failed to remove intermediate file {intermediate_path}: {e}")

    return cmd_str
