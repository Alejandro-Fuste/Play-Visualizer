"""Filtering and priority logic for actions."""

from __future__ import annotations

from collections.abc import Sequence

from .config import ConfigModel
from .config import ConfigModel
from .models import DenseFrameAnnotation

DEFAULT_PRIORITY = [
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
]

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


class ActionFilter:
    """Filter and prioritize annotations based on configuration."""

    def __init__(self, config: ConfigModel):
        self.config = config

        portfolio_hidden = config.hidden_actions.get("portfolio", []) if isinstance(config.hidden_actions, dict) else []
        self.hidden_actions = set(portfolio_hidden)
        self.action_priority = config.action_priority or DEFAULT_PRIORITY

        suspicious_cfg = config.suspicious_actions
        self.suspicious_offensive_actions = set(
            suspicious_cfg.get("defensive_offensive_actions", list(SUSPICIOUS_DEFENSE_OFFENSIVE_ACTIONS))
        )
        self.suppress_suspicious = suspicious_cfg.get("suppress_in_portfolio", True)

        # Build priority rank dict (lower index = higher priority)
        self.priority_rank = {act: i for i, act in enumerate(self.action_priority)}

    def is_action_hidden(self, annotation: DenseFrameAnnotation) -> bool:
        """Check if an annotation's action should be hidden."""
        if annotation.action in self.hidden_actions:
            return True

        if (
            self.suppress_suspicious
            and annotation.team_side == "defense"
            and annotation.action in self.suspicious_offensive_actions
        ):
            return True

        return False

    def get_action_priority(self, action_name: str) -> int:
        """Get numerical priority rank (lower number = higher priority)."""
        if action_name == "Action_None":
            return 9999
        return self.priority_rank.get(action_name, 999)

    def filter_frame_annotations(
        self, annotations: Sequence[DenseFrameAnnotation]
    ) -> list[DenseFrameAnnotation]:
        """Filter a frame's annotations according to configured rules."""
        filtered = []
        for ann in annotations:
            if not self.is_action_hidden(ann):
                filtered.append(ann)
        return filtered


    def get_highest_priority_annotation_per_actor(
        self, annotations: Sequence[DenseFrameAnnotation]
    ) -> dict[str, DenseFrameAnnotation]:
        """Group frame annotations by actor ID and pick the highest priority action for each actor."""
        grouped: dict[str, list[DenseFrameAnnotation]] = {}
        for ann in annotations:
            grouped.setdefault(ann.actor_track_id, []).append(ann)

        best_per_actor: dict[str, DenseFrameAnnotation] = {}
        for actor_id, actor_anns in grouped.items():
            best_ann = min(actor_anns, key=lambda a: self.get_action_priority(a.action))
            best_per_actor[actor_id] = best_ann

        return best_per_actor

    def get_active_panel_actions(
        self, annotations: Sequence[DenseFrameAnnotation], max_items: int = 5
    ) -> list[DenseFrameAnnotation]:
        """Get top active meaningful actions for the current-actions panel."""
        meaningful = [ann for ann in annotations if not self.is_action_hidden(ann)]

        # Deduplicate same actor + action combination
        seen_combos = set()
        unique_anns = []
        for ann in meaningful:
            key = (ann.actor_track_id, ann.action)
            if key not in seen_combos:
                seen_combos.add(key)
                unique_anns.append(ann)

        # Sort by priority rank
        sorted_anns = sorted(unique_anns, key=lambda a: self.get_action_priority(a.action))

        return sorted_anns[:max_items]
