from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import tempfile
import traceback
from typing import List, Tuple
import xml.etree.ElementTree as ET

import numpy as np

import bpy  # type: ignore

from ..materials.mtx_material_system import (
    resolve_texture_path,
    summarize_texture_warnings_for_material_names,
)
from ..materials.mtx_processor import prepare_mtx_files_from_materials
from ..meshes import MeshExportOptions
from ..meshes.blender_meb_export import extract_mesh_data_from_blender
from ..meshes.meb_writer import write_meb_file
from ..settings.userflags import DEFAULT_USERFLAGS
from ..utils import effective_materials_for_object
from ..utils.coordinate_transforms import decompose_matrix
from .object_export import (
    ObjectInfo,
    collect_empty_objects_with_meb,
    combine_objects_into_mesh,
    has_temp_export_name,
    is_temp_export_datablock,
    is_temp_export_name,
    iter_visible_scene_objects,
    parse_kstree_group,
    parse_sms_group,
    sanitize,
    skip_viewport_disabled_modifiers,
    tag_temp_export_datablock,
)


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


def _log_export_error(context: str, exc: Exception):
    print(f"ERROR: {context}: {exc}")
    traceback.print_exc()


def _build_mesh_validation_summary(mesh_validation_issues: List[_MeshValidationIssue]) -> dict:
    return {
        "meshes": len(mesh_validation_issues),
        "issues": sum(len(item.issues) for item in mesh_validation_issues),
        "details": [{"mesh": item.mesh, "issues": item.issues} for item in mesh_validation_issues],
    }


def _restore_selection(context, original_selection, original_active):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in original_selection:
        if obj.name in bpy.data.objects:
            obj.select_set(True)
    if original_active and original_active.name in bpy.data.objects:
        context.view_layer.objects.active = original_active


def _snapshot_original_mesh_bindings() -> List[_OriginalMeshBinding]:
    return [
        _OriginalMeshBinding(obj, obj.data, obj.data.name)
        for obj in bpy.data.objects
        if obj.type == "MESH" and obj.data
    ]


def _restore_original_mesh_bindings(bindings: List[_OriginalMeshBinding]):
    for binding in bindings:
        obj = binding.obj
        try:
            if obj.name not in bpy.data.objects or binding.mesh.name not in bpy.data.meshes:
                continue
        except ReferenceError:
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


def _build_maybe_overridden_options(obj, resource_prefix: str) -> MeshExportOptions:
    options = MeshExportOptions(material_dir=resource_prefix if resource_prefix else "vehicles/car_name/")
    if not hasattr(obj.data, "meb_export_settings"):
        return options

    settings = obj.data.meb_export_settings
    uv_indices = []
    for i in range(1, 7):
        value = getattr(settings, f"uv{i}", 0)
        if value > 0:
            uv_indices.append(value - 1)
    if uv_indices:
        options.uv_map_indices = uv_indices

    options.generate_tangent_space = bool(getattr(settings, "tangent_space", options.generate_tangent_space))
    options.bodywork_data = bool(getattr(settings, "bodywork", options.bodywork_data))
    options.disable_materials = bool(getattr(settings, "disable_material", options.disable_materials))
    options.skip_uv_compression = bool(getattr(settings, "skip_uv_compression", options.skip_uv_compression))
    return options


def _get_userflags(obj) -> int:
    if hasattr(obj.data, "meb_export_settings"):
        from ..settings.userflags import bool_vector_to_userflags
        return bool_vector_to_userflags(obj.data.meb_export_settings.userflags)
    return DEFAULT_USERFLAGS


def _get_group_userflags(group_name: str, group_objects: List[object]) -> int:
    values = [_get_userflags(obj) for obj in group_objects]
    if len(set(values)) > 1 and group_objects:
        print(
            f"  Warning: {group_name} has mixed source userflags; "
            f"using {values[0]} from {group_objects[0].name}"
        )
    return values[0] if values else DEFAULT_USERFLAGS


