import bpy  # type: ignore
from bpy.props import BoolProperty, FloatProperty, EnumProperty, FloatVectorProperty, PointerProperty# type: ignore
import json
from pathlib import Path


# Cache for sound lists to avoid repeated file reads
_sound_cache = None


def get_available_sounds():
    """Load available sound paths from lsd_analysis_results.json"""
    global _sound_cache

    # Return cached results if available
    if _sound_cache is not None:
        return _sound_cache

    # Get the database folder path relative to this addon
    addon_dir = Path(__file__).parent.parent
    database_path = addon_dir / "database" / "lsd_analysis_results.json"

    sounds = {
        'ENVIRONMENT_SOUND': [("", "Select Sound", "")],
        'AMBIENT_SOUND': [("", "Select Sound", "")],
        'AMBIENT_REVERB': [("", "Select Reverb", "")],
        'LOCAL_REVERB': [("", "Select Reverb", "")]
    }

    if database_path.exists():
        try:
            with open(database_path, 'r') as f:
                data = json.load(f)

            # Load Environment Sounds - prioritize Both > AMS2 > PC2
            if 'EnvironmentSounds' in data:
                env_sounds = []
                
                # Add "Both Games" sounds first
                if 'Both' in data['EnvironmentSounds']:
                    for sound_path, info in data['EnvironmentSounds']['Both'].items():
                        category = info.get('Category', 'Other')
                        count = info.get('Count', 0)
                        env_sounds.append((sound_path, f"[Both] {sound_path.split('/')[-1]} ({category})", f"Both games, used {count} times"))
                
                # Add AMS2-only sounds
                if 'AMS2' in data['EnvironmentSounds']:
                    for sound_path, info in data['EnvironmentSounds']['AMS2'].items():
                        # Skip if already in Both
                        if 'Both' in data['EnvironmentSounds'] and sound_path in data['EnvironmentSounds']['Both']:
                            continue
                        category = info.get('Category', 'Other')
                        count = info.get('Count', 0)
                        env_sounds.append((sound_path, f"[AMS2] {sound_path.split('/')[-1]} ({category})", f"AMS2 only, used {count} times"))
                
                # Sort by prefix (Both first, then AMS2), then by category, then by name
                env_sounds.sort(key=lambda x: (0 if x[1].startswith('[Both]') else 1, x[1].split('(')[1] if '(' in x[1] else '', x[0]))
                sounds['ENVIRONMENT_SOUND'].extend(env_sounds)

            # Load Ambient Sounds
            if 'AmbientSounds' in data:
                amb_sounds = []
                
                # Add "Both Games" sounds first
                if 'Both' in data['AmbientSounds']:
                    for sound_path, info in data['AmbientSounds']['Both'].items():
                        category = info.get('Category', 'Other')
                        count = info.get('Count', 0)
                        amb_sounds.append((sound_path, f"[Both] {sound_path.split('/')[-1]} ({category})", f"Both games, used {count} times"))
                
                # Add AMS2-only sounds
                if 'AMS2' in data['AmbientSounds']:
                    for sound_path, info in data['AmbientSounds']['AMS2'].items():
                        if 'Both' in data['AmbientSounds'] and sound_path in data['AmbientSounds']['Both']:
                            continue
                        category = info.get('Category', 'Other')
                        count = info.get('Count', 0)
                        amb_sounds.append((sound_path, f"[AMS2] {sound_path.split('/')[-1]} ({category})", f"AMS2 only, used {count} times"))
                
                amb_sounds.sort(key=lambda x: (0 if x[1].startswith('[Both]') else 1, x[1].split('(')[1] if '(' in x[1] else '', x[0]))
                sounds['AMBIENT_SOUND'].extend(amb_sounds)

            # Load Ambient Reverbs
            if 'AmbientReverbs' in data:
                amb_reverbs = []
                
                # Add "Both Games" reverbs first
                if 'Both' in data['AmbientReverbs']:
                    for reverb_name, info in data['AmbientReverbs']['Both'].items():
                        count = info.get('Count', 0)
                        amb_reverbs.append((reverb_name, f"[Both] {reverb_name}", f"Both games, used {count} times"))
                
                # Add AMS2-only reverbs
                if 'AMS2' in data['AmbientReverbs']:
                    for reverb_name, info in data['AmbientReverbs']['AMS2'].items():
                        if 'Both' in data['AmbientReverbs'] and reverb_name in data['AmbientReverbs']['Both']:
                            continue
                        count = info.get('Count', 0)
                        amb_reverbs.append((reverb_name, f"[AMS2] {reverb_name}", f"AMS2 only, used {count} times"))
                
                amb_reverbs.sort(key=lambda x: (0 if x[1].startswith('[Both]') else 1, x[0]))
                sounds['AMBIENT_REVERB'].extend(amb_reverbs)

            # Load Local Reverbs
            if 'LocalReverbs' in data:
                local_reverbs = []
                
                # Add "Both Games" reverbs first
                if 'Both' in data['LocalReverbs']:
                    for reverb_name, info in data['LocalReverbs']['Both'].items():
                        count = info.get('Count', 0)
                        local_reverbs.append((reverb_name, f"[Both] {reverb_name}", f"Both games, used {count} times"))
                
                # Add AMS2-only reverbs
                if 'AMS2' in data['LocalReverbs']:
                    for reverb_name, info in data['LocalReverbs']['AMS2'].items():
                        if 'Both' in data['LocalReverbs'] and reverb_name in data['LocalReverbs']['Both']:
                            continue
                        count = info.get('Count', 0)
                        local_reverbs.append((reverb_name, f"[AMS2] {reverb_name}", f"AMS2 only, used {count} times"))
                
                local_reverbs.sort(key=lambda x: (0 if x[1].startswith('[Both]') else 1, x[0]))
                sounds['LOCAL_REVERB'].extend(local_reverbs)

        except Exception as e:
            print(f"Error loading sound database: {e}")
            # Return basic sound list on error
            for key in sounds.keys():
                sounds[key].append(("ERROR", "Sound Load Error", "Failed to load sounds"))

    # Cache the results
    _sound_cache = sounds
    return sounds


