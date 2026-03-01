"""
Extracts mesh data directly from Blender objects to write MEB files.
"""

import numpy as np
from pathlib import Path
from typing import Any, List, Tuple, Optional
from dataclasses import dataclass, field

try:
    import bpy  # type: ignore
    import bmesh  # type: ignore
    import mathutils  # type: ignore
    BLENDER_AVAILABLE = True
except ImportError:
    bpy: Any = None
    bmesh: Any = None
    mathutils: Any = None
    BLENDER_AVAILABLE = False

from .meb_writer import BoundingInfo, write_meb_file


@dataclass
class MeshExportOptions:
    """Options for MEB mesh export."""

    # Material settings
    material_dir: str = "tracks/trackname"
    disable_materials: bool = False

    # Coordinate system
    flip_coordinates: bool = False

    # UV maps (indices into the mesh's UV layers)
    uv_map_indices: List[int] = field(default_factory=list)

    # Tangent space
    generate_tangent_space: bool = False

    # Special sections
    bodywork_data: bool = False
    w_sections: List[Tuple[int, int]] = field(default_factory=list)


def extract_mesh_data_from_blender(
    obj,
    options: MeshExportOptions
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, List[Tuple[int, np.ndarray]],
           List[str], List[np.ndarray], List[np.ndarray],
           Optional[np.ndarray], Optional[np.ndarray]]:
    """Extract mesh data from a Blender object.

    Args:
        obj: Blender mesh object
        options: Export options

    Returns:
        Tuple of:
        - vertices (Nx3)
        - normals (Nx3)
        - colors (Nx4, RGBA)
        - uv_layers (list of (index, Nx2 array) tuples)
        - material_names (list of strings)
        - indices_by_material (list of index arrays)
        - vertices_by_material (list of vertex arrays for bounds calculation)
        - tangents (optional Nx3)
        - bitangents (optional Nx3)
    """
    if not BLENDER_AVAILABLE:
        raise RuntimeError("Blender is not available")

    # Ensure we're working with a mesh
    if obj.type != 'MESH':
        raise ValueError(f"Object {obj.name} is not a mesh")

    # Get mesh with modifiers applied
    eval_obj = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    eval_mesh = eval_obj.to_mesh()

    try:
        # Apply ONLY scale to mesh vertices (rotation/location stay in SGX transform)
        # Extract scale from the world matrix
        scale_matrix = mathutils.Matrix.Diagonal(obj.matrix_world.to_scale()).to_4x4()
        eval_mesh.transform(scale_matrix)

        # Ensure mesh has triangulated faces
        bm = bmesh.new()
        bm.from_mesh(eval_mesh)
        bmesh.ops.triangulate(bm, faces=bm.faces)
        bm.to_mesh(eval_mesh)
        bm.free()

        # Calculate tangents if needed
        if options.generate_tangent_space:
            # Ensure we have UVs before calculating tangents
            if len(eval_mesh.uv_layers) > 0:
                eval_mesh.calc_tangents()

        # Build vertex data with deduplication
        # We'll build unique vertices and an index buffer
        unique_vertices = []
        unique_normals = []
        unique_colors = []
        unique_tangents = []
        unique_bitangents = []

        # Map from vertex data tuple to vertex index
        vertex_map = {}

        # Determine which UV layers to export
        # NOTE: Can have duplicates! e.g. [0, 1, 0, 1] means write UV0, UV1, UV0 again, UV1 again
        uv_indices_to_export = []
        if options.uv_map_indices:
            uv_indices_to_export = [idx for idx in options.uv_map_indices if idx < len(eval_mesh.uv_layers)]
        elif len(eval_mesh.uv_layers) > 0:
            # Auto: use first UV layer
            uv_indices_to_export = [0]

        # Build a set of unique source UV layers we need to read
        unique_source_uv_indices = sorted(set(uv_indices_to_export))
        unique_uv_data = {uv_idx: [] for uv_idx in unique_source_uv_indices}

        # Track indices by material
        material_names = []
        indices_by_material = []
        vertices_by_material = []

        # Get material names
        if eval_mesh.materials:
            for mat in eval_mesh.materials:
                if mat:
                    material_names.append(mat.name)
                else:
                    material_names.append("DefaultMaterial")
        else:
            material_names.append("DefaultMaterial")

        # Initialize index lists for each material
        material_indices = [[] for _ in material_names]
        material_vertex_sets = [set() for _ in material_names]

        # Extract per-loop data with vertex deduplication
        for poly in eval_mesh.polygons:
            mat_idx = poly.material_index
            if mat_idx >= len(material_names):
                mat_idx = 0

            for loop_idx in poly.loop_indices:
                loop = eval_mesh.loops[loop_idx]
                vert = eval_mesh.vertices[loop.vertex_index]

                # Build vertex data
                pos = tuple(vert.co)
                normal = tuple(loop.normal)

                # Vertex color
                if eval_mesh.vertex_colors:
                    color_layer = eval_mesh.vertex_colors[0]
                    color = color_layer.data[loop_idx].color
                    color_tuple = (color[0], color[1], color[2], 1.0)
                else:
                    color_tuple = (1.0, 1.0, 1.0, 1.0)

                # UVs - build tuple with ALL requested UV data (including duplicates for dedup key)
                uv_tuple = ()
                for uv_idx in uv_indices_to_export:
                    if uv_idx < len(eval_mesh.uv_layers):
                        uv_layer = eval_mesh.uv_layers[uv_idx]
                        uv = uv_layer.data[loop_idx].uv
                        uv_tuple += (uv[0], uv[1])

                # Tangents/bitangents
                tangent_tuple = ()
                bitangent_tuple = ()
                if options.generate_tangent_space and len(eval_mesh.uv_layers) > 0:
                    tangent_tuple = tuple(loop.tangent)
                    bitangent_tuple = tuple(loop.bitangent)

                # Create a unique key for this vertex
                vertex_key = (pos, normal, color_tuple, uv_tuple, tangent_tuple, bitangent_tuple)

                # Check if we've seen this exact vertex before
                if vertex_key in vertex_map:
                    # Reuse existing vertex
                    vertex_index = vertex_map[vertex_key]
                else:
                    # Add new unique vertex
                    vertex_index = len(unique_vertices)
                    vertex_map[vertex_key] = vertex_index

                    unique_vertices.append(list(pos))
                    unique_normals.append(list(normal))
                    unique_colors.append(list(color_tuple))

                    # Store UV data only once per unique source layer
                    for uv_idx in unique_source_uv_indices:
                        uv_layer = eval_mesh.uv_layers[uv_idx]
                        uv = uv_layer.data[loop_idx].uv
                        unique_uv_data[uv_idx].append([uv[0], uv[1]])

                    if options.generate_tangent_space and len(eval_mesh.uv_layers) > 0:
                        unique_tangents.append(list(tangent_tuple))
                        unique_bitangents.append(list(bitangent_tuple))

                # Track this vertex index for this material
                material_indices[mat_idx].append(vertex_index)
                material_vertex_sets[mat_idx].add(vertex_index)

        # Convert lists to numpy arrays
        vertices = np.array(unique_vertices, dtype=np.float32)
        normals = np.array(unique_normals, dtype=np.float32)
        colors = np.array(unique_colors, dtype=np.float32)

        tangents_array = None
        bitangents_array = None
        if options.generate_tangent_space and unique_tangents:
            tangents_array = np.array(unique_tangents, dtype=np.float32)
            bitangents_array = np.array(unique_bitangents, dtype=np.float32)

        # Convert material indices to numpy arrays
        for mat_idx, idx_list in enumerate(material_indices):
            indices_by_material.append(np.array(idx_list, dtype=np.uint16))

            # Extract vertices for this material (for bounding calculation)
            vertex_set = material_vertex_sets[mat_idx]
            mat_vertices = vertices[list(vertex_set)]
            vertices_by_material.append(mat_vertices)

        # Build UV layer list WITH DUPLICATES as specified in uv_indices_to_export
        # Each entry references the appropriate source UV data (may reference same data multiple times)
        uv_layers = []
        for slot_idx, source_uv_idx in enumerate(uv_indices_to_export):
            uv_array = np.array(unique_uv_data[source_uv_idx], dtype=np.float32)
            # Store as (slot_index, uv_array) - slot_index determines which UV section header to use
            uv_layers.append((slot_idx, uv_array))

        print(f"  Deduplicated {len(vertex_map)} unique vertices from {sum(len(p.loop_indices) for p in eval_mesh.polygons)} loops")
        print(f"  Export options: tangent_space={options.generate_tangent_space}, bodywork={options.bodywork_data}, UV slots={len(uv_layers)} (source layers: {uv_indices_to_export})")
        print(f"  Returning tangents: {tangents_array is not None}, bitangents: {bitangents_array is not None}")

        return (
            vertices,
            normals,
            colors,
            uv_layers,
            material_names,
            indices_by_material,
            vertices_by_material,
            tangents_array,
            bitangents_array
        )

    finally:
        # Clean up evaluated mesh
        eval_obj.to_mesh_clear()