def _get_group_skip_uv_compression(group_name: str, group_objects: List[object]) -> bool:
    values = [
        bool(getattr(getattr(getattr(obj, "data", None), "meb_export_settings", None), "skip_uv_compression", False))
        for obj in group_objects
    ]
    if len(set(values)) > 1:
        print(
            f"  Warning: {group_name} has mixed Skip UV Compression settings; "
            "using enabled to preserve UV precision"
        )
    return any(values)


def _build_export_mesh_stem(base_name: str, skip_uv_compression: bool) -> str:
    if not skip_uv_compression or base_name.lower().endswith("_no_uv_comp"):
        return base_name
    return f"{base_name}_no_uv_comp"


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
        bad_count = int(np.size(array) - np.count_nonzero(np.isfinite(array)))
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
        safe_name = sanitize(mat_name)
        if len(indices) == 0:
            issues.append(f"{safe_name} has no assigned triangles")
            continue
        if len(indices) % 3:
            issues.append(f"{safe_name} index buffer is not divisible by 3")
            continue
        if np.any(indices >= vertex_count):
            issues.append(f"{safe_name} references vertex index outside 0..{vertex_count - 1}")
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
            issues.append(f"{safe_name} has {degenerate_tris} degenerate triangle(s)")

    if issues:
        print(f"  Warning: Mesh validation issues in {mesh_name}:")
        for issue in issues:
            print(f"    - {issue}")
        return _MeshValidationIssue(mesh=sanitize(mesh_name), issues=issues), vertex_limit_exceeded
    return None, False


def _complete_next_pending_export(pending_exports, objects_list):
    pending = pending_exports.popleft()
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


def _queue_object_export(
    obj,
    obj_name,
    output_dir,
    resource_prefix,
    pending_exports,
    writer_pool: ThreadPoolExecutor,
    mesh_validation_issues: List[_MeshValidationIssue],
    objects,
    max_in_flight: int,
    userflags_override: int | None = None,
    skip_uv_compression_override: bool | None = None,
):
    matrix = np.array(obj.matrix_world.copy())
    translation, quaternion = decompose_matrix(matrix)
    options = _build_maybe_overridden_options(obj, resource_prefix)
    userflags = _get_userflags(obj) if userflags_override is None else userflags_override
    skip_uv_compression = (
        options.skip_uv_compression
        if skip_uv_compression_override is None
        else skip_uv_compression_override
    )
    base_name = sanitize(obj_name)
    export_name = _build_export_mesh_stem(base_name, skip_uv_compression)
    meb_path = output_dir / f"{export_name}.meb"
    print(
        f"Exporting {obj_name} to MEB... (tangents={options.generate_tangent_space}, "
        f"bodywork={options.bodywork_data}, UVs={options.uv_map_indices}, skip_uv_comp={skip_uv_compression})"
    )

    extracted_data = extract_mesh_data_from_blender(
        obj,
        options,
        log_prefix=export_name,
    )
    validation_issue, skip_export = _validate_extracted_mesh(export_name, extracted_data)
    if validation_issue:
        mesh_validation_issues.append(validation_issue)
    if skip_export:
        print(f"Skipping {export_name} MEB export due to vertex limit")
        return

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
    pending_exports.append(
        _PendingObjectExport(
            name=export_name,
            meb_path=meb_path,
            translation=translation,
            quaternion=quaternion,
            materials=material_names,
            userflags=userflags,
            future=writer_pool.submit(
                write_meb_file,
                output_path=meb_path,
                mesh_name=export_name,
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
                log_prefix=export_name,
            ),
        )
    )

    if len(pending_exports) >= max_in_flight:
        _complete_next_pending_export(pending_exports, objects)


