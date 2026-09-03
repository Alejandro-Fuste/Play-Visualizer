"""Configuration loader and management for Play-Visualizer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "default_visualization.yaml"
DEFAULT_ACTION_LABELS_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "action_labels.json"


def hex_to_bgr(hex_code: str) -> list[int]:
    """Convert hex color string (e.g. '#00ffff') to OpenCV BGR list [B, G, R]."""
    hex_str = hex_code.lstrip("#")
    if len(hex_str) == 6:
        r = int(hex_str[0:2], 16)
        g = int(hex_str[2:4], 16)
        b = int(hex_str[4:6], 16)
        return [b, g, r]
    return [0, 255, 0]


def load_action_colors(action_labels_path: Path | None = None) -> dict[str, list[int]]:
    """Load action label definitions JSON and return mapping of action name to BGR color."""
    target_path = (
        action_labels_path
        if action_labels_path and action_labels_path.exists()
        else DEFAULT_ACTION_LABELS_PATH
    )

    if not target_path.exists():
        return {}

    try:
        with open(target_path, encoding="utf-8") as f:
            data = json.load(f)

        colors: dict[str, list[int]] = {}
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "name" in item and "color" in item:
                    colors[item["name"]] = hex_to_bgr(item["color"])
        return colors
    except Exception:
        return {}


class StyleConfig(BaseModel):
    box_color: list[int]
    label_bg_color: list[int]
    text_color: list[int]
    thickness: int


class ConfigModel(BaseModel):
    modes: dict[str, Any] = Field(default_factory=dict)
    portfolio: dict[str, Any] = Field(default_factory=dict)
    styles: dict[str, Any] = Field(default_factory=dict)
    fonts: dict[str, Any] = Field(default_factory=dict)
    hidden_actions: dict[str, list[str]] = Field(default_factory=dict)
    action_priority: list[str] = Field(default_factory=list)
    suspicious_actions: dict[str, Any] = Field(default_factory=dict)
    panel: dict[str, Any] = Field(default_factory=dict)
    timeline: dict[str, Any] = Field(default_factory=dict)
    ffmpeg: dict[str, Any] = Field(default_factory=dict)
    audio: dict[str, Any] = Field(default_factory=dict)
    intermediate: dict[str, Any] = Field(default_factory=dict)
    action_colors: dict[str, list[int]] = Field(default_factory=dict)


def load_config(
    config_path: Path | None = None,
    action_labels_path: Path | None = None,
) -> ConfigModel:
    """Load configuration from a YAML file, falling back to default config if none provided."""
    target_path = config_path if config_path and config_path.exists() else DEFAULT_CONFIG_PATH
    action_colors = load_action_colors(action_labels_path)

    if not target_path.exists():
        # Return fallback configuration if file doesn't exist
        return ConfigModel(
            styles={
                "offense": StyleConfig(box_color=[46, 204, 113], label_bg_color=[39, 174, 96], text_color=[255, 255, 255], thickness=2),
                "defense": StyleConfig(box_color=[231, 76, 60], label_bg_color=[192, 57, 43], text_color=[255, 255, 255], thickness=2),
                "active_highlight": StyleConfig(box_color=[241, 196, 15], label_bg_color=[243, 156, 18], text_color=[0, 0, 0], thickness=3),
                "ball": StyleConfig(box_color=[52, 152, 219], label_bg_color=[41, 128, 185], text_color=[255, 255, 255], thickness=3),
                "neutral": StyleConfig(box_color=[149, 165, 166], label_bg_color=[127, 140, 141], text_color=[255, 255, 255], thickness=2),
            },
            hidden_actions={
                "portfolio": ["Action_Unknown", "Action_Defense_NotAnnotated"],
                "technical": [],
            },
            action_priority=[
                "Action_BallSnap",
                "Action_SnapReceive",
                "Action_JetMotion",
                "Action_Toss",
                "Action_BallCarry",
                "Action_ZoneBlock",
                "Action_LeadBlock",
                "Action_BlockSecondLevel",
                "Action_SealBlock",
                "Action_PlayEnd_OutOfBounds",
            ],
            panel={"max_items": 5, "bg_alpha": 0.8, "position": "top_right", "top_margin": 52, "right_margin": 24, "corner_radius": 14, "border_color": [255, 229, 0], "border_thickness": 1},
            timeline={"height_px": 50, "bg_alpha": 0.8},
            ffmpeg={"crf": 18, "preset": "medium", "pix_fmt": "yuv420p", "movflags": "+faststart"},
            audio={"preserve": True},
            intermediate={"keep": False},
            action_colors=action_colors,
        )

    with open(target_path, encoding="utf-8") as f:
        raw_data = yaml.safe_load(f) or {}

    cfg = ConfigModel(**raw_data)
    if action_colors:
        cfg.action_colors = action_colors
    return cfg

