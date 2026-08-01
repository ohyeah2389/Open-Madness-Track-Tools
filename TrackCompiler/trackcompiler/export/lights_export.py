import bpy  # type: ignore
from pathlib import Path
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
import mathutils  # type: ignore
import numpy as np
from ..properties.light import is_sms_light
from ..utils.coordinate_transforms import decompose_matrix, convert_position


def get_light_name(obj):
    """Get light name without SMS_LIGHT_ prefix"""
    if obj.name.startswith('SMS_LIGHT_'):
        return obj.name[10:]  # Remove 'SMS_LIGHT_' prefix
    return obj.name


def collect_lights(scene) -> List[Dict[str, Any]]:
    """Collect all SMS lights from the scene"""
    lights = []
    
    for obj in scene.objects:
        if is_sms_light(obj):
            light_data = obj.data
            light_props = light_data.madness_light
            
            # Get world transform and convert to Madness coordinate system
            world_matrix = obj.matrix_world
            
            # Convert position using coordinate transforms
            blender_position = world_matrix.translation
            position_array = np.array([blender_position.x, blender_position.y, blender_position.z])
            madness_position = convert_position(position_array)
            
            # Calculate direction vector in Blender space (lights point down -Z by default)
            blender_direction = world_matrix.to_3x3() @ mathutils.Vector((0.0, 0.0, -1.0))
            blender_direction.normalize()
            
            # Convert direction vector to Madness coordinates 
            # Direction vectors transform the same way as positions but without translation
            direction_array = np.array([blender_direction.x, blender_direction.y, blender_direction.z])
            madness_direction = convert_position(direction_array)  # Same transform as position
            
            # Convert back to mathutils Vector for consistency
            direction = mathutils.Vector(madness_direction)
            position = mathutils.Vector(madness_position)
            
            light_info = {
                'name': get_light_name(obj),
                'object': obj,
                'position': position,
                'direction': direction,
                'properties': light_props,
                'world_matrix': world_matrix
            }
            lights.append(light_info)
    
    return lights


def generate_light_xml(light_info: Dict[str, Any], uid: int) -> ET.Element:
    """Generate XML element for a single light"""
    props = light_info['properties']
    pos = light_info['position']
    direction = light_info['direction']
    
    # Create LIGHT element with all attributes
    light_elem = ET.Element("LIGHT")
    light_elem.set("UID", str(uid))
    light_elem.set("Name", light_info['name'])
    light_elem.set("Type", props.light_type)
    light_elem.set("Position", f"{pos.x:.6f} {pos.y:.6f} {pos.z:.6f}")
    light_elem.set("Direction", f"{direction.x:.6f} {direction.y:.6f} {direction.z:.6f}")
    light_elem.set("Colour", f"{props.colour[0]:.1f} {props.colour[1]:.1f} {props.colour[2]:.1f}")
    light_elem.set("Intensity", f"{props.intensity:.1f}")
    light_elem.set("Range", f"{props.range:.1f}")
    
    # Spotlight-specific properties
    if props.light_type in ['SPOTLIGHT', 'SPOTLIGHTPROJECTED']:
        light_elem.set("InnerAngle", f"{props.inner_angle:.1f}")
        light_elem.set("OuterAngle", f"{props.outer_angle:.1f}")
    
    # Projected spotlight-specific properties
    if props.light_type == 'SPOTLIGHTPROJECTED':
        light_elem.set("HorizontalAngle", f"{props.horizontal_angle:.1f}")
        light_elem.set("VerticalAngle", f"{props.vertical_angle:.1f}")
        if props.projected_texture:
            light_elem.set("ProjectedTexture", props.projected_texture)
    
    # Shadow and rendering properties
    light_elem.set("CastsShadows", "TRUE" if props.casts_shadows else "FALSE")
    light_elem.set("NoSpecular", "TRUE" if props.no_specular else "FALSE")
    light_elem.set("NoSmoothDistAtten", "TRUE" if props.no_smooth_dist_atten else "FALSE")
    light_elem.set("IncludeInLightMaps", "TRUE" if props.include_in_light_maps else "FALSE")
    light_elem.set("LightIntensityTweakable", "TRUE" if props.light_intensity_tweakable else "FALSE")
    
    # Light group
    light_elem.set("LightGroup", str(props.light_group))
    
    # Ground plane properties
    light_elem.set("GroundPlaneDistance", f"{props.ground_plane_distance:.6f}")
    normal = props.ground_plane_normal
    light_elem.set("GroundPlaneNormal", f"{normal[0]:.1f} {normal[1]:.1f} {normal[2]:.1f}")
    light_elem.set("GroundPlaneAutoSet", "TRUE" if props.ground_plane_auto_set else "FALSE")
    light_elem.set("GroundPlaneShow", "TRUE" if props.ground_plane_show else "FALSE")
    
    return light_elem


