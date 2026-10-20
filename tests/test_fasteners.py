import math

import pytest
from build123d import Box, Pos

from conftest import MIN, check, levels
from print3d_kit.parts import (
    clearance_hole,
    counterbore_hole,
    countersunk_hole,
    heat_insert_hole,
    nut_trap,
    screw,
    standoff,
    tap_hole,
)
from print3d_kit.parts.fasteners import AXES, OVERSHOOT

DEPTH = 10.0
M3 = screw("M3").clearance


def extent(shape):
    bb = shape.bounding_box()
    return {"X": (bb.min.X, bb.max.X), "Y": (bb.min.Y, bb.max.Y), "Z": (bb.min.Z, bb.max.Z)}


@pytest.mark.parametrize("axis", list(AXES))
def test_cutter_points_along_axis(axis):
    ext = extent(clearance_hole("M3", DEPTH, axis=axis))
    sign, along = axis
    lo, hi = ext[along]
    if sign == "-":
        assert lo == pytest.approx(-DEPTH, abs=1e-6) and hi == pytest.approx(OVERSHOOT, abs=1e-6)
    else:
        assert lo == pytest.approx(-OVERSHOOT, abs=1e-6) and hi == pytest.approx(DEPTH, abs=1e-6)
    for other in "XYZ".replace(along, ""):
        assert ext[other] == pytest.approx((-M3 / 2, M3 / 2), abs=1e-6)


@pytest.mark.parametrize(
    "make",
    [
        lambda axis: tap_hole("M3", DEPTH, axis=axis),
        lambda axis: counterbore_hole("M3", DEPTH, axis=axis),
        lambda axis: countersunk_hole("M3", DEPTH, axis=axis),
        lambda axis: nut_trap("M3", axis=axis),
        lambda axis: heat_insert_hole("M3", axis=axis),
    ],
    ids=["tap", "counterbore", "countersunk", "nut_trap", "insert"],
)
@pytest.mark.parametrize("axis", ["-X", "+Y", "+Z"])
def test_every_cutter_honours_axis(make, axis):
    sign, along = axis
    lo, hi = extent(make(axis))[along]
    assert (hi > 1.0 and lo > -1.0) if sign == "+" else (lo < -1.0 and hi < 1.0)


def test_side_hole_cuts_into_plate():
    plate = Box(20, 20, 6, align=MIN)
    cut = plate - Pos(0, 10, 3) * clearance_hole("M3", depth=20, axis="-Y")
    expected = math.pi * (M3 / 2) ** 2 * 20
    assert plate.volume - cut.volume == pytest.approx(expected, rel=0.05)


def test_wrong_side_cuts_air():
    """The failure the axis argument exists to prevent: hole aimed out of the part."""
    plate = Box(20, 20, 6, align=MIN)
    cut = plate - Pos(0, 10, 3) * clearance_hole("M3", depth=20, axis="+Y")
    only_overshoot = math.pi * (M3 / 2) ** 2 * OVERSHOOT
    assert plate.volume - cut.volume == pytest.approx(only_overshoot, rel=0.05)


@pytest.mark.parametrize("axis", ["+X", "-X", "+Y", "-Y"])
def test_teardrop_tip_points_up(axis):
    bb = clearance_hole("M3", DEPTH, axis=axis, teardrop=True).bounding_box()
    assert bb.max.Z == pytest.approx(M3 / 2 * math.sqrt(2), abs=1e-3)
    assert bb.min.Z == pytest.approx(-M3 / 2, abs=1e-3)


def test_teardrop_is_bigger_than_round():
    round_ = clearance_hole("M5", DEPTH, axis="-Y")
    drop = clearance_hole("M5", DEPTH, axis="-Y", teardrop=True)
    assert drop.volume > round_.volume
    assert len(drop.solids()) == 1


def test_teardrop_prints_without_overhang():
    plate = Box(30, 20, 12, align=MIN)
    hole = dict(depth=20, axis="-Y")
    # 8 mm hole: use M6 insert size (8.0) through the 20 mm plate depth, at mid height.
    round_ = plate - Pos(0, 10, 6) * heat_insert_hole("M6", **hole)
    drop = plate - Pos(0, 10, 6) * heat_insert_hole("M6", teardrop=True, **hole)
    assert "overhangs" in levels(check(round_))
    assert "overhangs" not in levels(check(drop))


def test_teardrop_rejects_vertical_axis():
    with pytest.raises(ValueError, match="horizontal"):
        clearance_hole("M3", DEPTH, teardrop=True)


def test_unknown_axis_and_size():
    with pytest.raises(ValueError, match="axis"):
        clearance_hole("M3", DEPTH, axis="Z")
    with pytest.raises(ValueError, match="screw size"):
        clearance_hole("M7", DEPTH)


def test_standoff_has_insert_hole():
    post = standoff(10, "M3")
    solid_volume = math.pi * (post.bounding_box().size.X / 2) ** 2 * 10
    assert post.volume < solid_volume * 0.9
    assert post.bounding_box().min.Z == pytest.approx(0)
