"""Core frame rendering pipeline orchestrator."""

from __future__ import annotations

import logging

from .action_filter import ActionFilter
from .annotation_index import AnnotationIndex
from .config import ConfigModel
from .models import TapeVisionAnnotationPackage
from .overlays import OverlayRenderer
from .timeline import TimelineRenderer
from .validator import clamp_bbox
from .video_io import VideoReader, VideoWriter

logger = logging.getLogger("tapevision_visualizer")


class FrameRenderer:
    """Orchestrates frame-by-frame annotation rendering onto video frames."""

    def __init__(
        self,
        config: ConfigModel,
        pkg: TapeVisionAnnotationPackage,
        index: AnnotationIndex,
        show_offense: bool = True,
        show_defense: bool = True,
        show_action_panel: bool = True,
        show_timeline: bool = False,
    ):
        self.config = config
        self.pkg = pkg
        self.index = index
        self.show_offense = show_offense
        self.show_defense = show_defense
        self.show_action_panel = show_action_panel
        self.show_timeline = show_timeline

        self.action_filter = ActionFilter(config=self.config)
        self.overlay_renderer = OverlayRenderer(config=self.config)
        self.timeline_renderer = TimelineRenderer(
            action_segments=self.pkg.action_segments, play_meta=self.pkg.play
        )

        self.skipped_annotations_count = 0
        self.rendered_frames_count = 0


    def render_video(
        self,
        reader: VideoReader,
        writer: VideoWriter,
        start_frame: int,
        end_frame: int,
    ) -> int:
        """Process video frames within [start_frame, end_frame] and write annotated frames.

        Returns total rendered frame count.
        """
        self.skipped_annotations_count = 0
        self.rendered_frames_count = 0

        total_to_render = max(1, end_frame - start_frame + 1)
        fps = reader.metadata.fps
        width = reader.metadata.width
        height = reader.metadata.height

        logger.info(f"Beginning frame rendering: frames {start_frame} to {end_frame} ({total_to_render} frames)")

        for frame_idx, frame in reader.stream_frames(start_frame=start_frame, end_frame=end_frame):
            # 1. Fetch raw annotations for this frame
            frame_annotations = self.index.for_frame(frame_idx)

            # 2. Filter annotations by offense/defense toggles
            allowed_anns = []
            for ann in frame_annotations:
                if ann.team_side == "offense" and not self.show_offense:
                    continue
                if ann.team_side == "defense" and not self.show_defense:
                    continue
                allowed_anns.append(ann)

            # 3. Apply mode action filtering
            filtered_anns = self.action_filter.filter_frame_annotations(allowed_anns)

            # Pick highest priority annotation per actor if multiple exist
            best_per_actor = self.action_filter.get_highest_priority_annotation_per_actor(filtered_anns)

            # 4. Draw player bounding boxes & labels
            for _actor_id, ann in best_per_actor.items():
                clamped_box = clamp_bbox(ann.bbox_xyxy, width, height)
                if clamped_box is None:
                    self.skipped_annotations_count += 1
                    continue

                # Check if this performer is engaged in an active key action
                is_key_performer = (
                    ann.action
                    not in (
                        "Action_None",
                        "Action_Unknown",
                        "Action_Defense_NotAnnotated",
                    )
                    and self.action_filter.get_action_priority(ann.action) < 10
                )

                self.overlay_renderer.draw_player_box_and_label(
                    frame=frame,
                    annotation=ann,
                    clamped_xyxy=clamped_box,
                    is_highlighted=is_key_performer,
                )

            # 5. Draw ball bounding boxes if ball samples exist for frame
            ball_boxes = self.index.get_ball_boxes_for_frame(frame_idx)
            for ball_xyxy in ball_boxes:
                clamped_ball = clamp_bbox(ball_xyxy, width, height)
                if clamped_ball is not None:
                    self.overlay_renderer.draw_ball_box(frame, clamped_ball)

            # 6. Draw unified Play Info + Live Actions card in upper-right area
            if self.show_action_panel:
                active_panel_anns = self.action_filter.get_active_panel_actions(
                    filtered_anns, max_items=self.config.panel.get("max_items", 5)
                )
                self.overlay_renderer.draw_unified_info_card(
                    frame=frame,
                    play_meta=self.pkg.play,
                    active_actions=active_panel_anns,
                )

            # 8. Draw result banner on result frame
            if (
                self.pkg.play.result_frame is not None
                and frame_idx == self.pkg.play.result_frame
            ):
                self.overlay_renderer.draw_result_banner(
                    frame, self.pkg.play.result_tag
                )

            # 9. Draw timeline progress bar at bottom
            if self.show_timeline:
                self.timeline_renderer.draw_timeline(
                    frame=frame,
                    current_frame=frame_idx,
                    start_frame=start_frame,
                    end_frame=end_frame,
                )

            # Write frame to output writer
            writer.write_frame(frame)
            self.rendered_frames_count += 1

            # Log progress every 50 frames
            if (
                self.rendered_frames_count % 50 == 0
                or self.rendered_frames_count == total_to_render
            ):
                pct = (self.rendered_frames_count / total_to_render) * 100.0
                logger.info(
                    f"Render progress: {self.rendered_frames_count}/{total_to_render} frames ({pct:.1f}%)"
                )

        logger.info(
            f"Completed frame rendering. Total frames rendered: {self.rendered_frames_count}"
        )
        return self.rendered_frames_count
