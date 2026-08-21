import bpy  # type: ignore
from pathlib import Path
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
import mathutils  # type: ignore
import numpy as np
from ..properties.light import is_sms_light
from ..utils.coordinate_transforms import convert_position
from .object_export import iter_visible_scene_objects
from .partitions import PartitionItem, append_partitions, build_partition_tree


def get_light_name(obj):
    """Get light name without SMS_LIGHT_ prefix"""
    if obj.name.startswith('SMS_LIGHT_'):
        return obj.name[10:]  # Remove 'SMS_LIGHT_' prefix
    return obj.name


def collect_lights(view_layer) -> List[Dict[str, Any]]:
    """Collect SMS lights from visible collections."""
    lights = []

    for obj in iter_visible_scene_objects(view_layer):
        if not is_sms_light(obj):
            continue
        light_props = obj.data.madness_light
        world_matrix = obj.matrix_world

        blender_position = world_matrix.translation
        position_array = np.array([blender_position.x, blender_position.y, blender_position.z])
        madness_position = convert_position(position_array)

        blender_direction = world_matrix.to_3x3() @ mathutils.Vector((0.0, 0.0, -1.0))
        blender_direction.normalize()
        direction_array = np.array([blender_direction.x, blender_direction.y, blender_direction.z])
        madness_direction = convert_position(direction_array)

        lights.append({
            "name": get_light_name(obj),
            "object": obj,
            "position": mathutils.Vector(madness_position),
            "direction": mathutils.Vector(madness_direction),
            "properties": light_props,
            "world_matrix": world_matrix,
        })

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


def generate_lights_sgx(lights: List[Dict[str, Any]], filepath: Path, view_layer) -> None:
    """Generate a _lights.sgx file from light data"""
    if not lights:
        print("No SMS lights found in scene")
        return

    scene = ET.Element(
        "SCENE",
        FileVersion="0.1.0.0",
        ExporterVersion="Open Madness Track Tools 0.1.0",
        NumObjects=str(len(lights)),
        Merged="1",
        NumPartitions="1",
    )

    items = []
    for i, light in enumerate(lights, 1):
        obj_elem = ET.SubElement(scene, "OBJ_ID", no=str(i))
        obj_elem.append(generate_light_xml(light, 0))
        pos = light["position"]
        range_val = light["properties"].range
        items.append(
            PartitionItem(
                obj_id=i,
                source_objects=[light["object"]],
                aabb_min=np.array([pos.x - range_val, pos.y - range_val, pos.z - range_val], dtype=np.float64),
                aabb_max=np.array([pos.x + range_val, pos.y + range_val, pos.z + range_val], dtype=np.float64),
            )
        )

    partition_count = append_partitions(scene, build_partition_tree(view_layer, items))
    print(f"Built {partition_count} partition(s) from collection hierarchy")
    ET.indent(scene, space="  ")
    ET.ElementTree(scene).write(filepath, encoding="utf-8", xml_declaration=True)


def export_lights_sgx(filepath: str) -> int:
    """Export lights SGX file and return number of lights exported"""
    view_layer = bpy.context.view_layer
    lights = collect_lights(view_layer)

    filepath_obj = Path(filepath)
    if not filepath_obj.stem.endswith("_lights"):
        filepath_obj = filepath_obj.parent / (filepath_obj.stem + "_lights.sgx")

    generate_lights_sgx(lights, filepath_obj, view_layer)

    print(f"Exported {len(lights)} lights to {filepath_obj}")
    return len(lights)
