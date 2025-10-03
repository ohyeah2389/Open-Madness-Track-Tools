"""AIW UI panel in Blender."""

import bpy  # type: ignore
from .aiw_properties import AIWSceneProperties


class AIW_PT_ScenePanel(bpy.types.Panel):
    """AIW parameters panel in scene properties."""

    bl_label = "Madness AIW Params"
    bl_idname = "AIW_PT_scene_panel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        if not hasattr(scene, "aiw_properties"):
            return

        aiw_props = scene.aiw_properties

        # Track Features
        box = layout.box()
        box.label(text="Track Features", icon="SETTINGS")

        col = box.column(align=True)

        col.prop(aiw_props.track_features, "waypoint_span")

        col.separator()
        col.prop(aiw_props.track_features, "left_handed_pits")
        col.prop(aiw_props.track_features, "track_difficulty")

        row = col.row(align=True)
        row.prop(aiw_props.track_features, "pitlanes")
        row.prop(aiw_props.track_features, "starting_grid")

        row = col.row(align=True)
        row.prop(aiw_props.track_features, "pit_spots")
        row.prop(aiw_props.track_features, "garage_spots")

        # Track Type
        row = col.row(align=True)
        row.prop(aiw_props.track_features, "oval")
        row.prop(aiw_props.track_features, "rallycross")

        row = col.row(align=True)
        row.prop(aiw_props.track_features, "ice_track")
        row.prop(aiw_props.track_features, "narrow_track")

        # AI Setup
        ai_box = box.box()
        ai_box.label(text="AI Setup")
        ai_col = ai_box.column(align=True)
        ai_col.prop(aiw_props.track_features, "ai_late_braking_fraction")
        ai_col.prop(aiw_props.track_features, "ai_setup_gearing")
        ai_col.prop(aiw_props.track_features, "ai_setup_downforce")
        ai_col.prop(aiw_props.track_features, "ai_setup_balance")

        # Rolling Starts
        rolling_box = layout.box()
        rolling_box.label(text="Rolling Starts", icon="PLAY")

        for _, rolling_start in enumerate(aiw_props.rolling_starts):
            start_box = rolling_box.box()
            start_box.label(text=f"{rolling_start.race_type}")

            col = start_box.column(align=True)
            col.prop(rolling_start, "distance_behind_grid")
            col.prop(rolling_start, "distance_between_rows")

            row = col.row(align=True)
            row.prop(rolling_start, "cars_in_row")
            row.prop(rolling_start, "start_speed")
            row.prop(rolling_start, "max_speed")

        # Waypoint Metadata
        wp_box = layout.box()
        wp_box.label(text="Waypoint Metadata", icon="CURVE_PATH")

        col = wp_box.column(align=True)
        col.prop(aiw_props.waypoint_metadata, "fuel_use")
        col.prop(aiw_props.waypoint_metadata, "groove_width")
        col.prop(aiw_props.waypoint_metadata, "groove_width_wet")

        pit_col = wp_box.column(align=True)
        pit_col.label(text="Pit Configuration:")
        pit_col.prop(aiw_props.waypoint_metadata, "garage_depth")
        pit_col.prop(aiw_props.waypoint_metadata, "pit_stop_space_front")
        pit_col.prop(aiw_props.waypoint_metadata, "pit_stop_space_back")
        pit_col.prop(aiw_props.waypoint_metadata, "pit_stop_join_in")
        pit_col.prop(aiw_props.waypoint_metadata, "pit_stop_join_out") 