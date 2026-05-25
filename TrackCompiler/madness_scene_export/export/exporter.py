import bpy  # type: ignore
import tempfile
from pathlib import Path
import shutil
import os
from dataclasses import dataclass
from concurrent.futures import Future, ThreadPoolExecutor
from typing import List, Tuple
import xml.etree.ElementTree as ET
import numpy as np
from .object_export import (
    ObjectInfo,
    collect_empty_objects_with_meb,
    has_temp_export_name,
    is_temp_export_datablock,
    is_temp_export_name,
    sanitize,
    iter_visible_scene_objects,
    parse_kstree_group,
    parse_sms_group,
    combine_objects_into_mesh,
    skip_viewport_disabled_modifiers,
    tag_temp_export_datablock,
)
from ..meshes import MeshExportOptions
from ..meshes.blender_meb_export import extract_mesh_data_from_blender
from ..meshes.meb_writer import write_meb_file
from ..materials.mtx_processor import prepare_mtx_files_from_materials
from ..materials.mtx_material_system import summarize_texture_warnings_for_material_names
from ..settings.userflags import DEFAULT_USERFLAGS
from ..utils import effective_materials_for_object
from ..utils.coordinate_transforms import decompose_matrix


@dataclass
class _PendingObjectExport:
    name: str
    meb_path: Path
    translation: np.ndarray
    quaternion: np.ndarray
    materials: List[str]
    userflags: int
    future: Future


@dataclass
class _MeshValidationIssue:
    mesh: str
    issues: List[str]


@dataclass
class _OriginalMeshBinding:
    obj: object
    mesh: object
    mesh_name: str


@dataclass
class SingleMebExportSettings:
    export_scope: str = "SELECTED"
    transform_mode: str = "APPLY"
    export_textures: bool = False


def _build_maybe_overridden_options(obj, resource_prefix: str) -> MeshExportOptions:
    """Build MEB export options from object settings."""
    options = MeshExportOptions(
        material_dir=resource_prefix if resource_prefix else "vehicles/car_name/"
    )

    if not hasattr(obj.data, "meb_export_settings"):
        return options

    meb_settings = obj.data.meb_export_settings
    uv_indices = []
    for i in range(1, 7):
        uv_prop = f"uv{i}"
        if hasattr(meb_settings, uv_prop):
            uv_val = getattr(meb_settings, uv_prop)
            if uv_val > 0:
                uv_indices.append(uv_val - 1)
    if uv_indices:
        options.uv_map_indices = uv_indices

    if hasattr(meb_settings, "tangent_space"):
        options.generate_tangent_space = meb_settings.tangent_space
    if hasattr(meb_settings, "bodywork"):
        options.bodywork_data = meb_settings.bodywork
    if hasattr(meb_settings, "disable_material"):
        options.disable_materials = meb_settings.disable_material
    return options


def _get_userflags(obj) -> int:
    if hasattr(obj.data, "meb_export_settings"):
        from ..settings.meb_export_settings import get_userflags_value
        return get_userflags_value(obj.data.meb_export_settings)
    return DEFAULT_USERFLAGS


def _get_group_userflags(group_name: str, group_objects: List[object]) -> int:
    values = [_get_userflags(obj) for obj in group_objects]
    unique_values = sorted(set(values))
    if len(unique_values) > 1:
        print(
            f"  Warning: {group_name} has mixed source userflags; "
            f"using {values[0]} from {group_objects[0].name}"
        )
    return values[0] if values else DEFAULT_USERFLAGS


def _count_nonfinite(array) -> int:
    return int(np.size(array) - np.count_nonzero(np.isfinite(array)))


