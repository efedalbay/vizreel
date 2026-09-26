"""Check a theme for text contrast and for color separation under color vision deficiency.

Pure functions, standard library only. Contrast follows WCAG 2.x. Color vision deficiency
is simulated with the matrices of Machado, Oliveira and Fernandes (2009) at full severity,
applied in linear RGB. Color difference is CIEDE2000.
"""

import math
from dataclasses import dataclass

from vizreel.themes.models import Theme

TEXT_CONTRAST = 4.5
"""Least contrast of text against the backgrounds it sits on (WCAG 1.4.3)."""
MARK_CONTRAST = 3.0
"""Least contrast of data marks and large colored text (WCAG 1.4.11)."""
MIN_DIFFERENCE = 10.0
"""Least CIEDE2000 difference between colors that appear side by side, in every vision type."""

Matrix = tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]

VISIONS: dict[str, Matrix | None] = {
    "normal vision": None,
    "protanopia": (
        (0.152286, 1.052583, -0.204868),
        (0.114503, 0.786281, 0.099216),
        (-0.003882, -0.048116, 1.051998),
    ),
    "deuteranopia": (
        (0.367322, 0.860646, -0.227968),
        (0.280085, 0.672501, 0.047413),
        (-0.011820, 0.042940, 0.968881),
    ),
    "tritanopia": (
        (1.255528, -0.076749, -0.178779),
        (-0.078411, 0.930809, 0.147602),
        (0.004733, 0.691367, 0.303900),
    ),
}

_SRGB_TO_XYZ: Matrix = (
    (0.4124564, 0.3575761, 0.1804375),
    (0.2126729, 0.7151522, 0.0721750),
    (0.0193339, 0.1191920, 0.9503041),
)
_WHITE_D65 = (0.95047, 1.0, 1.08883)

Rgb = tuple[float, float, float]
Lab = tuple[float, float, float]


@dataclass(frozen=True)
class CheckResult:
    """The outcome of one check.

    Attributes:
        passed: Whether the value reaches the minimum.
        value: What was measured: a contrast ratio or a color difference.
        minimum: The least value that passes.
        description: What was checked, e.g. "colors.text on colors.surface".
    """

    passed: bool
    value: float
    minimum: float
    description: str


def linear_rgb(hex_color: str) -> Rgb:
    """Convert a #RRGGBB color to linear RGB channels from 0 to 1."""
    channels = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    r, g, b = (c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels)
    return (r, g, b)