def get_environment_sounds_enum(self, context):
    """Get available environment sounds"""
    try:
        sounds = get_available_sounds()
        return sounds.get('ENVIRONMENT_SOUND', [("", "No sounds available", "")])
    except Exception as e:
        print(f"Error in get_environment_sounds_enum: {e}")
        return [("", "Error loading sounds", ""), ("ERROR", "Sound Load Error", "Failed to load sounds")]


def get_ambient_sounds_enum(self, context):
    """Get available ambient sounds"""
    try:
        sounds = get_available_sounds()
        return sounds.get('AMBIENT_SOUND', [("", "No sounds available", "")])
    except Exception as e:
        print(f"Error in get_ambient_sounds_enum: {e}")
        return [("", "Error loading sounds", ""), ("ERROR", "Sound Load Error", "Failed to load sounds")]


def get_ambient_reverbs_enum(self, context):
    """Get available ambient reverbs"""
    try:
        sounds = get_available_sounds()
        return sounds.get('AMBIENT_REVERB', [("", "No reverbs available", "")])
    except Exception as e:
        print(f"Error in get_ambient_reverbs_enum: {e}")
        return [("", "Error loading reverbs", ""), ("ERROR", "Reverb Load Error", "Failed to load reverbs")]


def get_local_reverbs_enum(self, context):
    """Get available local reverbs"""
    try:
        sounds = get_available_sounds()
        return sounds.get('LOCAL_REVERB', [("", "No reverbs available", "")])
    except Exception as e:
        print(f"Error in get_local_reverbs_enum: {e}")
        return [("", "Error loading reverbs", ""), ("ERROR", "Reverb Load Error", "Failed to load reverbs")]


