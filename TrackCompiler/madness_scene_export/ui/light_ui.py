import bpy  # type: ignore
from ..properties.light_properties import is_sms_light


class MadnessLightPanel(bpy.types.Panel):
    """Panel for SMS Light properties"""
    bl_label = "Madness Light"
    bl_idname = "OBJECT_PT_madness_light"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"

    @classmethod
    def poll(cls, context):
        return (context.object and
                context.object.type == 'LIGHT' and
                is_sms_light(context.object))

    def draw(self, context):
        layout = self.layout
        light_props = context.object.data.madness_light

        # Light Type
        layout.prop(light_props, "light_type")

        # Basic Light Properties
        box = layout.box()
        box.label(text="Basic Properties")
        box.prop(light_props, "colour")
        box.prop(light_props, "intensity")
        box.prop(light_props, "range")

        # Angle Properties (for spotlights)
        if light_props.light_type in ['SPOTLIGHT', 'SPOTLIGHTPROJECTED']:
            box = layout.box()
            box.label(text="Spotlight Angles")
            box.prop(light_props, "inner_angle")
            box.prop(light_props, "outer_angle")

        # Projected Light Properties (for projected spotlights)
        if light_props.light_type == 'SPOTLIGHTPROJECTED':
            box = layout.box()
            box.label(text="Projection Properties")
            box.prop(light_props, "horizontal_angle")
            box.prop(light_props, "vertical_angle")
            box.prop(light_props, "projected_texture")

        # Shadow and Rendering Properties
        box = layout.box()
        box.label(text="Shadow & Rendering")
        box.prop(light_props, "casts_shadows")
        box.prop(light_props, "no_specular")
        box.prop(light_props, "no_smooth_dist_atten")
        box.prop(light_props, "include_in_light_maps")
        box.prop(light_props, "light_intensity_tweakable")

        # Light Group
        box = layout.box()
        box.label(text="Light Settings")
        box.prop(light_props, "light_group")

        # Ground Plane Properties
        box = layout.box()
        box.label(text="Ground Plane")
        box.prop(light_props, "ground_plane_distance")
        box.prop(light_props, "ground_plane_normal")
        box.prop(light_props, "ground_plane_auto_set")
        box.prop(light_props, "ground_plane_show")


def register():
    bpy.utils.register_class(MadnessLightPanel)


def unregister():
    bpy.utils.unregister_class(MadnessLightPanel)
