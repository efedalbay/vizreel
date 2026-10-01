from fractions import Fraction

import pytest

from vizreel.charts.base import (
    FrameClock,
    Phases,
    check_reading_time,
    reading_time,
    sequential_progress,
    split_duration,
    staggered_progress,
)
from vizreel.errors import RenderError


def test_short_clip_gives_remaining_time_to_data() -> None:
    phases = split_duration(3, intro=0, highlight=0, hold=1.5)

    assert phases == Phases(intro=0, main=1.5, highlight=0, hold=1.5)


def test_intro_takes_time_from_data_not_hold() -> None:
    phases = split_duration(3, intro=0.5, highlight=0, hold=1.5)

    assert phases.main == pytest.approx(1.0)
    assert phases.hold == pytest.approx(1.5)


def test_data_reveal_is_at_most_half_the_clip() -> None:
    phases = split_duration(10, intro=0.5, highlight=0.6, hold=1.5)

    assert phases.main == pytest.approx(5)
    assert phases.hold == pytest.approx(10 - 0.5 - 5 - 0.6)


@pytest.mark.parametrize(
    ("duration", "intro", "highlight", "hold"),
    [(3, 0, 0, 1.5), (6, 1.1, 0.6, 1.5), (7, 1.1, 0.6, 2), (20, 1.1, 0.6, 1.5), (2, 0, 0, 1.5)],
)
def test_phases_add_up_and_respect_minimum_hold(
    duration: float, intro: float, highlight: float, hold: float
) -> None:
    phases = split_duration(duration, intro=intro, highlight=highlight, hold=hold)

    assert phases.total == pytest.approx(duration)
    assert phases.hold >= hold
    assert phases.main <= duration / 2
    assert (phases.intro, phases.highlight) == (intro, highlight)


def test_phase_start_times() -> None:
    phases = Phases(intro=0.5, main=2, highlight=0.6, hold=1.9)

    assert phases.main_start == 0.5
    assert phases.highlight_start == 2.5
    assert phases.hold_start == pytest.approx(3.1)
    assert phases.total == pytest.approx(5)


def test_too_short_duration_names_the_minimum() -> None:
    with pytest.raises(
        RenderError, match=r"duration 2s is too short for this chart; use at least 2.5s"
    ):
        split_duration(2, intro=0.5, highlight=0, hold=1.5)


def test_frame_clock_keeps_the_total_exact() -> None:
    clock = FrameClock(15)

    frames = [clock.frames_for(duration) for duration in (0.5, 0.6, 2.8, 0.6, 1.5)]

    assert sum(frames) == 90
    assert clock.frames == 90
    assert frames == [8, 9, 42, 9, 22]


@pytest.mark.parametrize("fps", [15, 30, 60])
@pytest.mark.parametrize("durations", [(0.5, 1.0, 1.5), (0.5, 0.6, 1.8, 0.6, 1.5), (1 / 3,) * 9])
def test_frame_clock_total_matches_duration(fps: int, durations: tuple[float, ...]) -> None:
    clock = FrameClock(fps)
    elapsed = 0.0
    for duration in durations:
        clock.frames_for(duration)
        elapsed += duration
        assert abs(clock.frames - elapsed * fps) <= 0.5 + 1e-9

    assert clock.frames == round(sum(durations) * fps)


def test_frame_clock_gives_every_animation_a_frame() -> None:
    clock = FrameClock(15)

    assert clock.frames_for(0.001) == 1
    assert clock.frames_for(0.001) == 1


def test_staggered_items_start_one_after_another() -> None:
    def at(progress: float, index: int) -> float:
        return staggered_progress(progress, index, 3, stagger=0.1, total=2)

    assert [at(0, i) for i in range(3)] == [0, 0, 0]
    assert at(0.05, 0) == pytest.approx(0.1 / 1.8)
    assert at(0.05, 1) == 0
    assert at(0.1, 2) == 0
    assert [at(1, i) for i in range(3)] == [1, 1, 1]


def test_last_staggered_item_finishes_at_the_end() -> None:
    assert staggered_progress(0.999, 7, 8, stagger=0.08, total=2.5) < 1
    assert staggered_progress(1, 7, 8, stagger=0.08, total=2.5) == 1


def test_long_stagger_is_shortened_to_half_the_time() -> None:
    # 8 items with 1 s delays would need 7 s; they get 0.5 s in total instead.
    assert staggered_progress(0.5, 7, 8, stagger=1, total=1) == pytest.approx(0)
    assert staggered_progress(0.75, 7, 8, stagger=1, total=1) == pytest.approx(0.5)


def test_single_item_is_not_delayed() -> None:
    assert staggered_progress(0.5, 0, 1, stagger=0.1, total=2) == 0.5


@pytest.mark.parametrize(
    ("text", "seconds"),
    [("Revenue", 1 / 3), ("Northwind's peak valuation", 1), ("  one   two  three four ", 4 / 3)],
)
def test_reading_time_is_one_second_per_three_words(text: str, seconds: float) -> None:
    assert reading_time(text) == pytest.approx(seconds)


def test_text_that_stays_long_enough_passes() -> None:
    check_reading_time([("Northwind's peak valuation", 1.0), ("Source: example data", 0)], 3)


def test_text_that_appears_too_late_names_the_duration_needed() -> None:
    with pytest.raises(
        RenderError,
        match=r'"Revenue grew for six straight years" needs 2.0s on screen to be read; '
        r"set duration to at least 4.5s",
    ):
        check_reading_time([("Revenue grew for six straight years", 2.5)], 4)


@pytest.mark.parametrize(
    ("progress", "expected"),
    [(0.0, [0, 0, 0, 0]), (0.25, [1, 0, 0, 0]), (0.375, [1, 0.5, 0, 0]), (1.0, [1, 1, 1, 1])],
)
def test_sequential_items_run_one_after_another(progress: float, expected: list[float]) -> None:
    assert [sequential_progress(progress, index, 4) for index in range(4)] == pytest.approx(
        expected
    )


def test_the_clock_counts_ntsc_frames_exactly() -> None:
    clock = FrameClock(Fraction(30000, 1001))

    frames = [clock.frames_for(duration) for duration in (0.5, 1.25, 1.25)]

    assert clock.frames == round(3 * 30000 / 1001) == 90
    assert sum(frames) == 90


def test_a_suggested_duration_is_rounded_up_so_it_is_enough() -> None:
    from vizreel.charts.base import seconds_up

    assert seconds_up(3.04) == "3.1"
    assert seconds_up(3.0) == "3.0"
    assert seconds_up(2.9999999999) == "3.0"
    assert seconds_up(4.5) == "4.5"


def test_a_text_that_needs_a_little_more_than_the_duration_asks_for_more() -> None:
    with pytest.raises(RenderError, match=r"set duration to at least 3.1s"):
        check_reading_time([("one two three four five six seven eight", 0.38)], 3)
