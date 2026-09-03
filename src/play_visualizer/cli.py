"""Command Line Interface (CLI) entry point for tapevision-visualizer."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional


import typer

from .annotation_index import AnnotationIndex
from .annotation_loader import load_annotation_file
from .config import load_config
from .ffmpeg import run_ffmpeg_encode
from .logging_utils import setup_logger, write_run_report
from .models import RenderReport
from .renderer import FrameRenderer
from .validator import InputValidator
from .video_io import VideoReader, VideoWriter

app = typer.Typer(
    name="tapevision-visualizer",
    help="TapeVision Football Annotation Video Visualizer CLI",
    add_completion=False,
)


@app.command()
def main(
    video: Path = typer.Option(
        ..., "--video", "-v", help="Path to source football video MP4."
    ),
    annotations: Path = typer.Option(
        ..., "--annotations", "-a", help="Path to TapeVision JSON annotation file."
    ),
    output: Path = typer.Option(
        ..., "--output", "-o", help="Destination path for annotated output MP4."
    ),
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Optional YAML configuration file path."
    ),
    action_labels: Optional[Path] = typer.Option(
        None, "--action-labels", help="Optional action labels JSON file path containing action colors."
    ),
    start_frame: Optional[int] = typer.Option(
        None, "--start-frame", help="First frame to render (zero-based index)."
    ),
    end_frame: Optional[int] = typer.Option(
        None, "--end-frame", help="Last frame to render (zero-based index)."
    ),
    include_unannotated_tail: bool = typer.Option(
        False, "--include-unannotated-tail", help="Keep video frames after the last annotated frame."
    ),
    show_defense: bool = typer.Option(
        True, "--show-defense/--hide-defense", help="Draw defensive player boxes."
    ),
    show_offense: bool = typer.Option(
        True, "--show-offense/--hide-offense", help="Draw offensive player boxes."
    ),
    show_action_panel: bool = typer.Option(
        True, "--show-action-panel/--hide-action-panel", help="Display the LIVE ACTIONS panel."
    ),
    show_timeline: bool = typer.Option(
        False, "--show-timeline/--hide-timeline", help="Display the play timeline."
    ),
    slow_motion_replay: bool = typer.Option(
        False, "--slow-motion-replay", help="Append an optional highlighted replay (future milestone)."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Validate inputs without producing an output video."
    ),
    overwrite: bool = typer.Option(
        False, "--overwrite", help="Permit replacing an existing output file."
    ),
    log_level: str = typer.Option(
        "INFO", "--log-level", help="Logging verbosity (DEBUG, INFO, WARNING, ERROR)."
    ),
) -> None:
    """TapeVision Football Annotation Video Visualizer command entry point."""
    logger = setup_logger(log_level)

    logger.info("Initializing TapeVision Visualizer...")
    logger.info(f"Source video: {video}")
    logger.info(f"Annotations: {annotations}")
    logger.info(f"Output path: {output}")

    # Output file safety check
    if output.exists() and not overwrite and not dry_run:
        logger.error(
            f"Output file already exists: {output}. Use --overwrite to permit replacing existing files."
        )
        sys.exit(1)

    # 1. Load configuration
    cfg = load_config(config, action_labels)

    # 2. Load annotation package
    try:
        pkg = load_annotation_file(annotations)
        logger.info(f"Successfully loaded annotations (schema: {pkg.schema_version})")
    except Exception as e:
        logger.error(f"Failed to load annotation file: {e}")
        sys.exit(1)

    # 3. Build annotation index
    index = AnnotationIndex(pkg)

    # 4. Inspect video properties
    try:
        reader = VideoReader(video)
        logger.info(
            f"Video properties: {reader.metadata.width}x{reader.metadata.height} @ "
            f"{reader.metadata.fps} fps ({reader.metadata.num_frames} frames, audio={reader.metadata.has_audio})"
        )
    except Exception as e:
        logger.error(f"Failed to inspect source video: {e}")
        sys.exit(1)

    # 5. Run validation checks
    validator = InputValidator(video_meta=reader.metadata, pkg=pkg, index=index)
    render_start, render_end, warnings = validator.validate_all(
        user_start_frame=start_frame,
        user_end_frame=end_frame,
        include_tail=include_unannotated_tail,
    )

    # Check for fatal validation errors
    fatal_errors = [w for w in warnings if w.severity == "ERROR"]
    if fatal_errors:
        for err in fatal_errors:
            logger.error(f"Validation Error [{err.code}]: {err.message}")
        sys.exit(1)

    for w in warnings:
        logger.warning(f"Validation [{w.code}]: {w.message}")

    rendered_count = render_end - render_start + 1

    # Exit early if dry-run
    if dry_run:
        logger.info("Dry-run mode enabled. Validation successful. Exiting without rendering video.")
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
        report_path = output.parent / f"{output.stem}.report.json"
        write_run_report(report, report_path)
        logger.info(f"Run report written to {report_path}")
        reader.close()
        sys.exit(0)

    # 6. Setup intermediate output video path
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
    except Exception as e:
        logger.error(f"Failed to initialize intermediate VideoWriter: {e}")
        reader.close()
        sys.exit(1)

    # 7. Execute frame rendering
    renderer = FrameRenderer(
        config=cfg,
        pkg=pkg,
        index=index,
        show_offense=show_offense,
        show_defense=show_defense,
        show_action_panel=show_action_panel,
        show_timeline=show_timeline,
    )

    try:
        total_rendered = renderer.render_video(
            reader=reader,
            writer=writer,
            start_frame=render_start,
            end_frame=render_end,
        )
    except Exception as e:
        logger.error(f"Error during frame rendering: {e}")
        reader.close()
        writer.close()
        sys.exit(1)
    finally:
        reader.close()
        writer.close()

    # 8. Post-processing FFmpeg H.264 encode & audio muxing
    ffmpeg_cfg = cfg.ffmpeg
    audio_cfg = cfg.audio
    intermediate_cfg = cfg.intermediate

    try:
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
    except Exception as e:
        logger.error(f"FFmpeg encoding error: {e}")
        sys.exit(1)

    # Cleanup temp dir if empty
    if temp_dir.exists() and not any(temp_dir.iterdir()):
        try:
            temp_dir.rmdir()
        except Exception:
            pass

    # 9. Build and write run report
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


    logger.info(f"Processing complete! Rendered MP4: {output}")
    logger.info(f"Run report saved: {report_path}")


if __name__ == "__main__":
    app()
