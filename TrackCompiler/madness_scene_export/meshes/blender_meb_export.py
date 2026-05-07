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
from ..utils.utils import sanitize


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

        # Use Blender's cached loop triangles instead of always triangulating with bmesh.
        eval_mesh.calc_loop_triangles()

        # Calculate tangents if needed.
        # Some evaluated meshes still contain n-gons; calc_tangents can fail on those.
        # Triangulate first when n-gons are detected to avoid the exception path.
        if options.generate_tangent_space and len(eval_mesh.uv_layers) > 0:
            has_ngons = any(poly.loop_total > 4 for poly in eval_mesh.polygons)
            if has_ngons:
                print(f"  Warning: Tangent calc needs tris/quads on {obj.name}; triangulating fallback...")
                bm = bmesh.new()
                bm.from_mesh(eval_mesh)
                bmesh.ops.triangulate(bm, faces=bm.faces)
                bm.to_mesh(eval_mesh)
                bm.free()
                eval_mesh.calc_loop_triangles()

            try:
                eval_mesh.calc_tangents()
            except RuntimeError as e:
                if "Tangentspace can only be computed for tris/quads" not in str(e) and \
                   "Tangent space can only be computed for tris/quads" not in str(e):
                    raise
                bm = bmesh.new()
                bm.from_mesh(eval_mesh)
                bmesh.ops.triangulate(bm, faces=bm.faces)
                bm.to_mesh(eval_mesh)
                bm.free()
                eval_mesh.calc_loop_triangles()
                eval_mesh.calc_tangents()

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

        # Track indices by material
        material_names = []
        indices_by_material = []
        vertices_by_material = []

        # Get material names
        if eval_mesh.materials:
            for mat in eval_mesh.materials:
                if mat:
                    material_names.append(sanitize(mat.name))
                else:
                    material_names.append("DefaultMaterial")
        else:
            material_names.append("DefaultMaterial")

        # Flatten triangle loop/material references once.
        tri_count = len(eval_mesh.loop_triangles)
        tri_loop_indices = np.empty((tri_count, 3), dtype=np.int32)
        tri_material_indices = np.empty(tri_count, dtype=np.int32)
        for tri_idx, tri in enumerate(eval_mesh.loop_triangles):
            tri_loop_indices[tri_idx] = tri.loops
            mat_idx = tri.material_index
            tri_material_indices[tri_idx] = mat_idx if mat_idx < len(material_names) else 0

        loop_indices = tri_loop_indices.reshape(-1)
        material_per_loop = np.repeat(tri_material_indices, 3)

        # Gather positions from vertices via loop->vertex indirection.
        loop_vertex_index_all = np.empty(len(eval_mesh.loops), dtype=np.int32)
        eval_mesh.loops.foreach_get("vertex_index", loop_vertex_index_all)
        vertex_index_per_loop = loop_vertex_index_all[loop_indices]

        vertex_co_all = np.empty(len(eval_mesh.vertices) * 3, dtype=np.float32)
        eval_mesh.vertices.foreach_get("co", vertex_co_all)
        vertex_co_all = vertex_co_all.reshape(-1, 3)
        loop_positions = vertex_co_all[vertex_index_per_loop]

        # Loop normals.
        loop_normals_all = np.empty(len(eval_mesh.loops) * 3, dtype=np.float32)
        eval_mesh.loops.foreach_get("normal", loop_normals_all)
        loop_normals_all = loop_normals_all.reshape(-1, 3)
        loop_normals = loop_normals_all[loop_indices]

        # Loop colors (RGBA).
        if eval_mesh.vertex_colors:
            color_data_all = np.empty(len(eval_mesh.loops) * 4, dtype=np.float32)
            eval_mesh.vertex_colors[0].data.foreach_get("color", color_data_all)
            color_data_all = color_data_all.reshape(-1, 4)
            loop_colors = color_data_all[loop_indices].copy()
            loop_colors[:, 3] = 1.0
        else:
            loop_colors = np.ones((len(loop_indices), 4), dtype=np.float32)

        # Gather UV layers once per source layer.
        source_uv_per_loop = {}
        for uv_idx in unique_source_uv_indices:
            uv_data_all = np.empty(len(eval_mesh.loops) * 2, dtype=np.float32)
            eval_mesh.uv_layers[uv_idx].data.foreach_get("uv", uv_data_all)
            uv_data_all = uv_data_all.reshape(-1, 2)
            source_uv_per_loop[uv_idx] = uv_data_all[loop_indices]

        # Tangents/bitangents (optional).
        tangents_loop = None
        bitangents_loop = None
        if options.generate_tangent_space and len(eval_mesh.uv_layers) > 0:
            tangents_all = np.empty(len(eval_mesh.loops) * 3, dtype=np.float32)
            bitangents_all = np.empty(len(eval_mesh.loops) * 3, dtype=np.float32)
            eval_mesh.loops.foreach_get("tangent", tangents_all)
            eval_mesh.loops.foreach_get("bitangent", bitangents_all)
            tangents_loop = tangents_all.reshape(-1, 3)[loop_indices]
            bitangents_loop = bitangents_all.reshape(-1, 3)[loop_indices]

        # Build dedup key columns exactly matching exported attributes.
        key_columns = [loop_positions, loop_normals, loop_colors]
        for uv_idx in uv_indices_to_export:
            key_columns.append(source_uv_per_loop[uv_idx])
        if tangents_loop is not None and bitangents_loop is not None:
            key_columns.append(tangents_loop)
            key_columns.append(bitangents_loop)
        dedup_key = np.ascontiguousarray(np.concatenate(key_columns, axis=1))

        # Deduplicate in NumPy/C instead of Python dict + tuple creation.
        _, unique_idx, inverse = np.unique(
            dedup_key, axis=0, return_index=True, return_inverse=True
        )

        vertices = loop_positions[unique_idx].astype(np.float32, copy=False)
        normals = loop_normals[unique_idx].astype(np.float32, copy=False)
        colors = loop_colors[unique_idx].astype(np.float32, copy=False)

        tangents_array = (
            tangents_loop[unique_idx].astype(np.float32, copy=False)
            if tangents_loop is not None
            else None
        )
        bitangents_array = (
            bitangents_loop[unique_idx].astype(np.float32, copy=False)
            if bitangents_loop is not None
            else None
        )

        unique_uv_data = {
            uv_idx: source_uv_per_loop[uv_idx][unique_idx].astype(np.float32, copy=False)
            for uv_idx in unique_source_uv_indices
        }

        non_empty_material_names = []
        non_empty_indices_by_material = []
        non_empty_vertices_by_material = []
        for mat_idx, mat_name in enumerate(material_names):
            mat_loop_indices = inverse[material_per_loop == mat_idx].astype(np.uint16, copy=False)
            if len(mat_loop_indices) == 0:
                continue
            non_empty_material_names.append(mat_name)
            non_empty_indices_by_material.append(mat_loop_indices)
            unique_vertex_indices = np.unique(mat_loop_indices)
            non_empty_vertices_by_material.append(vertices[unique_vertex_indices])

        if len(non_empty_material_names) != len(material_names):
            print(
                f"  Dropped {len(material_names) - len(non_empty_material_names)} material slot(s) with zero triangles"
            )
        material_names = non_empty_material_names
        indices_by_material = non_empty_indices_by_material
        vertices_by_material = non_empty_vertices_by_material

        # Build UV layer list WITH DUPLICATES as specified in uv_indices_to_export
        # Each entry references the appropriate source UV data (may reference same data multiple times)
        uv_layers = []
        for slot_idx, source_uv_idx in enumerate(uv_indices_to_export):
            uv_array = np.array(unique_uv_data[source_uv_idx], dtype=np.float32)
            # Store as (slot_index, uv_array) - slot_index determines which UV section header to use
            uv_layers.append((slot_idx, uv_array))

        print(f"  Deduplicated {len(vertices)} unique vertices from {len(eval_mesh.loop_triangles) * 3} loops")
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
