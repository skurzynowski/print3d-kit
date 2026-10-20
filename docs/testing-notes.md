# Test notes: first end-to-end run (2026-10-20)

What was tested: the toolkit used the way the `print3d` skill prescribes, from a
fresh brief (Raspberry Pi 4B case for a Bambu A1 mini), plus a fastener demo
exercising every cutter in the library, plus deliberate misuse of the CLI.

## Found and fixed

| # | Finding | Fix |
|---|---|---|
| 1 | Checks said *that* a wall was 1.0 mm thin, not *where*. The spot was a 1 mm sliver above the USB opening; locating it needed a hand-written script. | `wall_min_at` metric, XYZ in `thin_walls`, new `thin_spot` info below 3 × nozzle. |
| 2 | Overhang warning gave one z-range for all overhangs together, so the real 52 mm bridge was indistinguishable from harmless 2 mm port-ceiling lips. | Overhanging faces clustered into connected regions, each reported as a box with its area, largest first. |
| 3 | `result = Rectangle(10, 10)` (a 2D sketch) exported an empty STL and "failed" only via a watertight error. | Rejected up front with exit 2 and a hint to extrude. |
| 4 | `p3d check file.3mf` named parts `1` and `3`; trimesh drops the 3MF `partnumber`. | Names read back from the 3MF XML. |
| 5 | 45° chamfers on rounded corners tessellate to 45.0x° and were flagged as overhangs (fillet at the bed correctly still is). | 1° slack on the threshold; regression test. |
| 6 | Skill said "for side holes rotate first: `Rot(90, 0, 0)`" without saying where the cutter then points. Using it on a +Y face cut air outside the part; nothing happened and nothing warned. | Table of the six directions in the skill, plus "look for the hole in the preview". |
| 7 | `trimesh.split()` repairs sub-meshes (fills holes), inflating region areas 10×. | Connected components computed on face indices with `repair=False`. |

## Verified working

- Exit codes: 0 ok / 1 check error / 2 script crashed, missing `result`, non-solid result. Bad printer name → exit 1 with the list of presets.
- Custom bed `50x50x50` → `bed` error for both parts.
- 3MF: `unit="millimeter"`, both parts carry `partnumber`; STEP re-imports as a 2-solid compound with the right volumes.
- Renderer: hidden faces never bleed through (z-buffer + back-face culling); bottom/left/back-iso views show the hidden sides; side hole visible after the orientation fix.
- Library cutters all cut as intended (countersunk, counterbore, clearance + nut trap from below, heat-set insert, standoff, side hole). Horizontal hole correctly shows up as a 20 mm bridge region.

## Still open

- Horizontal holes should get a teardrop option.
- `box_with_lid` lid vents and port openings are done by hand in the example; a `cutout()` helper that takes a face name (`"+X"`) and a rectangle would remove the rotation table from the user's path entirely.
- Thin-wall sampling is 3000 rays; a 1 mm sliver 2 mm wide can be missed on big parts. Raise samples with part area, or sample edges preferentially.
