import pytest

from conftest import check, levels
from print3d_kit.parts import box_with_lid, cutout, l_bracket

INNER = (60, 40, 25)
WALL = 2.0


@pytest.fixture(scope="module")
def box():
    return box_with_lid(INNER, wall=WALL)["box"]


@pytest.mark.parametrize("face", ["+X", "-X", "+Y", "-Y"])
def test_cutout_on_each_face(box, face):
    cut = cutout(box, face, width=10, height=6, z=8, wall=WALL)
    assert box.volume - cut.volume == pytest.approx(10 * 6 * WALL, rel=0.02)


def test_cutout_to_rim_leaves_no_sliver(box):
    rim = box.bounding_box().max.Z
    sliver = cutout(box, "+X", width=20, height=rim - 1 - 8, z=8, wall=WALL)  # ends 1 mm below the rim
    open_top = cutout(box, "+X", width=20, z=8, wall=WALL, to_rim=True)
    assert "thin_spot" in levels(check(sliver))
    assert "thin_spot" not in levels(check(open_top))


def test_cutout_argument_errors(box):
    with pytest.raises(ValueError, match="face"):
        cutout(box, "+Z", width=10, height=5)
    with pytest.raises(ValueError, match="height"):
        cutout(box, "+X", width=10)


def test_box_and_lid_are_clean():
    parts = box_with_lid(INNER, standoffs=[(-20, -10), (20, 10)])
    for shape in parts.values():
        assert check(shape).ok
    # lid lip must fit inside the box opening with the tolerance gap
    box_bb, lid_bb = parts["box"].bounding_box(), parts["lid"].bounding_box()
    assert lid_bb.min.X > box_bb.max.X  # laid out next to each other
    assert lid_bb.size.X == pytest.approx(box_bb.size.X)


def test_l_bracket_holes():
    plain = l_bracket(hole=None)
    holed = l_bracket(hole="M4")
    assert holed.volume < plain.volume
