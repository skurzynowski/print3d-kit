import numpy as np
import pytest
from build123d import Box, Cylinder, Pos, Rot

from conftest import MIN
from print3d_kit.mesh import to_trimesh
from print3d_kit.parts import nut_trap
from print3d_kit.render import BACKGROUND, EDGE, _render_view, render_preview

SIZE = 200


def view(shape, name):
    mesh = to_trimesh(shape)
    img = _render_view({"p": mesh}, name, mesh.bounds[0], mesh.bounds[1], SIZE)
    return np.asarray(img).astype(int)


def center(img):
    return tuple(img[SIZE // 2, SIZE // 2])


def test_hole_is_see_through():
    """Hidden-face regression: matplotlib's painter's algorithm drew the back wall over the hole."""
    block = Box(20, 20, 20)
    holed = block - Rot(90, 0, 0) * Cylinder(4, 30)
    assert center(view(holed, "front")) == BACKGROUND
    assert center(view(block, "front")) != BACKGROUND


def test_open_box_shows_its_floor():
    """Top view of a cup: the centre is the floor (lit like the rim), not the dark underside."""
    cup = Box(30, 30, 10, align=MIN) - Pos(0, 0, 2) * Box(26, 26, 10, align=MIN)
    img = view(cup, "top")
    rim = tuple(img[SIZE // 2, int(SIZE * 0.13)])  # on the 2 mm rim near the left edge
    assert center(img) != BACKGROUND
    assert np.abs(np.array(center(img)) - np.array(rim)).max() <= 2


def test_bottom_view_reveals_nut_trap():
    plate = Box(30, 30, 6, align=MIN) - Rot(180, 0, 0) * nut_trap("M5")  # pocket from below
    edge = np.array(EDGE)

    def edge_pixels(img):
        return int((np.abs(img - edge).max(axis=-1) == 0).sum())

    assert edge_pixels(view(plate, "bottom")) > edge_pixels(view(plate, "top")) + 50


def test_sheet_size_and_legend(tmp_path):
    parts = {"a": to_trimesh(Box(10, 10, 10, align=MIN)), "b": to_trimesh(Pos(20, 0, 0) * Box(5, 5, 5, align=MIN))}
    out = render_preview(parts, tmp_path / "p.png", views=("iso", "front", "top"), size=SIZE)
    from PIL import Image

    img = Image.open(out)
    assert img.size == (2 * SIZE, 2 * SIZE + 36)


@pytest.mark.parametrize("name", ["iso", "front", "right", "top", "back-iso", "bottom", "left", "back"])
def test_every_view_renders_something(name):
    img = view(Box(10, 20, 30, align=MIN), name)
    assert (np.abs(img - np.array(BACKGROUND)).max(axis=-1) > 0).sum() > 1000
