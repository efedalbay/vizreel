from pathlib import Path

import pytest

from vizreel.errors import SpecError
from vizreel.render.engine import clip_theme
from vizreel.spec.loader import parse_spec
from vizreel.spec.models import Motion
from vizreel.themes.loader import load_theme

THEME = load_theme("default", Path("."))


def test_the_built_in_theme_fades_in_and_does_not_leave() -> None:
    motion = THEME.motion

    assert (motion.entrance, motion.exit, motion.exit_time) == ("fade", "none", 0.5)


def test_a_spec_and_a_chart_take_motion_settings() -> None:
    spec = parse_spec(
        "version: 1\nmeta: { motion: { entrance: rise } }\n"
        "charts: [{ id: a, type: stat, value: 1, motion: { exit: fade, easing: ease_out_expo } }]",
        "spec.yaml",
    )

    assert spec.meta.motion == Motion(entrance="rise")
    assert spec.charts[0].motion == Motion(exit="fade", easing="ease_out_expo")


@pytest.mark.parametrize(
    ("motion", "location"),
    [
        ("{ entrance: bounce }", "charts[0].motion.entrance"),
        ("{ exit: slide }", "charts[0].motion.exit"),
        ("{ easing: linear }", "charts[0].motion.easing"),
        ("{ speed: 2 }", "charts[0].motion.speed"),
    ],
)
def test_motion_takes_only_what_the_design_rules_allow(motion: str, location: str) -> None:
    with pytest.raises(SpecError) as caught:
        parse_spec(
            f"version: 1\ncharts: [{{ id: a, type: stat, value: 1, motion: {motion} }}]", "s"
        )

    assert [issue.location for issue in caught.value.issues] == [location]


def test_a_chart_goes_over_the_spec_which_goes_over_the_theme() -> None:
    theme = clip_theme(
        THEME,
        Motion(entrance="rise", easing="ease_out_expo"),
        Motion(entrance="zoom"),
        last=True,
    )

    assert theme.motion.entrance == "zoom"
    assert theme.motion.easing == "ease_out_expo"
    assert theme.motion.exit == "none"
    assert theme.motion.hold == THEME.motion.hold
    assert theme.colors == THEME.colors


def test_a_clip_that_leaves_holds_for_its_exit_too() -> None:
    theme = clip_theme(THEME, Motion(), Motion(exit="sink"), last=True)

    assert theme.motion.exit == "sink"
    assert theme.motion.hold == THEME.motion.hold + THEME.motion.exit_time


def test_only_the_last_clip_of_a_sequence_leaves() -> None:
    theme = clip_theme(THEME, Motion(exit="fade"), Motion(), last=False)

    assert theme.motion.exit == "none"
    assert theme.motion.hold == THEME.motion.hold


def test_the_theme_is_left_unchanged() -> None:
    clip_theme(THEME, Motion(exit="fade"), Motion(entrance="zoom"), last=True)

    assert (THEME.motion.entrance, THEME.motion.exit) == ("fade", "none")
