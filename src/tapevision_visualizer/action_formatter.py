"""Formatting utilities for action labels, play tags, and result tags."""

from __future__ import annotations

import re

EXPLICIT_ACTION_MAP = {
    "Action_JetMotion": "Jet Motion",
    "Action_BallSnap": "Ball Snap",
    "Action_SnapReceive": "Snap Receive",
    "Action_Toss": "Toss",
    "Action_BallCarry": "Ball Carry",
    "Action_ZoneBlock": "Zone Block",
    "Action_LeadBlock": "Lead Block",
    "Action_BlockSecondLevel": "Second-Level Block",
    "Action_SealBlock": "Seal Block",
    "Action_PlayEnd_OutOfBounds": "Out of Bounds",
    "Action_None": "None",
    "Action_Unknown": "Unknown",
    "Action_Defense_NotAnnotated": "Not Annotated",
}

EXPLICIT_PLAY_MAP = {
    "Play_Run_JetSweep": "Jet Sweep",
    "Play_Pass_QuickScreen": "Quick Screen",
    "Play_Unknown": "Unknown Play",
}

EXPLICIT_RESULT_MAP = {
    "Result_OutOfBounds": "Out of Bounds",
    "Result_Touchdown": "Touchdown",
    "Result_IncompletePass": "Incomplete Pass",
    "Result_Unknown": "Unknown Result",
}


def format_action_label(raw_action: str) -> str:
    """Convert machine action label to human-readable text."""
    if not raw_action:
        return "Unknown"

    if raw_action in EXPLICIT_ACTION_MAP:
        return EXPLICIT_ACTION_MAP[raw_action]

    # Strip prefix if present
    cleaned = raw_action
    if cleaned.startswith("Action_"):
        cleaned = cleaned[7:]

    # Convert camelCase / PascalCase or snake_case to Space Separated
    cleaned = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", cleaned)
    cleaned = cleaned.replace("_", " ").strip()

    return cleaned


def format_play_tag(raw_play: str) -> str:
    """Convert machine play tag to human-readable text."""
    if not raw_play:
        return "Unknown Play"

    if raw_play in EXPLICIT_PLAY_MAP:
        return EXPLICIT_PLAY_MAP[raw_play]

    cleaned = raw_play
    if cleaned.startswith("Play_"):
        cleaned = cleaned[5:]
    cleaned = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", cleaned)
    cleaned = cleaned.replace("_", " ").strip()
    return cleaned


def format_result_tag(raw_result: str) -> str:
    """Convert machine result tag to human-readable text."""
    if not raw_result:
        return "Unknown Result"

    if raw_result in EXPLICIT_RESULT_MAP:
        return EXPLICIT_RESULT_MAP[raw_result]

    cleaned = raw_result
    if cleaned.startswith("Result_"):
        cleaned = cleaned[7:]
    cleaned = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", cleaned)
    cleaned = cleaned.replace("_", " ").strip()
    return cleaned
