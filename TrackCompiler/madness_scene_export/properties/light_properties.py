import bpy  # type: ignore
from bpy.props import (  # type: ignore
    BoolProperty, FloatProperty, IntProperty, StringProperty,
    EnumProperty, FloatVectorProperty, PointerProperty
)


class MadnessLightProperties(bpy.types.PropertyGroup):
    """Properties for SMS_LIGHT_ prefixed light objects"""

    # Light Type
    light_type: EnumProperty(
        name="Light Type",
        description="Type of light",
        items=[
            ('AMBIENT', "Ambient", "Ambient light"),
            ('DIRECTIONAL', "Directional", "Directional light (like sun)"),
            ('POINT', "Point", "Point light"),
            ('SPOTLIGHT', "Spotlight", "Spotlight"),
            ('SPOTLIGHTPROJECTED', "Spotlight Projected", "Spotlight with projected texture"),
        ],
        default='SPOTLIGHT'
    )  # type: ignore

    # Light Color
    colour: FloatVectorProperty(
        name="Colour",
        description="Light color (RGB)",
        default=(1.0, 1.0, 1.0),
        min=0.0,
        max=1.0,
        subtype='COLOR'
    )  # type: ignore

    # Light Intensity
    intensity: FloatProperty(
        name="Intensity",
        description="Light intensity",
        default=1500.0,
        min=0.0,
        max=10000.0
    )  # type: ignore

    # Light Range
    range: FloatProperty(
        name="Range",
        description="Light range/distance",
        default=30.0,
        min=0.0,
        max=1000.0
    )  # type: ignore

    # Spotlight Angles
    inner_angle: FloatProperty(
        name="Inner Angle",
        description="Inner cone angle in degrees (-1.0 for auto)",
        default=-1.0,
        min=-1.0,
        max=180.0
    )  # type: ignore

    outer_angle: FloatProperty(
        name="Outer Angle",
        description="Outer cone angle in degrees",
        default=120.0,
        min=0.0,
        max=180.0
    )  # type: ignore

    # Projected Light Angles
    horizontal_angle: FloatProperty(
        name="Horizontal Angle",
        description="Horizontal projection angle in degrees",
        default=45.0,
        min=0.0,
        max=180.0
    )  # type: ignore

    vertical_angle: FloatProperty(
        name="Vertical Angle",
        description="Vertical projection angle in degrees",
        default=45.0,
        min=0.0,
        max=180.0
    )  # type: ignore

    # Shadow Properties
    casts_shadows: BoolProperty(
        name="Casts Shadows",
        description="Whether this light casts shadows",
        default=True
    )  # type: ignore

    no_specular: BoolProperty(
        name="No Specular",
        description="Disable specular highlights",
        default=False
    )  # type: ignore

    no_smooth_dist_atten: BoolProperty(
        name="No Smooth Distance Attenuation",
        description="Disable smooth distance attenuation",
        default=True
    )  # type: ignore

    # Light Maps
    include_in_light_maps: BoolProperty(
        name="Include In Light Maps",
        description="Include this light in light maps",
        default=False
    )  # type: ignore

    # Tweakable
    light_intensity_tweakable: BoolProperty(
        name="Light Intensity Tweakable",
        description="Allow intensity to be tweaked at runtime",
        default=True
    )  # type: ignore

    # Light Group
    light_group: IntProperty(
        name="Light Group",
        description="Light group ID",
        default=3,
        min=0,
        max=255
    )  # type: ignore

    # Ground Plane Properties
    ground_plane_distance: FloatProperty(
        name="Ground Plane Distance",
        description="Distance to ground plane",
        default=5.0,
        min=0.0,
        max=1000.0
    )  # type: ignore

    ground_plane_normal: FloatVectorProperty(
        name="Ground Plane Normal",
        description="Ground plane normal vector",
        default=(0.0, 1.0, 0.0),
        subtype='XYZ'
    )  # type: ignore

    ground_plane_auto_set: BoolProperty(
        name="Ground Plane Auto Set",
        description="Automatically set ground plane",
        default=True
    )  # type: ignore

    ground_plane_show: BoolProperty(
        name="Ground Plane Show",
        description="Show ground plane visualization",
        default=True
    )  # type: ignore

    # Projected Texture
    projected_texture: StringProperty(
        name="Projected Texture",
        description="Path to projected texture file",
        default=""
    )  # type: ignore


def is_sms_light(obj):
    """Check if object is an SMS light"""
    return obj.type == 'LIGHT' and obj.name.startswith('SMS_LIGHT_')


def register():
    bpy.utils.register_class(MadnessLightProperties)
    bpy.types.Light.madness_light = PointerProperty(type=MadnessLightProperties)


def unregister():
    del bpy.types.Light.madness_light
    bpy.utils.unregister_class(MadnessLightProperties)
