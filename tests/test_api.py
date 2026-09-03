"""Unit test for top-level render_annotation_video API function."""

from pathlib import Path

from play_visualizer import render_annotation_video
from tests.fixtures.synthetic_sample import create_synthetic_annotation, create_synthetic_video


def test_render_annotation_video_api(tmp_path: Path):
    video_path = tmp_path / "test_api_input.mp4"
    json_path = tmp_path / "test_api_annotations.json"
    output_path = tmp_path / "test_api_output.mp4"

    create_synthetic_video(video_path, num_frames=10)
    create_synthetic_annotation(json_path, num_frames=10)

    report = render_annotation_video(
        video=video_path,
        annotations=json_path,
        output=output_path,
        overwrite=True,
    )

    assert report.status == "success"
    assert report.rendered_frames == 10
    assert output_path.exists()
    assert output_path.stat().st_size > 0
