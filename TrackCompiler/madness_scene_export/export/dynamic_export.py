import bpy  # type: ignore
import bmesh  # type: ignore
from pathlib import Path
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
import mathutils  # type: ignore
import numpy as np
from ..properties.dynamic import (
    get_definition_name,
    get_definition_shapes,
    get_definition_visual,
    get_dynamic_name,
    is_dynamic_definition,
    is_sms_dynamic,
)
from ..utils.coordinate_transforms import (
    convert_position,
    convert_rotation_matrix,
    matrix_to_quaternion,
)
from .dynamic_registry import export_dynamic_registry

# PhysX cannot cook a convex hull with more than 255 vertices.
MAX_HULL_VERTICES = 255

# Dynamic objects live in a shared folder, not the track's own. The second spelling is
# the casing stock VHFs use for their resource references.
GAME_DYNAMIC_DIR = "tracks/_data/dynamic"
GAME_DYNAMIC_RESOURCE_DIR = "Tracks\\_Data\\Dynamic"

# Textures for dynamic objects sit alongside every other track texture rather than
# beside the meshes, which is where the engine resolves them from.
GAME_DYNAMIC_TEXTURE_DIR = "tracks/textures/_data/dynamic"


def collect_dynamic_objects(scene) -> List[Dict[str, Any]]:
    """Collect all SMS dynamic objects from the scene"""
    dynamic_objects = []
    
    for obj in scene.objects:
        if is_sms_dynamic(obj):
            dynamic_props = obj.madness_dynamic
            
            # Skip empties without a definition assigned. Since any empty can be
            # used, this avoids warning spam for non-dynamic helper empties.
            definition = dynamic_props.definition
            if not is_dynamic_definition(definition):
                continue
            
            # Get world transform and convert to Madness coordinate system
            world_matrix = obj.matrix_world
            
            # Convert Blender transform directly to Madness coordinates.
            # Dynamic env matrices expect direct converted basis axes here; using the
            # generic quaternion post-fix path can invert yaw direction for dynamics.
            world_matrix_np = np.array(world_matrix)
            madness_position = convert_position(world_matrix_np[:3, 3])
            madness_rotation = convert_rotation_matrix(world_matrix_np[:3, :3])
            
            # Handle scale - use object scale or override
            if dynamic_props.use_scale_override:
                scale = mathutils.Vector((dynamic_props.scale_x, dynamic_props.scale_y, dynamic_props.scale_z))
            else:
                scale = world_matrix.to_scale()
            
            # Build transformation matrix for AMS2 format
            # AMS2 uses column-major storage: R11;R21;R31;0;R12;R22;R32;0;R13;R23;R33;0;TX;TY;TZ;1
            scale_array = np.array([scale.x, scale.y, scale.z])
            # Apply scale by multiplying each column of rotation matrix by corresponding scale
            scaled_rotation = madness_rotation.copy()
            for i in range(3):
                scaled_rotation[:, i] *= scale_array[i]
            
            # Build matrix values in AMS2 column-major order
            matrix_values = []
            # First column: R11, R21, R31, 0
            matrix_values.extend([f"{scaled_rotation[0, 0]:.6f}", f"{scaled_rotation[1, 0]:.6f}", f"{scaled_rotation[2, 0]:.6f}", "0"])
            # Second column: R12, R22, R32, 0  
            matrix_values.extend([f"{scaled_rotation[0, 1]:.6f}", f"{scaled_rotation[1, 1]:.6f}", f"{scaled_rotation[2, 1]:.6f}", "0"])
            # Third column: R13, R23, R33, 0
            matrix_values.extend([f"{scaled_rotation[0, 2]:.6f}", f"{scaled_rotation[1, 2]:.6f}", f"{scaled_rotation[2, 2]:.6f}", "0"])
            # Translation: TX, TY, TZ, 1
            matrix_values.extend([f"{madness_position[0]:.6f}", f"{madness_position[1]:.6f}", f"{madness_position[2]:.6f}", "1"])
            
            matrix_string = ";".join(matrix_values)
            
            # Build 4x4 matrix for reference (not used in export, but kept for compatibility)
            madness_matrix = np.eye(4)
            madness_matrix[:3, :3] = scaled_rotation
            madness_matrix[:3, 3] = madness_position
            
            dynamic_info = {
                'name': get_dynamic_name(obj),
                'object': obj,
                'definition': definition,
                'definition_name': get_definition_name(definition),
                'position': madness_position,
                'world_matrix': madness_matrix,
                'matrix_string': matrix_string,
                'properties': dynamic_props,
                'scale': scale
            }
            dynamic_objects.append(dynamic_info)
    
    return dynamic_objects


