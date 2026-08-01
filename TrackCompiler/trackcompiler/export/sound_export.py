import bpy  # type: ignore
from pathlib import Path
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
import mathutils  # type: ignore
import numpy as np
from ..properties.sound import is_sms_sound, get_sound_name, get_sound_name_for_export
from ..utils.coordinate_transforms import convert_position, convert_rotation_matrix


def collect_sounds(scene) -> List[Dict[str, Any]]:
    """Collect all SMS sound objects from the scene"""
    sounds = []

    for obj in scene.objects:
        if is_sms_sound(obj):
            sound_props = obj.madness_sound

            # Get world transform and convert to Madness coordinate system
            world_matrix = obj.matrix_world

            # Convert position using coordinate transforms
            blender_position = world_matrix.translation
            position_array = np.array([blender_position.x, blender_position.y, blender_position.z])
            madness_position = convert_position(position_array)

            # Convert orientation vector using full rotation conversion
            blender_rot = np.array(world_matrix.to_3x3())
            madness_rot = convert_rotation_matrix(blender_rot)
            local_orientation = np.array(sound_props.orientation, dtype=float)
            madness_orientation = madness_rot @ local_orientation

            # Normalize and convert back to mathutils Vector for consistency
            position = mathutils.Vector(madness_position)
            orientation = mathutils.Vector(madness_orientation).normalized()

            sound_info = {
                'name': get_sound_name(obj),
                'object': obj,
                'position': position,
                'orientation': orientation,
                'properties': sound_props,
                'world_matrix': world_matrix
            }
            sounds.append(sound_info)

    return sounds


def generate_sound_area_xml(sound_info: Dict[str, Any], area_type: str) -> ET.Element:
    """Generate XML element for a sound area definition"""
    props = sound_info['properties']
    center = sound_info['position']

    if area_type == 'SPHERICAL':
        area_elem = ET.Element("data", **{'class': 'SoundAreaSpherical'})
        ET.SubElement(area_elem, 'prop', name="Name", data=f"{sound_info['name']}_Area")
        ET.SubElement(area_elem, 'prop', name="Centre", data=f"{center.x:.6f};{center.y:.6f};{center.z:.6f}")
        ET.SubElement(area_elem, 'prop', name="Radius", data=f"{props.spherical_radius:.6f}")
        ET.SubElement(area_elem, 'prop', name="Flat", data="true" if props.spherical_flat else "false")

    elif area_type == 'OBB_2D':
        area_elem = ET.Element("data", **{'class': 'SoundArea2DOBB'})
        ET.SubElement(area_elem, 'prop', name="Name", data=f"{sound_info['name']}_Area")
        ET.SubElement(area_elem, 'prop', name="Centre", data=f"{center.x:.6f};{center.y:.6f};{center.z:.6f}")
        ET.SubElement(area_elem, 'prop', name="Direction", data=f"{props.obb_direction[0]:.6f};{props.obb_direction[1]:.6f}")
        ET.SubElement(area_elem, 'prop', name="Length", data=f"{props.obb_length:.6f}")
        ET.SubElement(area_elem, 'prop', name="Width", data=f"{props.obb_width:.6f}")

    return area_elem


def generate_environment_sound_xml(sound_info: Dict[str, Any], uid: int) -> ET.Element:
    """Generate XML element for an EnvironmentSound"""
    props = sound_info['properties']
    pos = sound_info['position']
    orientation = sound_info['orientation']
    obj = sound_info['object']

    sound_elem = ET.Element("data", **{'class': 'EnvironmentSound', 'id': f'0x{uid:08X}'})

    # Basic properties
    ET.SubElement(sound_elem, 'prop', name="Name", data=sound_info['name'])
    ET.SubElement(sound_elem, 'prop', name="SoundName", data=get_sound_name_for_export(obj))
    ET.SubElement(sound_elem, 'prop', name="Position", data=f"{pos.x:.6f};{pos.y:.6f};{pos.z:.6f}")
    ET.SubElement(sound_elem, 'prop', name="Velocity", data="0;0;0")  # Static sounds
    ET.SubElement(sound_elem, 'prop', name="Orientation", data=f"{orientation.x:.6f};{orientation.y:.6f};{orientation.z:.6f}")
    ET.SubElement(sound_elem, 'prop', name="Volume", data=f"{props.volume:.6f}")
    ET.SubElement(sound_elem, 'prop', name="FadeInTime", data=f"{props.fade_in_time:.6f}")
    ET.SubElement(sound_elem, 'prop', name="FadeOutTime", data=f"{props.fade_out_time:.6f}")
    ET.SubElement(sound_elem, 'prop', name="Range", data=f"{props.range:.6f}")

    return sound_elem