def _validate_extracted_mesh(mesh_name: str, extracted_data) -> Tuple[_MeshValidationIssue | None, bool]:
    (
        vertices,
        normals,
        colors,
        uv_layers,
        material_names,
        indices_by_material,
        _vertices_by_material,
        tangents,
        bitangents,
        repair_notes,
    ) = extracted_data
    issues = list(repair_notes)

    checks = [("vertices", vertices), ("normals", normals), ("colors", colors)]
    checks.extend((f"uv{slot_idx}", uv_data) for slot_idx, uv_data in uv_layers)
    if tangents is not None:
        checks.append(("tangents", tangents))
    if bitangents is not None:
        checks.append(("bitangents", bitangents))

    for label, array in checks:
        bad_count = _count_nonfinite(array)
        if bad_count:
            issues.append(f"{label} has {bad_count} non-finite value(s)")

    vertex_count = len(vertices)
    vertex_limit_exceeded = vertex_count > 65535
    if vertex_limit_exceeded:
        issues.append(
            f"has {vertex_count} unique vertices (after deduplication and triangulation), "
            "exceeding the MEB format limit of 65535, and was therefore not exported"
        )

    for mat_name, indices in zip(material_names, indices_by_material):
        if len(indices) == 0:
            issues.append(f"{sanitize(mat_name)} has no assigned triangles")
            continue
        if len(indices) % 3:
            issues.append(f"{sanitize(mat_name)} index buffer is not divisible by 3")
            continue
        if np.any(indices >= vertex_count):
            issues.append(f"{sanitize(mat_name)} references vertex index outside 0..{vertex_count - 1}")
            continue

        tris = indices.reshape(-1, 3)
        repeated_index_tris = np.count_nonzero(
            (tris[:, 0] == tris[:, 1]) | (tris[:, 1] == tris[:, 2]) | (tris[:, 0] == tris[:, 2])
        )
        tri_vertices = vertices[tris]
        areas = np.linalg.norm(
            np.cross(tri_vertices[:, 1] - tri_vertices[:, 0], tri_vertices[:, 2] - tri_vertices[:, 0]),
            axis=1,
        )
        zero_area_tris = int(np.count_nonzero(areas <= 1e-10))
        degenerate_tris = max(int(repeated_index_tris), zero_area_tris)
        if degenerate_tris:
            issues.append(f"{sanitize(mat_name)} has {degenerate_tris} degenerate triangle(s)")

    if issues:
        print(f"  Warning: Mesh validation issues in {mesh_name}:")
        for issue in issues:
            print(f"    - {issue}")
        return _MeshValidationIssue(mesh=sanitize(mesh_name), issues=issues), vertex_limit_exceeded
    return None, False


def _write_meb_from_extracted(meb_path: Path, mesh_name: str, options: MeshExportOptions, extracted_data) -> object:
    """Write MEB file using already extracted mesh data (thread-safe, no bpy usage)."""
    (
        vertices,
        normals,
        colors,
        uv_layers,
        material_names,
        indices_by_material,
        vertices_by_material,
        tangents,
        bitangents,
        _repair_notes,
    ) = extracted_data

    return write_meb_file(
        output_path=meb_path,
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
        w_sections=options.w_sections,
    )


def _mesh_datablock_exists(mesh) -> bool:
    try:
        return mesh.name in bpy.data.meshes
    except ReferenceError:
        return False


def _snapshot_original_mesh_bindings() -> List[_OriginalMeshBinding]:
    return [
        _OriginalMeshBinding(obj, obj.data, obj.data.name)
        for obj in bpy.data.objects
        if obj.type == "MESH" and obj.data
    ]


def _restore_original_mesh_bindings(bindings: List[_OriginalMeshBinding]):
    for binding in bindings:
        obj = binding.obj
        if obj.name not in bpy.data.objects or not _mesh_datablock_exists(binding.mesh):
            continue

        if obj.data != binding.mesh and (
            is_temp_export_datablock(obj.data) or has_temp_export_name(obj.data)
        ):
            print(f"Restoring original mesh on {obj.name}: {obj.data.name} -> {binding.mesh_name}")
            obj.data = binding.mesh

        if (
            obj.data == binding.mesh
            and binding.mesh.name != binding.mesh_name
            and not is_temp_export_name(binding.mesh_name)
            and has_temp_export_name(binding.mesh)
        ):
            print(f"Restoring original mesh name on {obj.name}: {binding.mesh.name} -> {binding.mesh_name}")
            binding.mesh.name = binding.mesh_name


def _remove_temp_export_data(temp_objects):
    temp_meshes = set()

    for temp_obj in temp_objects:
        try:
            if temp_obj.name not in bpy.data.objects:
                continue
            if not (is_temp_export_datablock(temp_obj) or has_temp_export_name(temp_obj)):
                print(f"Skipping cleanup of non-temp object: {temp_obj.name}")
                continue
            if temp_obj.type == "MESH" and temp_obj.data:
                temp_meshes.add(temp_obj.data)
            bpy.data.objects.remove(temp_obj, do_unlink=True)
        except ReferenceError:
            pass
        except Exception as e:
            print(f"Warning: Could not delete temporary object {getattr(temp_obj, 'name', '<removed>')}: {e}")

    for mesh in list(temp_meshes) + list(bpy.data.meshes):
        try:
            if mesh.users == 0 and (is_temp_export_datablock(mesh) or has_temp_export_name(mesh)):
                bpy.data.meshes.remove(mesh)
        except ReferenceError:
            pass


def _complete_next_pending_export(pending_exports, objects_list):
    pending = pending_exports.pop(0)
    bounds = pending.future.result()
    objects_list.append(
        ObjectInfo(
            name=pending.name,
            meb_path=pending.meb_path,
            translation=pending.translation,
            quaternion=pending.quaternion,
            sphere_center=bounds.sphere_center,
            sphere_radius=bounds.sphere_radius,
            materials=pending.materials,
            bb_min=bounds.bb_min,
            bb_max=bounds.bb_max,
            userflags=pending.userflags,
        )
    )
    print(f"Successfully exported {pending.name} -> {pending.meb_path.name}")


