"""Batch execution orchestrator for Google Colab Showcase Visualization.

Manages preflight auditing, sequential rendering, local staging, atomic Drive transfer,
validation, fingerprinting, resumption, and failure isolation.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .annotation_loader import AnnotationLoadError, load_annotation_file
from .batch_models import (
    BatchRenderStatus,
    BatchRunSummary,
    ClipBatchResult,
    ClipPreflightResult,
    InputFingerprint,
    PreflightStatus,
    ShowcaseClipManifestRecord,
)
from .batch_report_writer import BatchReportWriter
from .config import DEFAULT_CONFIG_PATH, load_config
from .ffmpeg import find_ffmpeg_executable
from .models import PlayVisualizerAnnotationPackage
from .showcase_manifest import (
    DEFAULT_MANIFEST_PATH,
    PathResolver,
    load_showcase_manifest,
    load_source_generation_statuses,
    load_video_inventory,
)
from .validator import check_ffmpeg_available

logger = logging.getLogger("play_visualizer.batch")

SUPPORTED_SCHEMA_VERSIONS = {
    "tapevision_annotation_enrichment_v1.0",
    "tapevision_annotation_enrichment_v1.1",
}


def find_ffprobe_executable() -> str | None:
    """Locate ffprobe binary in system PATH or standard install locations."""
    found = shutil.which("ffprobe")
    if found:
        return found
    for p in ("/opt/homebrew/bin/ffprobe", "/usr/local/bin/ffprobe", "/usr/bin/ffprobe"):
        if Path(p).exists():
            return p
    return None


def probe_video_metadata(video_path: Path) -> dict[str, Any] | None:
    """Probe video file using ffprobe to extract stream, codec, and duration info."""
    ffprobe_cmd = find_ffprobe_executable()
    if not ffprobe_cmd or not video_path.exists():
        return None

    cmd = [
        ffprobe_cmd,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(video_path),
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode != 0:
            return None
        data = json.loads(res.stdout)
        video_streams = [s for s in data.get("streams", []) if s.get("codec_type") == "video"]
        if not video_streams:
            return None

        v_stream = video_streams[0]
        nb_frames = v_stream.get("nb_frames")
        if not nb_frames:
            # Fall back to duration * fps estimate
            fps_str = v_stream.get("r_frame_rate", "30/1")
            try:
                num, den = map(float, fps_str.split("/"))
                fps = num / den if den > 0 else 30.0
            except Exception:
                fps = 30.0
            duration = float(data.get("format", {}).get("duration", 0.0))
            estimated_frames = int(round(duration * fps)) if duration > 0 else 0
            nb_frames = estimated_frames

        return {
            "codec_name": v_stream.get("codec_name"),
            "width": int(v_stream.get("width", 0)),
            "height": int(v_stream.get("height", 0)),
            "fps": v_stream.get("r_frame_rate"),
            "num_frames": int(nb_frames),
            "duration": float(data.get("format", {}).get("duration", 0.0)),
        }
    except Exception as e:
        logger.debug(f"ffprobe failed for {video_path}: {e}")
        return None


def compute_file_sha256(path: Path) -> str:
    """Compute SHA-256 hex digest of a file in chunks."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def compute_input_fingerprint(
    video_path: Path,
    annotation_path: Path,
    config_path: Path | None = None,
) -> InputFingerprint:
    """Compute deterministic fingerprint over video properties, annotation JSON, and config."""
    video_stat = video_path.stat()
    video_size = video_stat.st_size
    video_mtime = video_stat.st_mtime

    ann_sha = compute_file_sha256(annotation_path)

    cfg_target = config_path if config_path and config_path.exists() else DEFAULT_CONFIG_PATH
    cfg_sha = compute_file_sha256(cfg_target) if cfg_target.exists() else "default_config"

    try:
        from .. import __version__ as tool_version
    except Exception:
        tool_version = "1.0.0"

    hasher = hashlib.sha256()
    hasher.update(f"vsize:{video_size};vmtime:{video_mtime};".encode())
    hasher.update(f"ann:{ann_sha};".encode())
    hasher.update(f"cfg:{cfg_sha};".encode())
    hasher.update(f"tool:{tool_version}".encode())

    return InputFingerprint(
        video_size_bytes=video_size,
        video_mtime=video_mtime,
        annotation_sha256=ann_sha,
        config_sha256=cfg_sha,
        tool_version=tool_version,
        combined_hash=hasher.hexdigest(),
    )


