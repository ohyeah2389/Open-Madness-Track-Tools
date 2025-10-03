"""Geometric calculations for MEB mesh export.

Primarily handles bounding sphere and bounding box calculations.
Uses Ritter's algorithm for fast bounding sphere approximation.
"""

import numpy as np
from typing import Tuple, List


class BoundingInfo:
    """Container for mesh bounding information."""
    
    def __init__(
        self,
        sphere_center: np.ndarray,
        sphere_radius: float,
        bb_min: np.ndarray,
        bb_max: np.ndarray
    ):
        self.sphere_center = sphere_center
        self.sphere_radius = sphere_radius
        self.bb_min = bb_min
        self.bb_max = bb_max
    
    def to_bytes(self) -> bytes:
        """Convert bounding info to 40-byte binary representation.
        
        Format: center(3 floats), radius(1 float), min(3 floats), max(3 floats)
        Total: 10 floats = 40 bytes
        """
        data = np.array([
            self.sphere_center[0],
            self.sphere_center[1],
            self.sphere_center[2],
            self.sphere_radius,
            self.bb_min[0],
            self.bb_min[1],
            self.bb_min[2],
            self.bb_max[0],
            self.bb_max[1],
            self.bb_max[2],
        ], dtype=np.float32)
        return data.tobytes()


def calculate_bounding_sphere_ritter(vertices: np.ndarray) -> Tuple[np.ndarray, float]:
    """Calculate bounding sphere using Ritter's algorithm.
    
    This is a fast approximation that gives good (but not always minimal) bounding spheres.
    
    Args:
        vertices: Nx3 array of vertex positions
    
    Returns:
        Tuple of (center, radius)
    """
    if len(vertices) == 0:
        return np.array([0.0, 0.0, 0.0]), 0.0
    
    if len(vertices) == 1:
        return vertices[0].copy(), 0.0
    
    # Find the pair of points with maximum distance
    # For large meshes, approximate by checking a subset
    if len(vertices) > 1000:
        # Sample random points for initial sphere
        indices = np.random.choice(len(vertices), size=min(1000, len(vertices)), replace=False)
        sample_verts = vertices[indices]
    else:
        sample_verts = vertices
    
    # Find most distant pair in sample
    dists = np.linalg.norm(sample_verts[:, None] - sample_verts[None, :], axis=2)
    max_idx = np.unravel_index(np.argmax(dists), dists.shape)
    p1 = sample_verts[max_idx[0]]
    p2 = sample_verts[max_idx[1]]
    
    # Initial sphere from two most distant points
    center = (p1 + p2) / 2.0
    radius = np.linalg.norm(p1 - p2) / 2.0
    
    # Ritter's algorithm: iteratively expand sphere to include all points
    max_iterations = 10
    for iteration in range(max_iterations):
        sphere_changed = False
        
        for vertex in vertices:
            dist = np.linalg.norm(vertex - center)
            
            if dist > radius + 1e-12:  # Point outside sphere
                # Expand sphere to include this point
                new_radius = (radius + dist) / 2.0
                ratio = (new_radius - radius) / dist
                
                # Move center toward the new point
                center = center + ratio * (vertex - center)
                radius = new_radius
                sphere_changed = True
        
        if not sphere_changed:
            break
    
    # Final verification and adjustment
    max_outside_dist = 0.0
    for vertex in vertices:
        dist = np.linalg.norm(vertex - center)
        if dist > radius:
            max_outside_dist = max(max_outside_dist, dist - radius)
    
    # Add safety margin to ensure all points are contained
    radius += max_outside_dist + 1e-10
    
    # Additional refinement
    center, radius = refine_bounding_sphere(vertices, center, radius)
    
    return center, float(radius)