def _export_single_object(
    obj,
    obj_name,
    output_dir,
    resource_prefix,
    pending_exports,
    writer_pool: ThreadPoolExecutor,
    mesh_validation_issues: List[_MeshValidationIssue],
    userflags_override: int | None = None,
):
    """Queue a single object for pipelined MEB export."""
    world_matrix = obj.matrix_world.copy()
    matrix = np.array(world_matrix)
    translation, quaternion = decompose_matrix(matrix)
    options = _build_maybe_overridden_options(obj, resource_prefix)
    userflags = _get_userflags(obj) if userflags_override is None else userflags_override

    print(f"Exporting {obj_name} to MEB... (tangents={options.generate_tangent_space}, bodywork={options.bodywork_data}, UVs={options.uv_map_indices})")
    meb_path = output_dir / f"{sanitize(obj_name)}.meb"
    sanitized_name = sanitize(obj_name)
    extracted_data = extract_mesh_data_from_blender(obj, options)
    materials = extracted_data[4]
    validation_issue, skip_export = _validate_extracted_mesh(sanitized_name, extracted_data)
    if validation_issue:
        mesh_validation_issues.append(validation_issue)
    if skip_export:
        print(f"Skipping {sanitized_name} MEB export due to vertex limit")
        return

    pending_exports.append(
        _PendingObjectExport(
            name=sanitized_name,
            meb_path=meb_path,
            translation=translation,
            quaternion=quaternion,
            materials=materials,
            userflags=userflags,
            future=writer_pool.submit(
                _write_meb_from_extracted,
                meb_path,
                sanitized_name,
                options,
                extracted_data,
            ),
        )
    )


def _curve_to_temp_mesh_object(curve_obj, context):
    """Create a temporary mesh object from a curve object for export."""
    depsgraph = context.evaluated_depsgraph_get()
    with skip_viewport_disabled_modifiers(curve_obj):
        eval_obj = curve_obj.evaluated_get(depsgraph)

        try:
            mesh_data = bpy.data.meshes.new_from_object(
                eval_obj, preserve_all_data_layers=True, depsgraph=depsgraph
            )
        except TypeError:
            eval_mesh = eval_obj.to_mesh()
            if not eval_mesh:
                return None
            mesh_data = eval_mesh.copy()
            eval_obj.to_mesh_clear()

    if not mesh_data or not mesh_data.polygons:
        if mesh_data:
            bpy.data.meshes.remove(mesh_data)
        return None

    tag_temp_export_datablock(mesh_data)
    temp_obj = bpy.data.objects.new(f"TEMP_CURVE_MESH_{curve_obj.name}", mesh_data)
    tag_temp_export_datablock(temp_obj)
    context.scene.collection.objects.link(temp_obj)
    temp_obj.matrix_world = curve_obj.matrix_world.copy()

    source_materials = effective_materials_for_object(curve_obj, getattr(curve_obj.data, "materials", []))
    if source_materials:
        for mat in source_materials:
            temp_obj.data.materials.append(mat)

    return temp_obj


def _collect_single_meb_export_entries(context, export_scope: str):
    if export_scope == "ALL":
        source_objects = list(iter_visible_scene_objects(context.view_layer))
    else:
        source_objects = list(context.selected_objects)

    export_entries = []
    skipped_objects = []
    temp_objects_to_cleanup = []
    for obj in source_objects:
        if is_temp_export_datablock(obj) or has_temp_export_name(obj):
            temp_objects_to_cleanup.append(obj)
            continue
        if obj.type == "MESH":
            if obj.data and obj.data.polygons:
                export_entries.append((obj, obj.name))
            else:
                skipped_objects.append(f"{obj.name} (empty mesh)")
            continue
        if obj.type != "CURVE":
            skipped_objects.append(f"{obj.name} ({obj.type})")
            continue
        if obj.data.bevel_depth <= 0:
            skipped_objects.append(f"{obj.name} (curve without bevel depth)")
            continue
        temp_curve_mesh = _curve_to_temp_mesh_object(obj, context)
        if not temp_curve_mesh:
            print(f"Skipping {obj.name} - curve could not be converted to mesh")
            skipped_objects.append(f"{obj.name} (curve conversion failed)")
            continue
        temp_objects_to_cleanup.append(temp_curve_mesh)
        export_entries.append((temp_curve_mesh, obj.name))
    return export_entries, temp_objects_to_cleanup, skipped_objects


