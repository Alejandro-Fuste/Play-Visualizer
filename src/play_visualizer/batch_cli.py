"""Command Line Interface for Google Colab Showcase Batch-Rendering Workflow."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import List, Optional

import typer

from .batch_models import BatchRenderStatus, PreflightStatus
from .batch_pipeline import BatchPipeline
from .logging_utils import setup_logger

app = typer.Typer(
    name="play-visualizer-showcase-batch",
    help="Play-Visualizer Google Colab Showcase Batch-Rendering CLI",
    add_completion=False,
)


@app.command()
def main(
    videos_root: Path = typer.Option(
        ...,
        "--videos-root",
        help="Path to directory containing source football videos (e.g. JetSweep_1.mp4).",
    ),
    annotations_root: Path = typer.Option(
        ...,
        "--annotations-root",
        help="Path to directory containing extracted annotation folders (<PlayName>/<ClipName>/annotations.json).",
    ),
    output_root: Path = typer.Option(
        ...,
        "--output-root",
        help="Persistent Google Drive directory for output videos and reports.",
    ),
    manifest: Optional[Path] = typer.Option(
        None,
        "--manifest",
        "-m",
        help="Path to authoritative showcase_clips.json (defaults to packaged config/showcase_clips.json).",
    ),
    inventory: Optional[Path] = typer.Option(
        None,
        "--inventory",
        "-i",
        help="Optional path to 1_Videos_Inventory.csv for provenance cross-checking.",
    ),
    scratch_root: Path = typer.Option(
        Path("/content/play_visualizer_batch"),
        "--scratch-root",
        help="Local scratch directory for intermediate rendering and staging.",
    ),
    clip: Optional[List[str]] = typer.Option(
        None,
        "--clip",
        help="Specific clip name to process (repeatable, e.g. --clip JetSweep_1 --clip Power_3).",
    ),
    clips: Optional[str] = typer.Option(
        None,
        "--clips",
        help="Comma-separated list of clip names (e.g. --clips JetSweep_1,Power_3).",
    ),
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Optional custom YAML visualization configuration file path.",
    ),
    action_labels: Optional[Path] = typer.Option(
        None,
        "--action-labels",
        help="Optional action labels JSON path containing action color mappings.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Validate manifest, paths, schema, and video stream properties without rendering MP4s.",
    ),
    resume: bool = typer.Option(
        False,
        "--resume",
        help="Skip verified, up-to-date completed clips matching input fingerprints.",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Permit overwriting existing outputs using safe staging and atomic commit.",
    ),
    show_timeline: bool = typer.Option(
        False,
        "--show-timeline/--hide-timeline",
        help="Display play timeline progress bar at bottom of frame.",
    ),
    show_offense: bool = typer.Option(
        True,
        "--show-offense/--hide-offense",
        help="Draw offensive player bounding boxes.",
    ),
    show_defense: bool = typer.Option(
        True,
        "--show-defense/--hide-defense",
        help="Draw defensive player bounding boxes.",
    ),
    show_action_panel: bool = typer.Option(
        True,
        "--show-action-panel/--hide-action-panel",
        help="Display LIVE ACTIONS card in upper-right.",
    ),
    include_unannotated_tail: bool = typer.Option(
        False,
        "--include-unannotated-tail",
        help="Render all video frames through the end of the video file.",
    ),
    log_level: str = typer.Option(
        "INFO",
        "--log-level",
        help="Logging verbosity (DEBUG, INFO, WARNING, ERROR).",
    ),
) -> None:
    """Execute the showcase batch rendering pipeline in Google Colab."""
    logger = setup_logger(log_level)

    logger.info("Initializing Play-Visualizer Showcase Batch Pipeline...")
    logger.info(f"Videos root: {videos_root}")
    logger.info(f"Annotations root: {annotations_root}")
    logger.info(f"Output root: {output_root}")
    logger.info(f"Scratch root: {scratch_root}")

    # Check mutual exclusivity
    if resume and overwrite:
        logger.error("Conflicting options: --resume and --overwrite are mutually exclusive.")
        sys.exit(2)

    # Resolve clip filter
    clip_filter: list[str] = []
    if clip:
        clip_filter.extend(clip)
    if clips:
        for c in clips.split(","):
            c_clean = c.strip()
            if c_clean and c_clean not in clip_filter:
                clip_filter.append(c_clean)

    if clip_filter:
        logger.info(f"Running subset filter ({len(clip_filter)} clips): {clip_filter}")
    else:
        logger.info("Running in full showcase mode (targeting 50 clips).")

    # Initialize batch pipeline
    try:
        pipeline = BatchPipeline(
            videos_root=videos_root,
            annotations_root=annotations_root,
            output_root=output_root,
            scratch_root=scratch_root,
            manifest_path=manifest,
            inventory_path=inventory,
            config_path=config,
            action_labels_path=action_labels,
        )
    except FileNotFoundError as e:
        logger.error(f"Configuration or input error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Initialization failure: {e}")
        sys.exit(1)

    # Execute batch
    try:
        summary = pipeline.run_batch(
            clip_filter=clip_filter if clip_filter else None,
            dry_run=dry_run,
            resume=resume,
            overwrite=overwrite,
            show_timeline=show_timeline,
            show_offense=show_offense,
            show_defense=show_defense,
            show_action_panel=show_action_panel,
            include_unannotated_tail=include_unannotated_tail,
        )
    except Exception as e:
        logger.error(f"Batch execution aborted unexpectedly: {e}", exc_info=True)
        sys.exit(1)

    # Report results summary
    logger.info("=" * 60)
    logger.info(f"BATCH EXECUTION COMPLETE [Run ID: {summary.run_id}]")
    logger.info(f"Elapsed time: {summary.elapsed_seconds:.2f} seconds")
    for status, count in summary.status_counts.items():
        logger.info(f"  {status:10s}: {count}")

    if summary.unresolved_errors:
        logger.error(f"Encountered {len(summary.unresolved_errors)} unresolved error(s) during batch:")
        for err in summary.unresolved_errors:
            logger.error(f"  - [{err.get('clip_name')}] ({err.get('stage')}): {err.get('message')}")

    # Set exit code
    if dry_run:
        # Fail if preflight had errors
        failed_preflight = [c for c in summary.clip_results if c.preflight_status == PreflightStatus.FAILED]
        if failed_preflight:
            logger.error(f"Dry-run preflight failed for {len(failed_preflight)} clips.")
            sys.exit(1)
    else:
        failed_renders = [c for c in summary.clip_results if c.render_status == BatchRenderStatus.FAILED]
        if failed_renders:
            logger.error(f"Batch completed with {len(failed_renders)} failed clip(s).")
            sys.exit(1)

    logger.info("Showcase batch workflow succeeded.")
    sys.exit(0)


if __name__ == "__main__":
    app()

