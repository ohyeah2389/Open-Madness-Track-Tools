import bpy  # type: ignore
from pathlib import Path
from typing import List, Tuple
import numpy as np
import re
from ..utils.coordinate_transforms import decompose_matrix
from ..utils import sanitize


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
        userflags: int = 0b10000000000100000001000001110101,
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


def is_collection_visible(collection, view_layer):
    """Check if a collection is visible in the view layer, considering hierarchy."""
    if collection.name in view_layer.layer_collection.children:
        layer_collection = view_layer.layer_collection.children[collection.name]
    else:
        layer_collection = find_layer_collection(
            view_layer.layer_collection, collection
        )

    if not layer_collection:
        return False

    if layer_collection.exclude:
        return False

    parent = layer_collection
    while parent.collection != view_layer.layer_collection.collection:
        parent = get_parent_layer_collection(view_layer.layer_collection, parent)
        if parent and parent.exclude:
            return False

    return True


def find_layer_collection(layer_collection, target_collection):
    """Recursively find a layer collection for a given collection."""
    if layer_collection.collection == target_collection:
        return layer_collection

    for child in layer_collection.children:
        result = find_layer_collection(child, target_collection)
        if result:
            return result

    return None


def get_parent_layer_collection(root_layer_collection, target_layer_collection):
    """Find the parent layer collection of a given layer collection."""
    for child in root_layer_collection.children:
        if child == target_layer_collection:
            return root_layer_collection

        parent = get_parent_layer_collection(child, target_layer_collection)
        if parent:
            return parent

    return None


def is_object_in_visible_collection(obj, view_layer):
    """Check if an object is in any visible collection."""
    for collection in obj.users_collection:
        if is_collection_visible(collection, view_layer):
            return True

    if not obj.users_collection:
        return not view_layer.layer_collection.exclude

    return False


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


def combine_objects_into_mesh(objects: List, group_name: str, context, group_type: str = "KSTREE_GROUP") -> Tuple:
    """Combine multiple objects into a single temporary mesh object using fast join operations.

    Returns: (combined_object, combined_materials, combined_transform_data)
    """
    import mathutils  # type: ignore

    if not objects:
        return None, [], None

    print(f"Combining {len(objects)} objects for group {group_name}...")

    try:
        original_active = context.active_object

        # Clear selection
        bpy.ops.object.select_all(action="DESELECT")

        # Build unified material list from all objects to combine
        combined_materials = []
        material_mapping = {}  # old_material -> new_index

        for obj in objects:
            if obj.data.materials:
                for mat in obj.data.materials:
                    if mat and mat not in [m for m, _ in combined_materials]:
                        material_mapping[mat] = len(combined_materials)
                        combined_materials.append((mat, obj.name))

        print(f"  Combined materials: {[mat.name if mat else 'None' for mat, _ in combined_materials]}")

        # Create copies of all objects with applied transforms and modifiers
        temp_objects = []

        for obj in objects:
            temp_obj = obj.copy()
            temp_obj.data = obj.data.copy()
            temp_obj.name = f"TEMP_COMBINE_{obj.name}"

            # Link to scene
            context.collection.objects.link(temp_obj)
            temp_objects.append(temp_obj)

            # Apply world transform
            temp_obj.matrix_world = obj.matrix_world

        if not temp_objects:
            return None, [], None

        # Apply modifiers only to objects that actually have them
        for temp_obj in temp_objects:
            if temp_obj.modifiers:
                bpy.ops.object.select_all(action="DESELECT")
                temp_obj.select_set(True)
                context.view_layer.objects.active = temp_obj

                modifier_count = len(temp_obj.modifiers)
                try:
                    # Apply the first modifier until none are left
                    while temp_obj.modifiers:
                        bpy.ops.object.modifier_apply(modifier=temp_obj.modifiers[0].name)
                    print(f"  Applied {modifier_count} modifiers to {temp_obj.name}")
                except Exception as e:
                    print(f"  Warning: Could not apply modifiers to {temp_obj.name}: {e}")

        # Select all temp objects for joining
        bpy.ops.object.select_all(action="DESELECT")
        for temp_obj in temp_objects:
            temp_obj.select_set(True)

        # Set the first object as active
        context.view_layer.objects.active = temp_objects[0]

        # Apply transforms to all objects first
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

        # Join all objects into the first one
        bpy.ops.object.join()

        # The combined object is now the active object
        combined_obj = context.active_object
        combined_obj.name = f"COMBINED_{group_name}"
        combined_obj.data.name = f"TEMP_COMBINED_{group_name}"

        # Store original material assignments before clearing
        original_material_indices = {}
        if combined_obj.data.materials:
            for poly in combined_obj.data.polygons:
                original_material_indices[poly.index] = poly.material_index

        # Clear materials and reassign based on our unified list
        combined_obj.data.materials.clear()
        for mat, source_obj in combined_materials:
            combined_obj.data.materials.append(mat)

        # Fix material indices based on original assignments
        for poly_idx, original_idx in original_material_indices.items():
            if original_idx < len(combined_materials):
                combined_obj.data.polygons[poly_idx].material_index = original_idx

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

        world_matrix = combined_obj.matrix_world.copy()
        world_location, world_rotation, world_scale = world_matrix.decompose()

        import mathutils  # type: ignore

        loc_matrix = mathutils.Matrix.Translation(world_location)
        rot_matrix = world_rotation.to_matrix().to_4x4()
        transform_matrix = loc_matrix @ rot_matrix

        matrix = np.array(transform_matrix)
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

        # Restore original selection
        bpy.ops.object.select_all(action="DESELECT")
        if original_active and original_active.name in bpy.data.objects:
            context.view_layer.objects.active = original_active

        print(f"Successfully combined {len(objects)} objects into {combined_obj.name}")
        return combined_obj, material_names, (translation, quaternion)

    except Exception as e:
        print(f"Error combining objects: {e}")
        import traceback

        traceback.print_exc()
        return None, [], None


def collect_empty_objects_with_meb(context):
    """Collect Empty objects with MEB references from visible collections.

    Returns: List of (object_name, meb_path, translation, quaternion, sphere_radius, userflags)
    """
    view_layer = context.view_layer
    results = []

    for obj in context.scene.objects:
        if obj.type != "EMPTY":
            continue

        if not is_object_in_visible_collection(obj, view_layer):
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
        from ..settings.empty_meb_settings import get_empty_userflags_value
        userflags = get_empty_userflags_value(obj.empty_meb_settings)

        results.append((
            obj.name,
            relative_meb_path,
            translation,
            quaternion,
            sphere_radius,
            userflags,
        ))

    return results