def export_single_meb_set(
    filepath: str,
    context,
    settings: SingleMebExportSettings,
):
    output_path = Path(filepath)
    output_dir = output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    track_name = output_dir.name if output_dir.name else output_path.stem
    mesh_validation_issues = []
    exported_count = 0
    all_materials = []

    original_selection = context.selected_objects[:]
    original_active = context.active_object
    original_mesh_bindings = _snapshot_original_mesh_bindings()

    try:
        export_entries, temp_objects_to_cleanup, skipped_objects = _collect_single_meb_export_entries(
            context, settings.export_scope
        )
        print(
            f"Single MEB export: {len(export_entries)} object(s), "
            f"scope={settings.export_scope}, transform_mode={settings.transform_mode}"
        )
        if export_entries:
            source_objects = [obj for obj, _ in export_entries]
            bake_world_transform = settings.transform_mode == "APPLY"
            combined_obj, _, _ = combine_objects_into_mesh(
                source_objects,
                output_path.stem,
                context,
                "SINGLE_MEB",
                bake_world_transform=bake_world_transform,
            )
            if combined_obj:
                temp_objects_to_cleanup.append(combined_obj)
                options = _build_maybe_overridden_options(combined_obj, "")
                options.vertex_transform_mode = "NONE"
                # Standalone MEB should still use standard MEB axis conversion.
                options.flip_coordinates = False
                meb_path = output_path.with_suffix(".meb")
                mesh_name = sanitize(output_path.stem)
                extracted_data = extract_mesh_data_from_blender(combined_obj, options)
                materials = extracted_data[4]
                validation_issue, skip_export = _validate_extracted_mesh(mesh_name, extracted_data)
                if validation_issue:
                    mesh_validation_issues.append(validation_issue)
                if not skip_export:
                    _write_meb_from_extracted(meb_path, mesh_name, options, extracted_data)
                    exported_count = 1
                    all_materials.extend(materials)
                    print(f"Successfully exported combined mesh -> {meb_path.name}")
                else:
                    print("Skipping combined MEB export due to vertex limit")

        unique_materials = sorted(set(all_materials))
        if unique_materials:
            texture_mapping = {}
            if settings.export_textures:
                texture_export_dir = determine_texture_export_path(output_dir, track_name)
                texture_mapping = prepare_texture_mapping(
                    unique_materials, output_dir, texture_export_dir, track_name, context
                )
            prepare_mtx_files_from_materials(
                unique_materials,
                output_dir,
                context,
                track_name=track_name,
                texture_mapping=texture_mapping,
            )
            if settings.export_textures and texture_mapping:
                export_textures(texture_mapping, texture_export_dir)
            print(f"Generated {len(unique_materials)} MTX file(s)")

    finally:
        _restore_original_mesh_bindings(original_mesh_bindings)
        if "temp_objects_to_cleanup" in locals() and temp_objects_to_cleanup:
            _remove_temp_export_data(temp_objects_to_cleanup)

        bpy.ops.object.select_all(action="DESELECT")
        for obj in original_selection:
            if obj.name in bpy.data.objects:
                obj.select_set(True)
        if original_active and original_active.name in bpy.data.objects:
            context.view_layer.objects.active = original_active

    mesh_validation_summary = {
        "meshes": len(mesh_validation_issues),
        "issues": sum(len(item.issues) for item in mesh_validation_issues),
        "details": [
            {"mesh": item.mesh, "issues": item.issues}
            for item in mesh_validation_issues
        ],
    }
    return {
        "status": "FINISHED",
        "exported": exported_count,
        "materials": len(sorted(set(all_materials))),
        "skipped_objects": len(skipped_objects) if "skipped_objects" in locals() else 0,
        "skipped_object_names": skipped_objects[:10] if "skipped_objects" in locals() else [],
        "mesh_warnings": mesh_validation_summary,
    }


