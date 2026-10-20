"""print3d-kit: design printable 3D models with build123d.

Typical use from a model script::

    from build123d import *
    from print3d_kit.parts import clearance_hole, box_with_lid

    result = Box(40, 20, 5, align=(Align.CENTER, Align.CENTER, Align.MIN))
    result -= Pos(0, 0, 5) * clearance_hole("M3", depth=5)

Then build it with ``p3d build model.py``.
"""

from .place import arrange, on_bed
from .printers import PRINTERS, Printer, get_printer

__version__ = "0.1.0"
__all__ = ["PRINTERS", "Printer", "arrange", "get_printer", "on_bed", "__version__"]
