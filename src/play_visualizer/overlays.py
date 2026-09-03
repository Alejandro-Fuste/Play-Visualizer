"""Resolution-aware OpenCV overlay rendering functions for visual annotations."""

from __future__ import annotations

import cv2
import numpy as np

from .action_formatter import (
    format_action_label,
    format_play_tag,
    format_result_tag,
)
from .config import ConfigModel
from .models import DenseFrameAnnotation, PlayMetadata


def _get_style_prop(style: Any, prop: str, default: Any) -> Any:
    if style is None:
        return default
    if isinstance(style, dict):
        return style.get(prop, default)
    return getattr(style, prop, default)


def draw_rounded_rectangle(
    image: np.ndarray,
    pt1: tuple[int, int],
    pt2: tuple[int, int],
    color: tuple[int, int, int] | list[int],
    radius: int = 14,
    thickness: int = -1,
    alpha: float = 1.0,
    border_color: tuple[int, int, int] | list[int] | None = None,
    border_thickness: int = 1,
) -> None:
    """Draw a rounded rectangle with fill, transparency (alpha), and optional border on an OpenCV image."""
    x1, y1 = int(pt1[0]), int(pt1[1])
    x2, y2 = int(pt2[0]), int(pt2[1])
    w = x2 - x1
    h = y2 - y1

    if w <= 0 or h <= 0:
        return

    r = max(1, min(radius, w // 2, h // 2))

    if alpha < 1.0:
        overlay = image.copy()
        draw_target = overlay
    else:
        draw_target = image

    fill_c = tuple(int(c) for c in color)

    # Fill central cross rectangles
    cv2.rectangle(draw_target, (x1 + r, y1), (x2 - r, y2), fill_c, -1)
    cv2.rectangle(draw_target, (x1, y1 + r), (x2, y2 - r), fill_c, -1)

    # Fill 4 corner arcs
    cv2.ellipse(draw_target, (x1 + r, y1 + r), (r, r), 180, 0, 90, fill_c, -1)
    cv2.ellipse(draw_target, (x2 - r, y1 + r), (r, r), 270, 0, 90, fill_c, -1)
    cv2.ellipse(draw_target, (x2 - r, y2 - r), (r, r), 0, 0, 90, fill_c, -1)
    cv2.ellipse(draw_target, (x1 + r, y2 - r), (r, r), 90, 0, 90, fill_c, -1)

    if alpha < 1.0:
        cv2.addWeighted(overlay, alpha, image, 1.0 - alpha, 0, image)

    # Optional border
    if border_color is not None and border_thickness > 0:
        b_color = tuple(int(c) for c in border_color)
        bt = border_thickness

        # Draw 4 straight edge lines
        cv2.line(image, (x1 + r, y1), (x2 - r, y1), b_color, bt, cv2.LINE_AA)
        cv2.line(image, (x1 + r, y2), (x2 - r, y2), b_color, bt, cv2.LINE_AA)
        cv2.line(image, (x1, y1 + r), (x1, y2 - r), b_color, bt, cv2.LINE_AA)
        cv2.line(image, (x2, y1 + r), (x2, y2 - r), b_color, bt, cv2.LINE_AA)

        # Draw 4 corner arcs
        cv2.ellipse(image, (x1 + r, y1 + r), (r, r), 180, 0, 90, b_color, bt, cv2.LINE_AA)
        cv2.ellipse(image, (x2 - r, y1 + r), (r, r), 270, 0, 90, b_color, bt, cv2.LINE_AA)
        cv2.ellipse(image, (x2 - r, y2 - r), (r, r), 0, 0, 90, b_color, bt, cv2.LINE_AA)
        cv2.ellipse(image, (x1 + r, y2 - r), (r, r), 90, 0, 90, b_color, bt, cv2.LINE_AA)


class OverlayRenderer:
    """Renders visual overlays on video frames using OpenCV."""

    def __init__(
        self,
        config: ConfigModel,
    ):
        self.config = config

        # Load style colors (BGR)
        styles = config.styles
        self.offense_style = styles.get("offense", None) if isinstance(styles, dict) else getattr(styles, "offense", None)
        self.defense_style = styles.get("defense", None) if isinstance(styles, dict) else getattr(styles, "defense", None)
        self.active_style = styles.get("active_highlight", None) if isinstance(styles, dict) else getattr(styles, "active_highlight", None)
        self.ball_style = styles.get("ball", None) if isinstance(styles, dict) else getattr(styles, "ball", None)
        self.neutral_style = styles.get("neutral", None) if isinstance(styles, dict) else getattr(styles, "neutral", None)
        self.cyan_accent = _get_style_prop(styles, "cyan_accent", [255, 229, 0])
        self.gold_accent = _get_style_prop(styles, "gold_accent", [7, 193, 255])
        self.neutral_player = _get_style_prop(styles, "neutral_player", [178, 178, 178])
        self.panel_bg = _get_style_prop(styles, "panel_bg", [33, 24, 20])

    def _get_team_colors(
        self,
        team_side: str,
        is_highlighted: bool = False,
        action: str | None = None,
    ):
        """Determine box color, label background color, text color, and thickness."""
        thickness = 2 if is_highlighted else 1

        if action and action in self.config.action_colors and action not in (
            "Action_Unknown",
            "Action_Defense_NotAnnotated",
        ):
            act_color = self.config.action_colors[action]
            return (act_color, act_color, [255, 255, 255], thickness)

        if is_highlighted and self.active_style:
            box_c = _get_style_prop(self.active_style, "box_color", [241, 196, 15])
            lbl_c = _get_style_prop(self.active_style, "label_bg_color", [243, 156, 18])
            txt_c = _get_style_prop(self.active_style, "text_color", [0, 0, 0])
            return (box_c, lbl_c, txt_c, 3)

        if team_side == "offense" and self.offense_style:
            box_c = _get_style_prop(self.offense_style, "box_color", [46, 204, 113])
            lbl_c = _get_style_prop(self.offense_style, "label_bg_color", [39, 174, 96])
            txt_c = _get_style_prop(self.offense_style, "text_color", [255, 255, 255])
            return (box_c, lbl_c, txt_c, thickness)
        elif team_side == "defense" and self.defense_style:
            box_c = _get_style_prop(self.defense_style, "box_color", [231, 76, 60])
            lbl_c = _get_style_prop(self.defense_style, "label_bg_color", [192, 57, 43])
            txt_c = _get_style_prop(self.defense_style, "text_color", [255, 255, 255])
            return (box_c, lbl_c, txt_c, thickness)
        elif self.neutral_style:
            box_c = _get_style_prop(self.neutral_style, "box_color", [149, 165, 166])
            lbl_c = _get_style_prop(self.neutral_style, "label_bg_color", [127, 140, 141])
            txt_c = _get_style_prop(self.neutral_style, "text_color", [255, 255, 255])
            return (box_c, lbl_c, txt_c, thickness)

        return (self.neutral_player, self.panel_bg, [255, 255, 255], thickness)

    def draw_player_box_and_label(
        self,
        frame: np.ndarray,
        annotation: DenseFrameAnnotation,
        clamped_xyxy: tuple[float, float, float, float],
        is_highlighted: bool = False,
    ) -> None:
        """Draw player bounding box and text label box on frame."""
        x1, y1, x2, y2 = map(int, clamped_xyxy)
        h_frame, w_frame = frame.shape[:2]

        box_color, bg_color, text_color, thickness = self._get_team_colors(
            annotation.team_side, is_highlighted, annotation.action
        )

        cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, thickness)

        lines: list[str] = []
        raw_pos = annotation.position if annotation.position else "Unknown"
        pos = raw_pos if raw_pos != "undefined" else "Unknown"
        lines.append(f"{pos} | {annotation.actor_track_id}")

        font_face = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = max(0.35, min(0.48, h_frame / 2200.0))
        line_height = int(18 * (h_frame / 1080.0))
        padding = 4

        max_text_w = 0
        total_text_h = len(lines) * line_height

        for line in lines:
            (w, _), _ = cv2.getTextSize(line, font_face, font_scale, 1)
            if w > max_text_w:
                max_text_w = w

        label_w = max_text_w + (padding * 2)
        label_h = total_text_h + (padding * 2)

        if y1 - label_h >= 5:
            lbl_y1 = y1 - label_h
            lbl_y2 = y1
        else:
            lbl_y1 = y2
            lbl_y2 = y2 + label_h

        lbl_x1 = max(5, min(w_frame - label_w - 5, x1))
        lbl_x2 = lbl_x1 + label_w

        overlay = frame.copy()
        cv2.rectangle(overlay, (lbl_x1, lbl_y1), (lbl_x2, lbl_y2), (20, 24, 33), -1)
        cv2.addWeighted(overlay, 0.8, frame, 0.2, 0, frame)
        cv2.rectangle(frame, (lbl_x1, lbl_y1), (lbl_x2, lbl_y2), box_color, 1)

        cur_y = lbl_y1 + line_height
        for line in lines:
            cv2.putText(
                frame,
                line,
                (lbl_x1 + padding, cur_y - padding),
                font_face,
                font_scale,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
            cur_y += line_height

    def draw_ball_box(
        self, frame: np.ndarray, clamped_xyxy: tuple[float, float, float, float]
    ) -> None:
        """Draw football bounding box when ball annotations exist."""
        x1, y1, x2, y2 = map(int, clamped_xyxy)
        box_color = _get_style_prop(self.ball_style, "box_color", [52, 152, 219])
        thickness = 2

        cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, thickness)
        cv2.putText(
            frame,
            "BALL",
            (x1, max(15, y1 - 5)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            box_color,
            1,
            cv2.LINE_AA,
        )

    def draw_unified_info_card(
        self,
        frame: np.ndarray,
        play_meta: PlayMetadata,
        active_actions: list[DenseFrameAnnotation],
    ) -> None:
        """Draw unified Play Information + Live Actions card in upper-right area of frame."""
        h_frame, w_frame = frame.shape[:2]
        panel_cfg = self.config.panel if isinstance(self.config.panel, dict) else {}

        scale = h_frame / 1080.0

        top_margin = int(panel_cfg.get("top_margin", 52) * scale)
        right_margin = int(panel_cfg.get("right_margin", 24) * scale)
        corner_radius = int(panel_cfg.get("corner_radius", 14) * scale)
        bg_alpha = float(panel_cfg.get("bg_alpha", 0.80))
        border_color = panel_cfg.get("border_color", self.cyan_accent)
        border_thickness = int(panel_cfg.get("border_thickness", 1))

        font_face = cv2.FONT_HERSHEY_SIMPLEX
        title_font_scale = max(0.48, min(0.65, 0.55 * scale))
        body_font_scale = max(0.38, min(0.50, 0.42 * scale))

        play_str = format_play_tag(play_meta.play_tag).upper()
        res_str = format_result_tag(play_meta.result_tag)

        # Unique active actions
        unique_actions: list[str] = []
        seen: set[str] = set()
        for ann in active_actions:
            if ann.action and ann.action not in (
                "Action_Unknown",
                "Action_Defense_NotAnnotated",
            ):
                if ann.action not in seen:
                    seen.add(ann.action)
                    unique_actions.append(ann.action)

        (w_play, h_play), _ = cv2.getTextSize(play_str, font_face, title_font_scale, 2)
        (w_res, h_res), _ = cv2.getTextSize(res_str, font_face, body_font_scale, 1)
        heading_str = "LIVE ACTIONS"
        (w_head, h_head), _ = cv2.getTextSize(heading_str, font_face, title_font_scale - 0.05, 2)

        max_act_w = 0
        formatted_actions: list[tuple[str, list[int]]] = []
        for act in unique_actions:
            act_color = self.config.action_colors.get(act, self.neutral_player)
            formatted = format_action_label(act)
            formatted_actions.append((formatted, act_color))
            (w_act, _), _ = cv2.getTextSize(formatted, font_face, body_font_scale, 1)
            if w_act > max_act_w:
                max_act_w = w_act

        pad = int(16 * scale)
        swatch_w = int(16 * scale)
        swatch_gap = int(8 * scale)
        live_action_row_w = swatch_w + swatch_gap + max_act_w

        content_w = max(w_play, w_res, w_head, live_action_row_w)
        min_card_w = int(220 * scale)
        card_w = max(min_card_w, content_w + (pad * 2))

        line_height_play = int(h_play + 4)
        line_height_res = int(h_res + 4)
        divider_gap = int(10 * scale)
        line_height_head = int(h_head + 4)
        action_item_h = int(22 * scale)

        num_actions = max(1, len(formatted_actions))
        actions_section_h = line_height_head + int(8 * scale) + (num_actions * action_item_h)

        card_h = (
            pad
            + line_height_play
            + int(6 * scale)
            + line_height_res
            + divider_gap
            + int(1 * scale)
            + divider_gap
            + actions_section_h
            + pad
        )

        x2 = w_frame - right_margin
        x1 = x2 - card_w
        y1 = top_margin
        y2 = y1 + card_h

        draw_rounded_rectangle(
            image=frame,
            pt1=(x1, y1),
            pt2=(x2, y2),
            color=(20, 24, 33),
            radius=corner_radius,
            alpha=bg_alpha,
            border_color=border_color,
            border_thickness=border_thickness,
        )

        # 1. Play Label (Cyan `#00E5FF`, prominent)
        curr_y = y1 + pad + line_height_play
        cv2.putText(
            frame,
            play_str,
            (x1 + pad, curr_y),
            font_face,
            title_font_scale,
            self.cyan_accent,
            2,
            cv2.LINE_AA,
        )

        # 2. Play Result (Light Gray `#B2B2B2`)
        curr_y += int(6 * scale) + line_height_res
        cv2.putText(
            frame,
            res_str,
            (x1 + pad, curr_y),
            font_face,
            body_font_scale,
            self.neutral_player,
            1,
            cv2.LINE_AA,
        )

        # 3. Horizontal Divider (Subtle muted gray)
        curr_y += divider_gap
        cv2.line(
            frame,
            (x1 + pad, curr_y),
            (x2 - pad, curr_y),
            (70, 75, 85),
            1,
            cv2.LINE_AA,
        )

        # 4. LIVE ACTIONS Heading (Cyan `#00E5FF`)
        curr_y += divider_gap + line_height_head
        cv2.putText(
            frame,
            heading_str,
            (x1 + pad, curr_y),
            font_face,
            title_font_scale - 0.05,
            self.cyan_accent,
            2,
            cv2.LINE_AA,
        )

        curr_y += int(10 * scale)

        # 5. Live Actions Swatches + Labels
        if not formatted_actions:
            cv2.putText(
                frame,
                "— None —",
                (x1 + pad, curr_y + int(12 * scale)),
                font_face,
                body_font_scale,
                (150, 150, 150),
                1,
                cv2.LINE_AA,
            )
            return

        for fmt_name, act_color in formatted_actions:
            swatch_y = curr_y + int(4 * scale)
            cv2.line(
                frame,
                (x1 + pad, swatch_y),
                (x1 + pad + swatch_w, swatch_y),
                act_color,
                3,
                cv2.LINE_AA,
            )
            cv2.putText(
                frame,
                fmt_name,
                (x1 + pad + swatch_w + swatch_gap, curr_y + int(12 * scale)),
                font_face,
                body_font_scale,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
            curr_y += action_item_h

    def draw_header(
        self,
        frame: np.ndarray,
        play_meta: PlayMetadata,
        current_frame: int,
        end_frame: int,
        fps: float,
    ) -> None:
        """Legacy header method retained for compatibility; unified card is drawn via renderer."""
        pass

    def draw_action_panel(
        self, frame: np.ndarray, active_actions: list[DenseFrameAnnotation]
    ) -> None:
        """Legacy action panel method retained for compatibility; unified card is drawn via renderer."""
        pass

    def draw_result_banner(self, frame: np.ndarray, result_tag: str) -> None:
        """Suppress center-screen result banner across all modes."""
        return



