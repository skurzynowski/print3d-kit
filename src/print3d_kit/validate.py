"""Printability checks on a triangle mesh.

Each check adds a Finding with a level: ``error`` (will not print / not a valid
solid), ``warning`` (likely to print badly) or ``info`` (worth knowing).
"""

from dataclasses import asdict, dataclass, field

import numpy as np
import trimesh

from .printers import Printer

PLA_DENSITY = 1.24  # g/cm3
BED_EPS = 0.05  # mm, faces this close to z_min count as touching the bed
FLAT = 0.99  # -normal.z above this: a horizontal ceiling (bridge), not a slope
MAX_BRIDGE = 10.0  # mm a typical FDM printer bridges cleanly
MAX_SLOPED_OVERHANG = 50.0  # mm2 of sloped overhang before it is worth a warning
MIN_REGION = 2.0  # mm2, smaller overhang patches are tessellation noise and not listed


@dataclass
class Finding:
    level: str  # error | warning | info
    check: str
    message: str
    where: dict | None = None  # machine-readable location: {"at": [x,y,z]} or {"regions": [...]}


@dataclass
class Report:
    name: str
    dimensions: tuple[float, float, float]
    volume_mm3: float
    mass_g_solid: float
    triangles: int
    findings: list[Finding] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not any(f.level == "error" for f in self.findings)

    def add(self, level: str, check: str, message: str, where: dict | None = None) -> None:
        self.findings.append(Finding(level, check, message, where))

    def to_dict(self) -> dict:
        d = asdict(self)
        d["ok"] = self.ok
        return d


def check_mesh(
    mesh: trimesh.Trimesh,
    name: str,
    printer: Printer,
    min_wall: float | None = None,
    overhang_deg: float = 45.0,
    samples: int | None = None,
) -> Report:
    min_wall = printer.min_wall if min_wall is None else min_wall
    extents = tuple(float(v) for v in mesh.extents)
    volume = float(mesh.volume) if mesh.is_volume else float("nan")
    report = Report(
        name=name,
        dimensions=tuple(round(v, 2) for v in extents),
        volume_mm3=round(volume, 1),
        mass_g_solid=round(volume / 1000 * PLA_DENSITY, 1),
        triangles=len(mesh.faces),
    )

    _check_solid(mesh, report)
    _check_bed(mesh, report, printer)
    if mesh.is_watertight:
        _check_walls(mesh, report, min_wall, 3 * printer.nozzle, samples)
    _check_overhangs(mesh, report, overhang_deg)
    _check_contact(mesh, report)
    return report


def _check_solid(mesh: trimesh.Trimesh, report: Report) -> None:
    if not mesh.is_watertight:
        report.add("error", "watertight", "Mesh has holes (not watertight); slicers may fail or print garbage.")
    if not mesh.is_winding_consistent:
        report.add("error", "winding", "Inconsistent face winding; normals point in mixed directions.")
    if mesh.is_watertight and mesh.volume <= 0:
        report.add("error", "volume", "Volume is not positive; the solid is inside out or empty.")
    bodies = mesh.split(only_watertight=False)
    if len(bodies) > 1:
        report.add(
            "warning",
            "bodies",
            f"{len(bodies)} disconnected bodies in one part. Intended? If not, they do not touch or overlap.",
        )


def _check_bed(mesh: trimesh.Trimesh, report: Report, printer: Printer) -> None:
    lo, _ = mesh.bounds
    dims = mesh.extents
    bed = printer.bed
    over = [f"{axis} {d:.1f} > {b:.0f}" for axis, d, b in zip("XYZ", dims, bed) if d > b]
    if over:
        # A part that is too long in X/Y may still fit diagonally or rotated 90 degrees.
        fits_rotated = dims[2] <= bed[2] and dims[1] <= bed[0] and dims[0] <= bed[1]
        hint = " It fits if rotated 90 degrees around Z." if fits_rotated else ""
        report.add("error", "bed", f"Does not fit {printer.name} build volume {bed}: {', '.join(over)}.{hint}")
    if abs(lo[2]) > 0.01:
        report.add("info", "z_min", f"Lowest point is at z={lo[2]:.2f}, not 0. Slicers drop it to the bed anyway.")


