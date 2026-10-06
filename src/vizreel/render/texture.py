"""Ruled lines or a picture on the background of a chart.

In transparent output the texture fills the background panel, inside its rounded corners;
in opaque output it fills the frame, as the camera's background. It never moves.
"""

import math
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

from vizreel.render.layout import Box, Layout, px, stroke_width
from vizreel.themes.models import Theme

if TYPE_CHECKING:
    import numpy as np
    from manim import Mobject
    from PIL.Image import Image

MARGIN_GAP = 3.0
"""Distance between the two lines of the margin, center to center, in line widths."""


def ruled_rows(top: float, bottom: float, spacing: float) -> list[float]:
    """The heights of lines `spacing` apart, from one spacing below `top` down to `bottom`.

    Works in any unit, scene units or pixels, as long as `top` is above `bottom` in it.
    """
    if top < bottom:
        return [top + spacing * index for index in range(1, math.ceil((bottom - top) / spacing))]
    count = math.ceil((top - bottom) / spacing)
    return [top - spacing * index for index in range(1, count)]


def corner_inset(distance: float, radius: float) -> float:
    """How far a rounded corner's curve is from the side, `distance` in from the top or bottom.

    A line across the panel that close to its top or bottom is shortened by this much at
    each end, so it stays inside the rounded corners.
    """
    if radius <= 0 or distance >= radius:
        return 0.0
    from_center = radius - max(distance, 0.0)
    return radius - math.sqrt(radius**2 - from_center**2)


def margin_center(box: Box, inner: Box, padding: float) -> float:
    """The x of the margin's double line: halfway into the space left of the content.

    The space is the panel padding, or the frame's margin when there is no panel; the line
    goes at most half a padding left of the content.
    """
    return inner.left - min(padding, inner.left - box.left) / 2


def cover_size(width: int, height: int, box_width: int, box_height: int) -> tuple[int, int]:
    """The size a picture takes to cover a box, keeping its proportions."""
    scale = max(box_width / width, box_height / height)
    return math.ceil(width * scale), math.ceil(height * scale)


def panel_texture(box: Box, theme: Theme, margin_x: float, radius: float) -> list["Mobject"]:
    """The texture of a background panel covering `box`, drawn just above its color.

    Args:
        box: The panel.
        theme: The texture, and the surface color a picture's corners are cut from.
        margin_x: Where the margin's double line goes, in scene units.
        radius: The panel's corner radius, in scene units.
    """
    from manim import ImageMobject, Line, VGroup, config

    from vizreel.render.elements import PANEL_Z_INDEX, color

    texture = theme.texture
    assert texture is not None
    if texture.image is not None:
        pixels_per_unit = config.pixel_height / config.frame_height
        width, height = round(box.width * pixels_per_unit), round(box.height * pixels_per_unit)
        array = _picture_pixels(
            texture.image.file,
            texture.image.fit,
            width,
            height,
            _resolution_scale(),
            round(radius * pixels_per_unit),
        )
        # A copy: an exit fades the picture by changing its pixels.
        picture = ImageMobject(array.copy())
        picture.stretch_to_fit_width(box.width).stretch_to_fit_height(box.height)
        picture.move_to((*box.center, 0.0)).set_z_index(PANEL_Z_INDEX)
        return [picture]
    ruled = texture.ruled
    assert ruled is not None
    lines = VGroup()
    for y in ruled_rows(box.top, box.bottom, px(ruled.spacing)):
        inset = corner_inset(min(box.top - y, y - box.bottom), radius)
        lines.add(Line((box.left + inset, y, 0.0), (box.right - inset, y, 0.0)))
    lines.set_stroke(color(ruled.color), width=stroke_width(ruled.width))
    parts: list[Mobject] = [lines]
    if ruled.margin is not None:
        margin = VGroup()
        for x in _margin_xs(margin_x, px(ruled.width)):
            inset = corner_inset(min(x - box.left, box.right - x), radius)
            margin.add(Line((x, box.top - inset, 0.0), (x, box.bottom + inset, 0.0)))
        margin.set_stroke(color(ruled.margin), width=stroke_width(ruled.width))
        parts.append(margin)
    for part in parts:
        part.set_z_index(PANEL_Z_INDEX)
    return parts


