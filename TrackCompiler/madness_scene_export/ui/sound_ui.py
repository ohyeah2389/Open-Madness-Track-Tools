import bpy  # type: ignore
from ..properties.sound_properties import is_sms_sound, get_sound_name_for_export


class SOUND_PT_MadnessSoundPanel(bpy.types.Panel):
    """Panel for Madness Sound properties"""

    bl_label = "Madness Sound"
    bl_idname = "DATA_PT_madness_sound"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"

    @classmethod
    def poll(cls, context):
        return is_sms_sound(context.object)

    def draw(self, context):
        layout = self.layout
        obj = context.object
        sound_props = obj.madness_sound

        # Sound Type
        layout.prop(sound_props, "sound_type")

        # Sound Name/Path - show appropriate dropdown based on type
        if sound_props.sound_type == 'ENVIRONMENT_SOUND':
            layout.prop(sound_props, "environment_sound_name")
        elif sound_props.sound_type == 'AMBIENT_SOUND':
            layout.prop(sound_props, "ambient_sound_name")
        elif sound_props.sound_type == 'AMBIENT_REVERB':
            layout.prop(sound_props, "ambient_reverb_name")
        elif sound_props.sound_type == 'LOCAL_REVERB':
            layout.prop(sound_props, "local_reverb_name")

        # Common properties
        if sound_props.sound_type in ['ENVIRONMENT_SOUND', 'AMBIENT_SOUND']:
            layout.prop(sound_props, "volume")
            layout.prop(sound_props, "fade_in_time")
            layout.prop(sound_props, "fade_out_time")

        # Environment Sound specific
        if sound_props.sound_type == 'ENVIRONMENT_SOUND':
            layout.prop(sound_props, "range")

        # Ambient Sound specific
        if sound_props.sound_type == 'AMBIENT_SOUND':
            layout.prop(sound_props, "default_ambient")
            layout.prop(sound_props, "velocity_min_volume")
            layout.prop(sound_props, "velocity_max_volume")

        # Reverb types specific
        if sound_props.sound_type in ['AMBIENT_REVERB', 'LOCAL_REVERB']:
            layout.prop(sound_props, "reverb_influence")

        # Local Reverb specific
        if sound_props.sound_type == 'LOCAL_REVERB':
            layout.prop(sound_props, "fade_range")

        # Sound Area (for Ambient and Local Reverb)
        if sound_props.sound_type in ['AMBIENT_SOUND', 'LOCAL_REVERB']:
            box = layout.box()
            box.label(text="Sound Area Definition:")
            box.prop(sound_props, "sound_area_type")

            if sound_props.sound_area_type == 'SPHERICAL':
                box.prop(sound_props, "spherical_radius")
                box.prop(sound_props, "spherical_flat")
            elif sound_props.sound_area_type == 'OBB_2D':
                box.prop(sound_props, "obb_direction")
                box.prop(sound_props, "obb_length")
                box.prop(sound_props, "obb_width")

        # Orientation (for Environment Sound)
        if sound_props.sound_type == 'ENVIRONMENT_SOUND':
            layout.prop(sound_props, "orientation")


def draw_sound_info(layout, obj):
    """Draw sound information in object properties"""
    if not is_sms_sound(obj):
        return

    sound_props = obj.madness_sound

    box = layout.box()
    box.label(text="Madness Sound Object", icon='SOUND')

    # Show sound type and basic info
    row = box.row()
    row.label(text=f"Type: {sound_props.sound_type.replace('_', ' ').title()}")

    sound_name = get_sound_name_for_export(obj)
    if sound_name:
        row = box.row()
        row.label(text=f"Sound: {sound_name.split('/')[-1]}")
    else:
        row = box.row()
        row.label(text="Sound: Not set", icon='ERROR')


def register():
    bpy.utils.register_class(SOUND_PT_MadnessSoundPanel)


def unregister():
    bpy.utils.unregister_class(SOUND_PT_MadnessSoundPanel)
