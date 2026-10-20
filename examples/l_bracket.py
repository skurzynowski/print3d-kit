"""Shelf bracket: 40 x 40 mm legs, 25 mm wide, M4 holes, center gusset."""

from print3d_kit.parts import l_bracket

result = l_bracket(width=25, leg_a=40, leg_b=40, thickness=5, hole="M4", holes_per_leg=2)
