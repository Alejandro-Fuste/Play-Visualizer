"""Tests for rounded rectangle helper and unified info card overlay rendering."""

import numpy as np
import pytest

from play_visualizer.config import load_config
from play_visualizer.models import DenseFrameAnnotation, PlayMetadata
from play_visualizer.overlays import OverlayRenderer, draw_rounded_rectangle


def test_draw_rounded_rectangle():
    img = np.zeros((200, 300, 3), dtype=np.uint8)
    draw_rounded_rectangle(
        image=img,
        pt1=(20, 20),
        pt2=(280, 180),
        color=(20, 24, 33),
        radius=14,
        alpha=0.8,
        border_color=(255, 229, 0),
        border_thickness=1,
    )
    # Check that drawing modified the image (central area and border are not all zeros)
    assert np.any(img != 0)


def test_draw_unified_info_card():
    config = load_config()
    renderer = OverlayRenderer(config)

    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    play_meta = PlayMetadata(
        play_tag="Action_JetSweep",
        result_tag="Action_PlayEnd_OutOfBounds",
    )
    active_actions = [
        DenseFrameAnnotation(
            frame=10,
            actor_track_id="16",
            position="WR-F",
            team_side="offense",
            action="Action_JetMotion",
            bbox_xyxy=[100, 100, 150, 200],
        ),
        DenseFrameAnnotation(
            frame=10,
            actor_track_id="64",
            position="RG",
            team_side="offense",
            action="Action_LeadBlock",
            bbox_xyxy=[200, 200, 250, 300],
        ),
    ]

    renderer.draw_unified_info_card(frame, play_meta, active_actions)
    # Check that the card was rendered into the upper-right quadrant
    upper_right_region = frame[52:300, 1500:1900]
    assert np.any(upper_right_region != 0)