def _collect_export_entries(source_objects, context, include_non_mesh_skips: bool):
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
            elif include_non_mesh_skips:
                skipped_objects.append(f"{obj.name} (empty mesh)")
            continue

        if obj.type != "CURVE":
            if include_non_mesh_skips:
                skipped_objects.append(f"{obj.name} ({obj.type})")
            continue

        if obj.data.bevel_depth <= 0:
            if include_non_mesh_skips:
                skipped_objects.append(f"{obj.name} (curve without bevel depth)")
            continue

        depsgraph = context.evaluated_depsgraph_get()
        with skip_viewport_disabled_modifiers(obj):
            eval_obj = obj.evaluated_get(depsgraph)
            try:
                mesh_data = bpy.data.meshes.new_from_object(
                    eval_obj, preserve_all_data_layers=True, depsgraph=depsgraph
                )
            except TypeError:
                eval_mesh = eval_obj.to_mesh()
                if not eval_mesh:
                    mesh_data = None
                else:
                    mesh_data = eval_mesh.copy()
                    eval_obj.to_mesh_clear()

        if not mesh_data or not mesh_data.polygons:
            if mesh_data:
                bpy.data.meshes.remove(mesh_data)
            print(f"Skipping {obj.name} - curve could not be converted to mesh")
            if include_non_mesh_skips:
                skipped_objects.append(f"{obj.name} (curve conversion failed)")
            continue

        tag_temp_export_datablock(mesh_data)
        temp_curve_mesh = bpy.data.objects.new(f"TEMP_CURVE_MESH_{obj.name}", mesh_data)
        tag_temp_export_datablock(temp_curve_mesh)
        context.scene.collection.objects.link(temp_curve_mesh)
        temp_curve_mesh.matrix_world = obj.matrix_world.copy()
        for mat in effective_materials_for_object(obj, getattr(obj.data, "materials", [])) or []:
            temp_curve_mesh.data.materials.append(mat)
        temp_objects_to_cleanup.append(temp_curve_mesh)
        export_entries.append((temp_curve_mesh, obj.name))

    return export_entries, temp_objects_to_cleanup, skipped_objects


def export_single_meb_set(filepath: str, context, settings: SingleMebExportSettings):
    output_path = Path(filepath)
    output_dir = output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    track_name = output_dir.name if output_dir.name else output_path.stem

    mesh_validation_issues = []
    exported_count = 0
    all_materials = []
    temp_objects_to_cleanup = []
    skipped_objects = []

    original_selection = context.selected_objects[:]
    original_active = context.active_object
    original_mesh_bindings = _snapshot_original_mesh_bindings()

    try:
        source_objects = (
            list(iter_visible_scene_objects(context.view_layer))
            if settings.export_scope == "ALL"
            else list(context.selected_objects)
        )
        export_entries, temp_objects_to_cleanup, skipped_objects = _collect_export_entries(
            source_objects, context, include_non_mesh_skips=True
        )
        print(
            f"Single MEB export: {len(export_entries)} object(s), "
            f"scope={settings.export_scope}, transform_mode={settings.transform_mode}"
        )
        if export_entries:
            source_meshes = [obj for obj, _ in export_entries]
            combined_obj, _, _ = combine_objects_into_mesh(
                source_meshes,
                output_path.stem,
                context,
                "SINGLE_MEB",
                bake_world_transform=settings.transform_mode == "APPLY",
            )
            if combined_obj:
                temp_objects_to_cleanup.append(combined_obj)
                options = _build_maybe_overridden_options(combined_obj, "")
                options.vertex_transform_mode = "NONE"
                options.flip_coordinates = False
                options.skip_uv_compression = _get_group_skip_uv_compression("Single MEB export", source_meshes)

                mesh_stem = _build_export_mesh_stem(output_path.stem, options.skip_uv_compression)
                meb_path = output_path.with_name(f"{mesh_stem}.meb")
                mesh_name = sanitize(mesh_stem)
                extracted_data = extract_mesh_data_from_blender(
                    combined_obj,
                    options,
                    log_prefix=mesh_name,
                )
                validation_issue, skip_export = _validate_extracted_mesh(mesh_name, extracted_data)
                if validation_issue:
                    mesh_validation_issues.append(validation_issue)
                if not skip_export:
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
                    write_meb_file(
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
                        log_prefix=mesh_name,
                    )
                    exported_count = 1
                    all_materials.extend(extracted_data[4])
                    print(f"Successfully exported combined mesh -> {meb_path.name}")
                else:
                    print("Skipping combined MEB export due to vertex limit")

        unique_materials = sorted(set(all_materials))
        if unique_materials:
            texture_mapping = {}
            if settings.export_textures:
                texture_export_dir = output_dir.parent / "textures" / track_name
                print(f"Texture export directory: {texture_export_dir}")
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
        if temp_objects_to_cleanup:
            _remove_temp_export_data(temp_objects_to_cleanup)
        _restore_selection(context, original_selection, original_active)

    return {
        "status": "FINISHED",
        "exported": exported_count,
        "materials": len(sorted(set(all_materials))),
        "skipped_objects": len(skipped_objects),
        "skipped_object_names": skipped_objects[:10],
        "mesh_warnings": _build_mesh_validation_summary(mesh_validation_issues),
    }


