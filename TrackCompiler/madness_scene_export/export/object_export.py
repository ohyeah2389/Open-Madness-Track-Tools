import bpy  # type: ignore
from pathlib import Path
from typing import List, Tuple
import numpy as np
import re
from ..utils.coordinate_transforms import decompose_matrix
from ..utils import sanitize


# Core export logic
class ObjectInfo:
    def __init__(
        self,
        name: str,
        fbx_path: Path,
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
        self.fbx_path = fbx_path
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
    match = re.match(r"KSTREE_GROUP_([^_]+)_", obj_name)
    return match.group(1) if match else ""


def parse_sms_group(obj_name: str) -> str:
    """Extract group identifier from SMS_GRP_groupname_ prefixed object names.

    Returns the groupname part if it matches the pattern, empty string otherwise.
    Examples: SMS_GRP_trees_objectname.024 -> "trees"
    """
    match = re.match(r"SMS_GRP_([^_]+)_", obj_name)
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
        # Store original selection
        original_selection = context.selected_objects[:]
        original_active = context.active_object

        # Clear selection
        bpy.ops.object.select_all(action="DESELECT")

        # Build unified material list from all objects to combine
        combined_materials = []
        material_name_to_obj = {}  # Track which materials we've seen
        
        if objects:
            # Collect all unique materials from all objects, preserving order
            for obj in objects:
                if obj.data.materials:
                    for mat in obj.data.materials:
                        mat_name = mat.name if mat else "None"
                        if mat_name not in material_name_to_obj:
                            combined_materials.append(mat)
                            material_name_to_obj[mat_name] = mat
                            print(f"  Added material '{mat_name}' to combined list")
                else:
                    # Object has no materials, add default if not already present
                    if "None" not in material_name_to_obj:
                        combined_materials.append(None)
                        material_name_to_obj["None"] = None
                        print(f"  Added default material to combined list")
        
        if not combined_materials:
            combined_materials.append(None)  # Fallback default material
            
        print(f"  Final combined materials: {[mat.name if mat else 'None' for mat in combined_materials]}")

        # Create copies of all objects with applied transforms and modifiers
        temp_objects = []

        for obj in objects:
            # Create a copy
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
        objects_with_modifiers = [obj for obj in temp_objects if obj.modifiers]
        
        if objects_with_modifiers:
            print(f"  Applying modifiers to {len(objects_with_modifiers)} out of {len(temp_objects)} objects...")
            import gc
            
            for i, temp_obj in enumerate(objects_with_modifiers):
                print(f"  Processing object {i+1}/{len(objects_with_modifiers)}: {temp_obj.name} ({len(temp_obj.modifiers)} modifiers)")
                
                bpy.ops.object.select_all(action="DESELECT")
                temp_obj.select_set(True)
                context.view_layer.objects.active = temp_obj
                
                try:
                    # Create a new mesh with modifiers applied using bmesh
                    import bmesh  # type: ignore
                    
                    # Force garbage collection before intensive operation
                    gc.collect()
                    
                    # Get the evaluated mesh with error handling
                    depsgraph = context.evaluated_depsgraph_get()
                    if not depsgraph:
                        print(f"    Warning: Could not get depsgraph for {temp_obj.name}, skipping modifiers")
                        continue
                        
                    evaluated_obj = temp_obj.evaluated_get(depsgraph)
                    if not evaluated_obj:
                        print(f"    Warning: Could not get evaluated object for {temp_obj.name}, skipping modifiers")
                        continue
                        
                    evaluated_mesh = evaluated_obj.to_mesh()
                    if not evaluated_mesh:
                        print(f"    Warning: Could not get evaluated mesh for {temp_obj.name}, skipping modifiers")
                        continue
                    
                    # Create a new mesh and copy data using bmesh
                    new_mesh = bpy.data.meshes.new(f"MODIFIED_{temp_obj.data.name}")
                    
                    # Use bmesh to copy the mesh data properly with error handling
                    bm = bmesh.new()
                    try:
                        bm.from_mesh(evaluated_mesh)
                        bm.to_mesh(new_mesh)
                    finally:
                        bm.free()  # Always free bmesh
                    
                    # Copy materials from the evaluated mesh to the new mesh
                    for mat in evaluated_mesh.materials:
                        new_mesh.materials.append(mat)
                    
                    # Replace the object's mesh
                    old_mesh = temp_obj.data
                    temp_obj.data = new_mesh
                    
                    # Clean up immediately
                    try:
                        evaluated_obj.to_mesh_clear()
                    except:
                        pass  # Sometimes this fails, but it's not critical
                        
                    bpy.data.meshes.remove(old_mesh)
                    
                    # Clear modifiers since they're now baked into the mesh
                    temp_obj.modifiers.clear()
                    
                    print(f"    Successfully applied modifiers to {temp_obj.name}")
                    
                    # Force cleanup after each object to prevent memory buildup
                    gc.collect()
                    
                except Exception as e:
                    print(f"  ERROR: Failed to apply modifiers to {temp_obj.name}: {e}")
                    # Try to continue with other objects
                    import traceback
                    traceback.print_exc()
                    continue
        else:
            print(f"  No modifiers found on any of the {len(temp_objects)} objects, skipping modifier application")

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
        if group_type == "SMS_GRP":
            combined_obj.name = f"{group_name}_COMBINED"
        else:
            combined_obj.name = f"KSTREE_GROUP_{group_name}_COMBINED"
        combined_obj.data.name = f"TEMP_COMBINED_{group_name}"

        # Store original material assignments before clearing
        original_face_materials = []
        if combined_obj.data.polygons and combined_obj.data.materials:
            # Map current material indices to material names
            current_materials = [mat.name if mat else "None" for mat in combined_obj.data.materials]
            print(f"  Current materials before clear: {current_materials}")
            
            for poly in combined_obj.data.polygons:
                if poly.material_index < len(current_materials):
                    mat_name = current_materials[poly.material_index]
                else:
                    mat_name = "None"
                original_face_materials.append(mat_name)
        
        # Clear materials and add combined materials in correct order
        combined_obj.data.materials.clear()
        for mat in combined_materials:
            combined_obj.data.materials.append(mat)
        
        # Remap face material indices to the new unified material list
        if combined_obj.data.polygons and original_face_materials:
            new_material_names = [mat.name if mat else "None" for mat in combined_materials]
            print(f"  New unified materials: {new_material_names}")
            
            remapped_count = 0
            for i, poly in enumerate(combined_obj.data.polygons):
                if i < len(original_face_materials):
                    original_mat_name = original_face_materials[i]
                    # Find the index in the new material list
                    try:
                        new_index = new_material_names.index(original_mat_name)
                        poly.material_index = new_index
                        if poly.material_index != (i % len(new_material_names)):  # Only count actual changes
                            remapped_count += 1
                    except ValueError:
                        # Material not found, use first material
                        poly.material_index = 0
                        remapped_count += 1
                        print(f"    Warning: Material '{original_mat_name}' not found in unified list, using material 0")
            
            print(f"  Remapped {remapped_count} face material assignments")
        
        # Final verification of material assignments
        if combined_obj.data.polygons:
            max_material_index = len(combined_obj.data.materials) - 1
            invalid_faces = 0
            material_usage = {}
            
            for poly in combined_obj.data.polygons:
                mat_idx = poly.material_index
                if mat_idx > max_material_index:
                    print(f"    Warning: Face {poly.index} has invalid material index {mat_idx}, setting to 0")
                    poly.material_index = 0
                    invalid_faces += 1
                    mat_idx = 0
                
                # Count usage
                if mat_idx not in material_usage:
                    material_usage[mat_idx] = 0
                material_usage[mat_idx] += 1
            
            print(f"  Verified material assignments for {len(combined_obj.data.polygons)} faces with {len(combined_obj.data.materials)} materials")
            print(f"  Material usage: {material_usage}")
            if invalid_faces > 0:
                print(f"  Fixed {invalid_faces} invalid material indices")

        # Calculate transform data for the combined object at origin
        combined_obj.location = (0, 0, 0)
        combined_obj.rotation_euler = (0, 0, 0)
        combined_obj.scale = (1, 1, 1)

        world_matrix = combined_obj.matrix_world.copy()
        matrix = np.array(world_matrix)
        translation, quaternion = decompose_matrix(matrix)

        # Get material names
        material_names = []
        if combined_obj.data.materials:
            for mat in combined_obj.data.materials:
                if mat:
                    material_names.append(mat.name)
                else:
                    material_names.append("DefaultMaterial")
        else:
            material_names.append("DefaultMaterial")

        # Restore original selection
        bpy.ops.object.select_all(action="DESELECT")
        for obj in original_selection:
            if obj.name in bpy.data.objects:
                obj.select_set(True)
        if original_active and original_active.name in bpy.data.objects:
            context.view_layer.objects.active = original_active

        print(f"Successfully combined {len(objects)} objects into {combined_obj.name}")
        return combined_obj, material_names, (translation, quaternion)

    except Exception as e:
        print(f"Error combining objects for group {group_name}: {e}")
        import traceback

        traceback.print_exc()
        return None, [], None


def collect_empty_objects_with_meb(context):
    """Collect Empty objects with MEB references from visible collections.

    Returns: List of (object_name, meb_path, translation, quaternion, sphere_radius, userflags)
    """
    results = []
    view_layer = context.view_layer

    for obj in context.scene.objects:
        if obj.type != "EMPTY":
            continue

        if not is_object_in_visible_collection(obj, view_layer):
            continue

        if obj.hide_get():
            print(f"Skipping Empty {obj.name} - object is hidden")
            continue

        # Check if this Empty has MEB reference settings
        if (
            not hasattr(obj, "empty_meb_settings")
            or not obj.empty_meb_settings.meb_file_path
        ):
            print(f"Skipping Empty {obj.name} - no MEB reference set")
            continue

        # Convert absolute path to relative game path
        from ..settings.empty_meb_settings import convert_to_relative_game_path

        # Convert MEB path using path pattern detection
        relative_meb_path = convert_to_relative_game_path(
            obj.empty_meb_settings.meb_file_path
        )

        if relative_meb_path.startswith("UNKNOWN_PATH/"):
            print(
                f"Warning: Could not convert path for {obj.name}: {obj.empty_meb_settings.meb_file_path}"
            )
            # Use the original path as fallback, but make it relative-ish
            relative_meb_path = Path(obj.empty_meb_settings.meb_file_path).name

        # Get transformation data
        world_matrix = obj.matrix_world.copy()
        matrix = np.array(world_matrix)
        translation, quaternion = decompose_matrix(matrix)

        # Get sphere radius for MEB object
        sphere_radius = obj.empty_meb_settings.sphere_radius
        
        # Get userflags from Empty settings
        from ..settings.empty_meb_settings import get_empty_userflags_value
        userflags = get_empty_userflags_value(obj.empty_meb_settings)

        results.append(
            (
                obj.name,
                relative_meb_path,
                translation,
                quaternion,
                sphere_radius,
                userflags,
                obj.empty_meb_settings.meb_file_path,
            )
        )
        print(
            f"Found Empty object {obj.name} with MEB reference: {relative_meb_path} (radius: {sphere_radius})"
        )

    return results



def export_objects_as_fbx(
    context, temp_dir: Path
) -> List[Tuple[Path, np.ndarray, np.ndarray, List[str]]]:
    """Export each mesh object as individual FBX files from visible collections only.

    Objects with KSTREE_GROUP_XYZ_ prefix are combined by group before export.
    """
    results = []
    view_layer = context.view_layer

    original_selection = context.selected_objects[:]
    original_active = context.active_object

    # Track temporary objects for cleanup
    temp_objects_to_cleanup = []

    try:
        bpy.ops.object.select_all(action="DESELECT")

        # First pass: identify and group objects by group ID
        grouped_objects = {}
        regular_objects = []

        for obj in context.scene.objects:
            if obj.type != "MESH" or not obj.data.polygons:
                continue

            if not is_object_in_visible_collection(obj, view_layer):
                continue

            if obj.hide_get():
                print(f"Skipping {obj.name} - object is hidden")
                continue

            # Check if this is a KSTREE_GROUP or SMS_GRP object
            group_id = parse_kstree_group(obj.name)
            group_type = "KSTREE_GROUP"
            
            if not group_id:
                group_id = parse_sms_group(obj.name)
                group_type = "SMS_GRP"
            
            if group_id:
                # Group only by group_id, not by materials
                if group_id not in grouped_objects:
                    grouped_objects[group_id] = {
                        "group_id": group_id,
                        "group_type": group_type,
                        "objects": [],
                    }
                grouped_objects[group_id]["objects"].append(obj)
                print(
                    f"Found {group_type} object {obj.name} in group {group_id}"
                )
            else:
                regular_objects.append(obj)

        if grouped_objects:
            print(f"Found {len(grouped_objects)} grouped objects:")
            for group_id, group_data in grouped_objects.items():
                print(
                    f"  {group_data['group_type']} {group_id}: {len(group_data['objects'])} objects"
                )
        print(f"Processing {len(regular_objects)} regular objects")

        # Second pass: create combined objects for grouped objects
        combined_objects = []
        for group_id, group_data in grouped_objects.items():
            group_objects = group_data["objects"]
            group_type = group_data["group_type"]

            print(
                f"Combining {len(group_objects)} objects in {group_type} group {group_id}"
            )
            combined_obj, materials, transform_data = combine_objects_into_mesh(
                group_objects, group_id, context, group_type
            )
            if combined_obj:
                combined_objects.append((combined_obj, materials, transform_data))
                temp_objects_to_cleanup.append(combined_obj)

        # Third pass: export combined objects and regular objects
        all_export_objects = []

        # Add combined objects
        for combined_obj, materials, transform_data in combined_objects:
            translation, quaternion = transform_data
            all_export_objects.append(
                (combined_obj, translation, quaternion, materials)
            )

        # Add regular objects
        for obj in regular_objects:
            world_matrix = obj.matrix_world.copy()
            world_location, world_rotation, world_scale = world_matrix.decompose()

            import mathutils  # type: ignore

            loc_matrix = mathutils.Matrix.Translation(world_location)
            rot_matrix = world_rotation.to_matrix().to_4x4()
            transform_matrix = loc_matrix @ rot_matrix

            matrix = np.array(transform_matrix)
            translation, quaternion = decompose_matrix(matrix)

            materials = []
            if obj.data.materials:
                for mat in obj.data.materials:
                    if mat:
                        materials.append(sanitize(mat.name))
                    else:
                        materials.append("DefaultMaterial")
            else:
                materials.append("DefaultMaterial")

            all_export_objects.append((obj, translation, quaternion, materials))

        # Export all objects
        for obj, translation, quaternion, materials in all_export_objects:
            has_non_unity_scale = False
            if hasattr(obj, "matrix_world"):
                world_location, world_rotation, world_scale = (
                    obj.matrix_world.decompose()
                )
                has_non_unity_scale = (
                    abs(world_scale.x - 1.0) > 0.00001
                    or abs(world_scale.y - 1.0) > 0.00001
                    or abs(world_scale.z - 1.0) > 0.00001
                )

            export_obj = obj
            temp_obj = None

            # Always create a temporary object to apply modifiers properly
            if obj.parent or has_non_unity_scale or obj.modifiers:
                if obj.parent:
                    print(
                        f"  Unparenting {obj.name} for export (parent: {obj.parent.name})"
                    )
                if has_non_unity_scale:
                    print(f"  Applying scale to {obj.name}")
                if obj.modifiers:
                    print(f"  Applying {len(obj.modifiers)} modifiers to {obj.name}")

                temp_obj = obj.copy()
                temp_obj.data = obj.data.copy()
                temp_obj.name = f"TEMP_EXPORT_{obj.name}"

                context.collection.objects.link(temp_obj)
                temp_objects_to_cleanup.append(temp_obj)

                temp_obj.parent = None
                temp_obj.parent_type = "OBJECT"
                if hasattr(obj, "matrix_world"):
                    temp_obj.matrix_world = obj.matrix_world

                bpy.ops.object.select_all(action="DESELECT")
                temp_obj.select_set(True)
                context.view_layer.objects.active = temp_obj

                # Apply modifiers first, then transforms
                if temp_obj.modifiers:
                    try:
                        # Create a new mesh with modifiers applied using bmesh
                        import bmesh  # type: ignore
                        import gc
                        
                        # Force garbage collection before intensive operation
                        gc.collect()
                        
                        # Get the evaluated mesh with error handling
                        depsgraph = context.evaluated_depsgraph_get()
                        if not depsgraph:
                            print(f"    Warning: Could not get depsgraph for {temp_obj.name}, skipping modifiers")
                        else:
                            evaluated_obj = temp_obj.evaluated_get(depsgraph)
                            if not evaluated_obj:
                                print(f"    Warning: Could not get evaluated object for {temp_obj.name}, skipping modifiers")
                            else:
                                evaluated_mesh = evaluated_obj.to_mesh()
                                if not evaluated_mesh:
                                    print(f"    Warning: Could not get evaluated mesh for {temp_obj.name}, skipping modifiers")
                                else:
                                    # Create a new mesh and copy data using bmesh
                                    new_mesh = bpy.data.meshes.new(f"MODIFIED_{temp_obj.data.name}")
                                    
                                    # Use bmesh to copy the mesh data properly with error handling
                                    bm = bmesh.new()
                                    try:
                                        bm.from_mesh(evaluated_mesh)
                                        bm.to_mesh(new_mesh)
                                    finally:
                                        bm.free()  # Always free bmesh
                                    
                                    # Copy materials from the evaluated mesh to the new mesh
                                    for mat in evaluated_mesh.materials:
                                        new_mesh.materials.append(mat)
                                    
                                    # Replace the object's mesh
                                    old_mesh = temp_obj.data
                                    temp_obj.data = new_mesh
                                    
                                    # Clean up immediately
                                    try:
                                        evaluated_obj.to_mesh_clear()
                                    except:
                                        pass  # Sometimes this fails, but it's not critical
                                        
                                    bpy.data.meshes.remove(old_mesh)
                                    
                                    # Clear modifiers since they're now baked into the mesh
                                    temp_obj.modifiers.clear()
                                    
                                    print(f"    Successfully applied modifiers to {temp_obj.name}")
                                    
                                    # Force cleanup after operation
                                    gc.collect()
                        
                    except Exception as e:
                        print(f"  ERROR: Failed to apply modifiers to {temp_obj.name}: {e}")
                        import traceback
                        traceback.print_exc()

                # Apply scale transforms if needed
                if has_non_unity_scale:
                    bpy.ops.object.transform_apply(
                        location=False, rotation=False, scale=True
                    )

                export_obj = temp_obj
            else:
                bpy.ops.object.select_all(action="DESELECT")
                obj.select_set(True)
                context.view_layer.objects.active = obj
                export_obj = obj

            temp_mesh = export_obj.data.copy()
            temp_mesh.name = f"TEMP_MESH_{export_obj.data.name}"

            if hasattr(temp_mesh, "color_attributes"):
                for attr in temp_mesh.color_attributes:
                    if attr.data_type == "FLOAT_COLOR":
                        for i in range(len(attr.data)):
                            attr.data[i].color = (1.0, 1.0, 1.0, 1.0)
                    elif attr.data_type == "BYTE_COLOR":
                        for i in range(len(attr.data)):
                            attr.data[i].color = (255, 255, 255, 255)
                    print(
                        f"  Set color attribute {attr.name} to all white for {export_obj.name}"
                    )

            original_mesh = export_obj.data
            export_obj.data = temp_mesh

            fbx_name = sanitize(obj.name) + ".fbx"
            fbx_path = temp_dir / fbx_name

            # Debug material assignments before export
            if export_obj.data.materials:
                material_usage = {}
                for poly in export_obj.data.polygons:
                    mat_idx = poly.material_index
                    if mat_idx not in material_usage:
                        material_usage[mat_idx] = 0
                    material_usage[mat_idx] += 1
                
                print(f"Exporting {obj.name} to {fbx_name}")
                print(f"  Materials ({len(export_obj.data.materials)}): {[mat.name if mat else 'None' for mat in export_obj.data.materials]}")
                print(f"  Face assignments: {material_usage}")
                
                # Verify no invalid material indices
                max_mat_idx = len(export_obj.data.materials) - 1
                invalid_faces = [poly.index for poly in export_obj.data.polygons if poly.material_index > max_mat_idx]
                if invalid_faces:
                    print(f"  WARNING: {len(invalid_faces)} faces have invalid material indices!")
            else:
                print(f"Exporting {obj.name} to {fbx_name} (no materials)")

            bpy.ops.export_scene.fbx(
                filepath=str(fbx_path),
                use_selection=True,
                bake_space_transform=False,
                mesh_smooth_type="OFF",
                use_mesh_modifiers=True,
                object_types={"MESH"},
                use_active_collection=False,
                use_metadata=True,
                use_mesh_edges=True,
                check_existing=False,
                use_custom_props=False,
                add_leaf_bones=False,
                primary_bone_axis="Y",
                secondary_bone_axis="X",
                use_armature_deform_only=False,
                armature_nodetype="NULL",
                bake_anim=False,
                path_mode="AUTO",
                embed_textures=False,
            )

            export_obj.data = original_mesh
            bpy.data.meshes.remove(temp_mesh)

            results.append((fbx_path, translation, quaternion, materials))
            bpy.ops.object.select_all(action="DESELECT")

    finally:
        # Clean up all temporary objects
        print(f"Cleaning up {len(temp_objects_to_cleanup)} temporary objects...")
        bpy.ops.object.select_all(action="DESELECT")

        # Fast cleanup: select all temp objects at once and delete
        temp_objects_to_delete = []
        temp_meshes_to_delete = []

        for i, temp_obj in enumerate(temp_objects_to_cleanup):
            if i % 100 == 0:
                print(f"Processing cleanup object {i+1}/{len(temp_objects_to_cleanup)}")

            if temp_obj and temp_obj.name in bpy.data.objects:
                try:
                    # Collect mesh data for later deletion
                    if temp_obj.data and temp_obj.data.name.startswith(
                        "TEMP_COMBINED_"
                    ):
                        temp_meshes_to_delete.append(temp_obj.data)

                    temp_objects_to_delete.append(temp_obj)
                    temp_obj.select_set(True)
                except Exception as e:
                    print(
                        f"Warning: Could not prepare cleanup for {temp_obj.name}: {e}"
                    )

        # Delete all selected objects at once
        if temp_objects_to_delete:
            print(f"Deleting {len(temp_objects_to_delete)} temporary objects...")
            try:
                bpy.ops.object.delete()
            except Exception as e:
                print(f"Warning: Bulk delete failed: {e}")
                # Fallback to individual deletion
                for temp_obj in temp_objects_to_delete:
                    try:
                        bpy.data.objects.remove(temp_obj)
                    except:
                        pass

        # Clean up temporary meshes
        if temp_meshes_to_delete:
            print(f"Cleaning up {len(temp_meshes_to_delete)} temporary meshes...")
            for mesh in temp_meshes_to_delete:
                try:
                    bpy.data.meshes.remove(mesh)
                except:
                    pass

        print("Cleanup complete.")

        # Restore original selection
        bpy.ops.object.select_all(action="DESELECT")
        for obj in original_selection:
            if obj and obj.name in bpy.data.objects:
                try:
                    obj.select_set(True)
                except:
                    pass
        if original_active and original_active.name in bpy.data.objects:
            try:
                context.view_layer.objects.active = original_active
            except:
                pass

    print(f"export_objects_as_fbx returning {len(results)} results")
    return results
