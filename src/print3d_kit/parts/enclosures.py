"""Boxes and enclosures."""

from build123d import Align, Box, Part, Pos, RectangleRounded, extrude

from .fasteners import standoff


def _rounded_block(x: float, y: float, z: float, r: float) -> Part:
    r = max(min(r, x / 2 - 0.01, y / 2 - 0.01), 0.01)
    return extrude(RectangleRounded(x, y, r), z)


def box_with_lid(
    inner: tuple[float, float, float],
    wall: float = 2.0,
    floor: float = 2.0,
    lid_thickness: float = 2.0,
    lip_height: float = 4.0,
    lip_wall: float = 1.6,
    corner_radius: float = 3.0,
    tolerance: float = 0.25,
    standoffs: list[tuple[float, float]] | None = None,
    standoff_height: float = 5.0,
    standoff_screw: str = "M3",
) -> dict[str, Part]:
    """Box plus a friction-fit lid with an inner lip.

    ``inner`` is the usable space (X, Y, Z) in mm. Both parts come laid out on
    the bed ready to print: the box open side up, the lid flat side down next
    to it. ``standoffs`` are (x, y) positions relative to the box center.
    """
    ix, iy, iz = inner
    ox, oy = ix + 2 * wall, iy + 2 * wall
    inner_r = max(corner_radius - wall, 0.5)

    box = _rounded_block(ox, oy, floor + iz, corner_radius)
    box -= Pos(0, 0, floor) * _rounded_block(ix, iy, iz + 1, inner_r)
    for x, y in standoffs or []:
        box += Pos(x, y, floor) * standoff(standoff_height, standoff_screw)

    lx, ly = ix - 2 * tolerance, iy - 2 * tolerance
    lid = _rounded_block(ox, oy, lid_thickness, corner_radius)
    lip = _rounded_block(lx, ly, lip_height, inner_r)
    lip -= Pos(0, 0, -0.5) * _rounded_block(lx - 2 * lip_wall, ly - 2 * lip_wall, lip_height + 1, max(inner_r - lip_wall, 0.5))
    lid += Pos(0, 0, lid_thickness) * lip

    gap = 10.0
    return {"box": box, "lid": Pos(ox + gap, 0, 0) * lid}


WALL_FACES = ("+X", "-X", "+Y", "-Y")


def cutout(
    part: Part,
    face: str,
    width: float,
    height: float | None = None,
    z: float = 0.0,
    offset: float = 0.0,
    to_rim: bool = False,
    wall: float = 2.0,
    overshoot: float = 1.0,
) -> Part:
    """Cut a rectangular opening through one side wall of a box (ports, cables, switches).

    ``face`` is the wall's outward side (``"+X"``, ``"-X"``, ``"+Y"``, ``"-Y"``),
    ``z`` the bottom edge of the opening, ``offset`` its center along the wall,
    measured from the part's center. ``to_rim=True`` runs the opening up through the
    top edge, so no weak sliver of wall is left above it (the lid closes it).
    ``wall`` is the wall thickness; the cut goes ``overshoot`` mm past both sides.
    """
    if face not in WALL_FACES:
        raise ValueError(f"Unknown face '{face}'. Use one of: {', '.join(WALL_FACES)}")
    if height is None and not to_rim:
        raise ValueError("cutout() needs a height, or to_rim=True")
    bb = part.bounding_box()
    cx, cy = (bb.min.X + bb.max.X) / 2, (bb.min.Y + bb.max.Y) / 2
    h = bb.max.Z - z + overshoot if to_rim else height
    depth = wall + 2 * overshoot
    sign = 1 if face[0] == "+" else -1
    if face[1] == "X":
        x = (bb.max.X if sign > 0 else bb.min.X) - sign * wall / 2
        cutter = Pos(x, cy + offset, z) * Box(depth, width, h, align=(Align.CENTER, Align.CENTER, Align.MIN))
    else:
        y = (bb.max.Y if sign > 0 else bb.min.Y) - sign * wall / 2
        cutter = Pos(cx + offset, y, z) * Box(width, depth, h, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return part - cutter