def export_objects_to_meb(
    context,
    output_dir: Path,
    resource_prefix: str,
    mesh_validation_issues: List[_MeshValidationIssue],
) -> List[ObjectInfo]:
    """
    Export mesh objects to MEB format, grouping KSTREE_GROUP and SMS_GRP objects.
    """
    objects = []
    # Track temporary objects for cleanup
    temp_objects_to_cleanup = []
    original_mesh_bindings = _snapshot_original_mesh_bindings()
    original_selection = context.selected_objects[:]
    original_active = context.active_object

    writer_workers = max(1, min(4, os.cpu_count() or 1))
    max_in_flight = writer_workers * 2

    try:
        with ThreadPoolExecutor(max_workers=writer_workers) as writer_pool:
            pending_exports = []
            bpy.ops.object.select_all(action="DESELECT")

            # Collect all visible mesh objects (and curves with bevel depth as temporary meshes)
            export_entries = []
            for obj in iter_visible_scene_objects(context.view_layer):
                if is_temp_export_datablock(obj) or has_temp_export_name(obj):
                    temp_objects_to_cleanup.append(obj)
                    continue
                if obj.type not in {"MESH", "CURVE"}:
                    continue
                if obj.hide_get():
                    print(f"Skipping {obj.name} - object is hidden")
                    continue

                if obj.type == "MESH":
                    if obj.data.polygons:
                        export_entries.append((obj, obj.name))
                    continue

                if obj.data.bevel_depth <= 0:
                    continue

                temp_curve_mesh = _curve_to_temp_mesh_object(obj, context)
                if not temp_curve_mesh:
                    print(f"Skipping {obj.name} - curve could not be converted to mesh")
                    continue
                temp_objects_to_cleanup.append(temp_curve_mesh)
                export_entries.append((temp_curve_mesh, obj.name))

            print(f"Found {len(export_entries)} visible exportable objects (meshes + beveled curves)")

            # Group objects by their group prefix
            kstree_groups = {}
            sms_groups = {}
            ungrouped_objects = []
            for obj, source_name in export_entries:
                kstree_group = parse_kstree_group(source_name)
                sms_group = parse_sms_group(source_name)
                if kstree_group:
                    kstree_groups.setdefault(kstree_group, []).append(obj)
                elif sms_group:
                    sms_groups.setdefault(sms_group, []).append(obj)
                else:
                    ungrouped_objects.append((obj, source_name))

            print(f"Grouped: {len(kstree_groups)} KSTREE groups, {len(sms_groups)} SMS groups, {len(ungrouped_objects)} ungrouped objects")

            # Process grouped objects
            for group_id, group_objects in kstree_groups.items():
                try:
                    group_name = f"KSTREE_GROUP_{group_id}"
                    print(f"Processing KSTREE_GROUP_{group_id} ({len(group_objects)} objects)...")
                    combined_obj, _, _ = combine_objects_into_mesh(group_objects, group_id, context, "KSTREE_GROUP")
                    if combined_obj:
                        temp_objects_to_cleanup.append(combined_obj)
                        group_userflags = _get_group_userflags(group_name, group_objects)
                        _export_single_object(
                            combined_obj,
                            group_name,
                            output_dir,
                            resource_prefix,
                            pending_exports,
                            writer_pool,
                            mesh_validation_issues,
                            userflags_override=group_userflags,
                        )
                        if len(pending_exports) >= max_in_flight:
                            _complete_next_pending_export(pending_exports, objects)
                except Exception as e:
                    print(f"ERROR: Failed to process KSTREE_GROUP_{group_id}: {e}")
                    import traceback
                    traceback.print_exc()

            for group_name, group_objects in sms_groups.items():
                try:
                    full_group_name = f"SMS_GRP_{group_name}"
                    print(f"Processing SMS_GRP_{group_name} ({len(group_objects)} objects)...")
                    combined_obj, _, _ = combine_objects_into_mesh(group_objects, group_name, context, "SMS_GRP")
                    if combined_obj:
                        temp_objects_to_cleanup.append(combined_obj)
                        group_userflags = _get_group_userflags(full_group_name, group_objects)
                        _export_single_object(
                            combined_obj,
                            full_group_name,
                            output_dir,
                            resource_prefix,
                            pending_exports,
                            writer_pool,
                            mesh_validation_issues,
                            userflags_override=group_userflags,
                        )
                        if len(pending_exports) >= max_in_flight:
                            _complete_next_pending_export(pending_exports, objects)
                except Exception as e:
                    print(f"ERROR: Failed to process SMS_GRP_{group_name}: {e}")
                    import traceback
                    traceback.print_exc()

            # Process ungrouped objects
            for obj, source_name in ungrouped_objects:
                try:
                    _export_single_object(
                        obj,
                        source_name,
                        output_dir,
                        resource_prefix,
                        pending_exports,
                        writer_pool,
                        mesh_validation_issues,
                    )
                    if len(pending_exports) >= max_in_flight:
                        _complete_next_pending_export(pending_exports, objects)
                except Exception as e:
                    print(f"ERROR: Failed to export {source_name}: {e}")
                    import traceback
                    traceback.print_exc()

            while pending_exports:
                _complete_next_pending_export(pending_exports, objects)

    finally:
        _restore_original_mesh_bindings(original_mesh_bindings)

        # Clean up temporary combined/curve objects and their mesh datablocks directly.
        if temp_objects_to_cleanup:
            print(f"Cleaning up {len(temp_objects_to_cleanup)} temporary objects...")
            _remove_temp_export_data(temp_objects_to_cleanup)

        # Restore selection
        bpy.ops.object.select_all(action="DESELECT")
        for obj in original_selection:
            if obj.name in bpy.data.objects:
                obj.select_set(True)
        if original_active and original_active.name in bpy.data.objects:
            context.view_layer.objects.active = original_active

    return objects


def get_parent_layer_collection(root_layer_collection, target_layer_collection):
    """Find the parent layer collection of a given layer collection."""
    for child in root_layer_collection.children:
        if child == target_layer_collection:
            return root_layer_collection

        parent = get_parent_layer_collection(child, target_layer_collection)
        if parent:
            return parent

    return None