def generate_ambient_sound_xml(sound_info: Dict[str, Any], uid: int, area_uid: int = None) -> ET.Element:
    """Generate XML element for an AmbientSound"""
    props = sound_info['properties']
    obj = sound_info['object']

    sound_elem = ET.Element("data", **{'class': 'AmbientSound', 'id': f'0x{uid:08X}'})

    # Basic properties
    ET.SubElement(sound_elem, 'prop', name="Name", data=sound_info['name'])
    ET.SubElement(sound_elem, 'prop', name="SoundName", data=get_sound_name_for_export(obj))
    ET.SubElement(sound_elem, 'prop', name="DefaultAmbient", data="true" if props.default_ambient else "false")
    ET.SubElement(sound_elem, 'prop', name="FadeInTime", data=f"{props.fade_in_time:.6f}")
    ET.SubElement(sound_elem, 'prop', name="FadeOutTime", data=f"{props.fade_out_time:.6f}")
    ET.SubElement(sound_elem, 'prop', name="VelocityMinVolume", data=f"{props.velocity_min_volume:.6f}")
    ET.SubElement(sound_elem, 'prop', name="VelocityMaxVolume", data=f"{props.velocity_max_volume:.6f}")

    # Sound area definition if specified
    if props.sound_area_type != 'NONE' and area_uid is not None:
        area_ref = ET.SubElement(sound_elem, 'prop', name="SoundAreaDef")
        area_ref_data = ET.SubElement(area_ref, 'funcpropdata')
        area_data = generate_sound_area_xml(sound_info, props.sound_area_type)
        area_data.set('id', f'0x{area_uid:08X}')
        area_ref_data.append(area_data)

    # Dynamic parameters (empty for now)
    ET.SubElement(sound_elem, 'prop', name="DynamicParameters")

    return sound_elem


def generate_ambient_reverb_xml(sound_info: Dict[str, Any], uid: int) -> ET.Element:
    """Generate XML element for an AmbientReverb"""
    props = sound_info['properties']
    obj = sound_info['object']

    reverb_elem = ET.Element("data", **{'class': 'AmbientReverb', 'id': f'0x{uid:08X}'})

    # Basic properties
    ET.SubElement(reverb_elem, 'prop', name="Name", data=sound_info['name'])
    ET.SubElement(reverb_elem, 'prop', name="ReverbName", data=get_sound_name_for_export(obj))
    ET.SubElement(reverb_elem, 'prop', name="ReverbInfluence", data=f"{props.reverb_influence:.6f}")

    return reverb_elem


def generate_local_reverb_xml(sound_info: Dict[str, Any], uid: int, area_uid: int = None) -> ET.Element:
    """Generate XML element for a LocalReverb"""
    props = sound_info['properties']
    obj = sound_info['object']

    reverb_elem = ET.Element("data", **{'class': 'LocalReverb', 'id': f'0x{uid:08X}'})

    # Basic properties
    ET.SubElement(reverb_elem, 'prop', name="Name", data=sound_info['name'])
    ET.SubElement(reverb_elem, 'prop', name="ReverbName", data=get_sound_name_for_export(obj))
    ET.SubElement(reverb_elem, 'prop', name="ReverbInfluence", data=f"{props.reverb_influence:.6f}")
    ET.SubElement(reverb_elem, 'prop', name="FadeRange", data=f"{props.fade_range:.6f}")

    # Sound area definition if specified
    if props.sound_area_type != 'NONE' and area_uid is not None:
        area_ref = ET.SubElement(reverb_elem, 'prop', name="SoundAreaDef")
        area_ref_data = ET.SubElement(area_ref, 'funcpropdata')
        area_data = generate_sound_area_xml(sound_info, props.sound_area_type)
        area_data.set('id', f'0x{area_uid:08X}')
        area_ref_data.append(area_data)

    return reverb_elem


