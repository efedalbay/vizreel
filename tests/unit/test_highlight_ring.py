import math
import random
from pathlib import Path

import pytest

from vizreel.render.scales import RING_WIDTH, ring_path
from vizreel.themes.check import check_theme
from vizreel.themes.loader import load_theme


def distance_to_box(point: tuple[float, float], width: float, height: float) -> float:
    """How far a point is outside a box centered at the origin; negative inside it."""
    dx, dy = abs(point[0]) - width / 2, abs(point[1]) - height / 2
    if dx <= 0 and dy <= 0:
        return max(dx, dy)
    return math.hypot(max(dx, 0.0), max(dy, 0.0))


def test_a_ring_never_comes_closer_to_its_box_than_its_padding() -> None:
    random.seed(7)
    for _ in range(300):
        width, height = random.uniform(0.2, 12), random.uniform(0.2, 4)
        padding = height * random.uniform(0.05, 0.3)
        points = ring_path((0.0, 0.0), width, height, padding, samples=800)

        nearest = min(distance_to_box(point, width, height) for point in points)
        # The path is drawn through its points, so allow for the chord between two of them.
        assert nearest >= padding * 0.97


def test_a_ring_around_a_wide_box_grows_taller_rather_than_much_wider() -> None:
    width, height, padding = 10.0, 1.0, 0.1
    points = ring_path((0.0, 0.0), width, height, padding)
    xs, ys = [x for x, _ in points], [y for _, y in points]

    assert max(xs) - min(xs) < (width + 2 * padding) * (RING_WIDTH + 0.1)
    assert max(ys) - min(ys) > height * 2


def test_a_ring_goes_round_once_and_ends_outside_where_it_began() -> None:
    # With 390 segments the ring turns one degree per segment: 360 around and 30 past.
    points = ring_path((1.0, 2.0), 4.0, 1.0, 0.1, samples=390)
    start, end = points[0], points[-1]

    assert start[0] < 1.0 and start[1] > 2.0
    # The end passes the point the first round drew at the same angle, a little outside it.
    first_round = points[30]
    assert math.dist(end, (1.0, 2.0)) > math.dist(first_round, (1.0, 2.0)) + 0.1


def test_the_ring_pen_is_checked_against_the_background(tmp_path: Path) -> None:
    theme = load_theme("default", tmp_path)
    marked = theme.model_copy(
        update={
            "colors": theme.colors.model_copy(update={"mark": "#20242A"}),
            "highlight_mark": "ring",
        }
    )

    failures = [r.description for r in check_theme(marked) if not r.passed]
    assert theme.highlight_mark == "none" and theme.colors.mark is None
    assert "colors.mark on colors.surface" in failures


@pytest.mark.parametrize("value", ["circle", True])
def test_highlight_mark_is_none_or_ring(tmp_path: Path, value: object) -> None:
    import yaml

    from vizreel.errors import ThemeError
    from vizreel.themes.loader import BUILTIN_DIR

    data = yaml.safe_load((BUILTIN_DIR / "default.yaml").read_text(encoding="utf-8"))
    data["highlight_mark"] = value
    (tmp_path / "t.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")

    with pytest.raises(ThemeError) as caught:
        load_theme("t.yaml", tmp_path)
    assert str(caught.value.issues[0]).startswith("highlight_mark:")