def export_objects_to_meb(
    context,
    output_dir: Path,
    resource_prefix: str,
    mesh_validation_issues: List[_MeshValidationIssue],
) -> List[ObjectInfo]:
    objects = []
    temp_objects_to_cleanup = []
    original_mesh_bindings = _snapshot_original_mesh_bindings()
    original_selection = context.selected_objects[:]
    original_active = context.active_object

    writer_workers = max(1, min(4, os.cpu_count() or 1))
    max_in_flight = writer_workers * 2

    try:
        with ThreadPoolExecutor(max_workers=writer_workers) as writer_pool:
            pending_exports = deque()
            bpy.ops.object.select_all(action="DESELECT")

            source_objects = list(iter_visible_scene_objects(context.view_layer))
            export_entries, temp_seen, _ = _collect_export_entries(
                source_objects, context, include_non_mesh_skips=False
            )
            temp_objects_to_cleanup.extend(temp_seen)
            print(f"Found {len(export_entries)} visible exportable objects (meshes + beveled curves)")

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

            print(
                f"Grouped: {len(kstree_groups)} KSTREE groups, {len(sms_groups)} SMS groups, "
                f"{len(ungrouped_objects)} ungrouped objects"
            )

            for group_id, group_objects in kstree_groups.items():
                try:
                    name = f"KSTREE_GROUP_{group_id}"
                    print(f"Processing {name} ({len(group_objects)} objects)...")
                    combined_obj, _, _ = combine_objects_into_mesh(
                        group_objects, group_id, context, "KSTREE_GROUP"
                    )
                    if combined_obj:
                        temp_objects_to_cleanup.append(combined_obj)
                        _queue_object_export(
                            combined_obj,
                            name,
                            output_dir,
                            resource_prefix,
                            pending_exports,
                            writer_pool,
                            mesh_validation_issues,
                            objects,
                            max_in_flight,
                            userflags_override=_get_group_userflags(name, group_objects),
                            skip_uv_compression_override=_get_group_skip_uv_compression(name, group_objects),
                        )
                except Exception as e:
                    _log_export_error(f"Failed to process KSTREE_GROUP_{group_id}", e)

            for group_name, group_objects in sms_groups.items():
                try:
                    name = f"SMS_GRP_{group_name}"
                    print(f"Processing {name} ({len(group_objects)} objects)...")
                    combined_obj, _, _ = combine_objects_into_mesh(
                        group_objects, group_name, context, "SMS_GRP"
                    )
                    if combined_obj:
                        temp_objects_to_cleanup.append(combined_obj)
                        _queue_object_export(
                            combined_obj,
                            name,
                            output_dir,
                            resource_prefix,
                            pending_exports,
                            writer_pool,
                            mesh_validation_issues,
                            objects,
                            max_in_flight,
                            userflags_override=_get_group_userflags(name, group_objects),
                            skip_uv_compression_override=_get_group_skip_uv_compression(name, group_objects),
                        )
                except Exception as e:
                    _log_export_error(f"Failed to process SMS_GRP_{group_name}", e)

            for obj, source_name in ungrouped_objects:
                try:
                    _queue_object_export(
                        obj,
                        source_name,
                        output_dir,
                        resource_prefix,
                        pending_exports,
                        writer_pool,
                        mesh_validation_issues,
                        objects,
                        max_in_flight,
                    )
                except Exception as e:
                    _log_export_error(f"Failed to export {source_name}", e)

            while pending_exports:
                _complete_next_pending_export(pending_exports, objects)
    finally:
        _restore_original_mesh_bindings(original_mesh_bindings)
        if temp_objects_to_cleanup:
            print(f"Cleaning up {len(temp_objects_to_cleanup)} temporary objects...")
            _remove_temp_export_data(temp_objects_to_cleanup)
        _restore_selection(context, original_selection, original_active)

    return objects


