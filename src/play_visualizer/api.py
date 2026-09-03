"""High-level Python API entry point for external codebase integration."""

from __future__ import annotations

import logging
from pathlib import Path

from .annotation_index import AnnotationIndex
from .annotation_loader import load_annotation_file
from .config import load_config
from .ffmpeg import run_ffmpeg_encode
from .logging_utils import setup_logger, write_run_report
from .models import RenderReport
from .renderer import FrameRenderer
from .validator import InputValidator
from .video_io import VideoReader, VideoWriter


def render_annotation_video(
    video: str | Path,
    annotations: str | Path,
    output: str | Path,
    config: str | Path | None = None,
    action_labels: str | Path | None = None,
    start_frame: int | None = None,
    end_frame: int | None = None,
    include_unannotated_tail: bool = False,
    show_defense: bool = True,
    show_offense: bool = True,
    show_action_panel: bool = True,
    show_timeline: bool = False,
    dry_run: bool = False,
    overwrite: bool = False,
    log_level: str = "INFO",
) -> RenderReport:
    """Render TapeVision annotations onto a video file via Python API.

    Returns a RenderReport object detailing the execution result.
    """
    video = Path(video)
    annotations = Path(annotations)
    output = Path(output)
    config = Path(config) if config else None
    action_labels = Path(action_labels) if action_labels else None

    logger = setup_logger(log_level)

    logger.info("Initializing TapeVision Visualizer API...")
    logger.info(f"Source video: {video}")
    logger.info(f"Annotations: {annotations}")
    logger.info(f"Output path: {output}")

    if output.exists() and not overwrite and not dry_run:
        raise FileExistsError(
            f"Output file already exists: {output}. Set overwrite=True to permit replacing existing files."
        )

    cfg = load_config(config, action_labels)
    pkg = load_annotation_file(annotations)
    index = AnnotationIndex(pkg)

    reader = VideoReader(video)

    validator = InputValidator(video_meta=reader.metadata, pkg=pkg, index=index)
    render_start, render_end, warnings = validator.validate_all(
        user_start_frame=start_frame,
        user_end_frame=end_frame,
        include_tail=include_unannotated_tail,
    )

    fatal_errors = [w for w in warnings if w.severity == "ERROR"]
    if fatal_errors:
        reader.close()
        raise ValueError(f"Fatal validation error: {fatal_errors[0].message}")

    rendered_count = render_end - render_start + 1

    if dry_run:
        report = RenderReport(
            input_video=str(video),
            input_annotations=str(annotations),
            output_video=str(output),
            mode="standard",
            video_properties=reader.metadata.model_dump(),
            annotation_properties={
                "clip": pkg.clip.model_dump(),
                "play": pkg.play.model_dump(),
                "num_players": len(pkg.players),
                "num_action_segments": len(pkg.action_segments),
                "num_dense_annotations": len(pkg.dense_annotations),
            },
            rendered_frame_start=render_start,
            rendered_frame_end=render_end,
            rendered_frames=rendered_count,
            warnings=[w.model_dump() for w in warnings],
            skipped_annotations=0,
            ffmpeg_command="",
            status="dry_run_success",
        )
        reader.close()
        return report

    temp_dir = output.parent / ".tmp_tapevision"
    temp_dir.mkdir(parents=True, exist_ok=True)
    intermediate_path = temp_dir / f"{output.stem}.intermediate.mp4"

    try:
        writer = VideoWriter(
            output_path=intermediate_path,
            width=reader.metadata.width,
            height=reader.metadata.height,
            fps=reader.metadata.fps,
        )
        renderer = FrameRenderer(
            config=cfg,
            pkg=pkg,
            index=index,
            show_offense=show_offense,
            show_defense=show_defense,
            show_action_panel=show_action_panel,
            show_timeline=show_timeline,
        )
        total_rendered = renderer.render_video(
            reader=reader,
            writer=writer,
            start_frame=render_start,
            end_frame=render_end,
        )
    finally:
        reader.close()
        if 'writer' in locals():
            writer.close()

    ffmpeg_cfg = cfg.ffmpeg
    audio_cfg = cfg.audio
    intermediate_cfg = cfg.intermediate

    cmd_str = run_ffmpeg_encode(
        intermediate_path=intermediate_path,
        final_output_path=output,
        source_video_path=video,
        has_audio=reader.metadata.has_audio and audio_cfg.get("preserve", True),
        crf=ffmpeg_cfg.get("crf", 18),
        preset=ffmpeg_cfg.get("preset", "medium"),
        pix_fmt=ffmpeg_cfg.get("pix_fmt", "yuv420p"),
        movflags=ffmpeg_cfg.get("movflags", "+faststart"),
        keep_intermediate=intermediate_cfg.get("keep", False),
    )

    if temp_dir.exists() and not any(temp_dir.iterdir()):
        try:
            temp_dir.rmdir()
        except Exception:
            pass

    report = RenderReport(
        input_video=str(video),
        input_annotations=str(annotations),
        output_video=str(output),
        mode="standard",
        video_properties=reader.metadata.model_dump(),
        annotation_properties={
            "clip": pkg.clip.model_dump(),
            "play": pkg.play.model_dump(),
            "num_players": len(pkg.players),
            "num_action_segments": len(pkg.action_segments),
            "num_dense_annotations": len(pkg.dense_annotations),
        },
        rendered_frame_start=render_start,
        rendered_frame_end=render_end,
        rendered_frames=total_rendered,
        warnings=[w.model_dump() for w in warnings],
        skipped_annotations=renderer.skipped_annotations_count,
        ffmpeg_command=cmd_str,
        status="success",
    )

    report_path = output.parent / f"{output.stem}.report.json"
    write_run_report(report, report_path)
    return report
