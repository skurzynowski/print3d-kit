"""Printer presets: build volume and nozzle, used by the print checks."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Printer:
    name: str
    bed: tuple[float, float, float]  # X, Y, Z build volume in mm
    nozzle: float = 0.4

    @property
    def min_wall(self) -> float:
        """Thinnest wall worth printing: two perimeters."""
        return 2 * self.nozzle


PRINTERS: dict[str, Printer] = {
    "generic": Printer("generic", (220, 220, 250)),
    "bambu-a1": Printer("bambu-a1", (256, 256, 256)),
    "bambu-a1-mini": Printer("bambu-a1-mini", (180, 180, 180)),
    "bambu-x1": Printer("bambu-x1", (256, 256, 256)),
    "bambu-p1s": Printer("bambu-p1s", (256, 256, 256)),
    "prusa-mk4": Printer("prusa-mk4", (250, 210, 220)),
    "prusa-mini": Printer("prusa-mini", (180, 180, 180)),
    "prusa-core-one": Printer("prusa-core-one", (250, 220, 270)),
    "ender3": Printer("ender3", (220, 220, 250)),
}


CONFIG_FILE = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "print3d-kit" / "printer"


def default_printer() -> str:
    """The user's own printer: $P3D_PRINTER, else the config file, else ``generic``."""
    if os.environ.get("P3D_PRINTER"):
        return os.environ["P3D_PRINTER"]
    try:
        return CONFIG_FILE.read_text().strip() or "generic"
    except OSError:
        return "generic"


def get_printer(name: str) -> Printer:
    """Look up a preset, or parse a custom bed like ``200x200x180``."""
    if name in PRINTERS:
        return PRINTERS[name]
    try:
        x, y, z = (float(v) for v in name.lower().split("x"))
    except ValueError:
        known = ", ".join(PRINTERS)
        raise ValueError(f"Unknown printer '{name}'. Use one of: {known}, or WxDxH like 200x200x180") from None
    return Printer(f"custom {name}", (x, y, z))
