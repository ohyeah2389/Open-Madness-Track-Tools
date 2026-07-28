import bpy # type: ignore
from bpy.props import FloatProperty, IntProperty, StringProperty, EnumProperty, FloatVectorProperty, PointerProperty # type: ignore


class MadnessAreaProperties(bpy.types.PropertyGroup):
    """Properties for SMS_CAMZONE_ prefixed empty objects"""

    area_type: EnumProperty(
        name="Area Type",
        description="Type of camera area",
        items=[
            ('SPHERE', "Sphere", "Spherical area"),
            ('OBB', "OBB", "Oriented bounding box area"),
        ],
        default='SPHERE',
        update=lambda self, context: update_area_display(context.object)
    )  # type: ignore

    # Common Properties
    area_name: StringProperty(
        name="Area Name",
        description="Name of the area",
        default=""
    )  # type: ignore


    fov: FloatProperty(
        name="FOV",
        description="Field of view override for cameras in this area (degrees)",
        default=0.0,
        min=0.0,
        max=180.0
    )  # type: ignore

    focus_delay: FloatProperty(
        name="Focus Delay",
        description="Focus delay for cameras in this area",
        default=0.0,
        min=0.0,
        max=10.0
    )  # type: ignore

    zoom_speed: FloatProperty(
        name="Zoom Speed",
        description="Zoom speed for cameras in this area",
        default=0.0,
        min=0.0,
        max=10.0
    )  # type: ignore

    camera_group: IntProperty(
        name="Camera Group",
        description="Camera group this area belongs to",
        default=2000,
        min=0,
        max=65535
    )  # type: ignore

    # Sphere Area Properties

    sphere_radius: FloatProperty(
        name="Radius",
        description="Radius of sphere area",
        default=10.0,
        min=0.1,
        max=1000.0,
        update=lambda self, context: update_sphere_display(context.object)
    )  # type: ignore

    # OBB Area Properties
    obb_dimensions: FloatVectorProperty(
        name="Dimensions",
        description="Dimensions of OBB area (width, height, depth)",
        default=(10.0, 5.0, 10.0),
        subtype='XYZ',
        min=0.1,
        update=lambda self, context: update_obb_display(context.object)
    )  # type: ignore


def update_area_display(obj):
    """Update the empty's display properties based on area type"""
    if not obj or obj.type != 'EMPTY' or not is_sms_area(obj):
        return

    area_props = obj.madness_area

    if area_props.area_type == 'SPHERE':
        obj.empty_display_type = 'SPHERE'
        obj.empty_display_size = area_props.sphere_radius
        obj.scale = (1.0, 1.0, 1.0)
    elif area_props.area_type == 'OBB':
        obj.empty_display_type = 'CUBE'
        obj.empty_display_size = 1.0
        # Scale the object to match OBB dimensions
        # Game dimensions (width, height, depth) -> Blender scale (x, z, y)
        game_dims = area_props.obb_dimensions
        blender_scale = (game_dims.x, game_dims.z, game_dims.y)
        obj.scale = blender_scale


def update_sphere_display(obj):
    """Update the empty's display size when sphere radius changes"""
    if not obj or obj.type != 'EMPTY' or not is_sms_area(obj):
        return

    area_props = obj.madness_area
    if area_props.area_type == 'SPHERE':
        obj.empty_display_size = area_props.sphere_radius


def update_obb_display(obj):
    """Update the empty's scale when OBB dimensions change"""
    if not obj or obj.type != 'EMPTY' or not is_sms_area(obj):
        return

    area_props = obj.madness_area
    if area_props.area_type == 'OBB':
        # Convert game dimensions to Blender scale for visualization
        # Game dimensions (width, height, depth) -> Blender scale (x, z, y)
        game_dims = area_props.obb_dimensions
        blender_scale = (game_dims.x, game_dims.z, game_dims.y)
        obj.scale = blender_scale


def is_sms_area(obj):
    """Check if object is an SMS camera area"""
    return obj.type == 'EMPTY' and obj.name.startswith('SMS_CAMZONE_')


def get_area_name(obj):
    """Get the area name, using custom name or object name without prefix"""
    if obj.madness_area.area_name:
        return obj.madness_area.area_name
    else:
        return obj.name[12:]  # Remove 'SMS_CAMZONE_' prefix


def register():
    bpy.utils.register_class(MadnessAreaProperties)
    bpy.types.Object.madness_area = PointerProperty(type=MadnessAreaProperties)


def unregister():
    del bpy.types.Object.madness_area
    bpy.utils.unregister_class(MadnessAreaProperties)
