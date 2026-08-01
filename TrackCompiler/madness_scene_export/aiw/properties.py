"""AIW property group classes for Blender UI."""

import bpy  # type: ignore
from bpy.props import StringProperty, BoolProperty, FloatProperty, IntProperty, PointerProperty, CollectionProperty  # type: ignore


class AIWTrackFeatures(bpy.types.PropertyGroup):
    """Track features properties for AIW export."""

    waypoint_span: FloatProperty(
        name="Waypoint Span",
        description="Distance between waypoints",
        default=5.0,
        min=0.1,
        max=100.0,
    )  # type: ignore

    pitlanes: IntProperty(
        name="Pit Lanes", description="Number of pit lanes", default=1, min=0, max=2
    )  # type: ignore

    left_handed_pits: BoolProperty(
        name="Left-Handed Pits",
        description="Pit spots turn to the left to exit",
        default=True,
    )  # type: ignore

    track_difficulty: FloatProperty(
        name="Track Difficulty",
        description="Unused according to Reiza devs",
        default=1.0,
        min=0.1,
        max=5.0,
    )  # type: ignore

    oval: BoolProperty(
        name="Oval Track", description="Track is an oval", default=False
    )  # type: ignore

    rallycross: BoolProperty(
        name="Rallycross Track", description="Track is rallycross", default=False
    )  # type: ignore

    ice_track: BoolProperty(
        name="Ice Track", description="Track has ice surface", default=False
    )  # type: ignore

    narrow_track: BoolProperty(
        name="Narrow Track", description="Track is narrow", default=False
    )  # type: ignore

    ai_late_braking_fraction: FloatProperty(
        name="AI Late Braking Fraction",
        description="AI late braking behavior",
        default=1.0,
        min=0.0,
        max=2.0,
    )  # type: ignore

    ai_setup_gearing: FloatProperty(
        name="AI Setup Gearing",
        description="AI gearing setup preference",
        default=0.5,
        min=0.0,
        max=1.0,
    )  # type: ignore

    ai_setup_downforce: FloatProperty(
        name="AI Setup Downforce",
        description="AI downforce setup preference",
        default=0.5,
        min=0.0,
        max=1.0,
    )  # type: ignore

    ai_setup_balance: FloatProperty(
        name="AI Setup Balance",
        description="AI balance setup preference",
        default=0.5,
        min=0.0,
        max=1.0,
    )  # type: ignore


class AIWRollingStart(bpy.types.PropertyGroup):
    """Rolling start configuration."""

    race_type: StringProperty(
        name="Race Type", description="Type of race", default="Race"
    )  # type: ignore

    distance_behind_grid: FloatProperty(
        name="Distance Behind Grid",
        description="Distance behind grid for rolling start",
        default=460.0,
        min=0.0,
    )  # type: ignore

    distance_between_rows: FloatProperty(
        name="Distance Between Rows",
        description="Distance between rows",
        default=16.0,
        min=1.0,
    )  # type: ignore

    cars_in_row: IntProperty(
        name="Cars in Row",
        description="Number of cars per row",
        default=2,
        min=1,
        max=4,
    )  # type: ignore

    start_speed: FloatProperty(
        name="Start Speed", description="Starting speed (km/h)", default=37.0, min=0.0
    )  # type: ignore

    max_speed: FloatProperty(
        name="Max Speed", description="Maximum speed (km/h)", default=60.0, min=0.0
    )  # type: ignore


class AIWWaypointMetadata(bpy.types.PropertyGroup):
    """Waypoint metadata properties."""

    fuel_use: FloatProperty(
        name="Fuel Use",
        description="AI fuel consumption rate",
        default=0.5,
        min=0.0,
        max=5.0,
    )  # type: ignore

    groove_width: FloatProperty(
        name="Groove Width", description="Racing groove width", default=7.5, min=0.0
    )  # type: ignore

    groove_width_wet: FloatProperty(
        name="Groove Width Wet",
        description="Racing groove width in wet conditions",
        default=3.0,
        min=0.0,
    )  # type: ignore

    garage_depth: FloatProperty(
        name="Garage Depth", description="Garage depth", default=2.0, min=0.0
    )  # type: ignore

    pit_stop_space_front: FloatProperty(
        name="Pit Stop Space Front",
        description="Space in front of pit stop",
        default=0.5,
        min=0.0,
    )  # type: ignore

    pit_stop_space_back: FloatProperty(
        name="Pit Stop Space Back",
        description="Space behind pit stop",
        default=4.0,
        min=0.0,
    )  # type: ignore

    pit_stop_join_in: FloatProperty(
        name="Pit Stop Join In",
        description="Distance to join pit lane",
        default=4.0,
        min=0.0,
    )  # type: ignore

    pit_stop_join_out: FloatProperty(
        name="Pit Stop Join Out",
        description="Distance to exit pit lane",
        default=7.0,
        min=0.0,
    )  # type: ignore


class AIWSceneProperties(bpy.types.PropertyGroup):
    """Main AIW scene properties."""

    track_features: PointerProperty(type=AIWTrackFeatures)  # type: ignore
    rolling_starts: CollectionProperty(type=AIWRollingStart)  # type: ignore
    waypoint_metadata: PointerProperty(type=AIWWaypointMetadata)  # type: ignore

    def ensure_rolling_starts(self):
        """Ensure default rolling starts exist."""
        if len(self.rolling_starts) == 0:
            # Add default race rolling start
            race_start = self.rolling_starts.add()
            race_start.race_type = "Race"
            race_start.distance_behind_grid = 460.0
            race_start.distance_between_rows = 16.0
            race_start.cars_in_row = 2
            race_start.start_speed = 37.0
            race_start.max_speed = 60.0

            # Add default time attack rolling start
            ta_start = self.rolling_starts.add()
            ta_start.race_type = "TimeAttack"
            ta_start.distance_behind_grid = 460.0
            ta_start.distance_between_rows = 15.0
            ta_start.cars_in_row = 1
            ta_start.start_speed = 30.0
            ta_start.max_speed = 37.0 