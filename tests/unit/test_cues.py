from fractions import Fraction
from pathlib import Path

from vizreel.render.cues import Cue, cue_document
from vizreel.render.engine import cues_path
from vizreel.spec.loader import parse_spec


def test_a_cue_document_gives_seconds_and_frames_and_ends_on_the_last_frame() -> None:
    document = cue_document(
        [Cue("title", 0, 8), Cue("reveal", 8, 44), Cue("hold", 44, 75)], 15, 75, "a.mov"
    )

    assert document["clip"] == "a.mov"
    assert (document["fps"], document["frames"], document["duration"]) == (15.0, 75, 5.0)
    assert document["cues"] == [
        {"name": "title", "start": 0.0, "end": 0.533, "start_frame": 0, "end_frame": 8},
        {"name": "reveal", "start": 0.533, "end": 2.933, "start_frame": 8, "end_frame": 44},
        {"name": "hold", "start": 2.933, "end": 5.0, "start_frame": 44, "end_frame": 75},
        {"name": "end", "start": 4.933, "end": 5.0, "start_frame": 74, "end_frame": 75},
    ]


def test_cue_times_use_the_exact_ntsc_frame_rate() -> None:
    document = cue_document([], Fraction(30000, 1001), 300, "a.mov")

    assert document["fps"] == 29.97002997002997
    assert document["duration"] == 10.01


def test_a_cue_file_is_named_like_its_clip() -> None:
    assert cues_path(Path("out/offers.mov")) == Path("out/offers.cues.json")
    assert cues_path(Path("out/a.2.vertical.preview.webm")) == Path(
        "out/a.2.vertical.preview.cues.json"
    )
    assert cues_path(Path("out/offers.prores.mov")) == Path("out/offers.cues.json")
    assert cues_path(Path("out/offers")) == Path("out/offers.cues.json")


def test_cue_files_are_asked_for_in_meta() -> None:
    spec = parse_spec("version: 1\ncharts: [{ id: a, type: stat, value: 1 }]\n", "s.yaml")
    with_cues = parse_spec(
        "version: 1\nmeta: { cues: true }\ncharts: [{ id: a, type: stat, value: 1 }]\n",
        "s.yaml",
    )

    assert spec.meta.cues is False
    assert with_cues.meta.cues is True
