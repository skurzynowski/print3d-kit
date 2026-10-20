"""Wall hook for a towel or headphones, one M4 screw. Printed on its side for strength."""

from print3d_kit import on_bed
from print3d_kit.parts import wall_hook

result = on_bed(wall_hook(width=18, height=60, reach=30, thickness=5, lip=12, hole="M4"))
