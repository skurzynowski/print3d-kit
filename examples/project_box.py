"""Enclosure for a 60 x 40 mm PCB with four M3 heat-set standoffs and a USB-C cutout."""

from build123d import Align, Box, Pos

from print3d_kit.parts import box_with_lid

PRINTER = "bambu-a1"

INNER = (66, 46, 25)
WALL = 2.0
FLOOR = 2.0
HOLES = [(x, y) for x in (-26.5, 26.5) for y in (-16.5, 16.5)]  # PCB mounting holes, from center

parts = box_with_lid(INNER, wall=WALL, floor=FLOOR, standoffs=HOLES, standoff_height=5)

# USB-C opening in the -X wall, centered on the PCB height above the standoffs.
usb = Box(WALL * 3, 10, 4.5, align=(Align.CENTER, Align.CENTER, Align.MIN))
parts["box"] -= Pos(-INNER[0] / 2 - WALL / 2, 0, FLOOR + 5 + 1.6) * usb
