# Backlog: improvements and tests

Written after the first end-to-end test run (see `testing-notes.md`). Items are
ordered by value; each has acceptance criteria. Ground rules for whoever picks
this up:

- Run `.venv/bin/python -m pytest -q` before and after every item; the suite must stay green.
- Keep build123d **algebra mode** (`Box(...) + Pos(...) * ...`), no builder contexts, so the
  skill's cheat sheet keeps matching the library code.
- After touching `validate.py` or `render.py`, rebuild `examples/*.py` and **look at every
  `preview.png`** with the Read tool; refresh `docs/img/*.png` from `examples/out/*/preview.png`.
- Update `skills/print3d/SKILL.md` whenever the user-facing API changes. The skill is the
  product; the Python is plumbing.
- Do not commit unless asked. Stage with `git add -A`.

---

## P1: things that bit during the test — DONE (2026-10-20)

All seven landed; 95 tests (was 20). Deviations from the spec below:

- **#4 span** is measured from the *support edges* (boundary edges whose neighbouring face
  goes down, i.e. the walls the ceiling rests on): span = 2 × the largest distance from a
  ceiling point to its nearest support. The spec's `min(x, y extent)` is the bridge *width*:
  it would have rated the 60 mm HDMI opening in the Pi case as a 2 mm bridge. Side effect:
  cantilevers are caught too (span = 2 × overhang length); that exposed one in the phone
  stand example, now fixed with a 45° notch instead of being accepted in the golden list.
- **#5** runtime: wall check 1.25 s on the Pi box (2.8k faces, 25k mm²); the rest of the
  build time is STL/3MF/STEP export.
- **#7** also covers missing model/mesh files and unreadable meshes.
- Tests are split into `test_fasteners`, `test_enclosures`, `test_validate`, `test_render`,
  `test_cli`; `test_smoke` is the golden-findings suite (every example must have an entry).

### 1. `axis=` on hole cutters, replacing the rotation table

`parts/fasteners.py`: every `*_hole`, `nut_trap`, `heat_insert_hole` gets `axis: str = "-Z"`
(one of `+X -X +Y -Y +Z -Z`): the direction the hole goes *into* the part. The cutter is
returned already rotated, opening at the origin. Implement once in a helper
`_aim(cutter, axis)` and apply at the end of each function.

Then simplify the direction table in `SKILL.md` to one line:
`part -= Pos(x_max, y, z) * clearance_hole("M3", depth=5, axis="-X")`.

Tests (`tests/test_fasteners.py`, new file):
- For each of the six axes, the cutter's bounding box extends from ~0 to `-(depth)` along that
  axis and is symmetric (±d/2) on the other two.
- Plate 20×20×6 with `axis="-Y"` hole placed at `y=10`: volume drops by ≈ π·(3.4/2)²·20 (±5 %).

### 2. `teardrop=True` for horizontal holes

Same file. When `axis` is horizontal and `teardrop=True`, the circular section gets a 45°
roof pointing +Z (after rotation), so the hole prints without support. Profile: circle ∪
triangle whose apex is at `r·√2` above the center. Ignored (or `ValueError`) for vertical axes.

Tests:
- 30×20×12 plate, 8 mm horizontal hole along Y at mid-height: round hole → `overhangs` finding
  present (flat ceiling); teardrop hole → no `overhangs` finding.
- Teardrop volume > round volume for the same size and depth.

### 3. `cutout()` helper for enclosure walls

`parts/enclosures.py`: `cutout(part, face, width, height, z, offset=0.0, to_rim=False)`.
`face` in `+X -X +Y -Y`. Uses `part.bounding_box()` to find the wall, cuts a box through it
(overshoot 1 mm each side), centered on the wall at lateral `offset`, bottom edge at `z`.
`to_rim=True` extends the opening up past the top (what the Pi example does by hand).
Rewrite `examples/rpi4_case.py` to use it.

Tests:
- Each of the four faces removes volume from a `box_with_lid(...)["box"]`.
- With `to_rim=True` the report has **no** `thin_spot`; with `to_rim=False` and
  `height` ending 1 mm below the rim it **has** one. (This is exactly finding #1 in
  `testing-notes.md`; make it a regression test.)

### 4. Smarter overhang level: use the bridge span

`validate.py::_check_overhangs`: for each region, compute `span = min(x-extent, y-extent)`
of its flat part. Message format per region: `... (120 mm2, flat, span 2.0 mm)` or
`(…, sloped)`. Level: `warning` only if some region has `span > 10 mm` or a sloped area
`> 50 mm2`; otherwise `info`. Drop regions under 2 mm² from the listing (tessellation noise),
but keep them in `overhang_area_mm2`.

Tests (`tests/test_validate.py`, move validator tests there from `test_smoke.py`):
- Table with 8 mm bridge → `info`; 30 mm bridge → `warning`; message contains `span 30.0`.
- `examples/rpi4_case.py` box: exactly one `overhangs` warning (the 60 mm HDMI slot ceiling),
  lid: no findings. Golden-findings test for every example: assert the exact set of
  `(check, level)` pairs per part, so validator regressions show up immediately.

### 5. Thin-wall sampling that scales with the part

`validate.py::_check_walls`: `samples = clip(mesh.area / 2, 3000, 25000)`, and additionally
cast from **every face centroid** when `len(faces) < 30000` (tessellation concentrates
triangles at features, which is where slivers live). Keep runtime under ~2 s for the Pi case
(`time p3d build examples/rpi4_case.py --no-render`).

