import bpy  # type: ignore
from ..properties.camera import is_sms_camera
from ..properties.area import is_sms_area


class MADNESS_OT_add_camera_zone(bpy.types.Operator):
    """Add a new camera zone slot"""
    bl_idname = "madness.add_camera_zone"
    bl_label = "Add Zone"
    bl_description = "Add a new camera zone slot"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.object and
                context.object.type == 'CAMERA' and
                is_sms_camera(context.object))

    def execute(self, context):
        cam_props = context.object.data.madness_camera
        cam_props.active_zones.add()
        return {'FINISHED'}


class MADNESS_OT_remove_camera_zone(bpy.types.Operator):
    """Remove a camera zone slot"""
    bl_idname = "madness.remove_camera_zone"
    bl_label = "Remove Zone"
    bl_description = "Remove this camera zone slot"
    bl_options = {'REGISTER', 'UNDO'}

    index: bpy.props.IntProperty()  # type: ignore

    @classmethod
    def poll(cls, context):
        return (context.object and
                context.object.type == 'CAMERA' and
                is_sms_camera(context.object))

    def execute(self, context):
        cam_props = context.object.data.madness_camera
        if 0 <= self.index < len(cam_props.active_zones):
            cam_props.active_zones.remove(self.index)
        return {'FINISHED'}


class MadnessCameraPanel(bpy.types.Panel):
    """Panel for SMS Camera properties"""
    bl_label = "Madness Camera"
    bl_idname = "OBJECT_PT_madness_camera"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"

    @classmethod
    def poll(cls, context):
        return (context.object and
                context.object.type == 'CAMERA' and
                is_sms_camera(context.object))

    def draw(self, context):
        layout = self.layout
        cam_props = context.object.data.madness_camera

        # Camera Type
        layout.prop(cam_props, "camera_type")

        # Basic Properties
        box = layout.box()
        box.label(text="Basic Properties")
        box.prop(cam_props, "fov")
        box.prop(cam_props, "fov_min")
        box.prop(cam_props, "fov_max")
        box.prop(cam_props, "near_z")
        box.prop(cam_props, "far_z")
        box.prop(cam_props, "cut_off_z")

        # Zoom Properties
        box = layout.box()
        box.label(text="Zoom Properties")
        box.prop(cam_props, "zoom_speed")
        box.prop(cam_props, "fov_delay")
        box.prop(cam_props, "fov_scalar")

        # Zoom Curve
        subbox = box.box()
        subbox.label(text="Zoom Curve")
        for point_index, (dist_prop, zoom_prop) in enumerate((
            ("zoom_curve_0", "zoom_curve_1"),
            ("zoom_curve_2", "zoom_curve_3"),
            ("zoom_curve_4", "zoom_curve_5"),
            ("zoom_curve_6", "zoom_curve_7"),
        )):
            row = subbox.row()
            row.label(text=f"P{point_index}")
            row.prop(cam_props, dist_prop, text="Distance")
            row.prop(cam_props, zoom_prop, text="Zoom")

        # Depth of Field
        box = layout.box()
        box.label(text="Depth of Field")
        box.prop(cam_props, "auto_focus")
        box.prop(cam_props, "dof_absolute")
        box.prop(cam_props, "dof")
        box.prop(cam_props, "dof_static_focus_distance")
        box.prop(cam_props, "dof_delay")
        box.prop(cam_props, "dof_sharp_range")
        box.prop(cam_props, "dof_blur_range")

        # Bokeh Properties
        box = layout.box()
        box.label(text="Bokeh Properties")
        box.prop(cam_props, "mBokehEnabled")
        box.prop(cam_props, "mBokehFStop")
        box.prop(cam_props, "mBokehFocalLength")
        box.prop(cam_props, "mBokehIrisType")

        # Target Properties
        box = layout.box()
        box.label(text="Target Properties")
        box.prop(cam_props, "target_type")
        box.prop(cam_props, "target_offset")
        box.prop(cam_props, "look_at_offset")
        box.prop(cam_props, "look_at_camera_relative")

        # Shake Properties
        box = layout.box()
        box.label(text="Shake Properties")
        box.prop(cam_props, "shake_magnitude")
        box.prop(cam_props, "shake_frequency")
        box.prop(cam_props, "is_vr")
        
        # Proximity Shake
        subbox = box.box()
        subbox.label(text="Proximity Shake")
        subbox.prop(cam_props, "ProximityShakeFrequency")
        subbox.prop(cam_props, "ProximityShakeMagnitude")
        subbox.prop(cam_props, "ProximityShakeMinDistance")
        subbox.prop(cam_props, "ProximityShakeMaxDistance")
        subbox.prop(cam_props, "ProximityShakeMinSpeed")
        subbox.prop(cam_props, "ProximityShakeMaxSpeed")

        # Movement Properties
        box = layout.box()
        box.label(text="Movement Properties")
        row = box.row()
        row.prop(cam_props, "Roll")
        row.prop(cam_props, "RollDelay")
        row.prop(cam_props, "RollTimer")
        row = box.row()
        row.prop(cam_props, "Pitch")
        row.prop(cam_props, "PitchDelay")
        row.prop(cam_props, "PitchTimer")
        row = box.row()
        row.prop(cam_props, "Yaw")
        row.prop(cam_props, "YawDelay")
        row.prop(cam_props, "YawTimer")

        # Camera Settings
        box = layout.box()
        box.label(text="Camera Settings")
        box.prop(cam_props, "camera_group")
        box.prop(cam_props, "camera_per_lap_flags")
        box.prop(cam_props, "force_keep")
        box.prop(cam_props, "lod_distance_multiplier")
        box.prop(cam_props, "shadow_type_index")
        box.prop(cam_props, "overridden_by")

        # Tracking Properties (only for tracking cameras)
        if cam_props.camera_type == 'TRACKING':
            box = layout.box()
            box.label(text="Tracking Properties")
            box.prop(cam_props, "movement_rate")
            box.prop(cam_props, "tracking_rate")
            box.prop(cam_props, "tracking_merge")
            box.prop(cam_props, "tracking_range")
            box.prop(cam_props, "tracking_range_leave")
            box.prop(cam_props, "auto_zoom")
            box.prop(cam_props, "static_direction")
            box.prop(cam_props, "tracking_lag")

        # Active Zones
        box = layout.box()
        box.label(text="Active Camera Zones")
        
        # Display existing zone slots
        zones_count = len(cam_props.active_zones)
        for i, zone_ref in enumerate(cam_props.active_zones):
            row = box.row(align=True)
            row.prop(zone_ref, "zone_object", text=f"Zone {i+1}")
            
            # Only show remove button if we have more than one zone or this zone is filled
            if zones_count > 1 or zone_ref.zone_object:
                remove_op = row.operator("madness.remove_camera_zone", text="", icon='X')
                remove_op.index = i
        
        # Show add button if all current slots are filled or if we have no zones yet
        all_filled = all(zone_ref.zone_object for zone_ref in cam_props.active_zones)
        if zones_count == 0 or all_filled:
            box.operator("madness.add_camera_zone", icon='ADD')