def create_level_sound_definition_xml(sounds: List[Dict[str, Any]]) -> ET.Element:
    """Create a LevelSoundDefinition XML with all sound objects"""
    # Separate sounds by type
    environment_sounds = [s for s in sounds if s['properties'].sound_type == 'ENVIRONMENT_SOUND']
    ambient_sounds = [s for s in sounds if s['properties'].sound_type == 'AMBIENT_SOUND']
    ambient_reverbs = [s for s in sounds if s['properties'].sound_type == 'AMBIENT_REVERB']
    local_reverbs = [s for s in sounds if s['properties'].sound_type == 'LOCAL_REVERB']

    # Create root element
    root = ET.Element('Reflection')

    # Add class definitions - Base classes
    ET.SubElement(root, 'class', name="BRTTIRefCount", base="root class")
    bpersistent = ET.SubElement(root, 'class', name="BPersistent", base="BRTTIRefCount")
    ET.SubElement(bpersistent, 'prop', name="Name", type="String")

    # LevelSoundDefinition class
    lsd_class = ET.SubElement(root, 'class', name="LevelSoundDefinition", base="BPersistent")
    ET.SubElement(lsd_class, 'prop', name="LevelSoundAreaDef", type="Fct")
    ET.SubElement(lsd_class, 'prop', name="AmbientSounds", type="Fct")
    ET.SubElement(lsd_class, 'prop', name="EnvironmentSounds", type="Fct")
    ET.SubElement(lsd_class, 'prop', name="AmbientReverb", type="Fct")
    ET.SubElement(lsd_class, 'prop', name="LocalReverbs", type="Fct")

    # AmbientSound class (always included)
    ET.SubElement(root, 'class', name="BRTTIRefCount", base="root class")
    bpersistent = ET.SubElement(root, 'class', name="BPersistent", base="BRTTIRefCount")
    ET.SubElement(bpersistent, 'prop', name="Name", type="String")
    
    ambient_sound_class = ET.SubElement(root, 'class', name="AmbientSound", base="BPersistent")
    ET.SubElement(ambient_sound_class, 'prop', name="SoundName", type="String")
    ET.SubElement(ambient_sound_class, 'prop', name="DefaultAmbient", type="Bool")
    ET.SubElement(ambient_sound_class, 'prop', name="FadeInTime", type="F32")
    ET.SubElement(ambient_sound_class, 'prop', name="FadeOutTime", type="F32")
    ET.SubElement(ambient_sound_class, 'prop', name="VelocityMinVolume", type="F32")
    ET.SubElement(ambient_sound_class, 'prop', name="VelocityMaxVolume", type="F32")
    ET.SubElement(ambient_sound_class, 'prop', name="SoundAreaDef", type="Fct")
    ET.SubElement(ambient_sound_class, 'prop', name="DynamicParameters", type="Fct")

    # EnvironmentSound class (always included)
    ET.SubElement(root, 'class', name="BRTTIRefCount", base="root class")
    bpersistent = ET.SubElement(root, 'class', name="BPersistent", base="BRTTIRefCount")
    ET.SubElement(bpersistent, 'prop', name="Name", type="String")
    
    env_sound_class = ET.SubElement(root, 'class', name="EnvironmentSound", base="BPersistent")
    ET.SubElement(env_sound_class, 'prop', name="SoundName", type="String")
    ET.SubElement(env_sound_class, 'prop', name="Position", type="Vec3")
    ET.SubElement(env_sound_class, 'prop', name="Velocity", type="Vec3")
    ET.SubElement(env_sound_class, 'prop', name="Orientation", type="Vec3")
    ET.SubElement(env_sound_class, 'prop', name="Volume", type="F32")
    ET.SubElement(env_sound_class, 'prop', name="FadeInTime", type="F32")
    ET.SubElement(env_sound_class, 'prop', name="FadeOutTime", type="F32")
    ET.SubElement(env_sound_class, 'prop', name="Range", type="F32")

    # AmbientReverb class (always included)
    ET.SubElement(root, 'class', name="BRTTIRefCount", base="root class")
    bpersistent = ET.SubElement(root, 'class', name="BPersistent", base="BRTTIRefCount")
    ET.SubElement(bpersistent, 'prop', name="Name", type="String")
    
    ambient_reverb_class = ET.SubElement(root, 'class', name="AmbientReverb", base="BPersistent")
    ET.SubElement(ambient_reverb_class, 'prop', name="ReverbName", type="String")
    ET.SubElement(ambient_reverb_class, 'prop', name="ReverbInfluence", type="F32")

    # LocalReverb class (always included)
    ET.SubElement(root, 'class', name="BRTTIRefCount", base="root class")
    bpersistent = ET.SubElement(root, 'class', name="BPersistent", base="BRTTIRefCount")
    ET.SubElement(bpersistent, 'prop', name="Name", type="String")
    
    local_reverb_class = ET.SubElement(root, 'class', name="LocalReverb", base="BPersistent")
    ET.SubElement(local_reverb_class, 'prop', name="ReverbName", type="String")
    ET.SubElement(local_reverb_class, 'prop', name="ReverbInfluence", type="F32")
    ET.SubElement(local_reverb_class, 'prop', name="FadeRange", type="F32")
    ET.SubElement(local_reverb_class, 'prop', name="SoundAreaDef", type="Fct")

    # Add sound area classes (always included)
    ET.SubElement(root, 'class', name="BRTTIRefCount", base="root class")
    bpersistent = ET.SubElement(root, 'class', name="BPersistent", base="BRTTIRefCount")
    ET.SubElement(bpersistent, 'prop', name="Name", type="String")
    ET.SubElement(root, 'class', name="ISoundArea", base="BPersistent")
    
    sound_area_obb = ET.SubElement(root, 'class', name="SoundArea2DOBB", base="ISoundArea")
    ET.SubElement(sound_area_obb, 'prop', name="Centre", type="Vec3")
    ET.SubElement(sound_area_obb, 'prop', name="Direction", type="Vec2")
    ET.SubElement(sound_area_obb, 'prop', name="Length", type="Float")
    ET.SubElement(sound_area_obb, 'prop', name="Width", type="Float")
    
    ET.SubElement(root, 'class', name="BRTTIRefCount", base="root class")
    bpersistent = ET.SubElement(root, 'class', name="BPersistent", base="BRTTIRefCount")
    ET.SubElement(bpersistent, 'prop', name="Name", type="String")
    ET.SubElement(root, 'class', name="ISoundArea", base="BPersistent")
    
    sound_area_spherical = ET.SubElement(root, 'class', name="SoundAreaSpherical", base="ISoundArea")
    ET.SubElement(sound_area_spherical, 'prop', name="Centre", type="Vec3")
    ET.SubElement(sound_area_spherical, 'prop', name="Radius", type="F32")
    ET.SubElement(sound_area_spherical, 'prop', name="Flat", type="Bool")

    # DynamicParameter class (always included)
    ET.SubElement(root, 'class', name="BRTTIRefCount", base="root class")
    bpersistent = ET.SubElement(root, 'class', name="BPersistent", base="BRTTIRefCount")
    ET.SubElement(bpersistent, 'prop', name="Name", type="String")
    
    dyn_param_class = ET.SubElement(root, 'class', name="DynamicParameter", base="BPersistent")
    ET.SubElement(dyn_param_class, 'prop', name="ParameterName", type="String")
    ET.SubElement(dyn_param_class, 'prop', name="MinValue", type="Float")
    ET.SubElement(dyn_param_class, 'prop', name="MaxValue", type="Float")
    ET.SubElement(dyn_param_class, 'prop', name="MinTime", type="Float")
    ET.SubElement(dyn_param_class, 'prop', name="MaxTime", type="Float")

    # Create main data element
    data_elem = ET.SubElement(root, 'data',
                             **{'class': 'LevelSoundDefinition', 'id': '0xA0046200'})
    track_name = Path(bpy.data.filepath).stem if bpy.data.filepath else "Track"
    ET.SubElement(data_elem, 'prop', name="Name", data=f"{track_name}SoundDefinition")

    # Add level sound area definition (minimal OBB covering the scene)
    if sounds:
        min_pos = mathutils.Vector((float('inf'), float('inf'), float('inf')))
        max_pos = mathutils.Vector((float('-inf'), float('-inf'), float('-inf')))

        for sound in sounds:
            pos = sound['position']
            min_pos.x = min(min_pos.x, pos.x)
            min_pos.y = min(min_pos.y, pos.y)
            min_pos.z = min(min_pos.z, pos.z)
            max_pos.x = max(max_pos.x, pos.x)
            max_pos.y = max(max_pos.y, pos.y)
            max_pos.z = max(max_pos.z, pos.z)

        center = (min_pos + max_pos) * 0.5
        length = max_pos.x - min_pos.x + 100  # Add padding
        width = max_pos.z - min_pos.z + 100   # Add padding

        level_area = ET.SubElement(data_elem, 'prop', name="LevelSoundAreaDef")
        level_data = ET.SubElement(level_area, 'funcpropdata')
        level_obb = ET.SubElement(level_data, 'data', **{'class': 'SoundArea2DOBB', 'id': '0x9F752DA0'})
        ET.SubElement(level_obb, 'prop', name="Name", data=f"{track_name}Level")
        ET.SubElement(level_obb, 'prop', name="Centre", data=f"{center.x:.6f};{center.y:.6f};{center.z:.6f}")
        ET.SubElement(level_obb, 'prop', name="Direction", data="1;0")
        ET.SubElement(level_obb, 'prop', name="Length", data=f"{length:.6f}")
        ET.SubElement(level_obb, 'prop', name="Width", data=f"{width:.6f}")

    # Add Ambient Sounds (always include property first, matching AMS2 ordering)
    amb_sounds_prop = ET.SubElement(data_elem, 'prop', name="AmbientSounds", elements=str(len(ambient_sounds)))
    amb_sounds_data = ET.SubElement(amb_sounds_prop, 'funcpropdata')

    for i, sound in enumerate(ambient_sounds, 1):
        uid = 0x4070000 + i * 0x1000  # Unique IDs
        area_uid = None
        if sound['properties'].sound_area_type != 'NONE':
            area_uid = 0x4080000 + i * 0x1000
        amb_sounds_data.append(generate_ambient_sound_xml(sound, uid, area_uid))

    # Add Environment Sounds (second, matching AMS2 ordering)
    env_sounds_prop = ET.SubElement(data_elem, 'prop', name="EnvironmentSounds", elements=str(len(environment_sounds)))
    env_sounds_data = ET.SubElement(env_sounds_prop, 'funcpropdata')

    for i, sound in enumerate(environment_sounds, 1):
        uid = 0x4060000 + i * 0x1000  # Unique IDs
        env_sounds_data.append(generate_environment_sound_xml(sound, uid))

    # Add Ambient Reverbs (single property, even if empty)
    amb_reverbs_prop = ET.SubElement(data_elem, 'prop', name="AmbientReverb")
    amb_reverbs_data = ET.SubElement(amb_reverbs_prop, 'funcpropdata')

    for i, reverb in enumerate(ambient_reverbs, 1):
        uid = 0x4090000 + i * 0x1000  # Unique IDs
        amb_reverbs_data.append(generate_ambient_reverb_xml(reverb, uid))

    # Add Local Reverbs (always include property)
    local_reverbs_prop = ET.SubElement(data_elem, 'prop', name="LocalReverbs", elements=str(len(local_reverbs)))
    local_reverbs_data = ET.SubElement(local_reverbs_prop, 'funcpropdata')

    for i, reverb in enumerate(local_reverbs, 1):
        uid = 0x40A0000 + i * 0x1000  # Unique IDs
        area_uid = None
        if reverb['properties'].sound_area_type != 'NONE':
            area_uid = 0x40B0000 + i * 0x1000
        local_reverbs_data.append(generate_local_reverb_xml(reverb, uid, area_uid))

    return root


