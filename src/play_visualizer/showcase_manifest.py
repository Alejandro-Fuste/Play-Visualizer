"""Showcase manifest loader, inventory CSV cross-checker, and path resolver."""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any

from .batch_models import InventoryVideoRecord, ShowcaseClipManifestRecord

logger = logging.getLogger("play_visualizer.batch")

DEFAULT_MANIFEST_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "showcase_clips.json"
EXPECTED_SHOWCASE_COUNT = 50


class ManifestError(Exception):
    """Raised when showcase manifest loading or validation fails."""


class InventoryError(Exception):
    """Raised when inventory CSV loading or validation fails."""


def load_showcase_manifest(
    manifest_path: Path | None = None,
    enforce_exact_count: bool = True,
) -> list[ShowcaseClipManifestRecord]:
    """Load and validate the showcase manifest records.

    Parameters:
        manifest_path: Path to showcase_clips.json. Falls back to bundled config/showcase_clips.json.
        enforce_exact_count: If True, requires exactly 50 records.

    Returns:
        List of ShowcaseClipManifestRecord preserving manifest order.
    """
    target_path = manifest_path if manifest_path else DEFAULT_MANIFEST_PATH
    if not target_path.exists():
        raise ManifestError(f"Showcase manifest file not found: {target_path}")

    try:
        with open(target_path, encoding="utf-8") as f:
            raw_data = json.load(f)
    except Exception as e:
        raise ManifestError(f"Failed to parse manifest JSON at {target_path}: {e}") from e

    if not isinstance(raw_data, list):
        raise ManifestError(f"Manifest root must be a JSON array, got {type(raw_data).__name__}")

    if enforce_exact_count and len(raw_data) != EXPECTED_SHOWCASE_COUNT:
        raise ManifestError(
            f"Expected exactly {EXPECTED_SHOWCASE_COUNT} showcase clips, found {len(raw_data)} in {target_path}"
        )

    seen_clip_names: set[str] = set()
    records: list[ShowcaseClipManifestRecord] = []

    for idx, item in enumerate(raw_data):
        if not isinstance(item, dict):
            raise ManifestError(f"Manifest record #{idx} must be a dictionary.")

        clip_name = item.get("logical_clip_name")
        play_name = item.get("play_name")
        video_id = str(item.get("video_id", ""))

        if not clip_name or not isinstance(clip_name, str):
            raise ManifestError(f"Record #{idx} missing required string 'logical_clip_name'.")
        if not play_name or not isinstance(play_name, str):
            raise ManifestError(f"Record #{idx} ('{clip_name}') missing required string 'play_name'.")
        if not video_id:
            raise ManifestError(f"Record #{idx} ('{clip_name}') missing required 'video_id'.")

        if clip_name in seen_clip_names:
            raise ManifestError(f"Duplicate logical_clip_name '{clip_name}' in manifest.")
        seen_clip_names.add(clip_name)

        records.append(
            ShowcaseClipManifestRecord(
                logical_clip_name=clip_name,
                play_name=play_name,
                video_id=video_id,
                tracking_source=item.get("tracking_source"),
                key_actions_source=item.get("key_actions_source"),
                player_tracks_source=item.get("player_tracks_source"),
            )
        )

    return records


