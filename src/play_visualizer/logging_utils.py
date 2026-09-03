"""Logging utilities and machine-readable report builder."""

import json
import logging
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

from .models import RenderReport

console = Console()


def setup_logger(log_level: str = "INFO") -> logging.Logger:
    """Configure and return the application logger."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    logger = logging.getLogger("play_visualizer")
    logger.setLevel(level)

    # Clear handlers to prevent duplicate outputs
    if logger.hasHandlers():
        logger.handlers.clear()

    rich_handler = RichHandler(
        console=console,
        show_path=False,
        omit_repeated_times=False,
        rich_tracebacks=True,
    )
    rich_handler.setLevel(level)
    formatter = logging.Formatter("%(message)s")
    rich_handler.setFormatter(formatter)
    logger.addHandler(rich_handler)

    return logger


def write_run_report(report: RenderReport, report_path: Path) -> None:
    """Write the machine-readable JSON run report to file."""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_dict = report.model_dump()
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_dict, f, indent=2)
