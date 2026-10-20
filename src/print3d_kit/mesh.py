"""Convert build123d shapes to trimesh meshes."""

import numpy as np
import trimesh
from build123d import Shape


def to_trimesh(shape: Shape, tolerance: float = 0.05, angular_tolerance: float = 0.2) -> trimesh.Trimesh:
    vertices, triangles = shape.tessellate(tolerance, angular_tolerance)
    verts = np.array([(v.X, v.Y, v.Z) for v in vertices], dtype=float)
    faces = np.array(triangles, dtype=np.int64)
    mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=True)
    mesh.merge_vertices()
    return mesh
