"""Export parts to STL (per part), 3MF (all parts in one file) and STEP."""

from pathlib import Path

from build123d import Compound, Mesher, Shape, export_step, export_stl

FORMATS = ("stl", "3mf", "step")


def export_parts(parts: dict[str, Shape], out_dir: Path, name: str, formats=FORMATS) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    if "stl" in formats:
        for part_name, shape in parts.items():
            path = out_dir / (f"{name}.stl" if len(parts) == 1 else f"{name}-{part_name}.stl")
            export_stl(shape, path, tolerance=0.01, angular_tolerance=0.1)
            written.append(path)

    if "3mf" in formats:
        path = out_dir / f"{name}.3mf"
        mesher = Mesher()
        for part_name, shape in parts.items():
            mesher.add_shape(shape, linear_deflection=0.01, angular_deflection=0.1, part_number=part_name)
        mesher.write(path)
        written.append(path)

    if "step" in formats:
        path = out_dir / f"{name}.step"
        shapes = list(parts.values())
        export_step(shapes[0] if len(shapes) == 1 else Compound(children=shapes), path)
        written.append(path)

    return written
