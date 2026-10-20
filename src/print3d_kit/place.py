"""Put parts where the printer wants them."""

from build123d import Pos, Shape


def on_bed(shape: Shape, center: bool = True) -> Shape:
    """Move a shape so its lowest point sits at z=0, optionally centered on X/Y."""
    bb = shape.bounding_box()
    dx = -(bb.min.X + bb.max.X) / 2 if center else 0
    dy = -(bb.min.Y + bb.max.Y) / 2 if center else 0
    return Pos(dx, dy, -bb.min.Z) * shape


def arrange(parts: dict[str, Shape], gap: float = 8.0) -> dict[str, Shape]:
    """Lay several parts on the bed in a row along X, each resting on z=0."""
    placed: dict[str, Shape] = {}
    x = 0.0
    for name, shape in parts.items():
        bb = shape.bounding_box()
        placed[name] = Pos(x - bb.min.X, -(bb.min.Y + bb.max.Y) / 2, -bb.min.Z) * shape
        x += bb.max.X - bb.min.X + gap
    return placed