def load_video_inventory(inventory_path: Path | None) -> dict[str, InventoryVideoRecord]:
    """Parse 1_Videos_Inventory.csv and index records by filename.

    The CSV includes a header, an optional summary row (e.g. Video Count=5132),
    followed by individual MP4 records.

    Returns:
        Mapping of filename (e.g. 'JetSweep_1.mp4') to InventoryVideoRecord.
    """
    if not inventory_path:
        return {}

    if not inventory_path.exists():
        raise InventoryError(f"Inventory CSV file not found: {inventory_path}")

    inventory: dict[str, InventoryVideoRecord] = {}

    try:
        with open(inventory_path, encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            header = None
            for row in reader:
                if not row or not any(field.strip() for field in row):
                    continue

                # Locate header row containing 'File Name'
                if header is None:
                    cleaned_row = [col.strip().lower() for col in row]
                    if "file name" in cleaned_row:
                        header = cleaned_row
                    continue

                # Map column indices
                fn_idx = header.index("file name") if "file name" in header else 0
                size_idx = header.index("size (mb)") if "size (mb)" in header else -1
                date_idx = header.index("date modified") if "date modified" in header else -1
                id_idx = header.index("file id") if "file id" in header else -1

                file_name = row[fn_idx].strip() if len(row) > fn_idx else ""
                if not file_name:
                    continue

                # Exclude summary rows
                if "video count" in file_name.lower() or "total size" in file_name.lower():
                    continue

                size_mb = None
                if size_idx >= 0 and len(row) > size_idx:
                    try:
                        raw_size = row[size_idx].strip().replace("MB", "").replace(",", "")
                        if raw_size:
                            size_mb = float(raw_size)
                    except ValueError:
                        size_mb = None

                date_modified = row[date_idx].strip() if (date_idx >= 0 and len(row) > date_idx) else None
                file_id = row[id_idx].strip() if (id_idx >= 0 and len(row) > id_idx) else None

                inventory[file_name] = InventoryVideoRecord(
                    file_name=file_name,
                    size_mb=size_mb,
                    date_modified=date_modified,
                    file_id=file_id,
                )

    except Exception as e:
        if not isinstance(e, InventoryError):
            raise InventoryError(f"Failed to read inventory CSV at {inventory_path}: {e}") from e
        raise

    return inventory


class PathResolver:
    """Deterministically resolves source and destination paths for batch processing."""

    def __init__(
        self,
        videos_root: Path,
        annotations_root: Path,
        output_root: Path,
        scratch_root: Path | None = None,
    ):
        self.videos_root = videos_root.resolve()
        self.annotations_root = annotations_root.resolve()
        self.output_root = output_root.resolve()
        self.scratch_root = scratch_root.resolve() if scratch_root else (Path("/content/play_visualizer_batch").resolve())

    def resolve_video_path(self, clip_name: str) -> Path:
        """Resolve source MP4 path: {videos_root}/{clip_name}.mp4"""
        if ".." in clip_name:
            raise ValueError(f"Path traversal detected in clip name: {clip_name}")
        return self.videos_root / f"{clip_name}.mp4"

    def resolve_annotation_path(self, play_name: str, clip_name: str) -> Path:
        """Resolve annotation JSON path: {annotations_root}/{play_name}/{clip_name}/annotations.json"""
        if ".." in play_name or ".." in clip_name:
            raise ValueError(f"Path traversal detected: {play_name}/{clip_name}")
        return self.annotations_root / play_name / clip_name / "annotations.json"

    def resolve_output_video_path(self, play_name: str, clip_name: str) -> Path:
        """Resolve persistent output MP4 path: {output_root}/{play_name}/{clip_name}.mp4"""
        if ".." in play_name or ".." in clip_name:
            raise ValueError(f"Path traversal detected: {play_name}/{clip_name}")
        return self.output_root / play_name / f"{clip_name}.mp4"

    def resolve_output_report_path(self, play_name: str, clip_name: str) -> Path:
        """Resolve persistent output report path: {output_root}/{play_name}/{clip_name}.report.json"""
        if ".." in play_name or ".." in clip_name:
            raise ValueError(f"Path traversal detected: {play_name}/{clip_name}")
        return self.output_root / play_name / f"{clip_name}.report.json"

    def resolve_staging_dir(self, clip_name: str) -> Path:
        """Resolve unique local scratch staging directory for a clip."""
        if ".." in clip_name:
            raise ValueError(f"Path traversal detected in clip name: {clip_name}")
        return self.scratch_root / "staging" / clip_name


def load_source_generation_statuses(annotations_root: Path) -> dict[str, dict[str, Any]]:
    """Attempt to load source showcase_summary.json for QA generation provenance."""
    summary_path = annotations_root / "showcase_summary.json"
    if not summary_path.exists():
        return {}

    try:
        with open(summary_path, encoding="utf-8") as f:
            data = json.load(f)
        results: dict[str, dict[str, Any]] = {}
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "clip_name" in item:
                    results[item["clip_name"]] = {
                        "status": item.get("status", "UNKNOWN"),
                        "errors_count": item.get("errors_count", 0),
                        "warnings_count": item.get("warnings_count", 0),
                        "warnings": item.get("warnings", []),
                    }
        return results
    except Exception:
        return {}