def build_hull_points(shape_obj) -> List[np.ndarray]:
    """Compute the convex hull of a shape object's mesh, in Madness coordinates.

    Points are in the shape's local space; its transform is carried by the
    shape's LocalPose and geometry Scale instead.
    """
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = shape_obj.evaluated_get(depsgraph)
    mesh = eval_obj.to_mesh()

    try:
        bm = bmesh.new()
        bm.from_mesh(mesh)
        result = bmesh.ops.convex_hull(bm, input=bm.verts, use_existing_faces=False)
        hull_verts = [item for item in result["geom"] if isinstance(item, bmesh.types.BMVert)]
        points = [convert_position(np.array(vert.co)) for vert in hull_verts]
        bm.free()
    finally:
        eval_obj.to_mesh_clear()

    return points


def _pose_string(matrix) -> str:
    """Format a Blender matrix as a PhysX pose (quaternion xyzw, then position)."""
    matrix_np = np.array(matrix)
    rotation = matrix_np[:3, :3]
    scales = np.linalg.norm(rotation, axis=0)
    rotation = rotation / np.where(scales > 1e-8, scales, 1.0)

    w, x, y, z = matrix_to_quaternion(convert_rotation_matrix(rotation))
    position = convert_position(matrix_np[:3, 3])

    values = [x, y, z, w, position[0], position[1], position[2]]
    return " ".join(f"{value:.6f}" for value in values)


def _append_shape(shapes_elem: ET.Element, shape_obj, mesh_id: int, local_matrix) -> None:
    """Append a PxShape referencing an already-emitted convex mesh."""
    props = shape_obj.madness_dynamic_def
    scale = local_matrix.to_scale()

    shape_elem = ET.SubElement(shapes_elem, 'PxShape')
    ET.SubElement(shape_elem, 'Name').text = shape_obj.name
    ET.SubElement(shape_elem, 'LocalPose').text = _pose_string(local_matrix)

    geometry = ET.SubElement(shape_elem, 'Geometry')
    convex_geometry = ET.SubElement(geometry, 'PxConvexMeshGeometry')
    scale_elem = ET.SubElement(convex_geometry, 'Scale')
    ET.SubElement(scale_elem, 'Scale').text = f"{scale.x:.6f} {scale.z:.6f} {scale.y:.6f}"
    ET.SubElement(scale_elem, 'Rotation').text = "0 0 0 1"
    ET.SubElement(convex_geometry, 'ConvexMesh').text = str(mesh_id)

    materials = ET.SubElement(shape_elem, 'Materials')
    ET.SubElement(materials, 'PxMaterialName').text = props.physics_material
    ET.SubElement(shape_elem, 'Mass').text = f"{props.mass:.6f}"


def _describe_shape(shape_obj, points, local_matrix) -> Dict[str, Any]:
    """Describe a shape for the object type registry, which stores it as an offset hull."""
    props = shape_obj.madness_dynamic_def
    matrix_np = np.array(local_matrix)
    rotation = matrix_np[:3, :3]
    scales = np.linalg.norm(rotation, axis=0)
    rotation = convert_rotation_matrix(rotation / np.where(scales > 1e-8, scales, 1.0))

    return {
        'name': shape_obj.name,
        'mass': props.mass,
        'material': props.physics_material,
        'points': points,
        'position': convert_position(matrix_np[:3, 3]),
        # Stored column-major, matching how the engine's other matrices are written.
        'orientation': rotation.flatten(order='F').tolist(),
    }


