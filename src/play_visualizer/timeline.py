"""Timeline overlay rendering play progress, key action markers, and playhead."""

from __future__ import annotations

import cv2
import numpy as np

from .action_formatter import format_action_label, format_result_tag
from .models import ActionSegment, PlayMetadata


class TimelineRenderer:
    """Renders bottom progress bar with key football event markers."""

    def __init__(self, action_segments: list[ActionSegment], play_meta: PlayMetadata):
        self.action_segments = action_segments
        self.play_meta = play_meta
        self.cyan_accent = [255, 229, 0]      # Cyan (#00E5FF in BGR)
        self.neutral_gray = [178, 178, 178]   # Light Gray
        self.key_markers = self._extract_key_markers()

    def _extract_key_markers(self) -> list[tuple[int, str, list[int]]]:
        """Extract frame index, label, and marker color for key action segments."""
        markers = []
        target_actions = {
            "Action_BallSnap": ("Snap", [255, 229, 0]),               # Cyan
            "Action_Handoff": ("Handoff", [7, 193, 255]),             # Gold
            "Action_FakeHandoff": ("Fake Handoff", [7, 193, 255]),     # Gold
            "Action_BootAway": ("Boot", [255, 229, 0]),                # Cyan
            "Action_ThrowPass": ("Pass", [255, 229, 0]),               # Cyan
            "Action_SecureCatch": ("Catch", [7, 193, 255]),            # Gold
            "Action_JetMotion": ("Jet Motion", [255, 229, 0]),        # Cyan
            "Action_Toss": ("Toss", [255, 229, 0]),                   # Cyan
            "Action_BallCarry": ("Ball Carry", [178, 178, 178]),      # Gray
            "Action_PlayEnd_Tackle": ("Tackle", [255, 229, 0]),       # Cyan
            "Action_PlayEnd_OutOfBounds": ("Out of Bounds", [255, 229, 0]), # Cyan
            "Action_PlayEnd_Touchdown": ("Touchdown", [255, 229, 0]),  # Cyan
        }

        seen_events: set[tuple[int, str]] = set()

        for seg in self.action_segments:
            if seg.action in target_actions:
                base_label, color = target_actions[seg.action]
                label_with_frame = f"{base_label} (f:{seg.frame_start})"
                event_key = (seg.frame_start, base_label)
                if event_key not in seen_events:
                    seen_events.add(event_key)
                    markers.append((seg.frame_start, label_with_frame, color))

        # Add result frame marker if present
        if self.play_meta.result_frame is not None:
            res_label = format_result_tag(self.play_meta.result_tag)
            label_with_frame = f"{res_label} (f:{self.play_meta.result_frame})"
            event_key = (self.play_meta.result_frame, res_label)
            if event_key not in seen_events:
                seen_events.add(event_key)
                markers.append((self.play_meta.result_frame, label_with_frame, [255, 229, 0]))

        # Sort markers by frame number
        markers.sort(key=lambda m: m[0])
        return markers

    def draw_timeline(
        self,
        frame: np.ndarray,
        current_frame: int,
        start_frame: int,
        end_frame: int,
    ) -> None:
        """Render the bottom timeline progress bar onto the frame."""
        h_frame, w_frame = frame.shape[:2]

        timeline_h = 34
        pad_x = 60
        y_bottom = h_frame - 12
        y_top = y_bottom - timeline_h

        # Translucent bar background
        overlay = frame.copy()
        cv2.rectangle(overlay, (pad_x, y_top), (w_frame - pad_x, y_bottom), (20, 24, 33), -1)
        cv2.addWeighted(overlay, 0.8, frame, 0.2, 0, frame)
        cv2.rectangle(frame, (pad_x, y_top), (w_frame - pad_x, y_bottom), (45, 50, 60), 1)

        font_face = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = max(0.3, min(0.38, h_frame / 2800.0))

        # Draw frame counter text on left side of timeline bar
        frame_counter_str = f"F: {current_frame} / {end_frame}"
        cv2.putText(
            frame,
            frame_counter_str,
            (pad_x + 10, y_top + 22),
            font_face,
            font_scale,
            self.cyan_accent,
            1,
            cv2.LINE_AA,
        )

        (fc_w, _), _ = cv2.getTextSize(frame_counter_str, font_face, font_scale, 1)

        track_x1 = pad_x + fc_w + 20
        track_x2 = w_frame - pad_x - 14
        track_w = max(10, track_x2 - track_x1)
        track_y = y_top + 18

        total_span = max(1, end_frame - start_frame)

        # Draw base track line (muted gray)
        cv2.line(frame, (track_x1, track_y), (track_x2, track_y), (70, 70, 75), 3)

        # Calculate progress ratio
        progress_ratio = max(0.0, min(1.0, (current_frame - start_frame) / total_span))
        current_x = int(track_x1 + (progress_ratio * track_w))

        # Draw progress filled track (Cyan accent)
        if current_x > track_x1:
            cv2.line(frame, (track_x1, track_y), (current_x, track_y), self.cyan_accent, 3)

        # Draw event markers
        for m_frame, m_label, m_color in self.key_markers:
            if start_frame <= m_frame <= end_frame:
                m_ratio = (m_frame - start_frame) / total_span
                mx = int(track_x1 + (m_ratio * track_w))

                # Draw tick marker
                cv2.circle(frame, (mx, track_y), 3, m_color, -1)

                # Draw label text with frame number
                cv2.putText(
                    frame,
                    m_label,
                    (mx - 18, track_y - 7),
                    font_face,
                    font_scale - 0.02,
                    (220, 220, 220),
                    1,
                    cv2.LINE_AA,
                )

        # Draw playhead indicator
        cv2.circle(frame, (current_x, track_y), 5, self.cyan_accent, -1)
        cv2.circle(frame, (current_x, track_y), 6, (255, 255, 255), 1)


