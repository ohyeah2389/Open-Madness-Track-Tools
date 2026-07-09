import math

import bpy  # type: ignore
from bpy.app.handlers import persistent  # type: ignore
from bpy.props import (  # type: ignore
    BoolProperty, FloatProperty, IntProperty, StringProperty,
    EnumProperty, FloatVectorProperty, PointerProperty, CollectionProperty
)


# Two-way link between Madness camera props and native Blender camera settings.
# Each entry: madness_prop -> (blender data path, to_blender, from_blender)
_CAM_LINKS = {
    "fov": ("angle", math.radians, math.degrees),
    "near_z": ("clip_start", None, None),
    "far_z": ("clip_end", None, None),
    "dof_static_focus_distance": ("dof.focus_distance", None, None),
    "mBokehEnabled": ("dof.use_dof", None, None),
    "mBokehFStop": ("dof.aperture_fstop", None, None),
}

_msgbus_owner = object()
_syncing = False


def _resolve(root, path):
    """Return (owner_object, attr_name) for a dotted data path."""
    parts = path.split(".")
    for p in parts[:-1]:
        root = getattr(root, p)
    return root, parts[-1]


def _madness_update(prop):
    """Push a Madness property change onto the native Blender camera setting."""
    def cb(self, context):
        global _syncing
        if _syncing:
            return
        path, to_bl, _ = _CAM_LINKS[prop]
        owner, attr = _resolve(self.id_data, path)
        val = getattr(self, prop)
        val = to_bl(val) if to_bl else val
        _syncing = True
        try:
            setattr(owner, attr, val)
        finally:
            _syncing = False
    return cb


def _blender_update(prop):
    """Push a native Blender camera change onto the Madness property."""
    def cb(*args):
        global _syncing
        if _syncing:
            return
        obj = bpy.context.object
        if not obj or obj.type != 'CAMERA':
            return
        cam = obj.data
        path, _, from_bl = _CAM_LINKS[prop]
        owner, attr = _resolve(cam, path)
        val = getattr(owner, attr)
        val = from_bl(val) if from_bl else val
        _syncing = True
        try:
            setattr(cam.madness_camera, prop, val)
        finally:
            _syncing = False
    return cb


def _subscribe():
    """(Re)subscribe to native camera settings so edits sync back to Madness."""
    bpy.msgbus.clear_by_owner(_msgbus_owner)
    for prop, (path, _, _) in _CAM_LINKS.items():
        parts = path.split(".")
        rna = bpy.types.CameraDOFSettings if len(parts) > 1 else bpy.types.Camera
        bpy.msgbus.subscribe_rna(
            key=(rna, parts[-1]),
            owner=_msgbus_owner,
            args=(),
            notify=_blender_update(prop),
        )


@persistent
def _on_load(dummy):
    _subscribe()


class CameraZoneReference(bpy.types.PropertyGroup):
    """Reference to a camera zone object"""
    zone_object: PointerProperty(
        name="Zone",
        description="Camera zone object",
        type=bpy.types.Object,
        poll=lambda self, obj: obj and obj.type == 'EMPTY' and obj.name.startswith('SMS_CAMZONE_')
    )  # type: ignore


