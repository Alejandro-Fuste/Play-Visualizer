"""End-to-end smoke test for rendering synthetic clip."""

from pathlib import Path

from pathlib import Path

from play_visualizer.annotation_index import AnnotationIndex
from play_visualizer.annotation_loader import load_annotation_file
from play_visualizer.config import load_config
from play_visualizer.renderer import FrameRenderer
from play_visualizer.video_io import VideoReader, VideoWriter
from tests.fixtures.synthetic_sample import create_synthetic_annotation, create_synthetic_video


def test_renderer_smoke(tmp_path: Path):
    video_path = tmp_path / "test_input.mp4"
    json_path = tmp_path / "test_annotations.json"
    output_path = tmp_path / "test_output.mp4"

    create_synthetic_video(video_path, num_frames=15)
    create_synthetic_annotation(json_path, num_frames=15)

    pkg = load_annotation_file(json_path)
    index = AnnotationIndex(pkg)
    cfg = load_config()

    with VideoReader(video_path) as reader, VideoWriter(output_path, reader.metadata.width, reader.metadata.height, reader.metadata.fps) as writer:
        renderer = FrameRenderer(config=cfg, pkg=pkg, index=index)
        rendered_count = renderer.render_video(reader, writer, start_frame=0, end_frame=14)

    assert rendered_count == 15
    assert output_path.exists()
    assert output_path.stat().st_size > 0

