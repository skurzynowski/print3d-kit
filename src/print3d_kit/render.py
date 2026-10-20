"""Headless multi-view PNG preview, so Claude can look at what it modeled.

A small numpy z-buffer rasterizer (orthographic, flat shading, outlined sharp
edges). No OpenGL or display needed, and unlike matplotlib's 3D painter's
algorithm it never draws hidden faces on top of visible ones.
"""

from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont

# name: (elevation, azimuth) in degrees; azimuth 0 looks from +X toward the origin.
VIEWS = {
    "iso": (30, -55),
    "front": (0, -90),
    "right": (0, 0),
    "top": (90, -90),
    "back-iso": (30, 125),
    "bottom": (-90, -90),
    "left": (0, 180),
    "back": (0, 90),
}
DEFAULT_VIEWS = ("iso", "front", "right", "top")
PALETTE = ["#e8735a", "#4f8fc0", "#7fb069", "#d4a72c", "#9b6fb5", "#5bb5a8"]
BACKGROUND = (255, 255, 255)
EDGE = (40, 40, 40)
AXIS_COLORS = {"X": (210, 50, 50), "Y": (50, 160, 50), "Z": (50, 70, 210)}


def render_preview(
    meshes: dict[str, trimesh.Trimesh],
    path: Path,
    views=DEFAULT_VIEWS,
    title: str = "",
    size: int = 520,
) -> Path:
    all_bounds = np.vstack([m.bounds for m in meshes.values()])
    lo, hi = all_bounds.min(axis=0), all_bounds.max(axis=0)
    dims = hi - lo

    tiles = [_render_view(meshes, view, lo, hi, size) for view in views]
    cols = 2 if len(tiles) > 1 else 1
    rows = int(np.ceil(len(tiles) / cols))
    header = 36
    sheet = Image.new("RGB", (cols * size, rows * size + header), BACKGROUND)
    for i, tile in enumerate(tiles):
        sheet.paste(tile, ((i % cols) * size, header + (i // cols) * size))

    draw = ImageDraw.Draw(sheet)
    font = _font(16)
    draw.text((12, 9), f"{title}   {dims[0]:.1f} x {dims[1]:.1f} x {dims[2]:.1f} mm", fill=(20, 20, 20), font=font)
    if len(meshes) > 1:
        x = sheet.width - 12
        for j, name in reversed(list(enumerate(meshes))):
            fill = _rgb(PALETTE[j % len(PALETTE)])
            x -= int(draw.textlength(name, font=font))
            draw.text((x, 9), name, fill=fill, font=font)
            draw.rectangle((x - 16, 13, x - 6, 23), fill=fill)
            x -= 30

    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)
    return path


def _render_view(meshes, view: str, lo: np.ndarray, hi: np.ndarray, size: int) -> Image.Image:
    elev, azim = np.radians(VIEWS[view])
    # Camera basis: d points from the camera toward the scene.
    eye = np.array([np.cos(elev) * np.cos(azim), np.cos(elev) * np.sin(azim), np.sin(elev)])
    d = -eye
    up_hint = np.array([0.0, 1.0, 0.0]) if abs(eye[2]) > 0.99 and eye[2] > 0 else np.array([0.0, 0.0, 1.0])
    if abs(eye[2]) > 0.99 and eye[2] < 0:
        up_hint = np.array([0.0, -1.0, 0.0])
    right = np.cross(d, up_hint)
    right /= np.linalg.norm(right)
    up = np.cross(right, d)

    center = (lo + hi) / 2
    corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    extent = max(np.ptp((corners - center) @ right), np.ptp((corners - center) @ up)) or 1.0
    margin = 0.12
    scale = size * (1 - 2 * margin) / extent

    def project(pts):
        rel = pts - center
        return np.stack([size / 2 + rel @ right * scale, size / 2 - rel @ up * scale, rel @ d], axis=-1)

    color = np.full((size, size, 3), BACKGROUND, dtype=float)
    depth = np.full((size, size), np.inf)
    ids = np.full((size, size), -1, dtype=np.int64)
    light = _normalize(-d * 0.6 + up * 0.5 + right * 0.3)

    offset = 0
    for j, mesh in enumerate(meshes.values()):
        base = np.array(_rgb(PALETTE[j % len(PALETTE)]), dtype=float)
        normals = mesh.face_normals
        shade = 0.35 + 0.65 * np.clip(normals @ light, 0, 1)
        # Back-face culling: on a closed mesh, faces turned away (or edge-on) are never visible.
        front = np.nonzero(normals @ eye > 1e-3)[0]
        tri = project(mesh.triangles[front])
        _rasterize(tri, (base[None, :] * shade[:, None])[front], offset + front, color, depth, ids)
        offset += len(mesh.faces)

    _outline(color, depth, ids, meshes, jump=0.02 * float(np.linalg.norm(hi - lo)))
    img = Image.fromarray(np.clip(color, 0, 255).astype(np.uint8))
    draw = ImageDraw.Draw(img)
    draw.text((10, 8), view, fill=(110, 110, 110), font=_font(15))
    _gizmo(draw, right, up, size)
    return img


def _rasterize(tri, face_colors, face_ids, color, depth, ids) -> None:
    size = depth.shape[0]
    for k in range(len(tri)):
        (x0, y0, z0), (x1, y1, z1), (x2, y2, z2) = tri[k]
        area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
        if abs(area) < 1e-9:
            continue
        xmin = max(int(np.floor(min(x0, x1, x2))), 0)
        xmax = min(int(np.ceil(max(x0, x1, x2))), size - 1)
        ymin = max(int(np.floor(min(y0, y1, y2))), 0)
        ymax = min(int(np.ceil(max(y0, y1, y2))), size - 1)
        if xmin > xmax or ymin > ymax:
            continue
        px, py = np.meshgrid(np.arange(xmin, xmax + 1) + 0.5, np.arange(ymin, ymax + 1) + 0.5)
        w0 = ((x1 - px) * (y2 - py) - (x2 - px) * (y1 - py)) / area
        w1 = ((x2 - px) * (y0 - py) - (x0 - px) * (y2 - py)) / area
        w2 = 1 - w0 - w1
        inside = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        if not inside.any():
            continue
        z = w0 * z0 + w1 * z1 + w2 * z2
        region = depth[ymin : ymax + 1, xmin : xmax + 1]
        closer = inside & (z < region)
        region[closer] = z[closer]
        color[ymin : ymax + 1, xmin : xmax + 1][closer] = face_colors[k]
        ids[ymin : ymax + 1, xmin : xmax + 1][closer] = face_ids[k]


def _outline(color, depth, ids, meshes, jump: float) -> None:
    """Darken pixels on silhouettes, depth jumps (> ``jump`` mm) and sharp creases."""
    normals = np.vstack([m.face_normals for m in meshes.values()])
    normal_img = np.zeros(depth.shape + (3,))
    hit = ids >= 0
    normal_img[hit] = normals[ids[hit]]
    depth = np.where(hit, depth, 0.0)

    edge = np.zeros(depth.shape, dtype=bool)
    for dy, dx in ((0, 1), (1, 0)):
        a = (slice(0, depth.shape[0] - dy), slice(0, depth.shape[1] - dx))
        b = (slice(dy, None), slice(dx, None))
        bg_change = hit[a] != hit[b]
        both = hit[a] & hit[b]
        depth_jump = both & (np.abs(depth[a] - depth[b]) > jump)
        crease = both & ((normal_img[a] * normal_img[b]).sum(-1) < np.cos(np.radians(30)))
        e = bg_change | depth_jump | crease
        edge[a] |= e
        edge[b] |= e
    color[edge] = EDGE


def _gizmo(draw: ImageDraw.ImageDraw, right, up, size: int) -> None:
    origin = np.array([38.0, size - 38.0])
    for axis, vec in (("X", (1, 0, 0)), ("Y", (0, 1, 0)), ("Z", (0, 0, 1))):
        v = np.array([np.dot(vec, right), -np.dot(vec, up)]) * 24
        if np.linalg.norm(v) < 3:
            # Axis points at the viewer or away from it.
            draw.text(tuple(origin + [-4, -8]), axis, fill=AXIS_COLORS[axis], font=_font(13))
            continue
        end = origin + v
        draw.line([tuple(origin), tuple(end)], fill=AXIS_COLORS[axis], width=2)
        draw.text(tuple(end + v / np.linalg.norm(v) * 8 - [4, 8]), axis, fill=AXIS_COLORS[axis], font=_font(13))


def _font(px: int):
    try:
        return ImageFont.load_default(size=px)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def _rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def _normalize(v: np.ndarray) -> np.ndarray:
    return v / np.linalg.norm(v)