class MadnessCameraProperties(bpy.types.PropertyGroup):
    """Properties for SMS_CAM_ prefixed camera objects"""

    # Basic Camera Properties
    camera_type: EnumProperty(
        name="Camera Type",
        description="Type of camera",
        items=[
            ('STATIC', "Static", "Static camera position"),
            ('TRACKING', "Tracking", "Camera that follows target"),
        ],
        default='TRACKING'
    )  # type: ignore

    # FOV and Zoom Properties
    fov: FloatProperty(
        name="FOV",
        description="Field of view in degrees",
        default=40.0,
        min=1.0,
        max=180.0,
        update=_madness_update("fov")
    )  # type: ignore

    fov_min: FloatProperty(
        name="FOV Min",
        description="Minimum FOV in degrees",
        default=10.0,
        min=1.0,
        max=180.0
    )  # type: ignore

    fov_max: FloatProperty(
        name="FOV Max",
        description="Maximum FOV in degrees",
        default=90.0,
        min=1.0,
        max=180.0
    )  # type: ignore

    zoom_speed: FloatProperty(
        name="Zoom Speed",
        description="Zoom speed",
        default=0.2,
        min=0.0,
        max=10.0
    )  # type: ignore

    fov_delay: FloatProperty(
        name="FOV Delay",
        description="FOV change delay",
        default=0.1,
        min=0.0,
        max=10.0
    )  # type: ignore

    fov_scalar: FloatProperty(
        name="FOV Scalar",
        description="FOV scalar multiplier",
        default=1.0,
        min=0.1,
        max=10.0
    )  # type: ignore

    # Depth of Field Properties
    auto_focus: BoolProperty(
        name="Auto Focus",
        description="Enable auto focus",
        default=True
    )  # type: ignore

    dof_absolute: BoolProperty(
        name="DOF Absolute",
        description="Absolute DOF control",
        default=False
    )  # type: ignore

    dof: FloatProperty(
        name="DOF",
        description="Depth of field",
        default=0.0,
        min=0.0,
        max=1000.0
    )  # type: ignore

    dof_static_focus_distance: FloatProperty(
        name="DOF Static Focus Distance",
        description="Static focus distance for DOF",
        default=0.0,
        min=0.0,
        max=10000.0,
        update=_madness_update("dof_static_focus_distance")
    )  # type: ignore

    dof_delay: FloatProperty(
        name="DOF Delay",
        description="DOF change delay",
        default=0.0,
        min=0.0,
        max=10.0
    )  # type: ignore

    dof_sharp_range: FloatProperty(
        name="DOF Sharp Range",
        description="DOF sharp range",
        default=350.0,
        min=0.0,
        max=10000.0
    )  # type: ignore

    dof_blur_range: FloatProperty(
        name="DOF Blur Range",
        description="DOF blur range",
        default=150.0,
        min=0.0,
        max=10000.0
    )  # type: ignore

    # Camera Distance Properties
    near_z: FloatProperty(
        name="Near Z",
        description="Near clipping plane",
        default=1.5,
        min=0.1,
        max=100.0,
        update=_madness_update("near_z")
    )  # type: ignore

    far_z: FloatProperty(
        name="Far Z",
        description="Far clipping plane",
        default=5000.0,
        min=1.0,
        max=50000.0,
        update=_madness_update("far_z")
    )  # type: ignore

    cut_off_z: FloatProperty(
        name="Cut Off Z",
        description="Cut off Z distance",
        default=0.0,
        min=0.0,
        max=10000.0
    )  # type: ignore

    # Target and Look At Properties
    target_type: EnumProperty(
        name="Target Type",
        description="Type of target to follow",
        items=[
            ('NONE', "None", "No target"),
            ('PLAYER', "Player", "Follow player car"),
            ('AI', "AI", "Follow AI car"),
            ('OBJECT', "Object", "Follow specific object"),
        ],
        default='PLAYER'
    )  # type: ignore

    target_offset: FloatVectorProperty(
        name="Target Offset",
        description="Offset from target position",
        default=(0.0, 0.75, 0.0),
        subtype='XYZ'
    )  # type: ignore

    look_at_offset: FloatVectorProperty(
        name="Look At Offset",
        description="Look at offset",
        default=(0.0, 0.0, 0.0),
        subtype='XYZ'
    )  # type: ignore

    look_at_camera_relative: BoolProperty(
        name="Look At Camera Relative",
        description="Look at is relative to camera",
        default=False
    )  # type: ignore

    # Shake Properties
    shake_magnitude: FloatProperty(
        name="Shake Magnitude",
        description="Camera shake magnitude",
        default=0.01,
        min=0.0,
        max=1.0
    )  # type: ignore

    shake_frequency: FloatProperty(
        name="Shake Frequency",
        description="Camera shake frequency",
        default=0.8,
        min=0.0,
        max=10.0
    )  # type: ignore

    # Render Properties
    render_helmet: BoolProperty(
        name="Render Helmet",
        description="Render helmet in cockpit view",
        default=False
    )  # type: ignore

    render_cockpit: BoolProperty(
        name="Render Cockpit",
        description="Render cockpit",
        default=False
    )  # type: ignore

    battle_worn: BoolProperty(
        name="Battle Worn",
        description="Apply battle worn effect",
        default=False
    )  # type: ignore

    is_vr: BoolProperty(
        name="Is VR",
        description="VR camera",
        default=False
    )  # type: ignore

    # Camera Group and Flags
    camera_group: IntProperty(
        name="Camera Group",
        description="Camera group ID",
        default=2000,
        min=0,
        max=65535
    )  # type: ignore

    camera_per_lap_flags: IntProperty(
        name="Camera Per Lap Flags",
        description="Camera per lap flags",
        default=1,
        min=0,
        max=255
    )  # type: ignore

    # Force Keep Properties
    force_keep: FloatProperty(
        name="Force Keep",
        description="Force keep distance",
        default=950.0,
        min=0.0,
        max=10000.0
    )  # type: ignore

    # LOD Properties
    lod_distance_multiplier: FloatProperty(
        name="LOD Distance Multiplier",
        description="LOD distance multiplier",
        default=5.0,
        min=0.1,
        max=100.0
    )  # type: ignore

    # Tracking Properties (for tracking cameras)
    movement_rate: FloatProperty(
        name="Movement Rate",
        description="Camera movement rate",
        default=0.0,
        min=0.0,
        max=100.0
    )  # type: ignore

    tracking_rate: FloatProperty(
        name="Tracking Rate",
        description="Target tracking rate",
        default=0.0,
        min=0.0,
        max=100.0
    )  # type: ignore

    tracking_merge: FloatProperty(
        name="Tracking Merge",
        description="Tracking merge factor",
        default=1.0,
        min=0.0,
        max=10.0
    )  # type: ignore

    tracking_range: FloatProperty(
        name="Tracking Range",
        description="Tracking range",
        default=0.0,
        min=0.0,
        max=10000.0
    )  # type: ignore

    tracking_range_leave: FloatProperty(
        name="Tracking Range Leave",
        description="Tracking range leave distance",
        default=0.0,
        min=0.0,
        max=10000.0
    )  # type: ignore

    auto_zoom: BoolProperty(
        name="Auto Zoom",
        description="Enable auto zoom",
        default=True
    )  # type: ignore

    static_direction: BoolProperty(
        name="Static Direction",
        description="Static camera direction",
        default=False
    )  # type: ignore

    tracking_lag: FloatProperty(
        name="Tracking Lag",
        description="Tracking lag",
        default=0.0,
        min=0.0,
        max=10.0
    )  # type: ignore

    # Post Processing
    pp_filter: StringProperty(
        name="PP Filter",
        description="Post processing filter",
        default=""
    )  # type: ignore

    # Sound and Effects
    sound_effect: StringProperty(
        name="Sound Effect",
        description="Camera sound effect",
        default=""
    )  # type: ignore

    # User Data
    user_data_name: StringProperty(
        name="User Data Name",
        description="User data name",
        default=""
    )  # type: ignore

    user_data_value: FloatProperty(
        name="User Data Value",
        description="User data value",
        default=0.0
    )  # type: ignore

    # Incident Properties
    incident_cam: StringProperty(
        name="Incident Cam",
        description="Incident camera reference",
        default=""
    )  # type: ignore

    min_speed_incident: FloatProperty(
        name="Min Speed Incident",
        description="Minimum speed for incident trigger",
        default=0.0,
        min=0.0,
        max=500.0
    )  # type: ignore

    # Override Properties
    overridden_by: StringProperty(
        name="Overridden By",
        description="Camera that overrides this one",
        default=""
    )  # type: ignore

    # Active Areas (references to SMS_CAMZONE_ objects)
    active_zones: CollectionProperty(
        name="Active Zones",
        description="Camera zones this camera is active in",
        type=CameraZoneReference
    )  # type: ignore

    # Shadow Properties
    shadow_type_index: IntProperty(
        name="Shadow Type Index",
        description="Shadow type index",
        default=0,
        min=0,
        max=10
    )  # type: ignore

    # Zoom Curves (8 values)
    zoom_curve_0: FloatProperty(name="Zoom Curve 0", default=0.0)  # type: ignore
    zoom_curve_1: FloatProperty(name="Zoom Curve 1", default=1.0)  # type: ignore
    zoom_curve_2: FloatProperty(name="Zoom Curve 2", default=0.1)  # type: ignore
    zoom_curve_3: FloatProperty(name="Zoom Curve 3", default=0.05)  # type: ignore
    zoom_curve_4: FloatProperty(name="Zoom Curve 4", default=0.5)  # type: ignore
    zoom_curve_5: FloatProperty(name="Zoom Curve 5", default=0.85)  # type: ignore
    zoom_curve_6: FloatProperty(name="Zoom Curve 6", default=0.65)  # type: ignore
    zoom_curve_7: FloatProperty(name="Zoom Curve 7", default=0.95)  # type: ignore

    # Bokeh Properties
    mBokehEnabled: BoolProperty(
        name="Bokeh Enabled",
        description="Enable bokeh effect",
        default=False,
        update=_madness_update("mBokehEnabled")
    )  # type: ignore

    mBokehFStop: FloatProperty(
        name="Bokeh F-Stop",
        description="Bokeh f-stop value",
        default=16.0,
        min=1.0,
        max=32.0,
        update=_madness_update("mBokehFStop")
    )  # type: ignore

    mBokehFocalLength: FloatProperty(
        name="Bokeh Focal Length",
        description="Bokeh focal length",
        default=0.075,
        min=0.001,
        max=1.0
    )  # type: ignore

    mBokehIrisType: IntProperty(
        name="Bokeh Iris Type",
        description="Type of bokeh iris",
        default=0,
        min=0,
        max=10
    )  # type: ignore

    # Movement Properties
    Roll: FloatProperty(
        name="Roll",
        description="Camera roll",
        default=0.0,
        min=-180.0,
        max=180.0
    )  # type: ignore

    RollDelay: FloatProperty(
        name="Roll Delay",
        description="Roll delay",
        default=0.0,
        min=0.0,
        max=10.0
    )  # type: ignore

    RollTimer: FloatProperty(
        name="Roll Timer",
        description="Roll timer",
        default=0.0,
        min=0.0,
        max=10.0
    )  # type: ignore

    Pitch: FloatProperty(
        name="Pitch",
        description="Camera pitch",
        default=0.0,
        min=-180.0,
        max=180.0
    )  # type: ignore

    PitchDelay: FloatProperty(
        name="Pitch Delay",
        description="Pitch delay",
        default=0.0,
        min=0.0,
        max=10.0
    )  # type: ignore

    PitchTimer: FloatProperty(
        name="Pitch Timer",
        description="Pitch timer",
        default=0.0,
        min=0.0,
        max=10.0
    )  # type: ignore

    Yaw: FloatProperty(
        name="Yaw",
        description="Camera yaw",
        default=0.0,
        min=-180.0,
        max=180.0
    )  # type: ignore

    YawDelay: FloatProperty(
        name="Yaw Delay",
        description="Yaw delay",
        default=0.0,
        min=0.0,
        max=10.0
    )  # type: ignore

    YawTimer: FloatProperty(
        name="Yaw Timer",
        description="Yaw timer",
        default=0.0,
        min=0.0,
        max=10.0
    )  # type: ignore

    # Proximity Shake Properties
    ProximityShakeFrequency: FloatProperty(
        name="Proximity Shake Frequency",
        description="Proximity shake frequency",
        default=12.0,
        min=0.0,
        max=100.0
    )  # type: ignore

    ProximityShakeMagnitude: FloatProperty(
        name="Proximity Shake Magnitude",
        description="Proximity shake magnitude",
        default=0.0,
        min=0.0,
        max=10.0
    )  # type: ignore

    ProximityShakeMinDistance: FloatProperty(
        name="Proximity Shake Min Distance",
        description="Proximity shake minimum distance",
        default=4.0,
        min=0.0,
        max=1000.0
    )  # type: ignore

    ProximityShakeMaxDistance: FloatProperty(
        name="Proximity Shake Max Distance",
        description="Proximity shake maximum distance",
        default=20.0,
        min=0.0,
        max=1000.0
    )  # type: ignore

    ProximityShakeMinSpeed: FloatProperty(
        name="Proximity Shake Min Speed",
        description="Proximity shake minimum speed",
        default=20.0,
        min=0.0,
        max=500.0
    )  # type: ignore

    ProximityShakeMaxSpeed: FloatProperty(
        name="Proximity Shake Max Speed",
        description="Proximity shake maximum speed",
        default=40.0,
        min=0.0,
        max=500.0
    )  # type: ignore


def is_sms_camera(obj):
    """Check if object is an SMS camera"""
    return obj.type == 'CAMERA' and obj.name.startswith('SMS_CAM_')


def register():
    bpy.utils.register_class(CameraZoneReference)
    bpy.utils.register_class(MadnessCameraProperties)
    bpy.types.Camera.madness_camera = PointerProperty(type=MadnessCameraProperties)
    _subscribe()
    if _on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load)


def unregister():
    if _on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load)
    bpy.msgbus.clear_by_owner(_msgbus_owner)
    del bpy.types.Camera.madness_camera
    bpy.utils.unregister_class(MadnessCameraProperties)
    bpy.utils.unregister_class(CameraZoneReference)