class MadnessAreaPanel(bpy.types.Panel):
    """Panel for SMS Camera Area properties"""
    bl_label = "Madness Camera Area"
    bl_idname = "OBJECT_PT_madness_area"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"

    @classmethod
    def poll(cls, context):
        return (context.object and
                is_sms_area(context.object))

    def draw(self, context):
        layout = self.layout
        area_props = context.object.madness_area

        # Area Type
        layout.prop(area_props, "area_type")

        # Name
        layout.prop(area_props, "area_name")

        # Common Properties
        box = layout.box()
        box.label(text="Common Properties")
        box.prop(area_props, "fov")
        box.prop(area_props, "focus_delay")
        box.prop(area_props, "zoom_speed")
        box.prop(area_props, "camera_group")

        if area_props.area_type == 'SPHERE':
            # Sphere Properties
            box = layout.box()
            box.label(text="Sphere Properties")
            box.prop(area_props, "sphere_radius")

        elif area_props.area_type == 'OBB':
            # OBB Properties
            box = layout.box()
            box.label(text="OBB Properties")
            box.prop(area_props, "obb_dimensions")

            # Transform info
            box = layout.box()
            box.label(text="Transform Information")
            box.label(text=f"Location: {context.object.location}")
            box.label(text=f"Rotation: {context.object.rotation_euler}")
            box.label(text=f"Scale: {context.object.scale}")


def register():
    bpy.utils.register_class(MADNESS_OT_add_camera_zone)
    bpy.utils.register_class(MADNESS_OT_remove_camera_zone)
    bpy.utils.register_class(MadnessCameraPanel)
    bpy.utils.register_class(MadnessAreaPanel)


def unregister():
    bpy.utils.unregister_class(MadnessAreaPanel)
    bpy.utils.unregister_class(MadnessCameraPanel)
    bpy.utils.unregister_class(MADNESS_OT_remove_camera_zone)
    bpy.utils.unregister_class(MADNESS_OT_add_camera_zone)