def calculate_scene_bounds(lights: List[Dict[str, Any]]) -> tuple:
    """Calculate bounding box for all lights"""
    if not lights:
        return (-10.0, -10.0, -10.0), (10.0, 10.0, 10.0)
    
    min_x = min_y = min_z = float('inf')
    max_x = max_y = max_z = float('-inf')
    
    for light in lights:
        pos = light['position']
        props = light['properties']
        
        # Expand bounds by light range
        range_val = props.range
        
        min_x = min(min_x, pos.x - range_val)
        min_y = min(min_y, pos.y - range_val)
        min_z = min(min_z, pos.z - range_val)
        
        max_x = max(max_x, pos.x + range_val)
        max_y = max(max_y, pos.y + range_val)
        max_z = max(max_z, pos.z + range_val)
    
    return (min_x, min_y, min_z), (max_x, max_y, max_z)


def generate_lights_sgx(lights: List[Dict[str, Any]], filepath: Path) -> None:
    """Generate a _lights.sgx file from light data"""
    if not lights:
        print("No SMS lights found in scene")
        return
    
    # Create root SCENE element
    scene = ET.Element(
        "SCENE",
        FileVersion="0.1.0.0",
        ExporterVersion="Open Madness Track Tools 0.1.0",
        NumObjects=str(len(lights)),
        Merged="1",
        NumPartitions="1"
    )
    
    # Add light objects
    for i, light in enumerate(lights, 1):
        obj_elem = ET.SubElement(scene, "OBJ_ID", no=str(i))
        light_elem = generate_light_xml(light, 0)  # UID 0 for all lights
        obj_elem.append(light_elem)
    
    # Calculate scene bounds
    scene_min, scene_max = calculate_scene_bounds(lights)
    
    # Add partition
    partition = ET.SubElement(scene, "PARTITION_ID", no="0")
    ET.SubElement(
        partition,
        "AABBOX",
        min=f"{scene_min[0]:.6f} {scene_min[1]:.6f} {scene_min[2]:.6f}",
        max=f"{scene_max[0]:.6f} {scene_max[1]:.6f} {scene_max[2]:.6f}"
    )
    
    # Add child partitions and objects
    ET.SubElement(partition, "CHILD_PARTITIONS", IDs="NONE")
    child_ids = " ".join(str(i) for i in range(1, len(lights) + 1))
    ET.SubElement(partition, "CHILD_OBJS", IDs=child_ids)
    
    # Format and write XML
    ET.indent(scene, space="  ")
    tree = ET.ElementTree(scene)
    tree.write(filepath, encoding="utf-8", xml_declaration=True)


def export_lights_sgx(filepath: str) -> int:
    """Export lights SGX file and return number of lights exported"""
    lights = collect_lights(bpy.context.scene)
    
    # Ensure the filename ends with _lights.sgx
    filepath_obj = Path(filepath)
    if not filepath_obj.stem.endswith('_lights'):
        # Replace .sgx with _lights.sgx
        new_stem = filepath_obj.stem + '_lights'
        filepath_obj = filepath_obj.parent / (new_stem + '.sgx')
    
    generate_lights_sgx(lights, filepath_obj)
    
    print(f"Exported {len(lights)} lights to {filepath_obj}")
    return len(lights)