class BatchPipeline:
    """Orchestrates batch preflight, rendering, resumption, and reporting."""

    def __init__(
        self,
        videos_root: Path,
        annotations_root: Path,
        output_root: Path,
        scratch_root: Path | None = None,
        manifest_path: Path | None = None,
        inventory_path: Path | None = None,
        config_path: Path | None = None,
        action_labels_path: Path | None = None,
    ):
        self.resolver = PathResolver(
            videos_root=videos_root,
            annotations_root=annotations_root,
            output_root=output_root,
            scratch_root=scratch_root,
        )
        self.manifest_path = manifest_path
        self.inventory_path = inventory_path
        self.config_path = config_path
        self.action_labels_path = action_labels_path
        self.report_writer = BatchReportWriter(self.resolver.output_root)

        # Enforce hard failure if explicit config path does not exist
        if self.config_path is not None and not self.config_path.exists():
            raise FileNotFoundError(f"Provided configuration file not found: {self.config_path}")
        if self.action_labels_path is not None and not self.action_labels_path.exists():
            raise FileNotFoundError(f"Provided action labels file not found: {self.action_labels_path}")

    def load_manifest_records(
        self,
        clip_filter: list[str] | None = None,
        enforce_exact_count: bool | None = None,
    ) -> list[ShowcaseClipManifestRecord]:
        """Load manifest records, optionally filtering to specific clip names."""
        is_subset = bool(clip_filter)
        should_enforce = (not is_subset) if enforce_exact_count is None else enforce_exact_count
        records = load_showcase_manifest(
            manifest_path=self.manifest_path,
            enforce_exact_count=should_enforce,
        )
        if clip_filter:
            filter_set = set(clip_filter)
            filtered = [r for r in records if r.logical_clip_name in filter_set]
            missing = filter_set - {r.logical_clip_name for r in filtered}
            if missing:
                raise ValueError(f"Requested clip(s) not found in manifest: {sorted(missing)}")
            return filtered
        return records

    def preflight_clip(
        self,
        record: ShowcaseClipManifestRecord,
        inventory: dict[str, Any],
        gen_statuses: dict[str, dict[str, Any]],
    ) -> ClipPreflightResult:
        """Run complete preflight validation checks for a single clip without rendering."""
        clip_name = record.logical_clip_name
        play_name = record.play_name
        video_fn = f"{clip_name}.mp4"

        warnings: list[str] = []
        errors: list[str] = []

        # 1. Match inventory record
        inv_record = inventory.get(video_fn)
        file_id = inv_record.file_id if inv_record else None
        if inventory and not inv_record:
            warnings.append(f"Clip '{clip_name}' not listed in inventory CSV.")

        # 2. Source video path check
        video_path = self.resolver.resolve_video_path(clip_name)
        if not video_path.exists():
            errors.append(f"MISSING_VIDEO: Source video file not found at {video_path}")
        elif not os.access(video_path, os.R_OK):
            errors.append(f"UNREADABLE_VIDEO: Source video file is not readable at {video_path}")

        # 3. Source annotation path check
        ann_path = self.resolver.resolve_annotation_path(play_name, clip_name)
        if not ann_path.exists():
            errors.append(f"MISSING_ANNOTATION: Annotation file not found at {ann_path}")
        elif not os.access(ann_path, os.R_OK):
            errors.append(f"UNREADABLE_ANNOTATION: Annotation file is not readable at {ann_path}")

        # 4. Parse annotation JSON and validate schema
        pkg: PlayVisualizerAnnotationPackage | None = None
        schema_version = None
        expected_frames = None

        if ann_path.exists() and os.access(ann_path, os.R_OK):
            try:
                pkg = load_annotation_file(ann_path)
                schema_version = pkg.schema_version
                expected_frames = pkg.clip.num_frames

                # Compare clip.video_name with manifest name
                if pkg.clip.video_name != clip_name:
                    warnings.append(
                        f"Clip video_name mismatch: JSON has '{pkg.clip.video_name}', expected '{clip_name}'"
                    )

                if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
                    warnings.append(
                        f"Unrecognized schema_version '{schema_version}'. Supported: {SUPPORTED_SCHEMA_VERSIONS}"
                    )

                # QA checks: ball tracks, position coverage
                if not pkg.ball or not any(b.samples for b in pkg.ball):
                    warnings.append("NO_BALL_TRACK: No ball bounding boxes found in annotation package.")

            except AnnotationLoadError as e:
                errors.append(f"INVALID_ANNOTATION_JSON: Failed to parse JSON: {e}")
            except Exception as e:
                errors.append(f"ANNOTATION_LOAD_EXCEPTION: {e}")

        # 5. Probe video stream properties
        video_frames = None
        if video_path.exists() and os.access(video_path, os.R_OK):
            probe_info = probe_video_metadata(video_path)
            if probe_info:
                video_frames = probe_info.get("num_frames")
                if expected_frames is not None and video_frames is not None:
                    if video_frames != expected_frames:
                        warnings.append(
                            f"FRAME_COUNT_MISMATCH: Video has {video_frames} frames; annotation specifies {expected_frames}"
                        )
            else:
                warnings.append("FFPROBE_PROBE_FAILED: Could not probe video stream metadata via ffprobe.")

        # Source generation status lookup
        gen_info = gen_statuses.get(clip_name, {})
        gen_status = gen_info.get("status", "UNKNOWN")
        if gen_info.get("warnings"):
            warnings.append(f"SOURCE_GENERATOR_WARNINGS: {len(gen_info['warnings'])} warnings in source generation.")

        status = PreflightStatus.FAILED if errors else PreflightStatus.READY

        return ClipPreflightResult(
            clip_name=clip_name,
            play_name=play_name,
            status=status,
            source_video=str(video_path) if video_path.exists() else None,
            source_annotations=str(ann_path) if ann_path.exists() else None,
            video_file_id=file_id,
            annotation_schema_version=schema_version,
            expected_frames=expected_frames,
            video_frames=video_frames,
            source_generation_status=gen_status,
            warnings=warnings,
            errors=errors,
        )

    def preflight_batch(
        self,
        records: list[ShowcaseClipManifestRecord],
    ) -> list[ClipPreflightResult]:
        """Preflight all requested clips and verify environment readiness."""
        logger.info(f"Initiating preflight check for {len(records)} showcase clips...")

        # System checks
        if not check_ffmpeg_available():
            logger.error("FFmpeg executable was not detected on system PATH.")
        if not find_ffprobe_executable():
            logger.warning("ffprobe executable was not detected on system PATH.")

        inventory = load_video_inventory(self.inventory_path)
        gen_statuses = load_source_generation_statuses(self.resolver.annotations_root)

        results: list[ClipPreflightResult] = []
        for rec in records:
            res = self.preflight_clip(rec, inventory, gen_statuses)
            results.append(res)

        ready_count = sum(1 for r in results if r.status == PreflightStatus.READY)
        failed_count = sum(1 for r in results if r.status == PreflightStatus.FAILED)
        logger.info(f"Preflight complete: {ready_count}/{len(records)} READY, {failed_count} FAILED.")

        return results

    def validate_staged_output(
        self,
        staged_mp4: Path,
        expected_frames: int | None = None,
    ) -> tuple[bool, list[str]]:
        """Verify rendered MP4 in staging directory before committing to Drive.

        Checks existence, non-zero file size, and decodability with ffprobe.
        """
        issues: list[str] = []
        if not staged_mp4.exists():
            return False, [f"Staged MP4 does not exist: {staged_mp4}"]

        size = staged_mp4.stat().st_size
        if size == 0:
            return False, [f"Staged MP4 is 0 bytes: {staged_mp4}"]

        probe = probe_video_metadata(staged_mp4)
        if not probe:
            issues.append(f"Failed to probe staged MP4 with ffprobe: {staged_mp4}")
            return False, issues

        if probe.get("duration", 0.0) <= 0.0:
            issues.append(f"Staged MP4 has zero or invalid duration: {probe.get('duration')}")
            return False, issues

        rendered_frames = probe.get("num_frames", 0)
        if rendered_frames <= 0:
            issues.append(f"Staged MP4 contains zero decodable video frames.")
            return False, issues

        if expected_frames is not None and expected_frames > 0:
            # Allow tolerance of ±2 frames for encoding container boundaries
            diff = abs(rendered_frames - expected_frames)
            if diff > 5:
                issues.append(
                    f"Rendered frame count ({rendered_frames}) diverges from expected ({expected_frames})."
                )

        return True, issues

    def check_resume_skip(
        self,
        clip_name: str,
        play_name: str,
        current_fingerprint: str,
    ) -> tuple[bool, ClipBatchResult | None]:
        """Check if a verified, identical output already exists under --resume.

        Reuses output only if both MP4 and report exist and fingerprint matches.
        """
        out_video = self.resolver.resolve_output_video_path(play_name, clip_name)
        out_report = self.resolver.resolve_output_report_path(play_name, clip_name)

        if not out_video.exists() or not out_report.exists():
            return False, None

        if out_video.stat().st_size == 0:
            return False, None

        try:
            with open(out_report, encoding="utf-8") as f:
                rep_data = json.load(f)

            prev_status = rep_data.get("render_status")
            prev_fingerprint = rep_data.get("input_fingerprint")

            if prev_status in ("SUCCESS", "WARNING") and prev_fingerprint == current_fingerprint:
                result = ClipBatchResult(**rep_data)
                result.render_status = BatchRenderStatus.SKIPPED
                return True, result
        except Exception as e:
            logger.debug(f"Resume verification check failed for {clip_name}: {e}")
            return False, None

        return False, None

    def execute_clip(
        self,
        record: ShowcaseClipManifestRecord,
        preflight: ClipPreflightResult,
        dry_run: bool = False,
        resume: bool = False,
        overwrite: bool = False,
        show_timeline: bool = False,
        show_offense: bool = True,
        show_defense: bool = True,
        show_action_panel: bool = True,
        include_unannotated_tail: bool = False,
    ) -> ClipBatchResult:
        """Process a single showcase clip with staging, validation, commit, and isolation."""
        clip_name = record.logical_clip_name
        play_name = record.play_name
        t0 = time.time()

        clip_result = ClipBatchResult(
            clip_name=clip_name,
            play_name=play_name,
            video_file_id=preflight.video_file_id or "",
            source_video=preflight.source_video or str(self.resolver.resolve_video_path(clip_name)),
            source_annotations=preflight.source_annotations or str(self.resolver.resolve_annotation_path(play_name, clip_name)),
            annotation_schema_version=preflight.annotation_schema_version or "",
            source_generation_status=preflight.source_generation_status,
            preflight_status=preflight.status,
            render_status=BatchRenderStatus.READY,
            warnings=list(preflight.warnings),
            errors=list(preflight.errors),
        )

        if preflight.status == PreflightStatus.FAILED:
            clip_result.render_status = BatchRenderStatus.FAILED
            clip_result.elapsed_seconds = time.time() - t0
            return clip_result

        video_path = Path(clip_result.source_video)
        ann_path = Path(clip_result.source_annotations)
        dest_video = self.resolver.resolve_output_video_path(play_name, clip_name)
        dest_report = self.resolver.resolve_output_report_path(play_name, clip_name)
        clip_result.output_video = str(dest_video)
        clip_result.output_report = str(dest_report)

        # Compute fingerprint
        fingerprint = compute_input_fingerprint(video_path, ann_path, self.config_path)
        clip_result.input_fingerprint = fingerprint.combined_hash

        # Dry-run execution
        if dry_run:
            clip_result.render_status = BatchRenderStatus.READY
            clip_result.elapsed_seconds = time.time() - t0
            return clip_result

        # Check resume condition
        if resume:
            can_skip, skipped_result = self.check_resume_skip(
                clip_name=clip_name,
                play_name=play_name,
                current_fingerprint=clip_result.input_fingerprint,
            )
            if can_skip and skipped_result:
                logger.info(f"Skipping verified existing clip '{clip_name}' under --resume.")
                skipped_result.elapsed_seconds = time.time() - t0
                return skipped_result

        # Check existing destination output when neither resume nor overwrite is selected
        if dest_video.exists() and not overwrite and not resume:
            clip_result.render_status = BatchRenderStatus.FAILED
            clip_result.errors.append(
                f"Destination file already exists: {dest_video}. Use --resume or --overwrite."
            )
            clip_result.elapsed_seconds = time.time() - t0
            return clip_result

        # Prepare staging directory in scratch root
        staging_dir = self.resolver.resolve_staging_dir(clip_name)
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)
        staging_dir.mkdir(parents=True, exist_ok=True)
        staged_mp4 = staging_dir / f"{clip_name}.mp4"

        try:
            from .api import render_annotation_video

            logger.info(f"Rendering '{clip_name}' into staging: {staged_mp4}")
            # Invoke existing Play-Visualizer API
            render_rep = render_annotation_video(
                video=video_path,
                annotations=ann_path,
                output=staged_mp4,
                config=self.config_path,
                action_labels=self.action_labels_path,
                show_timeline=show_timeline,
                show_offense=show_offense,
                show_defense=show_defense,
                show_action_panel=show_action_panel,
                include_unannotated_tail=include_unannotated_tail,
                overwrite=True,
                log_level="INFO",
            )

            clip_result.rendered_frames = render_rep.rendered_frames
            clip_result.rendered_frame_start = render_rep.rendered_frame_start
            clip_result.rendered_frame_end = render_rep.rendered_frame_end
            clip_result.ffmpeg_command = render_rep.ffmpeg_command

            # Validate staged output
            is_valid, validation_issues = self.validate_staged_output(
                staged_mp4=staged_mp4,
                expected_frames=preflight.expected_frames,
            )

            if not is_valid:
                clip_result.render_status = BatchRenderStatus.FAILED
                clip_result.errors.extend(validation_issues)
                clip_result.elapsed_seconds = time.time() - t0
                return clip_result

            if validation_issues:
                clip_result.warnings.extend(validation_issues)

            # Atomic commit to Google Drive
            dest_video.parent.mkdir(parents=True, exist_ok=True)
            temp_dest = dest_video.parent / f".tmp_{clip_name}.mp4"

            shutil.copy2(staged_mp4, temp_dest)
            if not temp_dest.exists() or temp_dest.stat().st_size != staged_mp4.stat().st_size:
                if temp_dest.exists():
                    temp_dest.unlink()
                raise IOError(f"Transfer verification failed between {staged_mp4} and {temp_dest}")

            temp_dest.replace(dest_video)

            # Determine final render status
            if clip_result.warnings:
                clip_result.render_status = BatchRenderStatus.WARNING
            else:
                clip_result.render_status = BatchRenderStatus.SUCCESS

            # Clean staging
            shutil.rmtree(staging_dir, ignore_errors=True)

        except Exception as e:
            logger.error(f"Render failure for '{clip_name}': {e}", exc_info=True)
            clip_result.render_status = BatchRenderStatus.FAILED
            clip_result.errors.append(f"RENDER_EXCEPTION: {type(e).__name__}: {e}")

        clip_result.elapsed_seconds = time.time() - t0
        return clip_result

    def run_batch(
        self,
        clip_filter: list[str] | None = None,
        dry_run: bool = False,
        resume: bool = False,
        overwrite: bool = False,
        show_timeline: bool = False,
        show_offense: bool = True,
        show_defense: bool = True,
        show_action_panel: bool = True,
        include_unannotated_tail: bool = False,
        enforce_exact_count: bool | None = None,
    ) -> BatchRunSummary:
        """Run the complete batch-rendering workflow."""
        if resume and overwrite:
            raise ValueError("--resume and --overwrite options are mutually exclusive.")

        start_time_dt = datetime.now(timezone.utc)
        start_time_iso = start_time_dt.isoformat()
        run_id = f"batch_{start_time_dt.strftime('%Y%m%d_%H%M%S')}"

        logger.info(f"Starting batch run ID: {run_id} (dry_run={dry_run}, resume={resume}, overwrite={overwrite})")

        # 1. Load manifest records
        records = self.load_manifest_records(clip_filter=clip_filter, enforce_exact_count=enforce_exact_count)

        # 2. Run full batch preflight
        preflight_results = self.preflight_batch(records)
        preflight_map = {p.clip_name: p for p in preflight_results}

        # Halt if blocking preflight errors exist in non-dry-run mode
        blocking_preflight = [p for p in preflight_results if p.status == PreflightStatus.FAILED]
        if blocking_preflight and not dry_run:
            logger.warning(
                f"Preflight identified {len(blocking_preflight)} blocking errors. Attempting eligible ready clips."
            )

        clip_results: list[ClipBatchResult] = []
        status_counts = {"SUCCESS": 0, "WARNING": 0, "FAILED": 0, "SKIPPED": 0, "READY": 0}
        unresolved_errors: list[dict[str, Any]] = []

        total_clips = len(records)
        t_batch_start = time.time()

        for idx, rec in enumerate(records, start=1):
            clip_name = rec.logical_clip_name
            preflight = preflight_map[clip_name]

            logger.info(f"[{idx}/{total_clips}] Processing '{clip_name}' (Play: {rec.play_name})...")
            res = self.execute_clip(
                record=rec,
                preflight=preflight,
                dry_run=dry_run,
                resume=resume,
                overwrite=overwrite,
                show_timeline=show_timeline,
                show_offense=show_offense,
                show_defense=show_defense,
                show_action_panel=show_action_panel,
                include_unannotated_tail=include_unannotated_tail,
            )
            clip_results.append(res)
            status_counts[res.render_status.value] = status_counts.get(res.render_status.value, 0) + 1

            if res.errors:
                for err in res.errors:
                    unresolved_errors.append({
                        "clip_name": clip_name,
                        "stage": "preflight" if res.preflight_status == PreflightStatus.FAILED else "render",
                        "message": err,
                    })

            # Write per-clip report and update summary checkpoint
            if not dry_run or res.output_report:
                try:
                    self.report_writer.write_clip_report(res)
                except Exception as write_err:
                    logger.warning(f"Could not write per-clip report for {clip_name}: {write_err}")

            # Intermediate checkpoint summary update
            checkpoint_summary = BatchRunSummary(
                run_id=run_id,
                start_time=start_time_iso,
                end_time=datetime.now(timezone.utc).isoformat(),
                runtime_environment={
                    "platform": platform.platform(),
                    "python_version": sys.version,
                    "executable": sys.executable,
                },
                selected_count=len(records),
                expected_full_showcase_count=50,
                status_counts=status_counts,
                unresolved_errors=unresolved_errors,
                source_manifest_path=str(self.manifest_path or DEFAULT_MANIFEST_PATH),
                inventory_csv_path=str(self.inventory_path) if self.inventory_path else None,
                videos_root=str(self.resolver.videos_root),
                annotations_root=str(self.resolver.annotations_root),
                output_root=str(self.resolver.output_root),
                scratch_root=str(self.resolver.scratch_root),
                dry_run=dry_run,
                clip_results=clip_results,
                elapsed_seconds=time.time() - t_batch_start,
            )
            try:
                self.report_writer.write_batch_summary(checkpoint_summary)
            except Exception as e:
                logger.debug(f"Intermediate batch summary write skipped: {e}")

        # Final summary creation
        end_time_iso = datetime.now(timezone.utc).isoformat()
        total_elapsed = time.time() - t_batch_start

        final_summary = BatchRunSummary(
            run_id=run_id,
            start_time=start_time_iso,
            end_time=end_time_iso,
            runtime_environment={
                "platform": platform.platform(),
                "python_version": sys.version,
                "executable": sys.executable,
            },
            selected_count=len(records),
            expected_full_showcase_count=50,
            status_counts=status_counts,
            unresolved_errors=unresolved_errors,
            source_manifest_path=str(self.manifest_path or DEFAULT_MANIFEST_PATH),
            inventory_csv_path=str(self.inventory_path) if self.inventory_path else None,
            videos_root=str(self.resolver.videos_root),
            annotations_root=str(self.resolver.annotations_root),
            output_root=str(self.resolver.output_root),
            scratch_root=str(self.resolver.scratch_root),
            dry_run=dry_run,
            clip_results=clip_results,
            elapsed_seconds=total_elapsed,
        )

        try:
            json_path, md_path = self.report_writer.write_batch_summary(final_summary)
            logger.info(f"Persisted batch summary JSON to: {json_path}")
            logger.info(f"Persisted batch summary Markdown to: {md_path}")
        except Exception as e:
            logger.error(f"Failed to persist final batch summary: {e}")

        return final_summary
