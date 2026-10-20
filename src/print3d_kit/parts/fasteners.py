"""Screw holes, nut traps, heat-set insert holes and standoffs, sized for FDM printing.

Every ``*_hole`` function returns a *cutter*: a solid you subtract from your part.
The hole opening is at the origin and the cutter goes ``depth`` mm into the part
along ``axis`` (default ``"-Z"``: down from a top face), with a small overshoot
out of the part so the cut is clean::

    part -= Pos(x, y, top_z) * clearance_hole("M3", depth=5)
    part -= Pos(x_max, y, z) * clearance_hole("M3", depth=5, axis="-X")  # into the +X face

Horizontal holes print with a sagging ceiling; pass ``teardrop=True`` to give
them a 45 degree roof that prints without support.
"""

import math
from dataclasses import dataclass

from build123d import Align, Circle, Cone, Cylinder, Part, Polygon, Pos, RegularPolygon, Rot, extrude

OVERSHOOT = 0.5  # mm the cutter sticks out of the part
DOWN = (Align.CENTER, Align.CENTER, Align.MAX)
UP = (Align.CENTER, Align.CENTER, Align.MIN)

# Rotation that turns a cutter pointing -Z into one pointing along each axis.
AXES = {
    "-Z": Rot(0, 0, 0),
    "+Z": Rot(180, 0, 0),
    "-Y": Rot(-90, 0, 0),
    "+Y": Rot(90, 0, 0),
    "-X": Rot(0, 90, 0),
    "+X": Rot(0, -90, 0),
}
# For horizontal axes: direction in the cutter's local XY plane (degrees from +X) that
# ends up pointing world +Z after the rotation above. The teardrop tip goes there.
TIP_ANGLE = {"+X": 0.0, "+Y": 90.0, "-X": 180.0, "-Y": 270.0}


@dataclass(frozen=True)
class Screw:
    clearance: float  # hole the screw slides through freely (printed holes shrink ~0.2 mm)
    tap: float  # hole the screw self-taps into plastic
    head_d: float  # socket/pan head diameter incl. clearance
    head_h: float
    csk_d: float  # countersunk head diameter incl. clearance
    nut_af: float  # hex nut across flats incl. clearance
    nut_h: float
    insert_d: float  # heat-set insert hole diameter
    insert_h: float


# Values are what prints well on a typical 0.4 mm nozzle; tweak with the tolerance args.
SCREWS: dict[str, Screw] = {
    "M2": Screw(2.4, 1.7, 4.2, 2.2, 4.4, 4.3, 1.8, 3.2, 4.0),
    "M2.5": Screw(2.9, 2.2, 5.0, 2.7, 5.2, 5.3, 2.2, 3.6, 4.5),
    "M3": Screw(3.4, 2.6, 6.0, 3.2, 6.3, 5.8, 2.6, 4.0, 5.7),
    "M4": Screw(4.5, 3.5, 7.6, 4.2, 8.4, 7.3, 3.4, 5.6, 8.1),
    "M5": Screw(5.5, 4.4, 9.2, 5.2, 10.4, 8.3, 4.2, 6.4, 9.5),
    "M6": Screw(6.6, 5.2, 10.8, 6.2, 12.4, 10.3, 5.2, 8.0, 12.7),
}


def _check_axis(axis: str, teardrop: bool) -> float | None:
    """Validate the axis; return the teardrop tip angle in the local frame, or None."""
    if axis not in AXES:
        raise ValueError(f"Unknown axis '{axis}'. Use one of: {', '.join(AXES)}")
    if not teardrop:
        return None
    if axis not in TIP_ANGLE:
        raise ValueError(f"teardrop=True only makes sense for horizontal holes (axis ±X/±Y), not {axis}")
    return TIP_ANGLE[axis]


def _aim(cutter: Part, axis: str) -> Part:
    return AXES[axis] * cutter


