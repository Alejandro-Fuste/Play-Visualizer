"""Unit tests for action, play, and result tag formatters."""

from play_visualizer.action_formatter import (
    format_action_label,
    format_play_tag,
    format_result_tag,
)


def test_explicit_action_mappings():
    assert format_action_label("Action_JetMotion") == "Jet Motion"
    assert format_action_label("Action_BallSnap") == "Ball Snap"
    assert format_action_label("Action_SnapReceive") == "Snap Receive"
    assert format_action_label("Action_Toss") == "Toss"
    assert format_action_label("Action_BallCarry") == "Ball Carry"
    assert format_action_label("Action_BlockSecondLevel") == "Second-Level Block"


def test_fallback_action_formatter():
    assert format_action_label("Action_RunAfterCatch") == "Run After Catch"
    assert format_action_label("Action_CustomNewMove") == "Custom New Move"


def test_play_and_result_formatters():
    assert format_play_tag("Play_Run_JetSweep") == "Jet Sweep"
    assert format_result_tag("Result_OutOfBounds") == "Out of Bounds"
