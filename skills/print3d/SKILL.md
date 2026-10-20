---
name: print3d
description: Design simple, printable 3D models (STL/3MF/STEP) for FDM printers with build123d and the p3d CLI — enclosures, brackets, hooks, stands, holders, spacers, adapters, replacement parts. Writes a Python model, builds it, LOOKS at the multi-view preview, fixes print-check warnings, and hands over files ready for a slicer. Triggers on "zaprojektuj model 3d", "narysuj do druku", "zrób STL", "model do drukarki 3d", "obudowa na płytkę", "uchwyt/wspornik/haczyk do wydruku", "design a 3D printable", "make an STL", "3D print a", "enclosure for", "bracket for".
---

# print3d: printable models with build123d + p3d

You design parts as Python (build123d), build them with `p3d build`, then **look at
the preview PNG** and **read the print checks** before calling anything done.

## Workflow

1. **Pin down the brief** (ask only for what you cannot sensibly assume):
   - critical dimensions in mm (what it must fit around / onto, screw sizes),
   - printer (`p3d printers`; default `generic` 220x220x250, 0.4 mm nozzle),
   - load / use (decides wall thickness and print orientation).
   State the assumptions you made in one line.
2. **Check the library first**: `p3d parts` lists ready parts and hole cutters
   (`box_with_lid`, `l_bracket`, `wall_hook`, `standoff`, `clearance_hole`,
   `counterbore_hole`, `countersunk_hole`, `nut_trap`, `heat_insert_hole`, ...).
3. **Write the model** to `models/<name>.py` in the user's project (create the dir).
   Put every dimension in a named UPPER_CASE constant at the top so the user can tweak it.
   The script must define `result` (one shape) or `parts` (dict name -> shape).
   Optionally `PRINTER = "bambu-a1"`.
4. **Build**: `p3d build models/<name>.py` (add `-p <printer>` if needed).
   Output goes to `models/out/<name>/`: STL per part, one 3MF with all parts, STEP,
   `preview.png`, `report.json`. Exit code 1 = errors in checks, 2 = script crashed.
5. **Look at `preview.png` with the Read tool. Every time.** Compare it to the brief:
   right features, right side, holes where intended, nothing floating, part lying on
   its intended print face. Use `--views iso,back-iso,bottom,left` to see hidden sides.
6. **Fix and rebuild** until there are no errors and every warning is either fixed
   or consciously accepted (say why). Typical loop is 2–4 builds.
7. **Hand over**: paths to the 3MF (for Bambu/Prusa/Orca slicers) and STL, the
   dimensions, suggested print settings (layer height, walls, infill, supports yes/no,
   orientation) and which constants to change for common tweaks.

## Coordinate & print conventions

- Units are mm. Z is up, the bed is z=0. Model the part **in its print orientation**,
  or model it naturally and finish with `result = on_bed(Rot(...) * part)`.
- `from print3d_kit import on_bed, arrange` — `on_bed` drops a shape to z=0 and
  centers it; `arrange(parts)` lays several parts out in a row.
- Hole cutters open at the origin and go `depth` mm into the part along `axis`
  (default `"-Z"`, down from a top face). Put the origin **on the face** the hole
  starts from and aim it inward:

  ```python
  part -= Pos(x, y, top_z) * clearance_hole("M3", depth=5)                 # from the top
  part -= Pos(x, y, 0) * nut_trap("M3", axis="+Z")                         # from the bottom
  part -= Pos(x_max, y, z) * clearance_hole("M3", depth=8, axis="-X")      # into the +X face
  part -= Pos(x, y_min, z) * clearance_hole("M4", depth=8, axis="+Y", teardrop=True)
  ```

  Wrong sign = the cutter points out of the part and cuts nothing; check the preview.
  Horizontal holes (±X/±Y): pass `teardrop=True` for anything ≥ 5 mm, it adds a 45° roof
  so the hole prints without support.
- Openings in enclosure walls: `cutout(box, "+X", width, height, z, offset=..., wall=WALL)`.
  Use `to_rim=True` (no height) when the opening can run up through the top edge — the lid
  closes it and no weak sliver is left above it.

## Design rules for FDM (0.4 mm nozzle)

- Walls ≥ 1.2 mm (3 perimeters), structural ≥ 2 mm. Floors/roofs ≥ 1.2 mm.
- Fits: sliding/lid 0.2–0.3 mm gap per side, press fit 0.1 mm, loose 0.4 mm.
  Library hole sizes already include clearance for printing.
