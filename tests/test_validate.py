import json

import pytest
from build123d import Axis, Box, Pos, chamfer, fillet

from conftest import GENERIC, MIN, check, finding, levels, table
from print3d_kit import get_printer


def test_too_big_for_bed():
    report = check(Box(300, 10, 10, align=MIN))
    assert levels(report)["bed"] == "error"
    assert not report.ok


def test_too_big_but_fits_rotated():
    report = check(Box(260, 100, 10, align=MIN), printer=get_printer("prusa-mk4"))  # 250 x 210 bed
    assert "rotated" not in finding(report, "bed").message  # 260 is too long either way
    report = check(Box(100, 240, 10, align=MIN), printer=get_printer("prusa-mk4"))
    assert "rotated 90" in finding(report, "bed").message


def test_custom_printer_bed():
    assert get_printer("100x120x80").bed == (100, 120, 80)
    with pytest.raises(ValueError, match="Unknown printer"):
        get_printer("nope")


def test_thin_sheet_is_a_warning_with_location():
    report = check(Box(30, 30, 0.4, align=MIN))
    f = finding(report, "thin_walls")
    assert f.level == "warning"
    assert f.where["thickness"] == pytest.approx(0.4, abs=0.02)
    assert len(f.where["at"]) == 3


def test_thin_sliver_is_reported_with_location():
    wall = Box(40, 20, 10, align=MIN)
    wall -= Pos(0, 11, 4) * Box(20, 6, 5, align=MIN)  # pocket leaves 1 mm to the +Y face
    report = check(wall)
    f = finding(report, "thin_spot")
    assert f.level == "info"
    assert report.metrics["wall_min_mm"] == pytest.approx(1.0, abs=0.05)
    assert abs(f.where["at"][1]) > 8  # on the +Y side, where the sliver is


def test_sliver_found_on_a_big_part():
    """3000 random samples over 100k mm2 would usually miss a 30 mm2 sliver."""
    slab = Box(200, 200, 30, align=MIN)
    slab -= Pos(100 - 1 - 2.5, 0, 20) * Box(5, 3, 10, align=MIN)  # 1 x 3 x 10 mm sliver at x=99..100
    f = finding(check(slab), "thin_spot")
    x, y, z = f.where["at"]
    assert 97 <= x <= 100.1 and abs(y) <= 3.5 and z >= 18


def test_45_degree_chamfer_is_not_an_overhang():
    block = chamfer(Box(30, 30, 10, align=MIN).edges().group_by(Axis.Z)[0], 1.0)
    assert "overhangs" not in levels(check(block))


def test_bottom_fillet_is_an_overhang():
    block = fillet(Box(30, 30, 10, align=MIN).edges().group_by(Axis.Z)[0], 3.0)
    f = finding(check(block), "overhangs")
    assert f.where["regions"][0]["kind"] == "sloped"


def test_short_bridge_is_info():
    f = finding(check(table(gap=8)), "overhangs")
    assert f.level == "info"
    assert f.where["regions"][0]["span"] == pytest.approx(8, abs=0.5)


def test_long_bridge_is_warning_with_span():
    f = finding(check(table(gap=30)), "overhangs")
    assert f.level == "warning"
    region = f.where["regions"][0]
    assert region["kind"] == "flat"
    assert region["span"] == pytest.approx(30, abs=0.5)
    assert "span 3" in f.message  # human message carries the number too


def test_ceiling_supported_on_all_sides_spans_its_short_side():
    """Closed box roof: 40 x 20 cavity, the bridge is the 20 mm direction."""
    shell = Box(44, 24, 14, align=MIN) - Pos(0, 0, 2) * Box(40, 20, 10, align=MIN)
    f = finding(check(shell), "overhangs")
    assert f.where["regions"][0]["span"] == pytest.approx(20, abs=0.6)


def test_cantilever_is_warning():
    """A shelf sticking out 15 mm with nothing under its far edge."""
    post = Box(5, 10, 20, align=MIN)
    shelf = Pos(10, 0, 20) * Box(15, 10, 3, align=MIN)
    f = finding(check(post + Pos(2.5, 0, 0) * shelf), "overhangs")
    assert f.level == "warning"


def test_overhang_regions_are_separate_and_sorted():
    two = table(gap=30) + Pos(60, 0, 0) * table(gap=8)
    regions = finding(check(two), "overhangs").where["regions"]
    assert len(regions) == 2
    assert regions[0]["area"] > regions[1]["area"]


def test_report_is_json_serialisable():
    report = check(table(gap=30) + Pos(0, 20, 0) * Box(30, 10, 0.5, align=MIN))  # bridge + thin sheet
    data = json.loads(json.dumps(report.to_dict()))
    assert data["ok"] is True
    located = {f["check"]: f["where"] for f in data["findings"] if f["check"] in ("thin_walls", "overhangs")}
    assert set(located) == {"thin_walls", "overhangs"}
    assert all(located.values())


def test_volume_and_mass():
    report = check(Box(10, 10, 10, align=MIN), printer=GENERIC)
    assert report.volume_mm3 == pytest.approx(1000, rel=1e-3)
    assert report.mass_g_solid == pytest.approx(1.24, abs=0.05)  # rounded to 0.1 g