def refine_bounding_sphere(
    vertices: np.ndarray,
    center: np.ndarray,
    radius: float
) -> Tuple[np.ndarray, float]:
    """Refine bounding sphere by adjusting center position.
    
    Attempts to optimize by moving the center toward boundary points.
    
    Args:
        vertices: Nx3 array of vertex positions
        center: Current sphere center
        radius: Current sphere radius
    
    Returns:
        Tuple of (refined_center, refined_radius)
    """
    # Find points near the boundary (within 90% of radius)
    distances = np.linalg.norm(vertices - center, axis=1)
    boundary_threshold = radius * 0.9
    boundary_mask = distances >= boundary_threshold
    boundary_points = vertices[boundary_mask]
    
    if len(boundary_points) >= 3:
        # Compute centroid of boundary points
        new_center = np.mean(boundary_points, axis=0)
        
        # Check if new center gives better sphere
        new_distances = np.linalg.norm(vertices - new_center, axis=1)
        new_radius = np.max(new_distances)
        
        # Use new sphere if it's not significantly worse (allow 5% increase)
        if new_radius < radius * 1.05:
            center = new_center
            radius = new_radius + 1e-10
    
    return center, radius


def verify_sphere_containment(
    vertices: np.ndarray,
    center: np.ndarray,
    radius: float,
    epsilon: float = 1e-10
) -> Tuple[bool, int, float]:
    """Verify that all vertices are contained within the bounding sphere.
    
    Args:
        vertices: Nx3 array of vertex positions
        center: Sphere center
        radius: Sphere radius
        epsilon: Tolerance for floating point comparison
    
    Returns:
        Tuple of (all_contained, outlier_count, max_outside_distance)
    """
    distances = np.linalg.norm(vertices - center, axis=1)
    outlier_mask = distances > (radius + epsilon)
    outlier_count = np.sum(outlier_mask)
    
    if outlier_count > 0:
        max_outside_dist = np.max(distances[outlier_mask] - radius)
    else:
        max_outside_dist = 0.0
    
    all_contained = outlier_count == 0
    return all_contained, int(outlier_count), float(max_outside_dist)


def calculate_bounds_from_vertices(
    vertices: np.ndarray,
    flip_coordinates: bool = False
) -> BoundingInfo:
    """Calculate complete bounding information from vertices.
    
    Args:
        vertices: Nx3 array of vertex positions (already in correct coordinate system)
        flip_coordinates: If True, coordinates are XYZ; if False, swap Y and Z
    
    Returns:
        BoundingInfo object with sphere and AABB data
    """
    if len(vertices) == 0:
        return BoundingInfo(
            sphere_center=np.array([0.0, 0.0, 0.0]),
            sphere_radius=0.0,
            bb_min=np.array([0.0, 0.0, 0.0]),
            bb_max=np.array([0.0, 0.0, 0.0])
        )
    
    # Apply coordinate transform if needed
    if flip_coordinates:
        # Use vertices as-is (XYZ)
        coords = vertices.copy()
    else:
        # Swap Y and Z (XYZ -> XZY)
        coords = vertices[:, [0, 2, 1]].copy()
    
    # Calculate bounding sphere
    sphere_center, sphere_radius = calculate_bounding_sphere_ritter(coords)
    
    # Calculate axis-aligned bounding box
    bb_min = np.min(coords, axis=0)
    bb_max = np.max(coords, axis=0)
    
    # Verify sphere containment
    all_contained, outlier_count, max_outside = verify_sphere_containment(
        coords, sphere_center, sphere_radius
    )
    
    if not all_contained:
        print(f"WARNING: Bounding sphere verification failed!")
        print(f"  {outlier_count}/{len(vertices)} points outside sphere")
        print(f"  Max outside distance: {max_outside:.6f}")
        print(f"  Sphere radius: {sphere_radius:.6f}")
    
    return BoundingInfo(
        sphere_center=sphere_center,
        sphere_radius=sphere_radius,
        bb_min=bb_min,
        bb_max=bb_max
    )


def calculate_material_bounds(
    vertices_by_material: List[np.ndarray],
    flip_coordinates: bool = False
) -> List[BoundingInfo]:
    """Calculate bounding information for each material group.
    
    Args:
        vertices_by_material: List of Nx3 vertex arrays, one per material
        flip_coordinates: Coordinate system flag
    
    Returns:
        List of BoundingInfo objects, one per material
    """
    bounds_list = []
    
    for mat_vertices in vertices_by_material:
        bounds = calculate_bounds_from_vertices(mat_vertices, flip_coordinates)
        bounds_list.append(bounds)
    
    return bounds_list