def export_madness_scene(
    filepath: str,
    resource_prefix: str,
    placeholder_mtx: Path,
    context,
):
    """Main export function with MTX material support and texture copying."""
    output_dir = Path(filepath).parent
    sgx_path = Path(filepath)
    track_name = sgx_path.stem

    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        print(f"Using temporary directory: {temp_dir}")
        mesh_validation_issues = []

        # Export mesh objects to MEB format
        print("Exporting mesh objects to MEB...")
        objects = export_objects_to_meb(context, output_dir, resource_prefix, mesh_validation_issues)
        print(f"MEB export completed. Exported {len(objects)} objects")

        # Collect all materials used
        all_materials = []
        for obj in objects:
            all_materials.extend(obj.materials)

        # Collect Empty objects with MEB references
        print("Collecting Empty objects with MEB references...")
        empty_data = collect_empty_objects_with_meb(context)
        print(f"Found {len(empty_data)} Empty objects with MEB references")

        # Add Empty objects with MEB references
        print("Processing Empty objects with MEB references...")
        for (
            obj_name,
            meb_path,
            translation,
            quaternion,
            sphere_radius,
            userflags,
        ) in empty_data:
            # Create ObjectInfo for Empty object
            # Use user-specified sphere radius for MEB
            obj = ObjectInfo(
                name=obj_name,
                meb_path=meb_path,
                translation=translation,
                quaternion=quaternion,
                sphere_center=np.array([0, 0, 0]),  # Bounding sphere at origin
                sphere_radius=sphere_radius,  # Use extracted/specified radius
                materials=["DefaultMaterial"],  # Default material
                bb_min=np.array(
                    [-sphere_radius, -sphere_radius, -sphere_radius]
                ),  # Scale bounding box with radius
                bb_max=np.array([sphere_radius, sphere_radius, sphere_radius]),
                userflags=userflags,
            )
            objects.append(obj)
            print(
                f"Added Empty object: {obj_name} -> {meb_path} (radius: {sphere_radius})"
            )

        # Count objects by type (mesh objects vs empty objects)
        mesh_objects = len(objects) - len(empty_data)
        empty_objects = len(empty_data)
        print(
            f"Total objects: {len(objects)} ({mesh_objects} compiled, {empty_objects} referenced)"
        )

        material_to_objects = {}
        for obj in objects:
            for mat_name in obj.materials:
                material_to_objects.setdefault(mat_name, []).append(obj.name)

        # Determine texture export path based on SGX location (needed before MTX generation)
        texture_export_dir = determine_texture_export_path(output_dir, track_name)

        # Generate list of unique materials
        unique_materials = sorted(set(all_materials))
        texture_warning_summary = summarize_texture_warnings_for_material_names(
            set(unique_materials), context
        )
        for detail in texture_warning_summary.get("details", []):
            users = material_to_objects.get(detail["material"], [])
            detail["objects"] = sorted(set(users))[:3] or ["<unknown object>"]

        # Prepare texture mapping (resolves paths and calculates game-relative paths)
        print("Preparing texture mapping...")
        texture_mapping = {}
        if unique_materials:
            texture_mapping = prepare_texture_mapping(
                unique_materials, output_dir, texture_export_dir, track_name, context
            )

        # Generate MTX files (passes texture_mapping for correct paths)
        print("Generating MTX files...")
        prepare_mtx_files_from_materials(
            unique_materials, output_dir, context, track_name, texture_mapping
        )
        print(f"Generated {len(unique_materials)} material files")

        # Export textures to determined location
        if texture_mapping:
            export_textures(texture_mapping, texture_export_dir)

        # Generate SGX file
        print("Generating SGX file...")
        build_sgx(objects, sgx_path, resource_prefix)
        print(f"Generated SGX file: {sgx_path}")

    mesh_validation_summary = {
        "meshes": len(mesh_validation_issues),
        "issues": sum(len(item.issues) for item in mesh_validation_issues),
        "details": [
            {"mesh": item.mesh, "issues": item.issues}
            for item in mesh_validation_issues
        ],
    }
    return {
        "status": "FINISHED",
        "texture_warnings": texture_warning_summary,
        "mesh_warnings": mesh_validation_summary,
    }


def determine_texture_export_path(output_dir: Path, track_name: str) -> Path:
    """Determine where to export textures based on SGX location."""
    # Always place textures one level above the SGX directory.
    texture_dir = output_dir.parent / "textures" / track_name
    print(f"Texture export directory: {texture_dir}")
    return texture_dir


