"""Play-Visualizer Football Annotation Video Visualizer package."""

from typing import Any

__version__ = "1.0.0"


def __getattr__(name: str) -> Any:
    if name == "render_annotation_video":
        from .api import render_annotation_video

        return render_annotation_video
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["render_annotation_video", "__version__"]