class MadnessSoundProperties(bpy.types.PropertyGroup):
    """Properties for SMS_SOUND_ prefixed empty objects"""

    # Sound Type
    sound_type: EnumProperty(
        name="Sound Type",
        description="Type of sound object",
        items=[
            ('ENVIRONMENT_SOUND', "Environment Sound", "Positional sound with volume and range"),
            ('AMBIENT_SOUND', "Ambient Sound", "Background ambient sound"),
            ('AMBIENT_REVERB', "Ambient Reverb", "Global reverb setting"),
            ('LOCAL_REVERB', "Local Reverb", "Local reverb area"),
        ],
        default='ENVIRONMENT_SOUND'
    )  # type: ignore

    # Sound Name/Path - EnumProperty for Environment Sounds
    environment_sound_name: EnumProperty(
        name="Environment Sound",
        description="Select environment sound from available sounds",
        items=get_environment_sounds_enum
    )  # type: ignore

    # Sound Name/Path - EnumProperty for Ambient Sounds
    ambient_sound_name: EnumProperty(
        name="Ambient Sound",
        description="Select ambient sound from available sounds",
        items=get_ambient_sounds_enum
    )  # type: ignore

    # Reverb Name - EnumProperty for Ambient Reverbs
    ambient_reverb_name: EnumProperty(
        name="Ambient Reverb",
        description="Select ambient reverb from available reverbs",
        items=get_ambient_reverbs_enum
    )  # type: ignore

    # Reverb Name - EnumProperty for Local Reverbs
    local_reverb_name: EnumProperty(
        name="Local Reverb",
        description="Select local reverb from available reverbs",
        items=get_local_reverbs_enum
    )  # type: ignore

    # Volume (for Environment and Ambient sounds)
    volume: FloatProperty(
        name="Volume",
        description="Sound volume (0.0 to 1.0)",
        default=1.0,
        min=0.0,
        max=1.0
    )  # type: ignore

    # Range (for Environment sounds)
    range: FloatProperty(
        name="Range",
        description="Sound range/distance in meters",
        default=50.0,
        min=0.0,
        max=1000.0
    )  # type: ignore

    # Fade Times
    fade_in_time: FloatProperty(
        name="Fade In Time",
        description="Time to fade in sound (seconds)",
        default=0.0,
        min=0.0,
        max=60.0
    )  # type: ignore

    fade_out_time: FloatProperty(
        name="Fade Out Time",
        description="Time to fade out sound (seconds)",
        default=0.0,
        min=0.0,
        max=60.0
    )  # type: ignore

    # Reverb Influence (for reverb types)
    reverb_influence: FloatProperty(
        name="Reverb Influence",
        description="Reverb influence strength (0.0 to 1.0)",
        default=1.0,
        min=0.0,
        max=1.0
    )  # type: ignore

    # Fade Range (for Local Reverb)
    fade_range: FloatProperty(
        name="Fade Range",
        description="Fade range for local reverb (meters)",
        default=10.0,
        min=0.0,
        max=1000.0
    )  # type: ignore

    # Default Ambient (for Ambient sounds)
    default_ambient: BoolProperty(
        name="Default Ambient",
        description="Whether this is the default ambient sound",
        default=False
    )  # type: ignore

    # Velocity-based volume control (for Ambient sounds)
    velocity_min_volume: FloatProperty(
        name="Velocity Min Volume",
        description="Minimum volume at low velocity",
        default=100.0,
        min=0.0,
        max=500.0
    )  # type: ignore

    velocity_max_volume: FloatProperty(
        name="Velocity Max Volume",
        description="Maximum volume at high velocity",
        default=0.0,
        min=0.0,
        max=500.0
    )  # type: ignore

    # Orientation (for Environment sounds)
    orientation: FloatVectorProperty(
        name="Orientation",
        description="Sound orientation vector",
        default=(0.0, 0.0, 1.0),
        subtype='XYZ'
    )  # type: ignore

    # Sound Area Type (for local reverb and ambient sounds)
    sound_area_type: EnumProperty(
        name="Sound Area Type",
        description="Type of sound area definition",
        items=[
            ('NONE', "None", "No area definition"),
            ('SPHERICAL', "Spherical", "Spherical area"),
            ('OBB_2D', "2D OBB", "2D Oriented Bounding Box"),
        ],
        default='NONE'
    )  # type: ignore

    # Spherical area properties
    spherical_radius: FloatProperty(
        name="Radius",
        description="Spherical area radius (meters)",
        default=10.0,
        min=0.0,
        max=1000.0
    )  # type: ignore

    spherical_flat: BoolProperty(
        name="Flat",
        description="Whether the spherical area is flat",
        default=False
    )  # type: ignore

    # 2D OBB area properties
    obb_direction: FloatVectorProperty(
        name="Direction",
        description="2D direction vector (X, Y components)",
        default=(1.0, 0.0),
        size=2
    )  # type: ignore

    obb_length: FloatProperty(
        name="Length",
        description="OBB length (meters)",
        default=20.0,
        min=0.0,
        max=1000.0
    )  # type: ignore

    obb_width: FloatProperty(
        name="Width",
        description="OBB width (meters)",
        default=10.0,
        min=0.0,
        max=1000.0
    )  # type: ignore


def get_sound_name_for_export(obj):
    """Get the appropriate sound name for export based on sound type"""
    sound_props = obj.madness_sound
    
    if sound_props.sound_type == 'ENVIRONMENT_SOUND':
        return sound_props.environment_sound_name
    elif sound_props.sound_type == 'AMBIENT_SOUND':
        return sound_props.ambient_sound_name
    elif sound_props.sound_type == 'AMBIENT_REVERB':
        return sound_props.ambient_reverb_name
    elif sound_props.sound_type == 'LOCAL_REVERB':
        return sound_props.local_reverb_name
    
    return ""


def is_sms_sound(obj):
    """Check if object is an SMS sound object"""
    return (obj and
            obj.type == 'EMPTY' and
            obj.name.startswith('SMS_SOUND_'))


def get_sound_name(obj):
    """Get sound object name without SMS_SOUND_ prefix"""
    if obj.name.startswith('SMS_SOUND_'):
        return obj.name[10:]  # Remove 'SMS_SOUND_' prefix
    return obj.name


def register():
    bpy.utils.register_class(MadnessSoundProperties)
    bpy.types.Object.madness_sound = PointerProperty(type=MadnessSoundProperties)
    
    # Load sounds to populate cache
    try:
        sounds = get_available_sounds()
        env_count = len(sounds.get('ENVIRONMENT_SOUND', [])) - 1  # Subtract the empty option
        amb_count = len(sounds.get('AMBIENT_SOUND', [])) - 1
        amb_rev_count = len(sounds.get('AMBIENT_REVERB', [])) - 1
        local_rev_count = len(sounds.get('LOCAL_REVERB', [])) - 1
        print(f"Loaded AMS2-compatible sounds: {env_count} environment, {amb_count} ambient, {amb_rev_count} ambient reverbs, {local_rev_count} local reverbs")
    except Exception as e:
        print(f"Warning: Could not load sound database: {e}")


def unregister():
    del bpy.types.Object.madness_sound
    bpy.utils.unregister_class(MadnessSoundProperties)