def export_object_to_meb(
    obj,
    output_path: Path,
    mesh_name: Optional[str] = None,
    options: Optional[MeshExportOptions] = None
) -> BoundingInfo:
    """Export a Blender mesh object to MEB format.

    Args:
        obj: Blender mesh object to export
        output_path: Output MEB file path
        mesh_name: Optional mesh name (defaults to object name)
        options: Export options (defaults to basic export)

    Returns:
        BoundingInfo object with sphere and AABB data
    """
    if options is None:
        options = MeshExportOptions()

    if mesh_name is None:
        mesh_name = obj.name
    mesh_name = str(mesh_name)

    # Extract mesh data from Blender
    (
        vertices,
        normals,
        colors,
        uv_layers,
        material_names,
        indices_by_material,
        vertices_by_material,
        tangents,
        bitangents
    ) = extract_mesh_data_from_blender(obj, options)

    # Validate vertex count (MEB uses 16-bit indices)
    if len(vertices) > 65535:
        raise ValueError(
            f"Mesh {obj.name} has {len(vertices)} unique vertices (after deduplication and triangulation), "
            f"which exceeds the MEB format limit of 65535. Split the mesh into smaller parts."
        )

    # Write MEB file
    bounds = write_meb_file(
        output_path=output_path,
        mesh_name=mesh_name,
        vertices=vertices,
        normals=normals,
        colors=colors,
        uv_layers=uv_layers,
        materials=material_names,
        indices_by_material=indices_by_material,
        vertices_by_material=vertices_by_material,
        tangents=tangents,
        bitangents=bitangents,
        flip_coordinates=options.flip_coordinates,
        material_dir=options.material_dir,
        disable_materials=options.disable_materials,
        bodywork_data=options.bodywork_data,
        w_sections=options.w_sections
    )

    return bounds
