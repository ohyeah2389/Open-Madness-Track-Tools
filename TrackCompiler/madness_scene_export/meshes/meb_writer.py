"""Core MEB file writer.

Writes mesh data to binary MEB format used by Automobilista 2.
"""

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from . import meb_format


@dataclass
class BoundingInfo:
    """Container for mesh bounding information."""

    sphere_center: np.ndarray
    sphere_radius: float
    bb_min: np.ndarray
    bb_max: np.ndarray

    def to_bytes(self) -> bytes:
        """Convert bounding info to 40-byte binary representation."""
        data = np.array(
            [
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
            ],
            dtype=np.float32,
        )
        return data.tobytes()


def _calculate_bounds(vertices: np.ndarray, flip_coordinates: bool) -> BoundingInfo:
    if len(vertices) == 0:
        zero = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        return BoundingInfo(
            sphere_center=zero.copy(),
            sphere_radius=0.0,
            bb_min=zero.copy(),
            bb_max=zero.copy(),
        )

    coords = np.asarray(vertices, dtype=np.float32)
    if not flip_coordinates:
        coords = coords[:, [0, 2, 1]]

    bb_min = coords.min(axis=0)
    bb_max = coords.max(axis=0)
    center = (bb_min + bb_max) * 0.5
    radius = float(np.linalg.norm(bb_max - center))

    return BoundingInfo(
        sphere_center=center,
        sphere_radius=radius,
        bb_min=bb_min,
        bb_max=bb_max,
    )


