"""Convert build123d shapes to trimesh meshes."""

import numpy as np
import trimesh
from build123d import Shape


def to_trimesh(shape: Shape, tolerance: float = 0.05, angular_tolerance: float = 0.2) -> trimesh.Trimesh:
    """Tessellate a shape into a clean, closed mesh.

    OpenCascade emits a zero-area triangle where a face collapses to a point (the tip
    of a cone, the pole of a sphere). It leaves a one-edge hole that makes the mesh
    non-watertight; dropping it closes the surface.
    """
    vertices, triangles = shape.tessellate(tolerance, angular_tolerance)
    verts = np.array([(v.X, v.Y, v.Z) for v in vertices], dtype=float)
    faces = np.array(triangles, dtype=np.int64)
    mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=True)
    mesh.update_faces(mesh.nondegenerate_faces(height=1e-9))
    mesh.merge_vertices()
    mesh.remove_unreferenced_vertices()
    return mesh
