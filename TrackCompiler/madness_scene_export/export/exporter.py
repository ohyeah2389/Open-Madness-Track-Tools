import bpy  # type: ignore
import tempfile
from pathlib import Path
import shutil
from typing import List
import xml.etree.ElementTree as ET
import numpy as np
from .object_export import (
    ObjectInfo,
    export_objects_as_fbx,
    collect_empty_objects_with_meb,
    sanitize,
)
from .meb_compiler import run_exporter, parse_bounds
from ..materials.mtx_processor import prepare_mtx_files_from_materials
from ..settings import meb_export_settings


def export_madness_scene(
    filepath: str,
    exporter_exe: Path,
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

        # Export objects as FBX and collect info
        print("Exporting objects as FBX...")
        fbx_data = export_objects_as_fbx(context, temp_dir)
        print(f"FBX export completed. Exported {len(fbx_data)} objects as FBX")

        # Collect Empty objects with MEB references
        print("Collecting Empty objects with MEB references...")
        empty_data = collect_empty_objects_with_meb(context)
        print(f"Found {len(empty_data)} Empty objects with MEB references")

        print("Transitioning to MEB compilation phase...")

        objects = []
        all_materials = []

        # Compile each object using MEB exporter
        print("Compiling objects with MEB exporter...")
        for fbx_file, translation, quaternion, materials in fbx_data:
            print(f"Processing FBX: {fbx_file.name}")

            # Find the corresponding Blender object to get its MEB settings
            obj_name = fbx_file.stem
            blender_obj = None
            for obj in context.scene.objects:
                if sanitize(obj.name) == obj_name and obj.type == "MESH":
                    blender_obj = obj
                    break

            # Get MEB settings for this specific object
            if blender_obj and hasattr(blender_obj.data, "meb_export_settings"):
                meb_settings = blender_obj.data.meb_export_settings
                extra_args = meb_export_settings.build_meb_args(meb_settings)
                userflags = meb_export_settings.get_userflags_value(meb_settings)
                print(
                    f"Using per-object MEB settings for {obj_name}: {' '.join(extra_args)}, userflags={userflags}"
                )
            else:
                # Use default settings if no specific settings found
                extra_args = [
                    "--uv1",
                    "1",
                    "--uv2",
                    "1",
                    "--uv3",
                    "1",
                    "--uv4",
                    "1",
                    "--uv5",
                    "1",
                    "--uv6",
                    "1",
                    "--tangent-space",
                ]
                userflags = 0b10000000000100000001000001110101  # Default userflags
                print(f"Using default MEB settings for {obj_name}")

            try:
                meb_path, log = run_exporter(
                    exporter_exe, fbx_file, output_dir, extra_args, resource_prefix
                )
                sphere_center, sphere_radius, bb_min, bb_max = parse_bounds(log)
                obj = ObjectInfo(
                    name=fbx_file.stem,
                    fbx_path=fbx_file,
                    meb_path=meb_path,
                    translation=translation,
                    quaternion=quaternion,
                    sphere_center=sphere_center,
                    sphere_radius=sphere_radius,
                    materials=materials,
                    bb_min=bb_min,
                    bb_max=bb_max,
                    userflags=userflags,
                )
                objects.append(obj)
                all_materials.extend(materials)
                print(f"Successfully compiled {fbx_file.name} -> {meb_path.name}")
            except Exception as e:
                print(f"ERROR: Failed to compile {fbx_file.name}: {e}")
                # Continue with other objects rather than failing completely
        print(f"Successfully compiled {len(objects)} objects")

        # Add Empty objects with MEB references
        print("Processing Empty objects with MEB references...")
        for (
            obj_name,
            meb_path,
            translation,
            quaternion,
            sphere_radius,
            userflags,
            original_meb_path,
        ) in empty_data:
            # Copy MEB file to export directory and update path
            copied_meb_path = copy_meb_file_to_export(
                original_meb_path, output_dir, meb_path, track_name
            )
            
            # Use the copied MEB path
            meb_file_path = copied_meb_path

            # Create ObjectInfo for Empty object
            # Use user-specified sphere radius for MEB
            obj = ObjectInfo(
                name=obj_name,
                fbx_path=Path(""),  # No FBX file for Empty objects
                meb_path=meb_file_path,
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

        total_objects = len(
            [obj for obj in objects if obj.fbx_path.name]
        )  # FBX objects
        empty_objects = len(
            [obj for obj in objects if not obj.fbx_path.name]
        )  # Empty objects
        print(
            f"Total objects: {len(objects)} ({total_objects} compiled, {empty_objects} referenced)"
        )

        # Generate MTX files
        print("Generating MTX files...")
        unique_materials = sorted(set(all_materials))
        prepare_mtx_files_from_materials(
            unique_materials, output_dir, context, track_name
        )
        print(f"Generated {len(unique_materials)} MTX files")

        # Determine texture export path based on SGX location
        texture_export_dir = determine_texture_export_path(output_dir, track_name)
        
        # Export textures to determined location and update MTX files
        if unique_materials:
            export_textures_and_update_mtx(
                unique_materials, output_dir, texture_export_dir, track_name, context
            )

        # Generate SGX file
        print("Generating SGX file...")
        scene_min, scene_max = np.array([0, 0, 0]), np.array([0, 0, 0])
        if objects:
            # Initialize with the first object's bounding box adjusted by translation
            first_obj = objects[0]
            scene_min = first_obj.translation + first_obj.bb_min
            scene_max = first_obj.translation + first_obj.bb_max
            for obj in objects[1:]:
                # Calculate object bounds using the bounding box data from exporter
                obj_min = obj.translation + obj.bb_min
                obj_max = obj.translation + obj.bb_max
                scene_min = np.minimum(scene_min, obj_min)
                scene_max = np.maximum(scene_max, obj_max)
        build_sgx(objects, sgx_path, scene_min, scene_max, resource_prefix)
        print(f"Generated SGX file: {sgx_path}")

    return {"FINISHED"}


def determine_texture_export_path(output_dir: Path, track_name: str) -> Path:
    """Determine where to export textures based on SGX location and path structure."""
    # Check if "tracks" is in the path
    path_parts = output_dir.parts
    
    # Look for "tracks" in the path
    tracks_index = -1
    for i, part in enumerate(path_parts):
        if part.lower() == "tracks":
            tracks_index = i
            break
    
    if tracks_index >= 0:
        # If "tracks" is found, export to tracks/textures/track_name
        # Navigate up to the parent of "tracks" and then down to tracks/textures/track_name
        tracks_parent = Path(*path_parts[:tracks_index])
        texture_dir = tracks_parent / "tracks" / "textures" / track_name
    else:
        # If no "tracks" in path, export to textures/track_name relative to SGX
        texture_dir = output_dir / "textures" / track_name
    
    print(f"Texture export directory: {texture_dir}")
    return texture_dir


def export_textures_and_update_mtx(
    material_names: list,
    mtx_dir: Path,
    texture_export_dir: Path,
    track_name: str,
    context
):
    """Export textures to target directory and update MTX files with correct paths."""
    texture_export_dir.mkdir(parents=True, exist_ok=True)
    
    texture_count = 0
    
    for mat_name in material_names:
        # Find corresponding Blender material
        blender_material = None
        for mat in bpy.data.materials:
            if sanitize(mat.name) == mat_name:
                blender_material = mat
                break
        
        if blender_material and hasattr(blender_material, "mtx_settings"):
            mtx = blender_material.mtx_settings
            mtx_path = mtx_dir / f"{mat_name.upper()}.mtx"
            
            # Track if we need to update the MTX file
            mtx_updated = False
            
            for param in mtx.shader_params:
                if param.param_type == "EPT_TEXTURE" and param.texture_value:
                    # Resolve the source texture path
                    from ..materials.mtx_material_system import resolve_texture_path
                    src_path, exists = resolve_texture_path(param.texture_value, context)
                    
                    if exists and src_path:
                        dest_path = texture_export_dir / src_path.name
                        
                        try:
                            # Copy texture to export location
                            shutil.copy2(src_path, dest_path)
                            texture_count += 1
                            print(f"  Copied texture: {src_path.name} -> {dest_path}")
                            
                            # Update MTX file with new relative path
                            if mtx_path.exists():
                                tree = ET.parse(mtx_path)
                                root = tree.getroot()
                                
                                for shaderparam in root.findall("shaderparam"):
                                    if shaderparam.get("name") == param.name:
                                        value_elem = shaderparam.find("value")
                                        if value_elem is not None:
                                            # Create relative path from MTX to texture
                                            relative_texture_path = create_relative_texture_path(
                                                mtx_dir, texture_export_dir, src_path.name, track_name
                                            )
                                            value_elem.set("v", relative_texture_path)
                                            mtx_updated = True
                                            print(f"  Updated MTX path for {param.name} to {relative_texture_path}")
                                        break
                                
                                if mtx_updated:
                                    tree.write(mtx_path, encoding="utf-8", xml_declaration=False)
                        
                        except Exception as e:
                            print(f"  Failed to copy texture {src_path.name}: {e}")
                    else:
                        print(f"  Warning: Texture not found: {param.texture_value}")
    
    print(f"Exported {texture_count} textures to {texture_export_dir}")


def create_relative_texture_path(
    mtx_dir: Path, 
    texture_dir: Path, 
    texture_name: str, 
    track_name: str
) -> str:
    """Create the correct relative texture path for MTX files based on export structure."""
    # Check if we're in a tracks-based structure
    mtx_parts = mtx_dir.parts
    texture_parts = texture_dir.parts
    
    # Look for "tracks" in both paths
    mtx_tracks_index = -1
    texture_tracks_index = -1
    
    for i, part in enumerate(mtx_parts):
        if part.lower() == "tracks":
            mtx_tracks_index = i
            break
    
    for i, part in enumerate(texture_parts):
        if part.lower() == "tracks":
            texture_tracks_index = i
            break
    
    if mtx_tracks_index >= 0 and texture_tracks_index >= 0:
        # Both are in tracks structure, use tracks/textures/track_name/texture
        return f"tracks\\textures\\{track_name}\\{texture_name}"
    else:
        # Not in tracks structure, use relative path
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
    scene_min: np.ndarray,
    scene_max: np.ndarray,
    resource_prefix: str = "",
):
    """Generate SGX file from object data."""
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

        # For Empty objects (no FBX file), use the full path; for compiled objects, use filename with prefix
        if not obj.fbx_path.name:  # Empty object with MEB reference
            # Use the full path stored in meb_path (already in game-relative format)
            # Ensure forward slashes and no leading slash to match compiled object format
            resource_filename = str(obj.meb_path).replace("\\", "/")
            if resource_filename.startswith("/"):
                resource_filename = resource_filename[1:]  # Remove leading slash
        else:  # Compiled object
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