- Overhangs ≤ 45° from vertical print without supports. Bridges up to ~10 mm are fine.
  Replace flat ceilings with 45° chamfers; horizontal holes ≥ 5 mm get `teardrop=True`.
- Put the largest flat face on the bed. Bottom edges: use a chamfer (0.5–1 mm), not a
  fillet — fillets on the bed overhang and fight elephant foot.
- Layer lines are the weak direction. Orient so the load runs *along* layers
  (hooks and brackets print on their side).
- Vertical holes are round; horizontal ones come out slightly oval — prefer vertical.
- Text: embossed/engraved ≥ 0.6 mm deep, ≥ 6 mm tall.

## build123d cheat sheet (algebra mode)

```python
from build123d import *
from print3d_kit import on_bed
from print3d_kit.parts import clearance_hole, countersunk_hole, standoff

W, D, H = 40, 20, 8
MIN = (Align.CENTER, Align.CENTER, Align.MIN)        # sits on z=0, centered in XY

body = Box(W, D, H, align=MIN)                        # Box(length_x, width_y, height_z)
body += Pos(0, 0, H) * Cylinder(5, 10, align=MIN)     # stack on top
body -= Pos(-12, 0, H) * countersunk_hole("M3", depth=H)
body = fillet(body.edges().filter_by(Axis.Z), 2)     # round vertical edges
body = chamfer(body.edges().group_by(Axis.Z)[0], 0.6)  # chamfer bottom edges
plate = extrude(RectangleRounded(60, 30, 4), 3)       # 2D sketch on XY -> solid
rib = extrude(Plane.YZ * Polygon((0, 0), (10, 0), (0, 10), align=None), 3)
ring = Cylinder(10, 5, align=MIN) - Cylinder(8, 5, align=MIN)
result = on_bed(body)
```

Gotchas:
- Primitives are **centered by default** on all axes. Pass `align=` to anchor them.
- `Pos(x, y, z) * shape` moves, `Rot(rx, ry, rz) * shape` rotates around the origin
  (degrees). `Pos(...) * Rot(...) * s` = rotate first, then move.
- `Polygon(...)` keeps points where you put them; `Rectangle`, `Circle`,
  `RectangleRounded`, `RegularPolygon` are centered. Pass `align=None` to Polygon
  anyway, older build123d versions centered it.
- Edge selectors: `.edges().filter_by(Axis.Z)` (parallel to Z), `.group_by(Axis.Z)[-1]`
  (topmost group), `.faces().sort_by(Axis.Z)[-1]` (top face).
- Do fillets/chamfers **before** cutting holes through those edges, and keep radius
  smaller than the adjacent wall; failures raise `StdFail_NotDone` — reduce radius
  or select fewer edges.
- Boolean ops on touching-but-not-overlapping faces can leave seams; overlap by 0.01–0.5 mm.
- Inspect: `shape.bounding_box()`, `shape.volume`, `shape.is_valid`.

## Reading the checks

| check | level | what to do |
|---|---|---|
| watertight / winding / volume | error | geometry broken; usually a bad boolean — overlap the solids slightly |
| bed | error | too big for the printer; rotate 90°, split into parts, or scale |
| bodies | warning | disconnected pieces in one part; unintended → make them overlap |
| thin_walls / thin_spot | warning / info | thicken to ≥ 2 × nozzle; the message gives the XYZ of the thinnest spot — a `thin_spot` right under the top face or beside a cutout usually means a sliver you did not intend (e.g. cutout ends 1 mm below the rim: extend it to the rim or raise the wall) |
| overhangs | warning/info | each region comes with a bbox, `flat`/`sloped` and the bridge `span`. Warning = some span > 10 mm (incl. cantilevers: span is 2× the overhang length) or > 50 mm² sloped. Fix the biggest region: rotate, chamfer the ceiling, teardrop the hole, run a cutout `to_rim`, or accept supports |
| bed_contact / tipping | warning | flip to a flat face, or recommend brim |

`report.json` carries the same findings with machine-readable `where` (`at`, `bbox`,
`regions[].span`) — read it instead of parsing the text when you need coordinates.

Other commands: `p3d check file.stl -p prusa-mk4` (check any mesh, also downloaded ones),
`p3d render file.stl --views iso,top` (preview any mesh), `p3d printers`, `p3d parts`.

If `p3d` is not on PATH, run `<repo>/bin/p3d` — it bootstraps its own venv on first use.
