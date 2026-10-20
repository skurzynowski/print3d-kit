"""Raspberry Pi 4B case: M2.5 standoffs, port openings on two sides, friction-fit lid with vent slots.

Port openings run all the way to the rim: the lid closes them from above, and
there is no weak sliver of wall left between the opening and the top edge.
"""

from build123d import Align, Axis, Box, Pos, chamfer

from print3d_kit.parts import box_with_lid, cutout

PRINTER = "bambu-a1-mini"

BOARD = (85.0, 56.0)
HOLE_SPACING = (58.0, 49.0)
HOLE_FROM_CORNER = 3.5  # Pi mounting holes sit 3.5 mm in from the board edges
CLEARANCE = 2.0  # air around the board
WALL = 2.0
FLOOR = 2.0
STANDOFF_H = 5.0
BOARD_T = 1.5
ABOVE_BOARD = 18.0  # USB stack is ~16 mm tall
VENT_SLOTS = 7

INNER = (BOARD[0] + 2 * CLEARANCE, BOARD[1] + 2 * CLEARANCE, STANDOFF_H + BOARD_T + ABOVE_BOARD)
BOARD_TOP = FLOOR + STANDOFF_H + BOARD_T  # z of the component side

# Board is centered in the box; hole positions relative to the box center.
hx0, hy0 = -BOARD[0] / 2 + HOLE_FROM_CORNER, -BOARD[1] / 2 + HOLE_FROM_CORNER
HOLES = [(hx0 + dx, hy0 + dy) for dx in (0, HOLE_SPACING[0]) for dy in (0, HOLE_SPACING[1])]

parts = box_with_lid(INNER, wall=WALL, floor=FLOOR, lip_height=4, standoffs=HOLES,
                     standoff_height=STANDOFF_H, standoff_screw="M2.5")
box, lid = parts["box"], parts["lid"]

# +X short side: Ethernet + 2x2 USB-A, one opening from the board up through the rim.
box = cutout(box, "+X", width=52, z=BOARD_TOP, wall=WALL, to_rim=True)
# -Y long side: USB-C power, 2x micro HDMI, audio jack.
box = cutout(box, "-Y", width=60, height=8, z=BOARD_TOP, offset=-6, wall=WALL)

CUT = (Align.CENTER, Align.CENTER, Align.MIN)
lid_x = lid.bounding_box().center().X
for i in range(VENT_SLOTS):
    lid -= Pos(lid_x + (i - (VENT_SLOTS - 1) / 2) * 7, 0, -1) * Box(3, INNER[1] - 20, 10, align=CUT)

box = chamfer(box.edges().group_by(Axis.Z)[0], 0.6)
parts = {"box": box, "lid": lid}
