from pathlib import Path

import pytest
from build123d import Align, Box, Pos

from print3d_kit import get_printer
from print3d_kit.mesh import to_trimesh
from print3d_kit.validate import check_mesh

EXAMPLES = Path(__file__).parent.parent / "examples"
GENERIC = get_printer("generic")
MIN = (Align.CENTER, Align.CENTER, Align.MIN)


def check(shape, printer=GENERIC, **kw):
    return check_mesh(to_trimesh(shape), "part", printer, **kw)


def levels(report) -> dict[str, str]:
    return {f.check: f.level for f in report.findings}


def finding(report, name):
    return next(f for f in report.findings if f.check == name)


def table(gap: float, top: float = 3.0, leg: float = 4.0, height: float = 10.0, depth: float = 10.0):
    """Two legs and a flat top: a bridge of exactly ``gap`` mm at z=height."""
    legs = Pos(-(gap + leg) / 2, 0, 0) * Box(leg, depth, height, align=MIN)
    legs += Pos((gap + leg) / 2, 0, 0) * Box(leg, depth, height, align=MIN)
    return legs + Pos(0, 0, height) * Box(gap + 2 * leg, depth, top, align=MIN)


@pytest.fixture
def examples_dir():
    return EXAMPLES
