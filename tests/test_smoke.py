"""Examples build, and their print checks say exactly what they said last time.

When a validator change shifts a golden entry on purpose, update it here and
mention it in the change description; otherwise it is a regression.
"""

import json

import pytest

from conftest import EXAMPLES, check
from print3d_kit.cli import main
from print3d_kit.parts import box_with_lid, l_bracket, standoff, wall_hook
from print3d_kit import on_bed

GOLDEN = {
    "l_bracket": {"result": {("overhangs", "info")}},  # two 4.5 mm side holes
    "phone_stand": {"result": set()},  # cable slot has a 45 degree side, so no cantilever
    "project_box": {"box": {("overhangs", "info")}, "lid": set()},  # 10 mm USB-C bridge
    "rpi4_case": {"box": {("overhangs", "warning")}, "lid": set()},  # 60 mm HDMI/power opening ceiling
    "wall_hook": {"result": {("overhangs", "info")}},  # M4 screw hole through the back plate
}


def test_every_example_has_a_golden_entry():
    assert {p.stem for p in EXAMPLES.glob("*.py")} == set(GOLDEN)


@pytest.mark.parametrize("name", sorted(GOLDEN))
def test_example_builds_with_golden_findings(name, tmp_path):
    assert main(["build", str(EXAMPLES / f"{name}.py"), "-o", str(tmp_path)]) == 0
    assert (tmp_path / "preview.png").stat().st_size > 10_000
    assert list(tmp_path.glob("*.3mf")) and list(tmp_path.glob("*.step"))
    report = json.loads((tmp_path / "report.json").read_text())
    found = {p["name"]: {(f["check"], f["level"]) for f in p["findings"]} for p in report["parts"]}
    assert found == GOLDEN[name]


def test_rpi_case_bridge_is_the_hdmi_opening(tmp_path):
    main(["build", str(EXAMPLES / "rpi4_case.py"), "-o", str(tmp_path), "--no-render", "-f", "stl"])
    box = json.loads((tmp_path / "report.json").read_text())["parts"][0]
    (overhang,) = [f for f in box["findings"] if f["check"] == "overhangs"]
    assert len(overhang["where"]["regions"]) == 1
    assert overhang["where"]["regions"][0]["span"] == pytest.approx(60, abs=1)


@pytest.mark.parametrize(
    "shape",
    [l_bracket(), wall_hook(), standoff(6), *box_with_lid((40, 30, 20)).values()],
    ids=["l_bracket", "wall_hook", "standoff", "box", "lid"],
)
def test_library_parts_are_printable_solids(shape):
    report = check(on_bed(shape))
    assert report.ok, report.findings
    assert report.volume_mm3 > 0