def _check_walls(mesh: trimesh.Trimesh, report: Report, min_wall: float, weak_wall: float, samples: int | None) -> None:
    """Estimate local wall thickness by casting rays inward from the surface.

    Rays start from random surface samples (density scales with area) and from every
    triangle centroid: CAD tessellation packs small triangles around features, which is
    exactly where slivers left by cutouts live.
    """
    if samples is None:
        samples = int(np.clip(mesh.area / 2, 3000, 25000))
    points, face_idx = trimesh.sample.sample_surface(mesh, samples, seed=0)
    if len(mesh.faces) < 30000:
        points = np.vstack([points, mesh.triangles_center])
        face_idx = np.concatenate([face_idx, np.arange(len(mesh.faces))])
    normals = mesh.face_normals[face_idx]
    origins = points - normals * 1e-4
    hits, ray_idx, _ = mesh.ray.intersects_location(origins, -normals, multiple_hits=False)
    if len(ray_idx) == 0:
        return
    thickness = np.linalg.norm(hits - origins[ray_idx], axis=1)
    where = origins[ray_idx]
    # Weight by surface area so the dense centroid rays do not skew the share.
    weights = np.concatenate(
        [np.full(samples, mesh.area / samples), mesh.area_faces if len(face_idx) > samples else []]
    )[ray_idx]
    thin = thickness < min_wall
    thinnest = int(np.argmin(thickness))
    at = _xyz(where[thinnest])
    report.metrics["wall_min_mm"] = round(float(thickness[thinnest]), 2)
    report.metrics["wall_min_at"] = at
    report.metrics["wall_p5_mm"] = round(float(np.percentile(thickness[:samples], 5)), 2)
    share = float(weights[thin].sum() / weights.sum())
    if share > 0.01:
        report.add(
            "warning",
            "thin_walls",
            f"{share:.0%} of the surface sits on walls thinner than {min_wall} mm "
            f"(thinnest ~{thickness[thinnest]:.2f} mm at {_pt(at)}; thin region spans {_box(where[thin])}). "
            "Thicken them or they may not print.",
            {"at": at, "bbox": _bbox(where[thin]), "thickness": round(float(thickness[thinnest]), 2)},
        )
    elif thickness[thinnest] < weak_wall:
        report.add(
            "info",
            "thin_spot",
            f"Thinnest spot is {thickness[thinnest]:.2f} mm at {_pt(at)}, under {weak_wall:.1f} mm (3 perimeters). "
            "Prints, but is weak; often a sliver left between a cutout and an edge. Check whether it is intended.",
            {"at": at, "thickness": round(float(thickness[thinnest]), 2)},
        )


def _check_overhangs(mesh: trimesh.Trimesh, report: Report, overhang_deg: float) -> None:
    z_min = mesh.bounds[0][2]
    normals = mesh.face_normals
    # A face tilted t degrees from vertical has -nz = sin(t). One degree of slack keeps
    # tessellated 45 degree chamfers out of the report.
    down = -normals[:, 2] > np.sin(np.radians(overhang_deg + 1.0))
    on_bed = mesh.triangles[:, :, 2].max(axis=1) <= z_min + BED_EPS
    overhang = down & ~on_bed
    area = float(mesh.area_faces[overhang].sum())
    report.metrics["overhang_area_mm2"] = round(area, 1)
    if area <= 1.0:
        return

    regions = _overhang_regions(mesh, overhang)
    sloped_area = sum(r["area"] - r["flat_area"] for r in regions)
    longest = max((r["span"] for r in regions if r["span"] is not None), default=0.0)
    level = "warning" if longest > MAX_BRIDGE or sloped_area > MAX_SLOPED_OVERHANG else "info"
    listed = [r for r in regions if r["area"] >= MIN_REGION]
    shown = "; ".join(_describe(r) for r in listed[:4])
    if len(listed) > 4:
        shown += f"; +{len(listed) - 4} smaller"
    flat_area = sum(r["flat_area"] for r in regions)
    report.add(
        level,
        "overhangs",
        f"{area:.0f} mm2 of downward faces steeper than {overhang_deg:.0f} deg from vertical "
        f"({flat_area:.0f} mm2 flat ceilings/bridges, {sloped_area:.0f} mm2 sloped). Regions: {shown or 'tiny only'}. "
        f"Bridges up to {MAX_BRIDGE:.0f} mm print fine; otherwise rotate the part, chamfer the ceiling, "
        "use a teardrop hole, or enable supports.",
        {"regions": [{k: v for k, v in r.items() if k != "flat_area"} | {"kind": _kind(r)} for r in listed]},
    )


