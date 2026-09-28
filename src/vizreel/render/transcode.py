"""Turn a rendered clip into the other formats editors take, keeping its transparency.

Manim writes transparent clips as QuickTime Animation. These functions read such a clip with
PyAV and write it again: as ProRes 4444, the professional editors' standard, or as a sequence
of PNG images, which every editor reads.
"""

from fractions import Fraction
from pathlib import Path
from typing import Any

import av
from av.container import OutputContainer
from av.video.stream import VideoStream

PRORES_PIXEL_FORMAT = "yuva444p10le"
"""ProRes 4444: full-resolution color, 10 bits per channel, and an alpha channel."""
PRORES_OPTIONS = {"profile": "4444", "vendor": "apl0", "alpha_bits": "16"}
"""The 4444 profile with a 16-bit alpha channel, marked as Apple's so editors trust it."""
BT709 = 1
"""The color standard of HD video, in FFmpeg's numbering of primaries, transfer and matrix."""
PRORES_STEP_FORMAT = "yuva444p"
"""The frames go to 8-bit YUV first. FFmpeg's direct conversion from RGB to 10-bit YUV with
alpha damages the alpha of frames whose width is not a multiple of 16, such as 1080 wide
vertical and square frames. The clips are 8-bit, so the step loses nothing."""
PNG_DIGITS = 5
"""Digits of the frame number in PNG file names: 99999 frames, 27 minutes at 60 fps."""


def to_prores(source: Path, target: Path) -> None:
    """Write the clip at `source` to `target` as ProRes 4444 with its alpha channel."""
    with av.open(str(target), "w", format="mov") as writer:
        _copy_frames(
            source,
            writer,
            "prores_ks",
            PRORES_PIXEL_FORMAT,
            PRORES_OPTIONS,
            BT709,
            PRORES_STEP_FORMAT,
        )


def to_png_sequence(source: Path, folder: Path) -> None:
    """Write each frame of the clip at `source` as a PNG with alpha in `folder`.

    The files are named after the folder and numbered from 1: `sales/sales_00001.png`. The
    frames of an earlier render into the same folder are removed first, so a shorter clip
    does not leave frames of a longer one behind; other files are left alone.
    """
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob(f"{folder.name}_{'[0-9]' * PNG_DIGITS}.png"):
        old.unlink()
    pattern = folder / f"{folder.name}_%0{PNG_DIGITS}d.png"
    with av.open(str(pattern), "w", format="image2") as writer:
        _copy_frames(source, writer, "png", "rgba", {}, None, None)


def _copy_frames(
    source: Path,
    writer: OutputContainer,
    codec: str,
    pixel_format: str,
    options: dict[str, str],
    colorspace: int | None,
    step_format: str | None,
) -> None:
    """Encode every frame of the clip at `source` into `writer`, at the clip's exact rate.

    Frames are converted to `pixel_format`, through `step_format` if given, and tagged with
    `colorspace` if given.
    """
    with av.open(str(source)) as reader:
        clip = reader.streams.video[0]
        if clip.average_rate is None:
            raise ValueError(f"{source} has no frame rate")
        rate = Fraction(clip.average_rate)
        stream = writer.add_stream(codec, rate=rate, options=options)
        assert isinstance(stream, VideoStream)
        stream.width, stream.height = clip.width, clip.height
        stream.pix_fmt = pixel_format
        convert: dict[str, Any] = {}
        if colorspace is not None:
            context = stream.codec_context
            context.color_primaries = context.color_trc = context.colorspace = colorspace
            convert["dst_colorspace"] = "ITU709"
        for index, frame in enumerate(reader.decode(clip)):
            if step_format is not None:
                frame = frame.reformat(format=step_format, **convert)
            converted = frame.reformat(format=pixel_format, **convert)
            converted.pts, converted.time_base = index, 1 / rate
            writer.mux(stream.encode(converted))
        writer.mux(stream.encode())