class MEBWriter:
    """Writer for MEB mesh files."""
    
    def __init__(self, filepath: Path):
        """Initialize MEB writer.
        
        Args:
            filepath: Output path for the MEB file
        """
        self.filepath = filepath
        self.data = bytearray()
    
    def write_header(self):
        """Write file header (8 bytes)."""
        self.data.extend(meb_format.HEADER)
    
    def write_mesh_name(self, name: str):
        """Write mesh name string, padded to 4-byte boundary.
        
        Args:
            name: Mesh name (will be converted to uppercase ASCII)
        """
        name_upper = name.upper()
        name_bytes = name_upper.encode('ascii', errors='replace')
        
        # Pad to 4-byte boundary
        padding_needed = (4 - len(name_bytes) % 4) % 4
        name_bytes += b'\x00' * padding_needed
        
        # Ensure null termination (add 4 more bytes if not already ending in null)
        if name_bytes[-1] != 0:
            name_bytes += b'\x00' * 4
        
        self.data.extend(name_bytes)
    
    def write_int32(self, value: int):
        """Write a 32-bit integer."""
        self.data.extend(struct.pack('<i', value))
    
    def write_uint32(self, value: int):
        """Write an unsigned 32-bit integer."""
        self.data.extend(struct.pack('<I', value))
    
    def write_uint16(self, value: int):
        """Write an unsigned 16-bit integer."""
        self.data.extend(struct.pack('<H', value))
    
    def write_float(self, value: float):
        """Write a 32-bit float."""
        self.data.extend(struct.pack('<f', value))
    
    def write_vertex_count(self, count: int):
        """Write vertex count (4 bytes)."""
        self.write_int32(count)
    
    def write_vertex_params_count(self, params_count: int):
        """Write vertex parameter count (4 bytes).
        
        Base parameters are: positions(1) + colors(1) + normals(1) = 3
        Additional params include: UVs, tangents, bitangents, bodywork, etc.
        
        Args:
            params_count: Number of additional parameters beyond the base 3
        """
        self.write_int32(3 + params_count)
    
    def write_material_count(self, count: int, disable_materials: bool = False):
        """Write material count (4 bytes).
        
        Args:
            count: Number of materials
            disable_materials: If True, write 0 regardless of count
        """
        if disable_materials:
            self.write_int32(0)
        else:
            self.write_int32(count)
    
    def write_bounding_info(self, bounds: BoundingInfo):
        """Write bounding sphere and box information (40 bytes).
        
        Args:
            bounds: BoundingInfo object with sphere and AABB data
        """
        self.data.extend(bounds.to_bytes())
    
    def write_section_header(self, section_bytes: bytes):
        """Write a section header (12 bytes).
        
        Args:
            section_bytes: Pre-formatted section header from meb_format
        """
        self.data.extend(section_bytes)
    
    def write_vector3_array(
        self,
        vectors: np.ndarray,
        flip_coordinates: bool = False
    ):
        """Write an array of 3D vectors as floats.
        
        Args:
            vectors: Nx3 array of vectors
            flip_coordinates: If True, write XYZ; if False, swap Y and Z to XZY
        """
        if flip_coordinates:
            # Use as-is (XYZ)
            coords = vectors
        else:
            # Swap Y and Z (XYZ -> XZY)
            coords = vectors[:, [0, 2, 1]]
        
        # Flatten and convert to float32
        float_data = coords.astype(np.float32).flatten()
        self.data.extend(float_data.tobytes())
    
    def write_vector2_array(self, uvs: np.ndarray):
        """Write an array of 2D UV coordinates.
        
        UV coordinates are written as (U, 1-V) to flip V coordinate.
        
        Args:
            uvs: Nx2 array of UV coordinates
        """
        # Flip V coordinate
        flipped_uvs = uvs.copy()
        flipped_uvs[:, 1] = 1.0 - flipped_uvs[:, 1]
        
        float_data = flipped_uvs.astype(np.float32).flatten()
        self.data.extend(float_data.tobytes())
    
    def write_vector3_as_uvw(self, uvws: np.ndarray):
        """Write an array of 3D UVW coordinates.
        
        Similar to UV but with W component preserved.
        
        Args:
            uvws: Nx3 array of UVW coordinates
        """
        # Flip V coordinate, keep W
        flipped_uvws = uvws.copy()
        flipped_uvws[:, 1] = 1.0 - flipped_uvws[:, 1]
        
        float_data = flipped_uvws.astype(np.float32).flatten()
        self.data.extend(float_data.tobytes())
    
    def write_color_array(self, colors: np.ndarray, has_alpha: bool = False):
        """Write vertex colors as RGBA bytes.
        
        Args:
            colors: Nx4 array of colors (RGBA, values 0.0-1.0)
            has_alpha: If True, write actual alpha; if False, always write 255
        """
        # Convert to 0-255 range
        colors_255 = (colors * 255.0).astype(np.uint8)
        
        if not has_alpha:
            # Force alpha to 255
            colors_255[:, 3] = 255
        
        self.data.extend(colors_255.tobytes())
    
    def write_bodywork_section(self, vertex_count: int):
        """Write bodywork/special data section (zeros).
        
        This section contains 4 zero bytes per vertex.
        
        Args:
            vertex_count: Number of vertices
        """
        self.write_section_header(meb_format.SECTION_BODYWORK)
        zeros = bytes(vertex_count * 4)
        self.data.extend(zeros)
    
    def write_material_data(
        self,
        materials: List[str],
        indices_by_material: List[np.ndarray],
        material_dir: str,
        flip_coordinates: bool,
        vertices_by_material: List[np.ndarray]
    ):
        """Write material data section.
        
        For each material:
        - Material path string (padded to 4 bytes, null terminated)
        - Triangle count (4 bytes)
        - Triangle indices (uint16, reversed order, padded to 4 bytes)
        - Min/max vertex index (2 bytes each)
        - Bounding info (40 bytes)
        
        Args:
            materials: List of material names
            indices_by_material: List of triangle index arrays (flat, not grouped by 3)
            material_dir: Material directory prefix
            flip_coordinates: Coordinate system flag
            vertices_by_material: Vertex arrays per material for bounding calculation
        """
        for mat_name, indices, vertices in zip(materials, indices_by_material, vertices_by_material):
            # Material path
            mat_path = f"{material_dir}{mat_name}.mtx".upper()
            # Convert forward slashes to backslashes for Windows-style paths
            mat_path = mat_path.replace('/', '\\')
            mat_bytes = mat_path.encode('ascii', errors='replace')
            
            # Pad to 4-byte boundary
            padding_needed = (4 - len(mat_bytes) % 4) % 4
            mat_bytes += b'\x00' * padding_needed
            
            # Ensure null termination
            if mat_bytes[-1] != 0:
                mat_bytes += b'\x00' * 4
            
            # Add extra 4 null bytes (seems to be required)
            mat_bytes += b'\x00' * 4
            
            self.data.extend(mat_bytes)
            
            # Triangle count
            tri_count = len(indices) // 3
            self.write_int32(tri_count)
            
            # Write indices in reversed order (per material, not per triangle)
            indices_uint16 = indices.astype(np.uint16)[::-1]  # Reverse entire array
            self.data.extend(indices_uint16.tobytes())
            
            # Pad to 4-byte boundary
            if len(indices_uint16) % 2 != 0:
                self.write_uint16(0)
            
            # Min/max vertex indices
            min_idx = np.min(indices)
            max_idx = np.max(indices)
            self.write_uint16(int(min_idx))
            self.write_uint16(int(max_idx))
            
            # Calculate and write bounding info for this material
            bounds = _calculate_bounds(vertices, flip_coordinates)
            self.write_bounding_info(bounds)
    
    def save(self):
        """Write accumulated data to file."""
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(self.filepath, 'wb') as f:
            f.write(self.data)


