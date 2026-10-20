import trimesh
import pytest
from build123d import Box, import_step

from conftest import EXAMPLES, MIN
from print3d_kit import arrange, on_bed
from print3d_kit.cli import main

BRACKET = str(EXAMPLES / "l_bracket.py")
FAST = ["--no-render", "-f", "stl"]


def script(tmp_path, body: str):
    path = tmp_path / "model.py"
    path.write_text("from build123d import *\n" + body + "\n")
    return str(path)


def test_ok_is_zero(tmp_path):
    assert main(["build", BRACKET, "-o", str(tmp_path), *FAST]) == 0


def test_check_error_is_one(tmp_path):
    assert main(["build", BRACKET, "-o", str(tmp_path), "-p", "20x20x20", *FAST]) == 1


@pytest.mark.parametrize(
    "body, message",
    [
        ("x = 1 / 0", "ZeroDivisionError"),
        ("foo = Box(1, 1, 1)", "must define"),
        ("result = Rectangle(10, 10)", "Not a solid"),
    ],
    ids=["crash", "no-result", "2d-result"],
)
def test_script_problems_are_two(tmp_path, capsys, body, message):
    assert main(["build", script(tmp_path, body), "-o", str(tmp_path / "out"), *FAST]) == 2
    assert message in capsys.readouterr().err


@pytest.mark.parametrize(
    "args, message",
    [
        (["build", BRACKET, "-p", "foo"], "Unknown printer"),
        (["build", BRACKET, "--views", "iso,foo", "--no-render"], "Unknown view"),
        (["build", "nope.py"], "not found"),
        (["check", "nope.stl"], "not found"),
        (["render", "nope.stl"], "not found"),
    ],
)
def test_usage_errors_are_one_line(capsys, args, message):
    assert main(args) == 2
    err = capsys.readouterr().err
    assert message in err and "Traceback" not in err


def test_check_flags_broken_mesh(tmp_path, capsys):
    mesh = trimesh.creation.box((10, 10, 10))
    mesh.update_faces(mesh.faces[1:] is not None and list(range(1, len(mesh.faces))))
    path = tmp_path / "holey.stl"
    mesh.export(path)
    assert main(["check", str(path)]) == 1
    assert "watertight" in capsys.readouterr().out


def test_3mf_round_trip_keeps_names_and_volumes(tmp_path, capsys):
    import runpy

    from print3d_kit.cli import _load_meshes

    model = EXAMPLES / "project_box.py"
    assert main(["build", str(model), "-o", str(tmp_path), "--no-render", "-f", "3mf"]) == 0
    expected = {n: s.volume for n, s in runpy.run_path(str(model))["parts"].items()}
    loaded = _load_meshes(tmp_path / "project_box.3mf")
    assert set(loaded) == set(expected)
    for name, mesh in loaded.items():
        assert mesh.volume == pytest.approx(expected[name], rel=0.01)
    capsys.readouterr()
    main(["check", str(tmp_path / "project_box.3mf")])
    out = capsys.readouterr().out
    assert "[box]" in out and "[lid]" in out


def test_step_round_trip(tmp_path):
    model = EXAMPLES / "project_box.py"
    assert main(["build", str(model), "-o", str(tmp_path), "--no-render", "-f", "step"]) == 0
    assert len(import_step(tmp_path / "project_box.step").solids()) == 2


def test_json_report(tmp_path, capsys):
    import json

    main(["build", BRACKET, "-o", str(tmp_path), "--json", *FAST])
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] and data["parts"][0]["dimensions"] == [25.0, 40.0, 40.0]
    assert json.loads((tmp_path / "report.json").read_text())["name"] == "l_bracket"


def test_on_bed_and_arrange():
    raised = on_bed(Box(10, 20, 5))
    bb = raised.bounding_box()
    assert bb.min.Z == pytest.approx(0) and bb.center().X == pytest.approx(0) and bb.center().Y == pytest.approx(0)

    laid = arrange({"a": Box(10, 10, 10), "b": Box(20, 5, 3, align=MIN), "c": Box(4, 4, 4)})
    boxes = [s.bounding_box() for s in laid.values()]
    assert all(b.min.Z == pytest.approx(0) for b in boxes)
    for left, right in zip(boxes, boxes[1:]):
        assert right.min.X > left.max.X


def test_parts_and_printers_list(capsys):
    assert main(["parts"]) == 0
    out = capsys.readouterr().out
    assert "cutout(" in out and "axis" in out
    assert main(["printers"]) == 0
    assert "bambu-a1" in capsys.readouterr().out
