from fractions import Fraction
from pathlib import Path

import av
import numpy as np
import pytest

from vizreel.render.transcode import to_png_sequence, to_prores

RATE = Fraction(30000, 1001)
FRAMES = 4


def rgba_frames() -> list[np.ndarray]:
    """Small frames of solid, half-transparent and transparent 8×8 blocks.

    ProRes compresses 8×8 blocks, so edges on the block grid measure the conversion rather
    than the compression. The width, 24, is not a multiple of 16, as 1080 is not: FFmpeg's
    direct conversion to 10-bit YUV damages the alpha of such frames.
    """
    frames = []
    for index in range(FRAMES):
        frame = np.zeros((16, 24, 4), dtype=np.uint8)
        frame[0:8, 0:16] = (240, 180 - index * 20, 40, 255)
        frame[8:16, 0:8] = (40, 90, 200, 128)
        frames.append(frame)
    return frames


@pytest.fixture
def clip(tmp_path: Path) -> Path:
    """A QuickTime Animation clip with alpha, as Manim writes it."""
    path = tmp_path / "clip.mov"
    with av.open(str(path), "w") as container:
        stream = container.add_stream("qtrle", rate=RATE)
        stream.width, stream.height, stream.pix_fmt = 24, 16, "argb"
        for index, pixels in enumerate(rgba_frames()):
            frame = av.VideoFrame.from_ndarray(pixels, format="rgba").reformat(format="argb")
            frame.pts, frame.time_base = index, 1 / RATE
            container.mux(stream.encode(frame))
        container.mux(stream.encode())
    return path


def decoded(path: Path) -> list[np.ndarray]:
    with av.open(str(path)) as container:
        return [frame.to_ndarray(format="rgba") for frame in container.decode(video=0)]


def test_prores_keeps_every_frame_the_rate_and_the_alpha(clip: Path, tmp_path: Path) -> None:
    target = tmp_path / "clip.prores.mov"

    to_prores(clip, target)

    with av.open(str(target)) as container:
        stream = container.streams.video[0]
        assert stream.codec_context.name == "prores"
        assert stream.average_rate == RATE
        assert stream.codec_context.pix_fmt.startswith("yuva444p")
    frames, source = decoded(target), rgba_frames()
    assert len(frames) == FRAMES
    for ours, original in zip(frames, source, strict=True):
        visible = original[:, :, 3] > 0
        assert np.abs(ours[:, :, 3].astype(int) - original[:, :, 3].astype(int)).max() <= 2
        assert np.abs(ours[visible].astype(int) - original[visible].astype(int)).max() <= 3


def test_png_sequence_is_exactly_the_frames(clip: Path, tmp_path: Path) -> None:
    folder = tmp_path / "sales"

    to_png_sequence(clip, folder)

    files = sorted(folder.iterdir())
    assert [file.name for file in files] == [f"sales_{i:05d}.png" for i in range(1, FRAMES + 1)]
    for file, original in zip(files, rgba_frames(), strict=True):
        [frame] = decoded(file)
        assert np.array_equal(frame, original)


def test_png_sequence_replaces_the_frames_of_an_earlier_render(clip: Path, tmp_path: Path) -> None:
    folder = tmp_path / "sales"
    folder.mkdir()
    (folder / "sales_00009.png").write_bytes(b"old frame")
    (folder / "notes.txt").write_text("keep me", encoding="utf-8")

    to_png_sequence(clip, folder)

    assert not (folder / "sales_00009.png").exists()
    assert (folder / "notes.txt").read_text(encoding="utf-8") == "keep me"
    assert len(list(folder.glob("sales_*.png"))) == FRAMES