def prepare_texture_mapping(
    material_names: list,
    mtx_dir: Path,
    texture_export_dir: Path,
    track_name: str,
    context
):
    """Create a mapping of textures for MTX generation and texture copying.

    Returns a dict mapping (material_name, param_name) to (resolved_src_path, game_relative_path).
    Does NOT modify material settings - just prepares the mapping.
    """
    texture_mapping = {}

    for mat_name in material_names:
        # Find corresponding Blender material
        blender_material = None
        for mat in bpy.data.materials:
            if sanitize(mat.name) == mat_name:
                blender_material = mat
                break

        if blender_material and hasattr(blender_material, "mtx_settings"):
            mtx = blender_material.mtx_settings

            for param in mtx.shader_params:
                if param.param_type == "EPT_TEXTURE" and param.texture_value:
                    # Resolve the texture path to actual file location
                    from ..materials.mtx_material_system import resolve_texture_path
                    src_path, exists = resolve_texture_path(param.texture_value, context)

                    if exists and src_path:
                        # Calculate the game-relative path for MTX files
                        game_relative_path = create_relative_texture_path(
                            mtx_dir, texture_export_dir, src_path.name, track_name
                        )

                        # Store mapping
                        key = (mat_name, param.name)
                        texture_mapping[key] = (str(src_path), game_relative_path)

                        print(f"  Mapped {mat_name}.{param.name}: {game_relative_path}")
                    else:
                        print(f"  Warning: Texture not found for {mat_name}.{param.name}: {param.texture_value}")

    return texture_mapping


def export_textures(
    texture_mapping: dict,
    texture_export_dir: Path
):
    """Export textures to target directory using the prepared texture mapping.

    Args:
        texture_mapping: Dict mapping (material_name, param_name) to (resolved_src_path, game_relative_path)
        texture_export_dir: Directory to export textures to
    """
    texture_export_dir.mkdir(parents=True, exist_ok=True)

    texture_count = 0
    copied_files = set()  # Track already copied files to avoid duplicates

    for (mat_name, param_name), (src_path_str, game_path) in texture_mapping.items():
        src_path = Path(src_path_str)

        if src_path.exists():
            dest_path = texture_export_dir / src_path.name

            # Skip if already copied
            if dest_path in copied_files:
                continue

            try:
                shutil.copy2(src_path, dest_path)
                texture_count += 1
                copied_files.add(dest_path)
                print(f"  Copied texture: {src_path.name}")
            except Exception as e:
                print(f"  Failed to copy texture {src_path.name}: {e}")
        else:
            print(f"  Warning: Source texture no longer exists: {src_path}")

    print(f"Exported {texture_count} textures to {texture_export_dir}")


def create_relative_texture_path(
    mtx_dir: Path,
    texture_dir: Path,
    texture_name: str,
    track_name: str
) -> str:
    """Create the correct relative texture path for MTX files."""
    if mtx_dir.parent.name.lower() == "tracks":
        return f"tracks\\textures\\{track_name}\\{texture_name}"
    try:
        rel_path = texture_dir.relative_to(mtx_dir.parent)
        return str(rel_path / texture_name).replace("/", "\\")
    except ValueError:
        # Fallback if paths are not related
        return f"textures\\{track_name}\\{texture_name}"


def copy_meb_file_to_export(
    original_meb_path: str,
    output_dir: Path,
    relative_meb_path: str,
    track_name: str
) -> Path:
    """Copy MEB file from source location to export directory."""
    if not original_meb_path:
        print(f"Warning: No source MEB path provided for {relative_meb_path}")
        return Path(relative_meb_path.lstrip("\\"))

    source_path = Path(original_meb_path)

    if not source_path.exists():
        print(f"Warning: Source MEB file not found: {source_path}")
        return Path(relative_meb_path.lstrip("\\"))

    # Determine the destination path based on export structure
    dest_path = determine_meb_export_path(output_dir, relative_meb_path, track_name)

    try:
        # Ensure destination directory exists
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Copy the MEB file
        shutil.copy2(source_path, dest_path)
        print(f"Copied MEB file: {source_path.name} -> {dest_path}")

        # Return the relative path for use in SGX
        return create_relative_meb_path_for_sgx(output_dir, dest_path, track_name)

    except Exception as e:
        print(f"Failed to copy MEB file {source_path}: {e}")
        # Return original relative path as fallback
        return Path(relative_meb_path.lstrip("\\"))


def determine_meb_export_path(output_dir: Path, relative_meb_path: str, track_name: str) -> Path:
    """Determine where to copy the MEB file based on export structure."""
    # Extract just the filename from the relative path
    meb_filename = Path(relative_meb_path).name

    # Check if we're in a tracks-based structure
    path_parts = output_dir.parts
    tracks_index = -1

    for i, part in enumerate(path_parts):
        if part.lower() == "tracks":
            tracks_index = i
            break

    if tracks_index >= 0:
        # If "tracks" is found, place MEB in tracks/track_name/
        tracks_parent = Path(*path_parts[:tracks_index])
        meb_dir = tracks_parent / "tracks" / track_name
    else:
        # If no "tracks" in path, place MEB in track_name/ relative to SGX
        meb_dir = output_dir / track_name

    return meb_dir / meb_filename