def _overhang_regions(mesh: trimesh.Trimesh, mask: np.ndarray) -> list[dict]:
    """Group flagged faces into connected regions, largest first, with bridge span."""
    idx = np.nonzero(mask)[0]
    adj = mesh.face_adjacency
    both = mask[adj[:, 0]] & mask[adj[:, 1]]
    components = trimesh.graph.connected_components(adj[both], nodes=idx)
    regions = []
    for comp in components:
        comp = np.asarray(comp)
        area = float(mesh.area_faces[comp].sum())
        flat = comp[-mesh.face_normals[comp, 2] > FLAT]
        flat_area = float(mesh.area_faces[flat].sum())
        regions.append(
            {
                "bbox": _bbox(mesh.triangles[comp].reshape(-1, 3)),
                "area": round(area, 1),
                "flat_area": round(flat_area, 1),
                "span": _bridge_span(mesh, flat) if flat_area > 0 else None,
            }
        )
    return sorted(regions, key=lambda r: -r["area"])


def _bridge_span(mesh: trimesh.Trimesh, faces: np.ndarray) -> float:
    """Longest distance a flat ceiling has to bridge, in mm.

    Boundary edges whose neighbouring face goes *down* from the ceiling (a wall it rests
    on) are supports. Every point of the ceiling is half a bridge away from its nearest
    support, so the span is twice the largest such distance. No supports at all means
    the ceiling floats: the span is its whole diagonal.
    """
    in_region = np.zeros(len(mesh.faces), dtype=bool)
    in_region[faces] = True
    adj, edges = mesh.face_adjacency, mesh.face_adjacency_edges
    crossing = in_region[adj[:, 0]] ^ in_region[adj[:, 1]]
    outside = np.where(in_region[adj[crossing, 0]], adj[crossing, 1], adj[crossing, 0])
    edge_z = mesh.vertices[edges[crossing]][:, :, 2].mean(axis=1)
    goes_down = mesh.triangles_center[outside, 2] < edge_z - 1e-3
    supports = mesh.vertices[edges[crossing][goes_down]][:, :, :2]  # (n, 2 ends, xy)

    region = mesh.submesh([faces], append=True, repair=False)
    n = int(np.clip(region.area * 2, 200, 4000))
    pts = np.vstack([trimesh.sample.sample_surface(region, n, seed=0)[0], region.vertices])[:, :2]
    if len(supports) == 0:
        lo, hi = pts.min(axis=0), pts.max(axis=0)
        return round(float(np.linalg.norm(hi - lo)), 1)
    a, b = supports[:, 0], supports[:, 1]
    ab = b - a
    t = np.clip(((pts[:, None] - a[None]) * ab[None]).sum(-1) / np.maximum((ab**2).sum(-1), 1e-12)[None], 0, 1)
    nearest = a[None] + t[..., None] * ab[None]
    dist = np.linalg.norm(pts[:, None] - nearest, axis=-1).min(axis=1)
    return round(float(2 * dist.max()), 1)


def _kind(region: dict) -> str:
    return "flat" if region["flat_area"] >= region["area"] / 2 else "sloped"


def _describe(region: dict) -> str:
    lo, hi = region["bbox"]
    box = f"x {lo[0]:.1f}..{hi[0]:.1f}, y {lo[1]:.1f}..{hi[1]:.1f}, z {lo[2]:.1f}..{hi[2]:.1f}"
    span = f", span {region['span']:.1f} mm" if region["span"] is not None else ""
    return f"{box} ({region['area']:.0f} mm2, {_kind(region)}{span})"


def _xyz(p: np.ndarray) -> list[float]:
    return [round(float(v), 2) for v in p]


def _bbox(pts: np.ndarray) -> list[list[float]]:
    return [_xyz(pts.min(axis=0)), _xyz(pts.max(axis=0))]


def _pt(p) -> str:
    return f"({p[0]:.1f}, {p[1]:.1f}, {p[2]:.1f})"


def _box(pts: np.ndarray) -> str:
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    return f"x {lo[0]:.1f}..{hi[0]:.1f}, y {lo[1]:.1f}..{hi[1]:.1f}, z {lo[2]:.1f}..{hi[2]:.1f}"


def _check_contact(mesh: trimesh.Trimesh, report: Report) -> None:
    z_min = mesh.bounds[0][2]
    on_bed = (mesh.triangles[:, :, 2].max(axis=1) <= z_min + BED_EPS) & (mesh.face_normals[:, 2] < -0.99)
    contact = float(mesh.area_faces[on_bed].sum())
    report.metrics["bed_contact_mm2"] = round(contact, 1)
    dx, dy, dz = mesh.extents
    if contact < 20:
        report.add("warning", "bed_contact", f"Only {contact:.0f} mm2 touches the bed; poor adhesion. Put a flat face down.")
    elif dz > 4 * min(dx, dy) and dz > 40:
        report.add("warning", "tipping", f"Tall and narrow ({dz:.0f} mm high on {min(dx, dy):.0f} mm). Consider a brim.")