def export_sound_definition_lsd(filepath: str) -> int:
    """Export sound definition LSD file and return number of sounds exported"""
    sounds = collect_sounds(bpy.context.scene)

    # Ensure the filename ends with .lsd
    filepath_obj = Path(filepath)
    if not filepath_obj.suffix == '.lsd':
        filepath_obj = filepath_obj.parent / (filepath_obj.stem + '.lsd')

    root = create_level_sound_definition_xml(sounds)

    # Format and write XML with 4-space indentation
    ET.indent(root, space="    ")
    tree = ET.ElementTree(root)
    
    # Write without encoding in declaration (matches Imola format)
    tree.write(filepath_obj, encoding="unicode", xml_declaration=False)
    
    # Manually prepend the XML declaration without encoding
    with open(filepath_obj, 'r+', encoding='utf-8') as f:
        content = f.read()
        f.seek(0)
        f.write('<?xml version="1.0"?>\n' + content)
        f.truncate()

    print(f"Exported {len(sounds)} sound objects to {filepath_obj}")
    return len(sounds)


def export_sounds(base_filepath: str) -> Dict[str, Any]:
    """Export sounds to LSD file"""
    sounds = collect_sounds(bpy.context.scene)

    if not sounds:
        print("No SMS sound objects found in scene")
        return {
            'sounds': 0,
            'lsd_path': 'No file created'
        }

    results = {}

    # Use the exact filepath specified by the user
    lsd_path = Path(base_filepath)
    
    # Ensure the filename ends with .lsd
    if not lsd_path.suffix == '.lsd':
        lsd_path = lsd_path.with_suffix('.lsd')
    
    # Create parent directory if it doesn't exist
    lsd_path.parent.mkdir(parents=True, exist_ok=True)
    
    results['sounds'] = export_sound_definition_lsd(str(lsd_path))
    results['lsd_path'] = str(lsd_path)

    print(f"Sounds exported:")
    print(f"  LSD: {results['lsd_path']}")
    print(f"  Total sounds: {results['sounds']}")

    return results
