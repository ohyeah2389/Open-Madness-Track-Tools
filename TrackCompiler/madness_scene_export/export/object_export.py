import bpy  # type: ignore
import bmesh  # type: ignore
from pathlib import Path
from typing import Iterable, List, Tuple
import numpy as np
import re
import traceback
from contextlib import contextmanager
from ..utils.coordinate_transforms import decompose_matrix
from ..utils import effective_materials_for_object, sanitize
from ..settings.userflags import DEFAULT_USERFLAGS

TEMP_EXPORT_TAG = "_omtt_temp_export"
TEMP_EXPORT_PREFIXES = ("TEMP_MESH", "TEMP_CURVE_MESH", "TEMP_COMBINED")


@contextmanager
def skip_viewport_disabled_modifiers(obj):
    overrides = []
    for modifier in getattr(obj, "modifiers", []):
        if (not getattr(modifier, "show_viewport", True)) and getattr(modifier, "show_render", False):
            overrides.append((modifier, modifier.show_render))
            modifier.show_render = False
    try:
        yield
    finally:
        for modifier, show_render in overrides:
            try:
                modifier.show_render = show_render
            except ReferenceError:
                pass


def tag_temp_export_datablock(datablock):
    """Mark an object or mesh as exporter-owned scratch data."""
    datablock[TEMP_EXPORT_TAG] = True


def is_temp_export_datablock(datablock) -> bool:
    if not datablock:
        return False
    return bool(datablock.get(TEMP_EXPORT_TAG, False))


def is_temp_export_name(name: str) -> bool:
    return name.split(".", 1)[0].startswith(TEMP_EXPORT_PREFIXES)


def has_temp_export_name(datablock) -> bool:
    if not datablock:
        return False
    return is_temp_export_name(datablock.name)


class ObjectInfo:
    def __init__(
        self,
        name: str,
        meb_path: Path,
        translation: np.ndarray,
        quaternion: np.ndarray,
        sphere_center: np.ndarray,
        sphere_radius: float,
        materials: List[str],
        bb_min: np.ndarray = np.array([0, 0, 0]),
        bb_max: np.ndarray = np.array([0, 0, 0]),
        userflags: int = DEFAULT_USERFLAGS,
    ):
        self.name = name
        self.meb_path = meb_path
        self.translation = translation
        self.quaternion = quaternion
        self.sphere_center = sphere_center
        self.sphere_radius = sphere_radius
        self.materials = materials
        self.bb_min = bb_min
        self.bb_max = bb_max
        self.userflags = userflags


def _iter_visible_layer_collections(root_layer_collection):
    """Yield only layer collections that are visible in the current view layer."""
    stack = [root_layer_collection]
    while stack:
        layer_collection = stack.pop()
        collection = layer_collection.collection
        if (layer_collection.exclude):
            continue
        yield layer_collection
        stack.extend(layer_collection.children)


def iter_visible_scene_objects(view_layer) -> Iterable:
    """Yield unique objects from visible layer collections only."""
    seen = set()
    for layer_collection in _iter_visible_layer_collections(view_layer.layer_collection):
        for obj in layer_collection.collection.objects:
            obj_ptr = obj.as_pointer()
            if obj_ptr in seen:
                continue
            seen.add(obj_ptr)
            yield obj


def parse_kstree_group(obj_name: str) -> str:
    """Extract group identifier from KSTREE_GROUP_XYZ_ prefixed object names.

    Returns the XYZ part if it matches the pattern, empty string otherwise.
    """
    match = re.match(r"^KSTREE_GROUP_([^_]+)_", obj_name)
    return match.group(1) if match else ""


def parse_sms_group(obj_name: str) -> str:
    """Extract group identifier from SMS_GRP_groupname_ prefixed object names.

    Returns the groupname part if it matches the pattern, empty string otherwise.
    """
    match = re.match(r"^SMS_GRP_([^_]+)_", obj_name)
    return match.group(1) if match else ""


