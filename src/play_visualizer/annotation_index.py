"""In-memory indexing for fast frame-by-frame annotation lookup."""

from __future__ import annotations

from collections import defaultdict

from .models import (
    ActionSegment,
    DenseFrameAnnotation,
    TapeVisionAnnotationPackage,
)


class AnnotationIndex:
    """Pre-indexed lookup structure for TapeVision annotations."""

    def __init__(self, pkg: TapeVisionAnnotationPackage):
        self.pkg = pkg
        self.by_frame: dict[int, list[DenseFrameAnnotation]] = defaultdict(list)
        self.actor_metadata: dict[str, dict] = {}
        self.action_segments_by_actor: dict[str, list[ActionSegment]] = defaultdict(list)
        self.ball_by_frame: dict[int, list[tuple[float, float, float, float]]] = defaultdict(list)
        self.is_fallback: bool = False
        self.duplicate_count: int = 0

        self._build_index()

    def _build_index(self) -> None:
        """Construct the lookup tables."""
        # 1. Build actor metadata from player tracks
        for player in self.pkg.players:
            self.actor_metadata[player.actor_track_id] = {
                "xml_track_id": player.xml_track_id,
                "actor_track_id": player.actor_track_id,
                "position": player.position,
                "team_side": player.team_side,
            }

        # 2. Build action segments lookup
        for segment in self.pkg.action_segments:
            self.action_segments_by_actor[segment.actor_track_id].append(segment)

        # 3. Build ball index if ball samples exist
        for ball_track in self.pkg.ball:
            for sample in ball_track.samples:
                self.ball_by_frame[sample.frame].append(sample.bbox_xyxy)

        # 4. Build dense frame annotation index
        if self.pkg.dense_annotations:
            seen_combos = set()
            for ann in self.pkg.dense_annotations:
                # Deduplication key
                combo_key = (
                    ann.frame,
                    ann.actor_track_id,
                    ann.position,
                    ann.team_side,
                    ann.action,
                    ann.bbox_xyxy,
                )
                if combo_key in seen_combos:
                    self.duplicate_count += 1
                    continue
                seen_combos.add(combo_key)
                self.by_frame[ann.frame].append(ann)
        else:
            # Fallback path: generate dense annotations from track samples
            self.is_fallback = True
            for player in self.pkg.players:
                for p_sample in player.samples:
                    ann = DenseFrameAnnotation(
                        frame=p_sample.frame,
                        actor_track_id=player.actor_track_id,
                        xml_track_id=player.xml_track_id,
                        position=player.position,
                        team_side=player.team_side,
                        action="Action_Unknown",
                        bbox_xyxy=p_sample.bbox_xyxy,
                        bbox_xywh=p_sample.bbox_xywh,
                    )
                    self.by_frame[sample.frame].append(ann)

    def for_frame(self, frame_number: int) -> list[DenseFrameAnnotation]:
        """Retrieve all dense annotations for a given frame index."""
        return self.by_frame.get(frame_number, [])

    def get_ball_boxes_for_frame(self, frame_number: int) -> list[tuple[float, float, float, float]]:
        """Retrieve ball bounding boxes for a given frame index."""
        return self.ball_by_frame.get(frame_number, [])

    def get_actor_info(self, actor_id: str) -> dict:
        """Get actor metadata dictionary."""
        return self.actor_metadata.get(
            actor_id,
            {"xml_track_id": "0", "actor_track_id": actor_id, "position": "UNK", "team_side": "unknown"},
        )