def write_meb_file(
    output_path: Path,
    mesh_name: str,
    vertices: np.ndarray,
    normals: np.ndarray,
    colors: np.ndarray,
    uv_layers: List[Tuple[int, np.ndarray]],  # List of (layer_index, uv_array)
    materials: List[str],
    indices_by_material: List[np.ndarray],
    vertices_by_material: List[np.ndarray],
    tangents: Optional[np.ndarray] = None,
    bitangents: Optional[np.ndarray] = None,
    flip_coordinates: bool = False,
    material_dir: str = "vehicles/car_name/",
    disable_materials: bool = False,
    bodywork_data: bool = False,
    w_sections: Optional[List[Tuple[int, int]]] = None,  # List of (uv_layer_idx, w_section_type)
    log_prefix: str = "",
) -> BoundingInfo:
    """Write a complete MEB file.
    
    Args:
        output_path: Output file path
        mesh_name: Name of the mesh
        vertices: Nx3 vertex positions
        normals: Nx3 vertex normals
        colors: Nx4 vertex colors (RGBA, 0-1 range)
        uv_layers: List of (layer_index, Nx2 UV array) tuples
        materials: List of material names
        indices_by_material: List of index arrays per material
        vertices_by_material: List of vertex arrays per material (for bounds)
        tangents: Optional Nx3 tangent vectors
        bitangents: Optional Nx3 bitangent vectors
        flip_coordinates: Coordinate system flag
        material_dir: Material directory prefix
        disable_materials: If True, don't write material data
        bodywork_data: If True, write bodywork section
        w_sections: Optional list of UV layers to write as UVW instead of UV
        log_prefix: Optional mesh label used to prefix log output
    
    Returns:
        BoundingInfo for the entire mesh
    """
    writer = MEBWriter(output_path)
    
    # Material slots can exist without any assigned triangles; skip them.
    # Keep count/data aligned to avoid writing empty index buffers.
    material_entries = [
        (name, idxs, verts)
        for name, idxs, verts in zip(materials, indices_by_material, vertices_by_material)
        if len(idxs) > 0
    ]
    filtered_materials = [entry[0] for entry in material_entries]
    filtered_indices = [entry[1] for entry in material_entries]
    filtered_vertices = [entry[2] for entry in material_entries]
    
    # Calculate overall bounds
    bounds = _calculate_bounds(vertices, flip_coordinates)
    
    # Count additional vertex parameters beyond the base 3 (positions, colors, normals)
    param_count = 0
    
    # Count UV layers (including W sections - they're the same UV data, just different format)
    param_count += len(uv_layers)
    
    # Tangent space adds 2 parameters (tangents + bitangents)
    if tangents is not None:
        param_count += 2
    
    # Bodywork data adds 1 parameter
    if bodywork_data:
        param_count += 1
    
    # NOTE: W sections don't add extra params - they're just UV layers with W component
    # The param count is based on SECTIONS written, not data format
    
    total_param_count = 3 + param_count
    log_message = (
        "MEB vertex params: "
        f"additional={param_count}, total={total_param_count} "
        f"(base=3, uv={len(uv_layers)}, tangent={2 if tangents is not None else 0}, "
        f"bodywork={1 if bodywork_data else 0})"
    )
    if log_prefix:
        print(f"[{log_prefix}] {log_message}")
    else:
        print(log_message)
    
    # Check color alpha usage
    has_alpha = bool(np.any(colors[:, 3] != 1.0)) if colors.shape[1] >= 4 else False
    
    # Write file structure
    writer.write_header()
    writer.write_mesh_name(mesh_name)
    writer.write_vertex_count(len(vertices))
    writer.write_vertex_params_count(param_count)
    writer.write_material_count(len(filtered_materials), disable_materials)
    writer.write_bounding_info(bounds)
    
    # Write vertex data sections
    writer.write_section_header(meb_format.SECTION_VERTEX_POSITIONS)
    writer.write_vector3_array(vertices, flip_coordinates)
    
    writer.write_section_header(meb_format.SECTION_VERTEX_COLORS)
    writer.write_color_array(colors, has_alpha)
    
    writer.write_section_header(meb_format.SECTION_VERTEX_NORMALS)
    writer.write_vector3_array(normals, flip_coordinates)
    
    # Write tangent space if requested
    if tangents is not None and bitangents is not None:
        writer.write_section_header(meb_format.SECTION_TANGENTS)
        writer.write_vector3_array(tangents, flip_coordinates)
        
        writer.write_section_header(meb_format.SECTION_BITANGENTS)
        writer.write_vector3_array(bitangents, flip_coordinates)
    
    # Write UV layers (in order they were specified)
    w_section_dict = {uv_idx: w_type for uv_idx, w_type in (w_sections or [])}
    
    for layer_idx, uv_data in uv_layers:
        if layer_idx in w_section_dict:
            # This UV layer should be written as UVW
            w_type = w_section_dict[layer_idx]
            header = meb_format.get_uv_section_header(w_type, include_w=True)
            writer.write_section_header(header)
            
            # Ensure we have W component (pad with zeros if needed)
            if uv_data.shape[1] == 2:
                uvw = np.zeros((len(uv_data), 3), dtype=np.float32)
                uvw[:, :2] = uv_data
            else:
                uvw = uv_data
            writer.write_vector3_as_uvw(uvw)
        else:
            # Regular UV section
            header = meb_format.get_uv_section_header(layer_idx, include_w=False)
            writer.write_section_header(header)
            writer.write_vector2_array(uv_data[:, :2])  # Ensure only UV, not W
    
    # Write bodywork section if requested
    if bodywork_data:
        writer.write_bodywork_section(len(vertices))
    
    # Write material data
    if not disable_materials and filtered_materials:
        writer.write_material_data(
            filtered_materials,
            filtered_indices,
            material_dir,
            flip_coordinates,
            filtered_vertices
        )
    
    # Save to file
    writer.save()
    
    return bounds