def create_relative_meb_path_for_sgx(output_dir: Path, copied_meb_path: Path, track_name: str) -> Path:
    """Create the relative MEB path for use in SGX file."""
    try:
        # Try to create a relative path from the SGX directory to the MEB file
        rel_path = copied_meb_path.relative_to(output_dir.parent)
        return rel_path
    except ValueError:
        # If that fails, use the filename with track prefix
        return Path(track_name) / copied_meb_path.name


def build_sgx(
    objects: List[ObjectInfo],
    dest_path: Path,
    resource_prefix: str = "",
):
    """Generate SGX file from object data."""
    def _scene_bounds(items: List[ObjectInfo]) -> Tuple[np.ndarray, np.ndarray]:
        if not items:
            zero = np.array([0.0, 0.0, 0.0], dtype=np.float32)
            return zero.copy(), zero.copy()

        first = items[0]
        scene_min = first.translation + first.bb_min
        scene_max = first.translation + first.bb_max
        for obj in items[1:]:
            obj_min = obj.translation + obj.bb_min
            obj_max = obj.translation + obj.bb_max
            scene_min = np.minimum(scene_min, obj_min)
            scene_max = np.maximum(scene_max, obj_max)
        return scene_min, scene_max

    scene_min, scene_max = _scene_bounds(objects)
    scene = ET.Element(
        "SCENE",
        FileVersion="0.1.0.0",
        ExporterVersion="Open Madness Track Tools 0.1.0",
        NumObjects=str(len(objects)),
        NumPartitions="1",
    )

    obj_id = 1
    for obj in objects:
        obj_elem = ET.SubElement(scene, "OBJ_ID", no=str(obj_id))

        # Create LOD parent node
        lod_node = ET.SubElement(
            obj_elem,
            "NODE",
            type="LOD",
            Name=obj.name,
            MatrixNumber="-1",
            matrices="1",
            subobjects="1",
        )

        # Add SPHERE and MATRIX to LOD node
        cx, cy, cz = obj.sphere_center
        ET.SubElement(
            lod_node,
            "SPHERE",
            Centre=f"{cx:.6f} {cy:.6f} {cz:.6f} 1.000000",
            Radius=f"{obj.sphere_radius:.6f}",
        )

        tx, ty, tz = obj.translation
        qw, qx, qy, qz = obj.quaternion
        ET.SubElement(
            lod_node,
            "MATRIX",
            Offset=f"{tx:.6f} {ty:.6f} {tz:.6f}",
            Orientation=f"{qx:.6f} {qy:.6f} {qz:.6f} {qw:.6f}",
            Scale="1.000000",
        )

        # Add CONTROL element to LOD node
        ET.SubElement(lod_node, "CONTROL", Distances="1000 ")

        # Create OBJECT child node
        node = ET.SubElement(
            lod_node,
            "NODE",
            type="OBJECT",
            Name=obj.name,
            MatrixNumber="0",
            instances="1",
            userflags=str(obj.userflags),
        )

        # Determine if this is an Empty object (referenced) or compiled mesh object
        # Empty objects have MEB paths that are already game-relative paths
        # Compiled objects need the resource prefix added
        if obj.meb_path.name != obj.name + ".meb":
            # This is likely an Empty object with a custom MEB path (referenced)
            resource_filename = str(obj.meb_path).replace("\\", "/")
            if resource_filename.startswith("/"):
                resource_filename = resource_filename[1:]  # Remove leading slash
        else:
            # This is a compiled mesh object
            resource_filename = f"{resource_prefix}{obj.meb_path.name}"

        ET.SubElement(node, "RESOURCE", Filename=resource_filename)

        # Add SPHERE to OBJECT node (duplicate from LOD)
        ET.SubElement(
            node,
            "SPHERE",
            Centre=f"{cx:.6f} {cy:.6f} {cz:.6f} 1.000000",
            Radius=f"{obj.sphere_radius:.6f}",
        )

        obj_id += 1

    # Single partition with all objects
    part = ET.SubElement(scene, "PARTITION_ID", no="0")
    ET.SubElement(
        part,
        "AABBOX",
        min=f"{scene_min[0]:.6f} {scene_min[1]:.6f} {scene_min[2]:.6f}",
        max=f"{scene_max[0]:.6f} {scene_max[1]:.6f} {scene_max[2]:.6f}",
    )

    child_ids = " ".join(str(i) for i in range(1, obj_id)) + " "
    ET.SubElement(part, "CHILD_OBJS", IDs=child_ids)
    ET.SubElement(part, "CHILD_PARTITIONS", IDs="NONE")

    ET.indent(scene, space="    ")
    tree = ET.ElementTree(scene)
    tree.write(dest_path, encoding="utf-8", xml_declaration=True)