def relative_luminance(hex_color: str) -> float:
    """WCAG relative luminance of a #RRGGBB color."""
    r, g, b = linear_rgb(hex_color)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(first: str, second: str) -> float:
    """WCAG contrast ratio of two #RRGGBB colors, from 1 to 21."""
    lighter, darker = sorted((relative_luminance(first), relative_luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def simulate(rgb: Rgb, matrix: Matrix | None) -> Rgb:
    """Linear RGB as seen with the color vision deficiency of `matrix` (None: normal vision)."""
    if matrix is None:
        return rgb
    r, g, b = (min(max(value, 0.0), 1.0) for value in _apply(matrix, rgb))
    return (r, g, b)


def lab(rgb: Rgb) -> Lab:
    """CIE L*a*b* (D65) of a linear RGB color."""
    x, y, z = (
        value / white for value, white in zip(_apply(_SRGB_TO_XYZ, rgb), _WHITE_D65, strict=True)
    )
    fx, fy, fz = (_lab_f(value) for value in (x, y, z))
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def _lab_f(t: float) -> float:
    delta = 6 / 29
    return t ** (1 / 3) if t > delta**3 else t / (3 * delta**2) + 4 / 29


def _apply(matrix: Matrix, vector: Rgb) -> Rgb:
    a, b, c = (sum(m * v for m, v in zip(row, vector, strict=True)) for row in matrix)
    return (a, b, c)


def ciede2000(first: Lab, second: Lab) -> float:
    """CIEDE2000 color difference of two L*a*b* colors (Sharma, Wu and Dalal, 2005)."""
    l1, a1, b1 = first
    l2, a2, b2 = second
    c_mean = (math.hypot(a1, b1) + math.hypot(a2, b2)) / 2
    g = 0.5 * (1 - math.sqrt(c_mean**7 / (c_mean**7 + 25**7)))
    a1p, a2p = a1 * (1 + g), a2 * (1 + g)
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360 if c1p else 0.0
    h2p = math.degrees(math.atan2(b2, a2p)) % 360 if c2p else 0.0

    delta_l = l2 - l1
    delta_c = c2p - c1p
    if c1p * c2p == 0:
        delta_h_angle = 0.0
    elif abs(h2p - h1p) <= 180:
        delta_h_angle = h2p - h1p
    elif h2p - h1p > 180:
        delta_h_angle = h2p - h1p - 360
    else:
        delta_h_angle = h2p - h1p + 360
    delta_h = 2 * math.sqrt(c1p * c2p) * math.sin(math.radians(delta_h_angle) / 2)

    l_mean = (l1 + l2) / 2
    cp_mean = (c1p + c2p) / 2
    if c1p * c2p == 0:
        h_mean = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        h_mean = (h1p + h2p) / 2
    elif h1p + h2p < 360:
        h_mean = (h1p + h2p + 360) / 2
    else:
        h_mean = (h1p + h2p - 360) / 2

    t = (
        1
        - 0.17 * math.cos(math.radians(h_mean - 30))
        + 0.24 * math.cos(math.radians(2 * h_mean))
        + 0.32 * math.cos(math.radians(3 * h_mean + 6))
        - 0.20 * math.cos(math.radians(4 * h_mean - 63))
    )
    delta_theta = 30 * math.exp(-(((h_mean - 275) / 25) ** 2))
    r_c = 2 * math.sqrt(cp_mean**7 / (cp_mean**7 + 25**7))
    s_l = 1 + 0.015 * (l_mean - 50) ** 2 / math.sqrt(20 + (l_mean - 50) ** 2)
    s_c = 1 + 0.045 * cp_mean
    s_h = 1 + 0.015 * cp_mean * t
    r_t = -math.sin(math.radians(2 * delta_theta)) * r_c
    return math.sqrt(
        (delta_l / s_l) ** 2
        + (delta_c / s_c) ** 2
        + (delta_h / s_h) ** 2
        + r_t * (delta_c / s_c) * (delta_h / s_h)
    )


def color_difference(first: str, second: str, matrix: Matrix | None = None) -> float:
    """CIEDE2000 difference of two #RRGGBB colors as seen with `matrix` (None: normal vision)."""
    return ciede2000(
        lab(simulate(linear_rgb(first), matrix)), lab(simulate(linear_rgb(second), matrix))
    )


def check_theme(theme: Theme) -> list[CheckResult]:
    """Run every contrast and color separation check on a theme."""
    colors = theme.colors
    backgrounds = {"colors.surface": colors.surface, "colors.background": colors.background}
    text_roles = {"colors.text": colors.text, "colors.muted": colors.muted}
    mark_roles = {
        "colors.accent": colors.accent,
        "colors.positive": colors.positive,
        "colors.negative": colors.negative,
        "colors.highlight": colors.highlight,
        **{f"colors.series[{i}]": color for i, color in enumerate(colors.series)},
    }
    results: list[CheckResult] = []
    for roles, minimum in ((text_roles, TEXT_CONTRAST), (mark_roles, MARK_CONTRAST)):
        for role, color in roles.items():
            for background_role, background in backgrounds.items():
                ratio = contrast_ratio(color, background)
                results.append(
                    CheckResult(ratio >= minimum, ratio, minimum, f"{role} on {background_role}")
                )

    series = {f"colors.series[{i}]": color for i, color in enumerate(colors.series)}
    side_by_side = [
        *(
            (first, second)
            for index, first in enumerate(series)
            for second in list(series)[index + 1 :]
        ),
        *(("colors.highlight", role) for role in series),
        ("colors.highlight", "colors.muted"),
    ]
    palette = {**series, "colors.highlight": colors.highlight, "colors.muted": colors.muted}
    for vision, matrix in VISIONS.items():
        for first, second in side_by_side:
            difference = color_difference(palette[first], palette[second], matrix)
            results.append(
                CheckResult(
                    difference >= MIN_DIFFERENCE,
                    difference,
                    MIN_DIFFERENCE,
                    f"{first} and {second} with {vision}",
                )
            )
    return results