def combine_objects_into_mesh(
    objects: List,
    group_name: str,
    context,
    group_type: str = "KSTREE_GROUP",
    bake_world_transform: bool = True,
) -> Tuple:
    """Combine multiple objects into a single temporary mesh object using fast join operations.

    Returns: (combined_object, combined_materials, combined_transform_data)
    """
    if not objects:
        return None, [], None

    print(f"Combining {len(objects)} objects for group {group_name}...")

    bm = bmesh.new()
    source_meshes_to_cleanup = []

    try:
        depsgraph = context.evaluated_depsgraph_get()
        # Build unified material list from all objects to combine
        combined_materials = []
        material_mapping = {}  # sanitized material name -> new_index

        for obj in objects:
            source_materials = effective_materials_for_object(obj, getattr(obj.data, "materials", []))
            if source_materials:
                for mat in source_materials:
                    mat_key = sanitize(mat.name) if mat else "DefaultMaterial"
                    if mat_key not in material_mapping:
                        material_mapping[mat_key] = len(combined_materials)
                        combined_materials.append((mat, obj.name))

        print(f"  Combined materials: {[mat.name if mat else 'None' for mat, _ in combined_materials]}")

        for obj in objects:
            mesh_data = None
            with skip_viewport_disabled_modifiers(obj):
                eval_obj = obj.evaluated_get(depsgraph)
                try:
                    mesh_data = bpy.data.meshes.new_from_object(
                        eval_obj, preserve_all_data_layers=True, depsgraph=depsgraph
                    )
                except TypeError:
                    eval_mesh = eval_obj.to_mesh()
                    if eval_mesh:
                        mesh_data = eval_mesh.copy()
                        eval_obj.to_mesh_clear()

            if not mesh_data or not mesh_data.polygons:
                if mesh_data:
                    bpy.data.meshes.remove(mesh_data)
                continue
            tag_temp_export_datablock(mesh_data)

            if bake_world_transform:
                # Bake world transform into vertex positions so merged object can stay at identity.
                mesh_data.transform(obj.matrix_world)

            # Remap material slots to the shared group material layout.
            source_materials = effective_materials_for_object(obj, list(mesh_data.materials))
            source_material_indices = [poly.material_index for poly in mesh_data.polygons]
            mesh_data.materials.clear()
            for mat, _ in combined_materials:
                mesh_data.materials.append(mat)

            if combined_materials:
                for poly, src_idx in zip(mesh_data.polygons, source_material_indices):
                    src_mat = source_materials[src_idx] if src_idx < len(source_materials) else None
                    src_key = sanitize(src_mat.name) if src_mat else "DefaultMaterial"
                    poly.material_index = material_mapping.get(src_key, 0)

            bm.from_mesh(mesh_data)
            source_meshes_to_cleanup.append(mesh_data)

        if not bm.verts:
            bm.free()
            return None, [], None

        combined_mesh = bpy.data.meshes.new(f"TEMP_COMBINED_{group_name}")
        tag_temp_export_datablock(combined_mesh)
        bm.to_mesh(combined_mesh)
        bm.free()
        combined_mesh.update()

        for mat, _ in combined_materials:
            combined_mesh.materials.append(mat)

        combined_obj = bpy.data.objects.new(f"TEMP_COMBINED_OBJECT_{group_name}", combined_mesh)
        tag_temp_export_datablock(combined_obj)
        context.collection.objects.link(combined_obj)

        # Verify material assignments
        invalid_faces = []
        for poly in combined_obj.data.polygons:
            if poly.material_index >= len(combined_obj.data.materials):
                invalid_faces.append(poly.index)

        if invalid_faces:
            print(f"  Fixed {len(invalid_faces)} invalid material indices")
            for poly_idx in invalid_faces:
                combined_obj.data.polygons[poly_idx].material_index = 0

        # Calculate transform data for the combined object at origin
        combined_obj.location = (0, 0, 0)
        combined_obj.rotation_euler = (0, 0, 0)
        combined_obj.scale = (1, 1, 1)

        matrix = np.array(combined_obj.matrix_world.copy())
        translation, quaternion = decompose_matrix(matrix)

        # Get material names
        material_names = []
        if combined_obj.data.materials:
            for mat in combined_obj.data.materials:
                if mat:
                    material_names.append(sanitize(mat.name))
                else:
                    material_names.append("DefaultMaterial")
        else:
            material_names.append("DefaultMaterial")

        print(f"Successfully combined {len(objects)} objects into {combined_obj.name}")
        return combined_obj, material_names, (translation, quaternion)

    except Exception as e:
        print(f"Error combining objects: {e}")
        traceback.print_exc()
        return None, [], None
    finally:
        if bm.is_valid:
            bm.free()
        for mesh_data in source_meshes_to_cleanup:
            try:
                bpy.data.meshes.remove(mesh_data)
            except ReferenceError:
                pass


def collect_empty_objects_with_meb(context):
    """Collect Empty objects with MEB references from visible collections.

    Returns: List of (object_name, meb_path, translation, quaternion, sphere_radius, userflags)
    """
    results = []

    for obj in iter_visible_scene_objects(context.view_layer):
        if obj.type != "EMPTY":
            continue

        if obj.hide_get():
            continue

        # Check if this Empty has MEB reference settings
        if not hasattr(obj, 'empty_meb_settings') or not obj.empty_meb_settings.meb_file_path:
            continue

        # Convert absolute path to relative game path
        from ..settings.empty_meb_settings import convert_to_relative_game_path

        # Convert MEB path using path pattern detection
        meb_file_path = obj.empty_meb_settings.meb_file_path
        relative_meb_path = convert_to_relative_game_path(
            meb_file_path, obj.empty_meb_settings.path_pattern
        )

        if relative_meb_path.startswith("UNKNOWN_PATH/"):
            # Fallback: use just the filename
            relative_meb_path = Path(obj.empty_meb_settings.meb_file_path).name

        # Get transformation data
        world_matrix = obj.matrix_world.copy()
        translation, quaternion = decompose_matrix(np.array(world_matrix))

        # Get sphere radius for MEB object
        sphere_radius = getattr(obj.empty_meb_settings, 'sphere_radius', 1.0)

        # Get userflags
        from ..settings.userflags import bool_vector_to_userflags
        userflags = bool_vector_to_userflags(obj.empty_meb_settings.userflags)

        results.append((
            obj.name,
            relative_meb_path,
            translation,
            quaternion,
            sphere_radius,
            userflags,
        ))

    return results