def _bore(d: float, depth: float, tip: float | None) -> Part:
    """Round (or teardrop) bore from z=+OVERSHOOT down to z=-depth."""
    r = d / 2
    if tip is None:
        return Pos(0, 0, OVERSHOOT) * Cylinder(r, depth + OVERSHOOT, align=DOWN)
    a = math.radians(tip)
    side1, side2 = a + math.radians(45), a - math.radians(45)
    apex = (r * math.sqrt(2) * math.cos(a), r * math.sqrt(2) * math.sin(a))
    # Counter-clockwise, so the face normal is +Z and extrude() goes the same way as the circle.
    roof = Polygon(
        (0, 0),
        (r * math.cos(side2), r * math.sin(side2)),
        apex,
        (r * math.cos(side1), r * math.sin(side1)),
        align=None,
    )
    return Pos(0, 0, -depth) * extrude(Circle(r) + roof, depth + OVERSHOOT)


def screw(size: str) -> Screw:
    try:
        return SCREWS[size]
    except KeyError:
        raise ValueError(f"Unknown screw size '{size}'. Known: {', '.join(SCREWS)}") from None


def clearance_hole(
    size: str, depth: float, tolerance: float = 0.0, axis: str = "-Z", teardrop: bool = False
) -> Part:
    """Through/blind hole the screw passes freely."""
    tip = _check_axis(axis, teardrop)
    return _aim(_bore(screw(size).clearance + tolerance, depth, tip), axis)


def tap_hole(size: str, depth: float, axis: str = "-Z", teardrop: bool = False) -> Part:
    """Undersized hole the screw cuts its own thread into."""
    tip = _check_axis(axis, teardrop)
    return _aim(_bore(screw(size).tap, depth, tip), axis)


def counterbore_hole(
    size: str,
    depth: float,
    head_depth: float | None = None,
    tolerance: float = 0.0,
    axis: str = "-Z",
    teardrop: bool = False,
) -> Part:
    """Clearance hole with a recess so a socket head sits flush."""
    tip = _check_axis(axis, teardrop)
    s = screw(size)
    head_depth = s.head_h if head_depth is None else head_depth
    cutter = _bore(s.clearance + tolerance, depth, tip) + _bore(s.head_d + tolerance, head_depth, tip)
    return _aim(cutter, axis)


def countersunk_hole(size: str, depth: float, tolerance: float = 0.0, axis: str = "-Z") -> Part:
    """Clearance hole with a 90 degree cone for flat-head screws."""
    _check_axis(axis, False)
    s = screw(size)
    r_top = (s.csk_d + tolerance) / 2
    r_bot = (s.clearance + tolerance) / 2
    cone = Cone(r_bot, r_top, r_top - r_bot, align=DOWN)
    cap = Cylinder(r_top, OVERSHOOT, align=UP)
    return _aim(_bore(s.clearance + tolerance, depth, None) + cone + cap, axis)


def nut_trap(
    size: str, depth: float | None = None, tolerance: float = 0.0, rotation: float = 0, axis: str = "-Z"
) -> Part:
    """Hexagonal pocket for a nut, opening at the origin. Combine with a clearance hole."""
    _check_axis(axis, False)
    s = screw(size)
    depth = s.nut_h + 0.2 if depth is None else depth
    hexagon = RegularPolygon((s.nut_af + tolerance) / 2, 6, major_radius=False, rotation=rotation)
    return _aim(Pos(0, 0, -depth) * extrude(hexagon, depth + OVERSHOOT), axis)


def heat_insert_hole(size: str, depth: float | None = None, axis: str = "-Z", teardrop: bool = False) -> Part:
    """Hole for a brass heat-set insert (Ruthex-style), with a 1 mm extra for melt."""
    tip = _check_axis(axis, teardrop)
    s = screw(size)
    depth = s.insert_h + 1.0 if depth is None else depth
    return _aim(_bore(s.insert_d, depth, tip), axis)


def standoff(height: float, size: str = "M3", outer_d: float | None = None, insert: bool = True) -> Part:
    """PCB standoff standing on z=0, with an insert or tap hole from the top."""
    s = screw(size)
    hole_d = s.insert_d if insert else s.tap
    outer_d = hole_d + 3.2 if outer_d is None else outer_d
    post = Cylinder(outer_d / 2, height, align=UP)
    hole = heat_insert_hole(size, min(height, s.insert_h + 1.0)) if insert else tap_hole(size, height)
    return post - Pos(0, 0, height) * hole
