"""Input validation, frame alignment checks, coordinate clamping, and quality warnings."""

from __future__ import annotations

import math
import shutil
import subprocess
from pathlib import Path


from .annotation_index import AnnotationIndex
from .models import PlayVisualizerAnnotationPackage, ValidationWarning, VideoMetadata

SUSPICIOUS_DEFENSE_OFFENSIVE_ACTIONS = {
    "Action_JetMotion",
    "Action_Toss",
    "Action_BallCarry",
    "Action_ZoneBlock",
    "Action_LeadBlock",
    "Action_BlockSecondLevel",
    "Action_SealBlock",
    "Action_BallSnap",
    "Action_SnapReceive",
}


def find_ffmpeg_executable() -> Optional[str]:
    """Locate ffmpeg binary in system PATH or standard install locations."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    for path in ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"):
        if Path(path).exists():
            return path
    return None


def check_ffmpeg_available() -> bool:
    """Check if ffmpeg executable is available in PATH or system paths."""
    ffmpeg_cmd = find_ffmpeg_executable()
    if not ffmpeg_cmd:
        return False
    try:
        res = subprocess.run([ffmpeg_cmd, "-version"], capture_output=True, text=True, check=False)
        return res.returncode == 0
    except Exception:
        return False


def clamp_bbox(
    bbox_xyxy: tuple[float, float, float, float], width: int, height: int
) -> tuple[float, float, float, float] | None:
    """Clamp bounding box coordinates to image dimensions [0, width] and [0, height].

    Returns None if the box is invalid (NaN, Inf, zero/negative area, or out-of-bounds).
    """
    x1, y1, x2, y2 = bbox_xyxy
    if any(math.isnan(v) or math.isinf(v) for v in (x1, y1, x2, y2)):
        return None

    # Clamp coordinates
    cx1 = max(0.0, min(float(width), float(x1)))
    cy1 = max(0.0, min(float(height), float(y1)))
    cx2 = max(0.0, min(float(width), float(x2)))
    cy2 = max(0.0, min(float(height), float(y2)))

    # Verify positive width and height
    w = cx2 - cx1
    h = cy2 - cy1

    if w <= 1.0 or h <= 1.0:
        return None

    return (cx1, cy1, cx2, cy2)


class InputValidator:
    """Validator for checking video, annotation JSON, and environment prerequisites."""

    def __init__(
        self,
        video_meta: VideoMetadata,
        pkg: PlayVisualizerAnnotationPackage,
        index: AnnotationIndex,
    ):
        self.video_meta = video_meta
        self.pkg = pkg
        self.index = index
        self.warnings: list[ValidationWarning] = []

    def validate_all(
        self,
        user_start_frame: int | None = None,
        user_end_frame: int | None = None,
        include_tail: bool = False,
    ) -> tuple[int, int, list[ValidationWarning]]:
        """Run all input validation checks and compute render frame range.

        Returns (render_start_frame, render_end_frame, list_of_warnings).
        """
        self.warnings.clear()

        # 1. FFmpeg availability check
        if not check_ffmpeg_available():
            self.warnings.append(
                ValidationWarning(
                    code="FFMPEG_MISSING",
                    message="FFmpeg is not installed or not found in system PATH.",
                    severity="ERROR",
                )
            )

        # 2. Frame count alignment check
        video_frames = self.video_meta.num_frames
        json_clip_start = self.pkg.clip.frame_start
        json_clip_end = self.pkg.clip.frame_end
        json_frames = self.pkg.clip.num_frames

        if video_frames != json_frames:
            msg = (
                f"Frame count mismatch: video has {video_frames} frames, "
                f"annotation clip specifies {json_frames} frames (frames {json_clip_start}-{json_clip_end})."
            )
            self.warnings.append(
                ValidationWarning(
                    code="FRAME_COUNT_MISMATCH",
                    message=msg,
                    severity="WARNING",
                )
            )

        # Compute effective render range
        if user_start_frame is not None:
            start_frame = max(0, user_start_frame)
        else:
            start_frame = max(0, json_clip_start)

        if user_end_frame is not None:
            end_frame = min(video_frames - 1, user_end_frame)
        elif include_tail:
            end_frame = video_frames - 1
        else:
            # Intersection of video frames and annotated range
            end_frame = min(video_frames - 1, json_clip_end)

        if start_frame > end_frame:
            self.warnings.append(
                ValidationWarning(
                    code="INVALID_FRAME_RANGE",
                    message=f"Effective start frame {start_frame} is greater than end frame {end_frame}.",
                    severity="ERROR",
                )
            )

        # 3. Check ball annotations
        if not self.pkg.ball or not any(b.samples for b in self.pkg.ball):
            self.warnings.append(
                ValidationWarning(
                    code="MISSING_BALL_TRACK",
                    message="No ball track annotations found in JSON package.",
                    severity="INFO",
                )
            )

        # 4. Check for duplicate dense annotations
        if self.index.duplicate_count > 0:
            self.warnings.append(
                ValidationWarning(
                    code="DUPLICATE_ANNOTATIONS",
                    message=f"Found and removed {self.index.duplicate_count} exact duplicate frame annotations.",
                    severity="INFO",
                )
            )

        # 5. Check suspicious team / action combinations
        suspicious_count = 0
        for frame_idx in range(start_frame, end_frame + 1):
            anns = self.index.for_frame(frame_idx)
            for ann in anns:
                if (
                    ann.team_side == "defense"
                    and ann.action in SUSPICIOUS_DEFENSE_OFFENSIVE_ACTIONS
                ):
                    suspicious_count += 1

        if suspicious_count > 0:
            self.warnings.append(
                ValidationWarning(
                    code="SUSPICIOUS_DEFENSE_ACTION",
                    message=f"Detected {suspicious_count} defensive player annotations assigned offensive actions.",
                    severity="WARNING",
                )
            )

        return start_frame, end_frame, self.warnings