def prepare_texture_mapping(
    material_names: list,
    mtx_dir: Path,
    texture_export_dir: Path,
    track_name: str,
    context,
):
    def _relative_texture_path(texture_name: str) -> str:
        if mtx_dir.parent.name.lower() == "tracks":
            return f"tracks\\textures\\{track_name}\\{texture_name}"
        try:
            rel_path = texture_export_dir.relative_to(mtx_dir.parent)
            return str(rel_path / texture_name).replace("/", "\\")
        except ValueError:
            return f"textures\\{track_name}\\{texture_name}"

    texture_mapping = {}
    material_lookup = {sanitize(mat.name): mat for mat in bpy.data.materials}

    for mat_name in material_names:
        blender_material = material_lookup.get(mat_name)
        if not blender_material or not hasattr(blender_material, "mtx_settings"):
            continue

        mtx = blender_material.mtx_settings
        for param in mtx.shader_params:
            if param.param_type != "EPT_TEXTURE" or not param.texture_value:
                continue
            src_path, exists = resolve_texture_path(param.texture_value, context)
            if exists and src_path:
                game_relative_path = _relative_texture_path(src_path.name)
                texture_mapping[(mat_name, param.name)] = (str(src_path), game_relative_path)
                print(f"  Mapped {mat_name}.{param.name}: {game_relative_path}")
            else:
                print(f"  Warning: Texture not found for {mat_name}.{param.name}: {param.texture_value}")
    return texture_mapping


def export_textures(texture_mapping: dict, texture_export_dir: Path):
    texture_export_dir.mkdir(parents=True, exist_ok=True)
    texture_count = 0
    copied_files = set()
    for (_mat_name, _param_name), (src_path_str, _game_path) in texture_mapping.items():
        src_path = Path(src_path_str)
        if not src_path.exists():
            print(f"  Warning: Source texture no longer exists: {src_path}")
            continue

        dest_path = texture_export_dir / src_path.name
        if dest_path in copied_files:
            continue
        try:
            shutil.copy2(src_path, dest_path)
            texture_count += 1
            copied_files.add(dest_path)
            print(f"  Copied texture: {src_path.name}")
        except Exception as e:
            print(f"  Failed to copy texture {src_path.name}: {e}")
    print(f"Exported {texture_count} textures to {texture_export_dir}")


def build_sgx(objects: List[ObjectInfo], dest_path: Path, resource_prefix: str = ""):
    if not objects:
        zero = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        scene_min, scene_max = zero.copy(), zero.copy()
    else:
        first = objects[0]
        scene_min = first.translation + first.bb_min
        scene_max = first.translation + first.bb_max
        for obj in objects[1:]:
            scene_min = np.minimum(scene_min, obj.translation + obj.bb_min)
            scene_max = np.maximum(scene_max, obj.translation + obj.bb_max)
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
        lod_node = ET.SubElement(
            obj_elem,
            "NODE",
            type="LOD",
            Name=obj.name,
            MatrixNumber="-1",
            matrices="1",
            subobjects="1",
        )
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
        ET.SubElement(lod_node, "CONTROL", Distances="1000 ")
        node = ET.SubElement(
            lod_node,
            "NODE",
            type="OBJECT",
            Name=obj.name,
            MatrixNumber="0",
            instances="1",
            userflags=str(obj.userflags),
        )
        if obj.meb_path.name != obj.name + ".meb":
            resource_filename = str(obj.meb_path).replace("\\", "/").lstrip("/")
        else:
            resource_filename = f"{resource_prefix}{obj.meb_path.name}"
        ET.SubElement(node, "RESOURCE", Filename=resource_filename)
        ET.SubElement(
            node,
            "SPHERE",
            Centre=f"{cx:.6f} {cy:.6f} {cz:.6f} 1.000000",
            Radius=f"{obj.sphere_radius:.6f}",
        )
        obj_id += 1

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
    ET.ElementTree(scene).write(dest_path, encoding="utf-8", xml_declaration=True)


