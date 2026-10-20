"""Brackets, mounts and hooks."""

from build123d import Align, Box, Cylinder, Part, Plane, Polygon, Pos, Rot, extrude

from .fasteners import screw

MIN = (Align.CENTER, Align.MIN, Align.MIN)


def l_bracket(
    width: float = 20.0,
    leg_a: float = 30.0,
    leg_b: float = 30.0,
    thickness: float = 4.0,
    hole: str | None = "M4",
    holes_per_leg: int = 2,
    gusset: bool = True,
    gusset_thickness: float = 3.0,
) -> Part:
    """90 degree angle bracket, printed lying on leg A.

    Leg A lies on the bed along +Y, leg B stands up along +Z at y=0. Holes are
    spread across the width; with a gusset, keep ``holes_per_leg`` even so no
    hole hits the center rib.
    """
    t = thickness
    part = Box(width, leg_a, t, align=MIN) + Box(width, t, leg_b, align=MIN)

    if gusset:
        g = min(leg_a, leg_b) - t
        rib = extrude(Plane.YZ * Polygon((t, t), (t + g, t), (t, t + g), align=None), gusset_thickness)
        part += Pos(-gusset_thickness / 2, 0, 0) * rib

    if hole:
        d = screw(hole).clearance
        xs = [(i + 0.5) * width / holes_per_leg - width / 2 for i in range(holes_per_leg)]
        ya = t + (leg_a - t) * 0.6
        zb = t + (leg_b - t) * 0.6
        for x in xs:
            part -= Pos(x, ya, t / 2) * Cylinder(d / 2, t * 3)
            part -= Pos(x, t / 2, zb) * Rot(90, 0, 0) * Cylinder(d / 2, t * 3)
    return part


def wall_hook(
    width: float = 15.0,
    height: float = 50.0,
    reach: float = 25.0,
    thickness: float = 4.0,
    lip: float = 10.0,
    hole: str | None = "M4",
) -> Part:
    """J-style hook printed on its side: back plate, arm and an upturned lip.

    Lies in the XZ profile extruded along Y by ``width``, so layer lines run
    along the load and the hook does not snap off.
    """
    t = thickness
    back = Box(t, width, height, align=(Align.MIN, Align.CENTER, Align.MIN))
    arm = Box(reach, width, t, align=(Align.MIN, Align.CENTER, Align.MIN))
    tip = Pos(reach - t, 0, 0) * Box(t, width, lip + t, align=(Align.MIN, Align.CENTER, Align.MIN))
    brace_profile = Polygon((t, t), (t + reach * 0.45, t), (t, t + reach * 0.45), align=None)
    brace = Pos(0, width / 2, 0) * extrude(Plane.XZ * brace_profile, width)
    part = back + arm + tip + brace
    if hole:
        d = screw(hole).clearance
        part -= Pos(t / 2, 0, height - 8) * Rot(0, 90, 0) * Cylinder(d / 2, t * 3)
    # Print lying on the side: rotate so the Y extrusion becomes the Z build direction.
    return Rot(90, 0, 0) * part
