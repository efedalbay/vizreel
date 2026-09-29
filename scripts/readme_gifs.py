"""Render the showcase charts as animated GIFs for the README.

A development tool, not part of the package. Run from the repository root:

    uv run python scripts/readme_gifs.py

Each chart is rendered as an opaque preview clip, then converted to a GIF with a palette
computed from the whole clip (FFmpeg's palettegen and paletteuse, through PyAV).
"""

import tempfile
from pathlib import Path

import av
import av.filter

from vizreel.render.engine import RenderOptions, render_spec

ROOT = Path(__file__).resolve().parents[1]
SHOWCASE = ROOT / "examples" / "showcase.yaml"
OUT_DIR = ROOT / "docs" / "images"
WIDTH = 640
CHARTS = {
    "peak-valuation": "stat",
    "valuation": "line",
    "offers": "bar",
    "final-years": "timeline",
    "headcount": "compare",
    "profit": "waterfall",
    "revenue-mix": "stacked",
    "region-growth": "grouped",
    "users": "area",
    "fundraiser": "progress",
    "market": "share",
    "top-markets": "table",
}


def _frames(video: Path) -> tuple[list[av.VideoFrame], int]:
    with av.open(str(video)) as container:
        stream = container.streams.video[0]
        rate = int(stream.average_rate)
        return [frame for frame in container.decode(stream)], rate


def _palette(frames: list[av.VideoFrame], rate: int) -> av.VideoFrame:
    graph = av.filter.Graph()
    source = graph.add_buffer(
        width=frames[0].width,
        height=frames[0].height,
        format=frames[0].format.name,
        time_base=f"1/{rate}",
    )
    scale = graph.add("scale", f"{WIDTH}:-1:flags=lanczos")
    palettegen = graph.add("palettegen", "stats_mode=full")
    sink = graph.add("buffersink")
    source.link_to(scale)
    scale.link_to(palettegen)
    palettegen.link_to(sink)
    graph.configure()
    for frame in frames:
        source.push(frame)
    source.push(None)
    return sink.pull()


def to_gif(video: Path, gif: Path) -> None:
    """Convert a clip to a GIF of `WIDTH` pixels with an optimized palette."""
    frames, rate = _frames(video)
    palette = _palette(frames, rate)
    graph = av.filter.Graph()
    source = graph.add_buffer(
        width=frames[0].width,
        height=frames[0].height,
        format=frames[0].format.name,
        time_base=f"1/{rate}",
    )
    palette_source = graph.add_buffer(
        width=palette.width,
        height=palette.height,
        format=palette.format.name,
        time_base=f"1/{rate}",
    )
    scale = graph.add("scale", f"{WIDTH}:-1:flags=lanczos")
    paletteuse = graph.add("paletteuse", "dither=sierra2_4a")
    sink = graph.add("buffersink")
    source.link_to(scale)
    scale.link_to(paletteuse, 0, 0)
    palette_source.link_to(paletteuse, 0, 1)
    paletteuse.link_to(sink)
    graph.configure()
    palette_source.push(palette)
    palette_source.push(None)

    with av.open(str(gif), "w", format="gif") as out:
        stream = out.add_stream("gif", rate=rate)
        stream.width = WIDTH
        stream.height = round(frames[0].height * WIDTH / frames[0].width / 2) * 2
        stream.pix_fmt = "pal8"

        def write_ready() -> None:
            while True:
                try:
                    converted = sink.pull()
                except (av.BlockingIOError, av.EOFError):
                    return
                converted.pts = None
                for packet in stream.encode(converted):
                    out.mux(packet)

        for index, frame in enumerate(frames):
            frame.pts = index
            source.push(frame)
            write_ready()
        source.push(None)
        write_ready()
        for packet in stream.encode():
            out.mux(packet)


def main() -> None:
    """Render every showcase chart and write docs/images/<type>.gif."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        options = RenderOptions(out_dir=Path(folder), quality="preview", format="mp4")
        for result in render_spec(SHOWCASE, options, reraise=True):
            if result.error or result.video is None:
                raise SystemExit(f"{result.chart_id}: {result.error}")
            gif = OUT_DIR / f"{CHARTS[result.chart_id]}.gif"
            to_gif(result.video, gif)
            print(f"{gif.relative_to(ROOT)}: {gif.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