def export_madness_scene(filepath: str, resource_prefix: str, placeholder_mtx: Path, context):
    _ = placeholder_mtx
    output_dir = Path(filepath).parent
    sgx_path = Path(filepath)
    track_name = sgx_path.stem

    with tempfile.TemporaryDirectory() as temp_dir_str:
        print(f"Using temporary directory: {Path(temp_dir_str)}")
        mesh_validation_issues = []

        print("Exporting mesh objects to MEB...")
        objects = export_objects_to_meb(context, output_dir, resource_prefix, mesh_validation_issues)
        print(f"MEB export completed. Exported {len(objects)} objects")

        all_materials = []
        for obj in objects:
            all_materials.extend(obj.materials)

        print("Collecting Empty objects with MEB references...")
        empty_data = collect_empty_objects_with_meb(context)
        print(f"Found {len(empty_data)} Empty objects with MEB references")

        print("Processing Empty objects with MEB references...")
        for obj_name, meb_path, translation, quaternion, sphere_radius, userflags in empty_data:
            objects.append(
                ObjectInfo(
                    name=obj_name,
                    meb_path=meb_path,
                    translation=translation,
                    quaternion=quaternion,
                    sphere_center=np.array([0, 0, 0]),
                    sphere_radius=sphere_radius,
                    materials=["DefaultMaterial"],
                    bb_min=np.array([-sphere_radius, -sphere_radius, -sphere_radius]),
                    bb_max=np.array([sphere_radius, sphere_radius, sphere_radius]),
                    userflags=userflags,
                )
            )
            print(f"Added Empty object: {obj_name} -> {meb_path} (radius: {sphere_radius})")

        print(
            f"Total objects: {len(objects)} "
            f"({len(objects) - len(empty_data)} compiled, {len(empty_data)} referenced)"
        )

        material_to_objects = {}
        for obj in objects:
            for mat_name in obj.materials:
                material_to_objects.setdefault(mat_name, []).append(obj.name)

        texture_export_dir = output_dir.parent / "textures" / track_name
        print(f"Texture export directory: {texture_export_dir}")
        unique_materials = sorted(set(all_materials))
        texture_warning_summary = summarize_texture_warnings_for_material_names(set(unique_materials), context)
        for detail in texture_warning_summary.get("details", []):
            users = material_to_objects.get(detail["material"], [])
            detail["objects"] = sorted(set(users))[:3] or ["<unknown object>"]

        print("Preparing texture mapping...")
        texture_mapping = (
            prepare_texture_mapping(unique_materials, output_dir, texture_export_dir, track_name, context)
            if unique_materials
            else {}
        )

        print("Generating MTX files...")
        prepare_mtx_files_from_materials(unique_materials, output_dir, context, track_name, texture_mapping)
        print(f"Generated {len(unique_materials)} material files")

        if texture_mapping:
            export_textures(texture_mapping, texture_export_dir)

        print("Generating SGX file...")
        build_sgx(objects, sgx_path, resource_prefix)
        print(f"Generated SGX file: {sgx_path}")

    return {
        "status": "FINISHED",
        "texture_warnings": texture_warning_summary,
        "mesh_warnings": _build_mesh_validation_summary(mesh_validation_issues),
    }


__all__ = [
    "SingleMebExportSettings",
    "export_single_meb_set",
    "export_objects_to_meb",
    "export_madness_scene",
    "prepare_texture_mapping",
    "export_textures",
    "build_sgx",
]