def create_dynamic_collisions_xml(dynamic_objects: List[Dict[str, Any]]):
    """Create a dynamic_collisions.xml from the definitions used in the scene.

    Also returns a body description per definition, so the object type registry can be
    written from the same hulls rather than computing them a second time.
    """
    root = ET.Element('PhysX30Collection')
    root.set('Version', '3.2.0-SMS')

    definitions = unique_definitions(dynamic_objects)

    next_mesh_id = 0
    rigid_elements = []
    bodies: List[Dict[str, Any]] = []

    for name in sorted(definitions):
        definition = definitions[name]
        shapes = get_definition_shapes(definition)
        if not shapes:
            print(f"Dynamic definition '{name}' has no mesh shapes, skipping")
            continue

        rigid_elem = ET.Element('PxRigidDynamic')
        ET.SubElement(rigid_elem, 'Name').text = name
        ET.SubElement(rigid_elem, 'GlobalPose').text = _pose_string(mathutils.Matrix.Identity(4))
        shapes_elem = ET.SubElement(rigid_elem, 'Shapes')

        body_shapes: List[Dict[str, Any]] = []
        root_inverse = definition.matrix_world.inverted()
        for shape_obj in shapes:
            points = build_hull_points(shape_obj)
            if not points:
                print(f"Shape '{shape_obj.name}' produced an empty hull, skipping")
                continue
            if len(points) > MAX_HULL_VERTICES:
                print(
                    f"Shape '{shape_obj.name}' hull has {len(points)} vertices, exceeding the "
                    f"PhysX limit of {MAX_HULL_VERTICES}. Simplify the collision mesh."
                )

            mesh_elem = ET.SubElement(root, 'PxConvexMesh')
            ET.SubElement(mesh_elem, 'Id').text = str(next_mesh_id)
            points_text = "\n".join(f"{p[0]:.6f} {p[1]:.6f} {p[2]:.6f}" for p in points)
            ET.SubElement(mesh_elem, 'points').text = f"\n{points_text}\n"

            local_matrix = root_inverse @ shape_obj.matrix_world
            _append_shape(shapes_elem, shape_obj, next_mesh_id, local_matrix)
            body_shapes.append(_describe_shape(shape_obj, points, local_matrix))
            next_mesh_id += 1

        rigid_elements.append(rigid_elem)
        if body_shapes:
            bodies.append({'name': name, 'shapes': body_shapes})

    # All PxConvexMesh entries must precede the bodies that reference them.
    root.extend(rigid_elements)
    return root, bodies


