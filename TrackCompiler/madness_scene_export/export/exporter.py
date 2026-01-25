import bpy  # type: ignore
import tempfile
from pathlib import Path
import shutil
from typing import List, Tuple
import xml.etree.ElementTree as ET
import numpy as np
from .object_export import (
    ObjectInfo,
    collect_empty_objects_with_meb,
    sanitize,
    is_object_in_visible_collection,
    parse_kstree_group,
    parse_sms_group,
    combine_objects_into_mesh,
)
from ..meshes import export_object_to_meb, MeshExportOptions
from ..materials.mtx_processor import prepare_mtx_files_from_materials
from ..utils.coordinate_transforms import decompose_matrix


def _export_single_object(obj, obj_name, output_dir, resource_prefix, objects_list, temp_objects_list):
    """Helper function to export a single object to MEB."""
    # Get transform
    world_matrix = obj.matrix_world.copy()
    matrix = np.array(world_matrix)
    translation, quaternion = decompose_matrix(matrix)

    # Prepare materials
    materials = []
    if obj.data.materials:
        for mat in obj.data.materials:
            if mat:
                materials.append(sanitize(mat.name))
            else:
                materials.append("DefaultMaterial")
    else:
        materials.append("DefaultMaterial")

    # Build MEB export options from object settings
    options = MeshExportOptions(
        material_dir=resource_prefix if resource_prefix else "vehicles/car_name/"
    )

    # Get MEB settings from object if available
    if hasattr(obj.data, "meb_export_settings"):
        meb_settings = obj.data.meb_export_settings

        # Manual UV map configuration
        uv_indices = []
        for i in range(1, 7):
            uv_prop = f'uv{i}'
            if hasattr(meb_settings, uv_prop):
                uv_val = getattr(meb_settings, uv_prop)
                if uv_val > 0:
                    uv_indices.append(uv_val - 1)
        if uv_indices:
            options.uv_map_indices = uv_indices

        if hasattr(meb_settings, 'tangent_space'):
            options.generate_tangent_space = meb_settings.tangent_space
        if hasattr(meb_settings, 'bodywork'):
            options.bodywork_data = meb_settings.bodywork
        if hasattr(meb_settings, 'disable_material'):
            options.disable_materials = meb_settings.disable_material

    # Export to MEB
    print(f"Exporting {obj_name} to MEB... (tangents={options.generate_tangent_space}, bodywork={options.bodywork_data}, UVs={options.uv_map_indices})")
    meb_path = output_dir / f"{sanitize(obj_name)}.meb"
    bounds = export_object_to_meb(
        obj,
        meb_path,
        mesh_name=sanitize(obj_name),
        options=options
    )

    # Get userflags (default if not specified)
    userflags = 0b10000000000100000001000001110101  # Default userflags

    # Create ObjectInfo
    obj_info = ObjectInfo(
        name=sanitize(obj_name),
        meb_path=meb_path,
        translation=translation,
        quaternion=quaternion,
        sphere_center=bounds.sphere_center,
        sphere_radius=bounds.sphere_radius,
        materials=materials,
        bb_min=bounds.bb_min,
        bb_max=bounds.bb_max,
        userflags=userflags,
    )
    objects_list.append(obj_info)
    print(f"Successfully exported {obj_name} -> {meb_path.name}")