Tests:
- 200×200×30 slab with a 1 mm × 3 mm × 10 mm sliver left beside a cutout at the rim →
  `thin_spot` found with `wall_min_at` within 2 mm of the sliver. (Currently likely missed.)

### 6. Structured locations in `report.json`

`validate.py::Finding` gets `where: dict | None` (`{"at": [x,y,z]}` or
`{"regions": [{"bbox": [[lo],[hi]], "area": …, "span": …}]}`). Messages stay human-readable;
JSON carries the numbers. Needed by the MCP server (P2) so the agent can reason on data,
not parse prose.

Test: `report.to_dict()["findings"][i]["where"]` present for `thin_spot`, `thin_walls`,
`overhangs`; `json.dumps` succeeds (no numpy types leak; cast with `float`).

### 7. Clean error for a bad printer name

`cli.py`: `-p foo` currently prints a raw `ValueError` traceback. Catch it in `main()` (and
any `ValueError` from `_views`), print the message to stderr, return 2.

Tests: `main(["build", example, "-p", "foo"]) == 2`, stderr contains `Unknown printer`,
no `Traceback`. Same for `--views iso,foo` (validate views even with `--no-render`).

---

## P2: next capabilities

### 8. MCP server (the planned next step)

`src/print3d_kit/mcp_server.py` using the `mcp` package (FastMCP), entry point
`p3d-mcp` in `pyproject.toml` (optional dependency group `mcp`). Tools, all thin wrappers over
existing functions:

| tool | input | output |
|---|---|---|
| `build_model` | `code: str` *or* `path: str`, `printer`, `views`, `out_dir` | the `_summary()` dict + preview PNG as an image content block |
| `check_mesh` | `path`, `printer`, `min_wall` | report dict |
| `render_mesh` | `path`, `views` | image block |
| `list_parts` | – | the `p3d parts` text |
| `list_printers` | – | list of presets |

`code` mode writes to a temp file under `out_dir/models/` so the user keeps the source.
Add `.mcp.json` at repo root for the plugin (`"command": "bin/p3d-mcp"` with the same venv
bootstrap as `bin/p3d`). Extend `SKILL.md`: "if the `print3d` MCP tools are available, call
`build_model` instead of the shell".

Tests: in-process call of each tool function (no transport) on `examples/l_bracket.py`;
`build_model` returns `ok: true` and an image block with non-empty PNG bytes.

### 9. Text labels

`parts/text.py::label(text, size=8, depth=0.6, font="sans", emboss=True)` returning a cutter
(engrave) or a solid (emboss) lying on z=0. build123d `Text(...)` + `extrude`. Document the
≥ 0.6 mm depth / ≥ 6 mm height rule next to it.

Test: label volume > 0; engraving a plate reduces volume; `is_valid`.

### 10. GitHub Actions CI

`.github/workflows/test.yml`: ubuntu-latest, Python 3.10–3.13 matrix, `pip install -e .[dev]`,
`pytest -q`. build123d ships Linux wheels, so no system deps. Cache pip.

### 11. `bin/p3d` robustness

Check `python3 -c 'import sys; assert sys.version_info >= (3,10)'` before creating the venv and
print a clear message otherwise. Also create `bin/p3d-mcp` (item 8).

---

## P3: nice to have

- `--size` for `render` / `build` (tile size px, default 520) and a `--views all` shortcut.
- Dimension callouts on the preview (overall X/Y/Z arrows on the iso tile).
- `l_bracket`: raise `ValueError` when `gusset=True` and `holes_per_leg` is odd (a hole would hit
  the rib). Test it.
- `box_with_lid(lid_screws="M3")`: corner posts in the box + countersunk holes in the lid.
- Gridfinity bin generator (`gridfinity_bin(x_units, y_units, z_units)`), base profile per spec.
- Auto-orientation suggestion: try the 6 axis-aligned orientations, report the one with the
  least overhang area and the largest bed contact.
- `[project.urls]` in `pyproject.toml` once the GitHub repo exists.

---

## Test inventory to add (summary)

New files: `tests/test_fasteners.py`, `tests/test_validate.py`, `tests/test_render.py`,
`tests/test_cli.py`, `tests/test_mcp.py` (P2). Move the matching tests out of `test_smoke.py`
and leave it as the examples/golden suite.

`tests/test_render.py` should contain:
- **Hidden-face regression**: box with a through-hole along the view axis, rendered from
  `front`; the pixel at the tile center is background white. Box without hole: not white.
- **Back-face culling**: hollow open box rendered from `top`; center pixel is darker than the
  rim pixel (we see the floor, not the underside).
- `bottom` view of a plate with a nut trap from below shows a non-white hexagon region where
  `top` shows plain surface (compare the same pixel in both tiles).
- Multi-part legend: output width/height match `cols*size` / `rows*size + header`.

`tests/test_cli.py` should contain:
- exit codes 0 / 1 / 2 for ok / check error / crash, missing `result`, 2D result, bad printer,
  bad view.
- `check` on a hand-made non-watertight STL (box with one face deleted via trimesh) → exit 1,
  `watertight` error.
- 3MF round trip: volumes within 1 % of the build123d volumes; part names preserved.
- STEP re-import: `len(import_step(path).solids()) == number of parts`.
- `arrange()`: parts do not overlap in X and all have `z_min == 0`; `on_bed()` centers XY.