def background_picture(theme: Theme, layout: Layout, width: int, height: int) -> "Image":
    """The whole frame's background in opaque output: the background color and the texture.

    Args:
        theme: The background color and the texture.
        layout: Where the content is, for the margin's double line.
        width: The frame's width, in pixels.
        height: The frame's height, in pixels.
    """
    from PIL import Image, ImageDraw

    texture = theme.texture
    assert texture is not None
    picture = Image.new("RGB", (width, height), theme.colors.background)
    if texture.image is not None:
        image = texture.image
        layer = _picture_pixels(image.file, image.fit, width, height, _resolution_scale(), 0)
        picture.paste(Image.fromarray(layer).convert("RGB"))
        return picture
    ruled = texture.ruled
    assert ruled is not None
    frame = layout.frame
    per_unit = width / frame.width
    line = max(1, round(px(ruled.width) * per_unit))
    draw = ImageDraw.Draw(picture)
    for y in ruled_rows(0, height, px(ruled.spacing) * per_unit):
        draw.rectangle((0, round(y - line / 2), width, round(y - line / 2) + line - 1), ruled.color)
    if ruled.margin is not None:
        padding = px(theme.sizes.panel_padding)
        center = margin_center(frame, layout.inner, padding)
        for x in _margin_xs(center, px(ruled.width)):
            left = round((x - frame.left) * per_unit - line / 2)
            draw.rectangle((left, 0, left + line - 1, height), ruled.margin)
    return picture


def save_background(theme: Theme, layout: Layout, width: int, height: int, path: Path) -> Path:
    """Write the opaque background of `background_picture` to a PNG file and return its path."""
    background_picture(theme, layout, width, height).save(path)
    return path


def _margin_xs(center: float, line: float) -> tuple[float, float]:
    gap = line * MARGIN_GAP / 2
    return center - gap, center + gap


def _resolution_scale() -> float:
    """How many output pixels a pixel at 1080p is."""
    from manim import config

    return min(config.pixel_width, config.pixel_height) / 1080


@cache
def _picture_pixels(
    file: str, fit: str, width: int, height: int, scale: float, radius: int
) -> "np.ndarray":
    """The texture picture covering or tiling `width` × `height` pixels, as RGBA pixels.

    With a `radius`, the corners are cut round, as the panel's are.
    """
    import numpy as np
    from PIL import Image, ImageDraw

    with Image.open(file) as source:
        picture = source.convert("RGBA")
    canvas = Image.new("RGBA", (width, height))
    if fit == "cover":
        size = cover_size(picture.width, picture.height, width, height)
        resized = picture.resize(size, Image.Resampling.LANCZOS)
        left, top = (size[0] - width) // 2, (size[1] - height) // 2
        canvas = resized.crop((left, top, left + width, top + height))
    else:
        tile_size = (max(1, round(picture.width * scale)), max(1, round(picture.height * scale)))
        tile = picture.resize(tile_size, Image.Resampling.LANCZOS)
        for top in range(0, height, tile.height):
            for left in range(0, width, tile.width):
                canvas.paste(tile, (left, top))
    if radius > 0:
        # Drawn four times larger and reduced, so the round corners are smooth.
        mask = Image.new("L", (width * 4, height * 4))
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, width * 4 - 1, height * 4 - 1), radius * 4, fill=255
        )
        mask = mask.resize((width, height), Image.Resampling.LANCZOS)
        alpha = Image.fromarray(np.minimum(np.asarray(canvas.getchannel("A")), np.asarray(mask)))
        canvas.putalpha(alpha)
    return np.asarray(canvas)