def unique_definitions(dynamic_objects: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Map exported name to definition, collapsing repeated placements."""
    definitions = {}
    for obj_info in dynamic_objects:
        definitions.setdefault(obj_info['definition_name'], obj_info['definition'])
    return definitions


def export_dynamic_visuals(dynamic_objects: List[Dict[str, Any]], tracks_dir: Path) -> int:
    """Export each definition's visual mesh, materials and textures.

    The engine resolves a dynamic body's appearance by looking up a mesh of the same
    name under tracks/_data/dynamic, so the MEB is written there rather than into the
    track's own folder.
    """
    from ..materials.mtx_processor import prepare_mtx_files_from_materials
    from ..meshes.blender_meb_export import export_object_to_meb
    from ..utils import effective_materials_for_object, sanitize
    from .sgx_export import (
        _build_maybe_overridden_options,
        _get_userflags,
        export_textures,
        prepare_texture_mapping,
    )
    from .vhf_export import write_vhf

    out_dir = tracks_dir / "_data" / "dynamic"
    texture_dir = tracks_dir / "textures" / "_data" / "dynamic"
    materials: List[str] = []
    exported = 0

    for name, definition in sorted(unique_definitions(dynamic_objects).items()):
        visual = get_definition_visual(definition)
        if not visual:
            print(f"Dynamic definition '{name}' has no visual mesh, skipping mesh export")
            continue
        out_dir.mkdir(parents=True, exist_ok=True)
        # The MEB stores each material's path, and dynamic objects resolve theirs from
        # the shared folder rather than from the track's own.
        options = _build_maybe_overridden_options(visual, f"{GAME_DYNAMIC_DIR}/")
        bounds = export_object_to_meb(
            visual, out_dir / f"{name}.meb", mesh_name=name, options=options, uppercase_name=False
        )
        write_vhf(
            out_dir / f"{name}.vhf",
            name,
            f"{GAME_DYNAMIC_RESOURCE_DIR}\\{name}.meb",
            bounds,
            _get_userflags(visual),
        )
        materials.extend(sanitize(mat.name) for mat in effective_materials_for_object(visual) if mat)
        exported += 1

    materials = sorted(set(materials))
    if materials:
        texture_mapping = prepare_texture_mapping(
            materials, out_dir, texture_dir, "dynamic", bpy.context,
            game_texture_dir=GAME_DYNAMIC_TEXTURE_DIR.replace("/", "\\"),
        )
        prepare_mtx_files_from_materials(
            materials, out_dir, bpy.context, track_name="dynamic", texture_mapping=texture_mapping
        )
        if texture_mapping:
            export_textures(texture_mapping, texture_dir)

    print(f"Exported {exported} dynamic object meshes and {len(materials)} materials to {out_dir}")
    return exported


def create_environment_xml(dynamic_objects: List[Dict[str, Any]]) -> ET.Element:
    """Create an environment XML with object placements"""
    # Create root Reflection element
    root = ET.Element('Reflection')
    
    # Add class definitions
    class_def1 = ET.SubElement(root, 'class', name="BRTTIRefCount", base="root class")
    
    class_def2 = ET.SubElement(root, 'class', name="BPersistent", base="BRTTIRefCount")
    ET.SubElement(class_def2, 'prop', name="Name", type="String")
    
    class_def3 = ET.SubElement(root, 'class', name="EnvironmentPhysics", base="BPersistent")
    ET.SubElement(class_def3, 'prop', name="Environment Physics Object Array", type="Fct")
    
    # Duplicate class definitions (as seen in original files)
    class_def4 = ET.SubElement(root, 'class', name="BRTTIRefCount", base="root class")
    
    class_def5 = ET.SubElement(root, 'class', name="BPersistent", base="BRTTIRefCount")
    ET.SubElement(class_def5, 'prop', name="Name", type="String")
    
    class_def6 = ET.SubElement(root, 'class', name="EnvironmentObject", base="BPersistent")
    ET.SubElement(class_def6, 'prop', name="World Matrix", type="Mtx4f")
    
    # Create main data element
    data_elem = ET.SubElement(root, 'data', 
                             **{'class': 'EnvironmentPhysics', 'id': '0x42839D80'})
    ET.SubElement(data_elem, 'prop', name="Name", data="Environment Physics")
    
    # Create environment objects array
    array_prop = ET.SubElement(data_elem, 'prop', 
                              name="Environment Physics Object Array", 
                              elements=str(len(dynamic_objects)))
    
    funcpropdata = ET.SubElement(array_prop, 'funcpropdata')
    
    # Add each dynamic object.
    # AMS2 stock files typically use high-range, pointer-like IDs and often
    # increase by 0xD0 between sibling EnvironmentObject entries.
    object_id_base = 0x8D100000
    for i, obj_info in enumerate(dynamic_objects, 1):
        object_id = object_id_base + ((i - 1) * 0xD0)
        obj_data = ET.SubElement(funcpropdata, 'data', 
                                **{'class': 'EnvironmentObject', 'id': f'0x{object_id:08X}'})
        
        # Generate instance name (template name + number)
        instance_name = f"{obj_info['definition_name']} {i}"
        ET.SubElement(obj_data, 'prop', name="Name", data=instance_name)
        
        # Add world matrix
        ET.SubElement(obj_data, 'prop', name="World Matrix", data=obj_info['matrix_string'])
    
    return root


def export_dynamic_collisions_xml(filepath: str, dynamic_objects: List[Dict[str, Any]]):
    """Export dynamic collisions XML file, returning its bodies for registration"""
    root, bodies = create_dynamic_collisions_xml(dynamic_objects)
    
    # Format and write XML without any declaration
    ET.indent(root, space="  ")
    tree = ET.ElementTree(root)
    tree.write(filepath, xml_declaration=False)
    
    print(f"Exported dynamic collisions with {len(dynamic_objects)} object types to {filepath}")
    return len(dynamic_objects), bodies


def export_dynamic_environment_xml(filepath: str, dynamic_objects: List[Dict[str, Any]]) -> int:
    """Export environment XML file with dynamic object placements"""
    root = create_environment_xml(dynamic_objects)
    
    # Format and write XML without encoding
    ET.indent(root, space="    ")
    tree = ET.ElementTree(root)
    tree.write(filepath, xml_declaration=False)
    
    # Manually write XML declaration without encoding
    with open(filepath, 'r+', encoding='utf-8') as f:
        content = f.read()
        f.seek(0)
        f.write('<?xml version="1.0"?>\n' + content)
        f.truncate()
    
    print(f"Exported environment XML with {len(dynamic_objects)} object instances to {filepath}")
    return len(dynamic_objects)


def export_dynamic_objects(base_filepath: str) -> Dict[str, Any]:
    """Export both dynamic collisions and environment files"""
    dynamic_objects = collect_dynamic_objects(bpy.context.scene)
    
    if not dynamic_objects:
        print("No dynamic objects found in scene")
        return {
            'collisions': 0, 
            'environment': 0,
            'visuals': 0,
            'registered': 0,
            'collisions_path': 'No file created',
            'env_path': 'No file created'
        }
    
    results = {}
    
    # Determine file paths
    base_path = Path(base_filepath)
    
    # Find the Tracks directory and extract track name from path structure
    tracks_dir = None
    track_name = None
    current_path = base_path.parent
    
    # Walk up the directory tree to find "Tracks" folder
    while current_path and current_path != current_path.parent:
        if current_path.name == "Tracks":
            tracks_dir = current_path
            break
        current_path = current_path.parent
    
    # Extract track name from the directory structure
    if tracks_dir is not None:
        # Look for track name in the path between the file location and Tracks directory
        relative_path = base_path.parent.relative_to(tracks_dir)
        path_parts = relative_path.parts
        
        # Track name should be in the path parts, look for common patterns
        for part in path_parts:
            if part not in ['Tracks', '_data', 'dynamic', 'physics', 'export', 'dynamic_collisions']:
                track_name = part
                break
        
    # If we still don't have a track name, try to extract from filename
    if not track_name:
        # Selecting a previously exported "<track>.env.xml" leaves ".env" on the stem,
        # which would otherwise be carried into the next export's paths.
        stem = base_path.stem.removesuffix('.env')
        track_name = stem.replace('_dynamic_collisions', '').replace('dynamic_collisions', '') or stem
    
    # If we can't find Tracks directory, create one at current location
    if tracks_dir is None:
        tracks_dir = base_path.parent
        # If no track name found yet, use the current directory name
        if not track_name:
            track_name = base_path.parent.name
    
    # Create proper AMS2 track structure paths
    # Collisions: Tracks/[track_name]/physics/dynamic_collisions.xml
    collisions_path = tracks_dir / track_name / "physics" / "dynamic_collisions.xml"
    collisions_path.parent.mkdir(parents=True, exist_ok=True)
    results['collisions'], bodies = export_dynamic_collisions_xml(str(collisions_path), dynamic_objects)
    results['collisions_path'] = str(collisions_path)
    
    # Environment: Tracks/_data/dynamic/physics/[track_name].env.xml
    env_path = tracks_dir / "_data" / "dynamic" / "physics" / f"{track_name}.env.xml"
    env_path.parent.mkdir(parents=True, exist_ok=True)
    results['environment'] = export_dynamic_environment_xml(str(env_path), dynamic_objects)
    results['env_path'] = str(env_path)

    # Registry: the pair beside the env.xml that makes these placements real bodies
    results['registered'] = export_dynamic_registry(bodies, env_path.parent)

    # Visuals: Tracks/_data/dynamic/[definition].meb
    results['visuals'] = export_dynamic_visuals(dynamic_objects, tracks_dir)

    print(f"Dynamic objects exported:")
    print(f"  Collisions: {results['collisions_path']}")
    print(f"  Environment: {results['env_path']}")
    print(f"  Visuals: {results['visuals']} mesh(es)")
    print(f"  Registered types: {results['registered']}")
    print(f"  Track name: {track_name}")
    print(f"  Tracks directory: {tracks_dir}")
    
    return results
