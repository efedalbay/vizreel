import pytest

from vizreel.charts.share import part_shades, part_spans, place_share
from vizreel.errors import RenderError, SpecError
from vizreel.render.layout import Box
from vizreel.spec.loader import parse_spec
from vizreel.spec.models import ShareChart

CONTENT = Box(-8.0, -4.0, 8.0, 4.0)


def share(parts: str, extra: str = "") -> ShareChart:
    spec = parse_spec(
        f"version: 1\ncharts:\n  - {{ id: s, type: share, parts: [{parts}]{extra} }}", "spec.yaml"
    )
    chart = spec.charts[0]
    assert isinstance(chart, ShareChart)
    return chart


def share_errors(parts: str, extra: str = "") -> list[str]:
    with pytest.raises(SpecError) as caught:
        share(parts, extra)
    return [str(issue) for issue in caught.value.issues]


THREE = "{ label: A, value: 25 }, { label: B, value: 47 }, { label: C, value: 28 }"


def test_the_largest_part_is_highlighted_unless_another_is_named() -> None:
    assert share(THREE).highlighted() == 1
    assert share(THREE, ", highlight: { label: C }").highlighted() == 2


def test_on_a_tie_the_first_largest_part_is_highlighted() -> None:
    assert share("{ label: A, value: 1 }, { label: B, value: 1 }").highlighted() == 0


def test_parts_go_around_the_ring_in_order() -> None:
    assert part_spans([25, 47, 28]) == pytest.approx([(0, 0.25), (0.25, 0.72), (0.72, 1.0)])


def test_the_highlighted_part_is_the_strongest_shade_and_the_others_step_down() -> None:
    assert part_shades(4, highlighted=1) == pytest.approx([0.8, 1.0, 0.6, 0.4])
    assert part_shades(2, highlighted=0) == pytest.approx([1.0, 0.8])


def test_ring_and_legend_side_by_side_are_centered() -> None:
    placement = place_share(CONTENT, False, (4.0, 2.0), gap=1.0, min_radius=1.0)

    # The ring (8 wide), the gap (1) and the legend (4) make 13, centered from -6.5 to 6.5.
    assert placement.radius == pytest.approx(4.0)
    assert placement.center == pytest.approx((-2.5, 0.0))
    assert placement.legend == pytest.approx((2.5, 1.0))


def test_legend_goes_under_the_ring_in_a_vertical_frame() -> None:
    tall = Box(-4.0, -7.0, 4.0, 7.0)

    placement = place_share(tall, True, (4.0, 2.0), gap=1.0, min_radius=1.0)

    assert placement.radius == pytest.approx(4.0)
    assert placement.center == pytest.approx((0.0, 5.5 - 4.0))
    assert placement.legend == pytest.approx((-2.0, 5.5 - 8.0 - 1.0))


def test_a_ring_smaller_than_the_least_radius_is_an_error() -> None:
    with pytest.raises(RenderError, match="not enough room"):
        place_share(CONTENT, False, (14.0, 2.0), gap=1.0, min_radius=1.5)


def test_part_labels_are_unique_and_the_highlight_matches_one() -> None:
    messages = share_errors(
        "{ label: A, value: 1 }, { label: A, value: 2 }", ", highlight: { label: Z }"
    )

    assert messages == [
        'charts[0].parts[1].label: "A" is already used by parts[0]; part labels must be unique',
        'charts[0].highlight.label: "Z" does not match any part. Parts: "A"',
    ]


@pytest.mark.parametrize(
    "parts",
    [
        "{ label: A, value: 1 }",
        ", ".join(f"{{ label: P{index}, value: 1 }}" for index in range(7)),
    ],
)
def test_two_to_six_parts(parts: str) -> None:
    [message] = share_errors(parts)

    assert message.startswith("charts[0].parts:")


def test_a_part_must_be_above_zero() -> None:
    [message] = share_errors("{ label: A, value: 0 }, { label: B, value: 2 }")

    assert message.startswith("charts[0].parts[0].value:")