def export_objects_to_meb(
    context,
    output_dir: Path,
    resource_prefix: str
) -> List[ObjectInfo]:
    """
    Export mesh objects to MEB format, grouping KSTREE_GROUP and SMS_GRP objects.
    """
    objects = []
    view_layer = context.view_layer

    # Track temporary objects for cleanup
    temp_objects_to_cleanup = []
    original_selection = context.selected_objects[:]
    original_active = context.active_object

    try:
        bpy.ops.object.select_all(action="DESELECT")

        # Collect all visible mesh objects
        mesh_objects = []

        for obj in context.scene.objects:
            if obj.type != "MESH" or not obj.data.polygons:
                continue

            if not is_object_in_visible_collection(obj, view_layer):
                continue

            if obj.hide_get():
                print(f"Skipping {obj.name} - object is hidden")
                continue

            mesh_objects.append(obj)

        print(f"Found {len(mesh_objects)} visible mesh objects to export")

        # Group objects by their group prefix
        kstree_groups = {}  # group_id -> [objects]
        sms_groups = {}     # group_name -> [objects]
        ungrouped_objects = []

        for obj in mesh_objects:
            kstree_group = parse_kstree_group(obj.name)
            sms_group = parse_sms_group(obj.name)

            if kstree_group:
                if kstree_group not in kstree_groups:
                    kstree_groups[kstree_group] = []
                kstree_groups[kstree_group].append(obj)
            elif sms_group:
                if sms_group not in sms_groups:
                    sms_groups[sms_group] = []
                sms_groups[sms_group].append(obj)
            else:
                ungrouped_objects.append(obj)

        print(f"Grouped: {len(kstree_groups)} KSTREE groups, {len(sms_groups)} SMS groups, {len(ungrouped_objects)} ungrouped objects")

        # Process KSTREE_GROUP objects
        for group_id, group_objects in kstree_groups.items():
            try:
                group_name = f"KSTREE_GROUP_{group_id}"
                print(f"Processing KSTREE_GROUP_{group_id} ({len(group_objects)} objects)...")
                
                combined_obj, _, _ = combine_objects_into_mesh(
                    group_objects, group_id, context, "KSTREE_GROUP"
                )
                
                if combined_obj:
                    temp_objects_to_cleanup.append(combined_obj)
                    
                    # Export the combined mesh
                    _export_single_object(
                        combined_obj, group_name, output_dir,
                        resource_prefix, objects, temp_objects_to_cleanup
                    )
            except Exception as e:
                print(f"ERROR: Failed to process KSTREE_GROUP_{group_id}: {e}")
                import traceback
                traceback.print_exc()

        # Process SMS_GRP objects
        for group_name, group_objects in sms_groups.items():
            try:
                full_group_name = f"SMS_GRP_{group_name}"
                print(f"Processing SMS_GRP_{group_name} ({len(group_objects)} objects)...")
                
                combined_obj, _, _ = combine_objects_into_mesh(
                    group_objects, group_name, context, "SMS_GRP"
                )
                
                if combined_obj:
                    temp_objects_to_cleanup.append(combined_obj)
                    
                    # Export the combined mesh
                    _export_single_object(
                        combined_obj, full_group_name, output_dir,
                        resource_prefix, objects, temp_objects_to_cleanup
                    )
            except Exception as e:
                print(f"ERROR: Failed to process SMS_GRP_{group_name}: {e}")
                import traceback
                traceback.print_exc()

        # Process ungrouped objects
        for obj in ungrouped_objects:
            try:
                _export_single_object(
                    obj, obj.name, output_dir,
                    resource_prefix, objects, temp_objects_to_cleanup
                )
            except Exception as e:
                print(f"ERROR: Failed to export {obj.name}: {e}")
                import traceback
                traceback.print_exc()
                continue

    finally:
        # Clean up temporary combined objects
        if temp_objects_to_cleanup:
            print(f"Cleaning up {len(temp_objects_to_cleanup)} temporary objects...")
            bpy.ops.object.select_all(action="DESELECT")
            for temp_obj in temp_objects_to_cleanup:
                if temp_obj and temp_obj.name in bpy.data.objects:
                    try:
                        # Select the temp object
                        temp_obj.select_set(True)
                        # Delete it
                        bpy.ops.object.delete()
                        bpy.ops.object.select_all(action="DESELECT")
                    except Exception as e:
                        print(f"Warning: Could not delete temporary object {temp_obj.name}: {e}")

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

        # Export mesh objects to MEB format
        print("Exporting mesh objects to MEB...")
        objects = export_objects_to_meb(context, output_dir, resource_prefix)
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

        # Determine texture export path based on SGX location (needed before MTX generation)
        texture_export_dir = determine_texture_export_path(output_dir, track_name)
        
        # Generate list of unique materials
        unique_materials = sorted(set(all_materials))
        
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

    return {"FINISHED"}


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
