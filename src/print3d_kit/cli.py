"""p3d: build, check and preview printable models.

A model is a Python file that defines either ``result`` (one build123d shape)
or ``parts`` (dict of name -> shape). Optional module-level ``PRINTER`` and
``NAME`` set defaults; command-line flags win.
"""

import argparse
import inspect
import json
import runpy
import sys
import traceback
from pathlib import Path

import trimesh
from build123d import Shape

from . import parts as parts_lib
from .export import FORMATS, export_parts
from .mesh import to_trimesh
from .printers import PRINTERS, get_printer
from .render import DEFAULT_VIEWS, VIEWS, render_preview
from .validate import Report, check_mesh

LEVEL_MARK = {"error": "ERROR", "warning": "WARN ", "info": "info "}


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.func(args)
    except UsageError as e:
        print(f"p3d: {e}", file=sys.stderr)
        return 2


class UsageError(Exception):
    """Bad command-line input: reported as one line, exit code 2."""


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="p3d", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(required=True, metavar="command")

    b = sub.add_parser("build", help="run a model script: export, check, render preview")
    b.add_argument("model", type=Path)
    b.add_argument("-o", "--out", type=Path, help="output dir (default: <model dir>/out/<name>)")
    b.add_argument("-n", "--name", help="file name stem (default: NAME in script or model file name)")
    _common(b)
    b.add_argument("-f", "--formats", default=",".join(FORMATS), help="comma list of stl,3mf,step")
    b.add_argument("--no-render", action="store_true")
    b.set_defaults(func=cmd_build)

    c = sub.add_parser("check", help="run print checks on an existing STL/3MF/OBJ")
    c.add_argument("mesh", type=Path)
    _common(c)
    c.set_defaults(func=cmd_check)

    r = sub.add_parser("render", help="render a multi-view PNG of an existing mesh")
    r.add_argument("mesh", type=Path)
    r.add_argument("-o", "--out", type=Path, help="PNG path (default: next to the mesh)")
    r.add_argument("--views", default=",".join(DEFAULT_VIEWS), help=f"comma list of {','.join(VIEWS)}")
    r.set_defaults(func=cmd_render)

    sub.add_parser("parts", help="list the parts library").set_defaults(func=cmd_parts)
    sub.add_parser("printers", help="list printer presets").set_defaults(func=cmd_printers)
    return p


def _common(p: argparse.ArgumentParser) -> None:
    p.add_argument("-p", "--printer", help="preset name or WxDxH, e.g. 200x200x180 (default: generic)")
    p.add_argument("--min-wall", type=float, help="thinnest acceptable wall in mm (default: 2 x nozzle)")
    p.add_argument("--overhang", type=float, default=45.0, help="max overhang from vertical in degrees")
    p.add_argument("--views", default=",".join(DEFAULT_VIEWS), help=f"comma list of {','.join(VIEWS)}")
    p.add_argument("--json", action="store_true", help="print the report as JSON instead of text")


def cmd_build(args) -> int:
    model = args.model.resolve()
    if not model.is_file():
        raise UsageError(f"Model file not found: {model}")
    views = _views(args.views)
    if args.printer:
        _printer(args.printer)
    try:
        ns = runpy.run_path(str(model), run_name="__p3d__")
    except Exception:
        print(f"Model script failed: {model}", file=sys.stderr)
        traceback.print_exc()
        return 2

    shapes = _collect_shapes(ns)
    if shapes is None:
        print("Model must define `result` (a build123d shape) or `parts` (dict name -> shape).", file=sys.stderr)
        return 2
    flat = [n for n, s in shapes.items() if not s.solids()]
    if flat:
        print(
            f"Not a solid: {', '.join(flat)}. Got a 2D sketch, wire or empty shape; "
            "extrude()/revolve() it or check that the boolean ops left something.",
            file=sys.stderr,
        )
        return 2

    name = args.name or ns.get("NAME") or model.stem
    printer = _printer(args.printer or ns.get("PRINTER") or "generic")
    out = (args.out or model.parent / "out" / name).resolve()

    written = export_parts(shapes, out, name, formats=[f.strip() for f in args.formats.split(",") if f.strip()])
    meshes = {n: to_trimesh(s) for n, s in shapes.items()}
    reports = [check_mesh(m, n, printer, args.min_wall, args.overhang) for n, m in meshes.items()]

    if not args.no_render:
        preview = render_preview(meshes, out / "preview.png", views=views, title=name)
        written.append(preview)

    (out / "report.json").write_text(json.dumps(_summary(name, printer, reports, written), indent=2))
    written.append(out / "report.json")
    _print(name, printer, reports, written, args.json)
    return 0 if all(r.ok for r in reports) else 1


