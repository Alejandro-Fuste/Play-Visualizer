"""Unit tests for action label color parsing and rendering integration."""

from pathlib import Path
import numpy as np

from play_visualizer.config import hex_to_bgr, load_action_colors, load_config
from play_visualizer.models import DenseFrameAnnotation
from play_visualizer.overlays import OverlayRenderer


def test_hex_to_bgr():
    assert hex_to_bgr("#00ffff") == [255, 255, 0]   # Cyan (RGB: 0, 255, 255 -> BGR: 255, 255, 0)
    assert hex_to_bgr("#ff0000") == [0, 0, 255]     # Red (RGB: 255, 0, 0 -> BGR: 0, 0, 255)
    assert hex_to_bgr("a52a2a") == [42, 42, 165]    # Brown
    assert hex_to_bgr("invalid") == [0, 255, 0]     # Fallback


def test_load_action_colors():
    colors = load_action_colors()
    assert isinstance(colors, dict)
    assert "Action_ArcToEdge" in colors
    assert colors["Action_ArcToEdge"] == [0, 0, 255]  # #ff0000 -> BGR [0, 0, 255]
    assert "Object_Ball" in colors
    assert colors["Object_Ball"] == [255, 255, 0]    # #00ffff -> BGR [255, 255, 0]
    assert "Action_None" in colors
    assert colors["Action_None"] == [128, 128, 128]  # #808080 -> BGR [128, 128, 128]


def test_overlay_renderer_uses_action_colors():
    cfg = load_config()
    renderer = OverlayRenderer(config=cfg)

    # Annotation with Action_ArcToEdge (#ff0000 -> BGR [0, 0, 255])
    ann = DenseFrameAnnotation(
        frame=0,
        actor_track_id="1",
        xml_track_id="1",
        team_side="offense",
        position="QB",
        bbox_xyxy=(10.0, 10.0, 50.0, 100.0),
        action="Action_ArcToEdge",
    )

    box_color, bg_color, text_color, thickness = renderer._get_team_colors(
        team_side=ann.team_side,
        is_highlighted=False,
        action=ann.action,
    )

    assert box_color == [0, 0, 255]
    assert bg_color == [0, 0, 255]


def test_overlay_renderer_uses_action_none_color():
    cfg = load_config()
    renderer = OverlayRenderer(config=cfg)

    box_color, bg_color, text_color, thickness = renderer._get_team_colors(
        team_side="offense",
        is_highlighted=False,
        action="Action_None",
    )

    assert box_color == [128, 128, 128]
    assert bg_color == [128, 128, 128]


def test_overlay_renderer_fallback_for_unmapped_action():
    cfg = load_config()
    renderer = OverlayRenderer(config=cfg)

    box_color, _, _, _ = renderer._get_team_colors(
        team_side="offense",
        is_highlighted=False,
        action="Action_Unknown_NonExistent",
    )

    # Should fall back to offense style box_color [46, 204, 113]
    assert box_color == [46, 204, 113]


