"""Desk phone stand: base, backrest leaning back 20 degrees, front lip, cable slot.

Modeled upright, then laid on its side for printing so the layers run along
the backrest and it does not snap at the base.
"""

from build123d import Align, Box, Plane, Polygon, Pos, Rot, extrude

from print3d_kit import on_bed

WIDTH = 70  # along the desk
T = 5  # plate thickness
PHONE_GAP = 13  # room for a phone in a case
LEAN = 20  # backrest tilt from vertical, degrees

MIN = (Align.MIN, Align.CENTER, Align.MIN)

base = Box(95, WIDTH, T, align=MIN)
lip = Pos(8, 0, 0) * Box(T, WIDTH, T + 12, align=MIN)
backrest = Pos(8 + T + PHONE_GAP, 0, 0) * Rot(0, LEAN, 0) * Box(T, WIDTH, 100, align=MIN)
# Strut from the back of the base up to the backrest at ~45 mm height.
strut = Pos(75, 0, 0) * Rot(0, -32, 0) * Box(T, WIDTH, 54, align=MIN)

stand = base + lip + backrest + strut
# Tilted plates poke below the bed; trim everything to z >= 0.
stand &= Box(300, 300, 300, align=(Align.CENTER, Align.CENTER, Align.MIN))
# Cable slot through the lip, so the phone can charge while standing. One side is
# cut at 45 degrees: printed on its side, a square notch would leave the lip above
# it hanging in the air (a 12 mm cantilever); the slope prints without support.
SLOT = 14
rise = T + 12 + 1  # through the top of the lip
notch = Polygon((-SLOT / 2, T), (SLOT / 2, T), (SLOT / 2 + rise, T + rise), (-SLOT / 2, T + rise), align=None)
stand -= Pos(8 - 1, 0, 0) * extrude(Plane.YZ * notch, T + 2)

# Lay it on its side (-Y face down) for printing.
result = on_bed(Rot(90, 0, 0) * stand)