def cmd_check(args) -> int:
    printer = _printer(args.printer or "generic")
    meshes = _load_meshes(args.mesh)
    reports = [check_mesh(m, n, printer, args.min_wall, args.overhang) for n, m in meshes.items()]
    _print(args.mesh.stem, printer, reports, [], args.json)
    return 0 if all(r.ok for r in reports) else 1


def cmd_render(args) -> int:
    views = _views(args.views)
    meshes = _load_meshes(args.mesh)
    out = args.out or args.mesh.with_suffix(".png")
    print(render_preview(meshes, out, views=views, title=args.mesh.stem))
    return 0


def cmd_parts(args) -> int:
    for name in parts_lib.__all__:
        obj = getattr(parts_lib, name)
        if not callable(obj) or name == "screw":
            continue
        doc = (inspect.getdoc(obj) or "").splitlines()[0]
        print(f"{name}{inspect.signature(obj)}\n    {doc}\n")
    print("Screw sizes:", ", ".join(parts_lib.SCREWS))
    return 0


def cmd_printers(args) -> int:
    for p in PRINTERS.values():
        x, y, z = p.bed
        print(f"{p.name:16} {x:.0f} x {y:.0f} x {z:.0f} mm, nozzle {p.nozzle} mm")
    return 0


def _printer(name: str):
    try:
        return get_printer(name)
    except ValueError as e:
        raise UsageError(str(e)) from None


def _load_meshes(path: Path) -> dict[str, trimesh.Trimesh]:
    """Load any mesh file as {part name: mesh}; a single-body file is named after the file."""
    if not path.is_file():
        raise UsageError(f"Mesh file not found: {path}")
    try:
        loaded = trimesh.load(path, force="scene")
    except Exception as e:  # trimesh raises a zoo of types for unreadable files
        raise UsageError(f"Cannot read {path}: {e}") from None
    meshes = dict(loaded.geometry)
    if len(meshes) <= 1:
        return {path.stem: next(iter(meshes.values()))} if meshes else {}
    names = _3mf_part_names(path) if path.suffix.lower() == ".3mf" else {}
    return {names.get(key, key): mesh for key, mesh in meshes.items()}


def _3mf_part_names(path: Path) -> dict[str, str]:
    """3MF object id -> partnumber/name; trimesh only keeps the numeric id."""
    import re
    import zipfile

    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("3D/3dmodel.model").decode("utf-8", "replace")
    except (OSError, KeyError, zipfile.BadZipFile):
        return {}
    names = {}
    for tag in re.findall(r"<object\b[^>]*>", xml):
        obj_id = re.search(r'\bid="([^"]+)"', tag)
        label = re.search(r'\b(?:partnumber|name)="([^"]+)"', tag)
        if obj_id and label:
            names[obj_id.group(1)] = label.group(1)
    return names


def _collect_shapes(ns: dict) -> dict[str, Shape] | None:
    if isinstance(ns.get("parts"), dict) and ns["parts"]:
        return dict(ns["parts"])
    if isinstance(ns.get("result"), Shape):
        return {"result": ns["result"]}
    return None


def _views(spec: str) -> list[str]:
    views = [v.strip() for v in spec.split(",") if v.strip()]
    unknown = [v for v in views if v not in VIEWS]
    if unknown:
        raise UsageError(f"Unknown view(s): {', '.join(unknown)}. Use: {', '.join(VIEWS)}")
    return views


def _summary(name, printer, reports: list[Report], written: list[Path]) -> dict:
    return {
        "name": name,
        "printer": {"name": printer.name, "bed": printer.bed, "nozzle": printer.nozzle},
        "ok": all(r.ok for r in reports),
        "parts": [r.to_dict() for r in reports],
        "files": [str(p) for p in written],
    }


def _print(name, printer, reports: list[Report], written: list[Path], as_json: bool) -> None:
    if as_json:
        print(json.dumps(_summary(name, printer, reports, written), indent=2))
        return
    status = "OK" if all(r.ok for r in reports) else "HAS ERRORS"
    print(f"== {name} on {printer.name} {printer.bed}: {status}")
    for r in reports:
        x, y, z = r.dimensions
        print(f"\n[{r.name}] {x} x {y} x {z} mm, {r.volume_mm3 / 1000:.1f} cm3, ~{r.mass_g_solid} g PLA if solid")
        if r.metrics:
            print("  " + ", ".join(f"{k}={v}" for k, v in r.metrics.items()))
        for f in r.findings or []:
            print(f"  {LEVEL_MARK[f.level]} {f.check}: {f.message}")
        if not r.findings:
            print("  no issues found")
    if written:
        print("\nFiles:")
        for p in written:
            print(f"  {p}")


if __name__ == "__main__":
    sys.exit(main())
