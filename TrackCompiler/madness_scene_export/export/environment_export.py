import bpy # type: ignore
import mathutils # type: ignore
import numpy as np
import math
from pathlib import Path
from typing import List, Dict, Any
from ..properties.camera_properties import is_sms_camera
from ..properties.area_properties import is_sms_area, get_area_name
from ..utils.coordinate_transforms import decompose_matrix, convert_position


def get_camera_name(obj):
    """Get camera name without SMS_CAM_ prefix"""
    return obj.name[8:]  # Remove 'SMS_CAM_' prefix


def get_target_type_value(target_type: str) -> int:
    """Convert target type to integer value"""
    target_map = {
        'NONE': -1,
        'PLAYER': 7,
        'AI': 0,
        'OBJECT': -1  # Would need object reference
    }
    return target_map.get(target_type, -1)


def format_vector3(v):
    """Format vector as string"""
    return f"{v[0]:.6g};{v[1]:.6g};{v[2]:.6g}"


def format_quaternion(q):
    """Format quaternion as string (w;x;y;z)"""
    return f"{q[0]:.6f};{q[1]:.6f};{q[2]:.6f};{q[3]:.6f}"


def format_matrix_4x4(m):
    """Format 4x4 matrix as string"""
    values = []
    for row in range(4):
        for col in range(4):
            value = m[row][col]
            values.append(f"{value:.6f}")
    return ";".join(values)


def collect_cameras(scene) -> List[Dict[str, Any]]:
    """Collect all SMS cameras from the scene"""
    cameras = []
    for obj in scene.objects:
        if is_sms_camera(obj):
            cam_data = obj.data
            cam_props = cam_data.madness_camera

            # Get world matrix and convert to Madness coordinate system
            world_matrix = obj.matrix_world
            
            # Apply -90 degree rotation about local X axis to correct orientation
            correction_matrix = mathutils.Matrix.Rotation(math.radians(-90), 4, 'X')
            corrected_matrix = world_matrix @ correction_matrix
            
            matrix = np.array(corrected_matrix)
            pos, quat = decompose_matrix(matrix)

            camera_info = {
                'name': get_camera_name(obj),
                'type': cam_props.camera_type,
                'position': pos,
                'quaternion': quat,
                'properties': cam_props
            }
            cameras.append(camera_info)

    return cameras


def collect_areas(scene) -> List[Dict[str, Any]]:
    """Collect all SMS camera areas from the scene"""
    areas = []
    for obj in scene.objects:
        if is_sms_area(obj):
            area_props = obj.madness_area

            # Get world matrix for OBB areas
            world_matrix = obj.matrix_world

            area_info = {
                'name': get_area_name(obj),
                'type': area_props.area_type,
                'object': obj,
                'properties': area_props,
                'world_matrix': world_matrix
            }
            areas.append(area_info)

    return areas


def generate_camera_xml(camera_info: Dict[str, Any], areas: List[Dict[str, Any]]) -> str:
    """Generate XML for a single camera"""
    props = camera_info['properties']

    # Determine camera class based on type
    camera_class = "CTrackingCamData" if props.camera_type == 'TRACKING' else "CStaticCamData"

    xml = f'                <data class="{camera_class}" id="0x{camera_info["id"]:08X}">\n'
    xml += f'                    <prop name="Name" data="{camera_info["name"]}" />\n'
    xml += f'                    <prop name="Pos" data="{format_vector3(camera_info["position"])}" />\n'
    xml += f'                    <prop name="QuatOri" data="{format_quaternion(camera_info["quaternion"])}" />\n'
    xml += f'                    <prop name="FOV" data="{math.radians(props.fov):.6f}" />\n'
    xml += f'                    <prop name="ZoomSpeed" data="{props.zoom_speed:.6f}" />\n'

    # Zoom curves
    xml += f'                    <prop name="ZoomCurve0" data="{props.zoom_curve_0:.6f}" />\n'
    xml += f'                    <prop name="ZoomCurve1" data="{props.zoom_curve_1:.6f}" />\n'
    xml += f'                    <prop name="ZoomCurve2" data="{props.zoom_curve_2:.6f}" />\n'
    xml += f'                    <prop name="ZoomCurve3" data="{props.zoom_curve_3:.6f}" />\n'
    xml += f'                    <prop name="ZoomCurve4" data="{props.zoom_curve_4:.6f}" />\n'
    xml += f'                    <prop name="ZoomCurve5" data="{props.zoom_curve_5:.6f}" />\n'
    xml += f'                    <prop name="ZoomCurve6" data="{props.zoom_curve_6:.6f}" />\n'
    xml += f'                    <prop name="ZoomCurve7" data="{props.zoom_curve_7:.6f}" />\n'

    xml += f'                    <prop name="FOVDelay" data="{props.fov_delay:.6f}" />\n'
    xml += f'                    <prop name="FOVManual" data="0" />\n'  # Default value
    xml += f'                    <prop name="FOVScalar" data="{props.fov_scalar:.6f}" />\n'
    xml += f'                    <prop name="FOVRadiansQuantisationInShadowMap" data="1.0e-10" />\n'
    xml += f'                    <prop name="AutoFocus" data="{"true" if props.auto_focus else "false"}" />\n'
    xml += f'                    <prop name="AutoFocusSlowdownFactor" data="0" />\n'  # Default value
    xml += f'                    <prop name="DOFAbsolute" data="{"true" if props.dof_absolute else "false"}" />\n'
    xml += f'                    <prop name="DOFSpeed" data="1" />\n'  # Default value
    xml += f'                    <prop name="DOF" data="{props.dof:.6f}" />\n'
    xml += f'                    <prop name="DOFStaticFocusDistance" data="{props.dof_static_focus_distance:.6f}" />\n'
    xml += f'                    <prop name="DOFDelay" data="{props.dof_delay:.6f}" />\n'
    xml += f'                    <prop name="DOFSharpRange" data="{props.dof_sharp_range:.6f}" />\n'
    xml += f'                    <prop name="DOFBlurRange" data="{props.dof_blur_range:.6f}" />\n'
    xml += f'                    <prop name="mBokehEnabled" data="{"true" if props.mBokehEnabled else "false"}" />\n'
    xml += f'                    <prop name="mBokehFStop" data="{props.mBokehFStop:.6f}" />\n'
    xml += f'                    <prop name="mBokehFocalLength" data="{props.mBokehFocalLength:.6f}" />\n'
    xml += f'                    <prop name="mBokehIrisType" data="{props.mBokehIrisType}" />\n'

    # Movement properties
    xml += f'                    <prop name="Roll" data="{props.Roll:.6f}" />\n'
    xml += f'                    <prop name="RollDelay" data="{props.RollDelay:.6f}" />\n'
    xml += f'                    <prop name="RollTimer" data="{props.RollTimer:.6f}" />\n'
    xml += f'                    <prop name="Pitch" data="{props.Pitch:.6f}" />\n'
    xml += f'                    <prop name="PitchDelay" data="{props.PitchDelay:.6f}" />\n'
    xml += f'                    <prop name="PitchTimer" data="{props.PitchTimer:.6f}" />\n'
    xml += f'                    <prop name="Yaw" data="{props.Yaw:.6f}" />\n'
    xml += f'                    <prop name="YawDelay" data="{props.YawDelay:.6f}" />\n'
    xml += f'                    <prop name="YawTimer" data="{props.YawTimer:.6f}" />\n'

    xml += f'                    <prop name="CollisionDistance" data="0" />\n'
    xml += f'                    <prop name="DualViewDistance" data="0" />\n'
    xml += f'                    <prop name="SimulationSpeed" data="1" />\n'
    xml += f'                    <prop name="SimulationRange" data="0" />\n'
    xml += f'                    <prop name="SimulationTimeout" data="0" />\n'
    xml += f'                    <prop name="Type" data="0" />\n'
    xml += f'                    <prop name="NearZ" data="{props.near_z:.6f}" />\n'
    xml += f'                    <prop name="FarZ" data="{props.far_z:.6f}" />\n'
    xml += f'                    <prop name="CutOffZ" data="{props.cut_off_z:.6f}" />\n'

    # Target properties
    target_value = get_target_type_value(props.target_type)
    xml += f'                    <prop name="Target" data="{target_value}" />\n'
    xml += f'                    <prop name="TargetOffset" data="{format_vector3(props.target_offset)}" />\n'
    xml += f'                    <prop name="LookAt" data="{target_value}" />\n'
    xml += f'                    <prop name="LookAtOffset" data="{format_vector3(props.look_at_offset)}" />\n'
    xml += f'                    <prop name="LookAtCameraRelative" data="{"true" if props.look_at_camera_relative else "false"}" />\n'

    # Proximity shake
    xml += f'                    <prop name="ProximityShakeFrequency" data="{props.ProximityShakeFrequency:.6f}" />\n'
    xml += f'                    <prop name="ProximityShakeMagnitude" data="{props.ProximityShakeMagnitude:.6f}" />\n'
    xml += f'                    <prop name="ProximityShakeMinDistance" data="{props.ProximityShakeMinDistance:.6f}" />\n'
    xml += f'                    <prop name="ProximityShakeMaxDistance" data="{props.ProximityShakeMaxDistance:.6f}" />\n'
    xml += f'                    <prop name="ProximityShakeMinSpeed" data="{props.ProximityShakeMinSpeed:.6f}" />\n'
    xml += f'                    <prop name="ProximityShakeMaxSpeed" data="{props.ProximityShakeMaxSpeed:.6f}" />\n'

    # Shake properties
    xml += f'                    <prop name="ShakeMagnitude" data="{props.shake_magnitude:.6f}" />\n'
    xml += f'                    <prop name="ShakeMagnitudeMin" data="0" />\n'  # Default value
    xml += f'                    <prop name="ShakeFrequency" data="{props.shake_frequency:.6f}" />\n'
    xml += f'                    <prop name="ShakeFrequencyMin" data="0.2" />\n'  # Default value
    xml += f'                    <prop name="ShakeScreenVelocity" data="0.8" />\n'  # Default value
    xml += f'                    <prop name="ShakeScreenVelocityMin" data="0.2" />\n'  # Default value

    xml += f'                    <prop name="SoundEffect" data="{props.sound_effect}" />\n'
    xml += f'                    <prop name="LODDistanceMultiplier" data="{props.lod_distance_multiplier:.6f}" />\n'
    xml += f'                    <prop name="OverridedBy" data="{props.overridden_by}" />\n'
    xml += f'                    <prop name="IncidentCam" data="{props.incident_cam}" />\n'
    xml += f'                    <prop name="UserDataName" data="{props.user_data_name}" />\n'
    xml += f'                    <prop name="UserDataValue" data="{props.user_data_value:.6f}" />\n'
    xml += f'                    <prop name="FOVMin" data="{math.radians(props.fov_min):.6f}" />\n'
    xml += f'                    <prop name="FOVMax" data="{math.radians(props.fov_max):.6f}" />\n'
    xml += f'                    <prop name="RenderHelmet" data="{"true" if props.render_helmet else "false"}" />\n'
    xml += f'                    <prop name="RenderCockpit" data="{"true" if props.render_cockpit else "false"}" />\n'
    xml += f'                    <prop name="BattleWorn" data="{"true" if props.battle_worn else "false"}" />\n'
    xml += f'                    <prop name="IsVR" data="{"true" if props.is_vr else "false"}" />\n'

    # Area references (will be filled in later)
    xml += f'                    <prop name="TrackingAreaEnter" data="-1" />\n'
    xml += f'                    <prop name="TrackingAreaLeave" data="-1" />\n'
    xml += f'                    <prop name="SimulationSpeedArea" data="-1" />\n'
    xml += f'                    <prop name="CollisionArea" data="-1" />\n'

    xml += f'                    <prop name="PPFilter" data="{props.pp_filter}" />\n'
    xml += f'                    <prop name="MinSpeedIncident" data="{props.min_speed_incident:.6f}" />\n'

    # Active areas - convert zone objects to indices based on scene collection order
    active_indices = []
    if props.active_zones:
        # Create mapping from area objects to their indices
        area_to_index = {area['object']: i for i, area in enumerate(areas)}
        
        for zone_ref in props.active_zones:
            if zone_ref.zone_object and zone_ref.zone_object in area_to_index:
                active_indices.append(area_to_index[zone_ref.zone_object])

    if active_indices:
        xml += f'                    <prop name="ActiveAreas" elements="{len(active_indices)}">\n'
        xml += '                        <funcpropdata'
        for i, idx in enumerate(active_indices):
            xml += f' areaIndex{i+1}="{idx}"'
        xml += ' />\n'
        xml += '                    </prop>\n'
    else:
        xml += f'                    <prop name="ActiveAreas" elements="0">\n'
        xml += f'                        <funcpropdata />\n'
        xml += f'                    </prop>\n'

    xml += f'                    <prop name="ShadowTypeIndex" data="{props.shadow_type_index}" />\n'
    xml += f'                    <prop name="CameraPerLapFlags" data="{props.camera_per_lap_flags}" />\n'
    xml += f'                    <prop name="CameraGroup" data="{props.camera_group}" />\n'
    xml += f'                    <prop name="ForceKeep" data="{props.force_keep:.6f}" />\n'
    xml += f'                    <prop name="ForceKeepDistance" data="0.0" />\n'
    xml += f'                    <prop name="DistanceRand" data="0.0" />\n'

    # Tracking-specific properties
    if props.camera_type == 'TRACKING':
        xml += f'                    <prop name="MovementRate" data="{props.movement_rate:.6f}" />\n'
        xml += f'                    <prop name="TrackingRate" data="{props.tracking_rate:.6f}" />\n'
        xml += f'                    <prop name="TrackingMerge" data="{props.tracking_merge:.6f}" />\n'
        xml += f'                    <prop name="TrackingRange" data="{props.tracking_range:.6f}" />\n'
        xml += f'                    <prop name="TrackingRangeLeave" data="{props.tracking_range_leave:.6f}" />\n'
        xml += f'                    <prop name="SplineID" data="-1" />\n'
        xml += f'                    <prop name="TargetSplineID" data="-1" />\n'
        xml += f'                    <prop name="bAutoZoom" data="{"true" if props.auto_zoom else "false"}" />\n'
        xml += f'                    <prop name="bStaticDirection" data="{"true" if props.static_direction else "false"}" />\n'
        xml += f'                    <prop name="SplineChaseDir" data="0" />\n'
        xml += f'                    <prop name="TargetSplineChaseDir" data="0" />\n'
        xml += f'                    <prop name="TrackingLag" data="{props.tracking_lag:.6f}" />\n'
        xml += f'                    <prop name="TrackingLagSmoothening" data="0.8" />\n'  # Default value
        xml += f'                    <prop name="TrackingErrorFrequency" data="1.5" />\n'  # Default value
        xml += f'                    <prop name="TrackingErrorCorrectionSpeed" data="0.12" />\n'  # Default value
        xml += f'                    <prop name="TrackingErrorMagnitude" data="0.08" />\n'  # Default value
        xml += f'                    <prop name="SplinesRatio" data="1" />\n'  # Default value
        xml += f'                    <prop name="bSyncSplines" data="false" />\n'  # Default value
        xml += f'                    <prop name="OnSplineEndReached" data="0" />\n'  # Default value
        xml += f'                    <prop name="OnTargetSplineEndReached" data="0" />\n'  # Default value
        xml += f'                    <prop name="bUniversalGimble" data="false" />\n'  # Default value
        xml += f'                    <prop name="bEnableYaw" data="false" />\n'  # Default value

    xml += f'                </data>\n'

    return xml


def generate_area_xml(area_info: Dict[str, Any], area_id: int) -> str:
    """Generate XML for a single area"""
    props = area_info['properties']

    if props.area_type == 'SPHERE':
        xml = f'                <data class="CSphereArea" id="0x{area_id:08X}">\n'
        xml += f'                    <prop name="Name" data="{area_info["name"]}" />\n'
        # Use the object's location as the sphere center
        centre_pos = convert_position(np.array(area_info['object'].location))
        xml += f'                    <prop name="Centre" data="{format_vector3(centre_pos)}" />\n'
        xml += f'                    <prop name="Radius" data="{props.sphere_radius:.6f}" />\n'
        xml += f'                    <prop name="DebugRenderColor" data="4278190080" />\n'
        xml += f'                    <prop name="FOV" data="0" />\n'
        xml += f'                    <prop name="FocusDelay" data="0" />\n'
        xml += f'                    <prop name="ZoomSpeed" data="0" />\n'
        xml += f'                    <prop name="CameraGroup" data="{props.camera_group}" />\n'
    else:  # OBB
        xml = f'                <data class="COBBArea" id="0x{area_id:08X}">\n'
        xml += f'                    <prop name="Name" data="{area_info["name"]}" />\n'
        xml += f'                    <prop name="XForm" data="{format_matrix_4x4(area_info["world_matrix"])}" />\n'
        xml += f'                    <prop name="Dimensions" data="{format_vector3(props.obb_dimensions)}" />\n'
        xml += f'                    <prop name="DebugRenderColor" data="4278190080" />\n'
        xml += f'                    <prop name="FOV" data="0" />\n'
        xml += f'                    <prop name="FocusDelay" data="0" />\n'
        xml += f'                    <prop name="ZoomSpeed" data="0" />\n'

    xml += f'                </data>\n'
    return xml


def export_environment_xml(filepath: Path, scene: bpy.types.Scene):
    """Export environment XML file"""

    cameras = collect_cameras(scene)
    areas = collect_areas(scene)

    # Generate XML content
    xml_content = '<?xml version="1.0"?>\n'
    xml_content += '<Reflection>\n'

    # Class definitions
    xml_content += '    <class name="BRTTIRefCount" base="root class" />\n'
    xml_content += '    <class name="BPersistent" base="BRTTIRefCount">\n'
    xml_content += '        <prop name="Name" type="String" />\n'
    xml_content += '    </class>\n'
    xml_content += '    <class name="CCameraDataSet" base="BPersistent">\n'
    xml_content += '        <prop name="Trackside Cams" type="Fct" />\n'
    xml_content += '        <prop name="Splines" type="Fct" />\n'
    xml_content += '        <prop name="Areas" type="Fct" />\n'
    xml_content += '    </class>\n'

    # Static Camera class - first definition
    xml_content += '    <class name="BRTTIRefCount" base="root class" />\n'
    xml_content += '    <class name="BPersistent" base="BRTTIRefCount">\n'
    xml_content += '        <prop name="Name" type="String" />\n'
    xml_content += '    </class>\n'
    xml_content += '    <class name="CStaticCamData" base="BPersistent">\n'
    xml_content += '        <prop name="Pos" type="Vec3f" />\n'
    xml_content += '        <prop name="QuatOri" type="Quatf" />\n'
    xml_content += '        <prop name="FOV" type="F32" />\n'
    xml_content += '        <prop name="ZoomSpeed" type="F32" />\n'
    xml_content += '        <prop name="ZoomCurve0" type="F32" />\n'
    xml_content += '        <prop name="ZoomCurve1" type="F32" />\n'
    xml_content += '        <prop name="ZoomCurve2" type="F32" />\n'
    xml_content += '        <prop name="ZoomCurve3" type="F32" />\n'
    xml_content += '        <prop name="ZoomCurve4" type="F32" />\n'
    xml_content += '        <prop name="ZoomCurve5" type="F32" />\n'
    xml_content += '        <prop name="ZoomCurve6" type="F32" />\n'
    xml_content += '        <prop name="ZoomCurve7" type="F32" />\n'
    xml_content += '        <prop name="FOVDelay" type="F32" />\n'
    xml_content += '        <prop name="FOVManual" type="F32" />\n'
    xml_content += '        <prop name="FOVScalar" type="F32" />\n'
    xml_content += '        <prop name="FOVRadiansQuantisationInShadowMap" type="F32" />\n'
    xml_content += '        <prop name="AutoFocus" type="B8" />\n'
    xml_content += '        <prop name="AutoFocusSlowdownFactor" type="F32" />\n'
    xml_content += '        <prop name="DOFAbsolute" type="B8" />\n'
    xml_content += '        <prop name="DOFSpeed" type="F32" />\n'
    xml_content += '        <prop name="DOF" type="F32" />\n'
    xml_content += '        <prop name="DOFStaticFocusDistance" type="F32" />\n'
    xml_content += '        <prop name="DOFDelay" type="F32" />\n'
    xml_content += '        <prop name="DOFSharpRange" type="F32" />\n'
    xml_content += '        <prop name="DOFBlurRange" type="F32" />\n'
    xml_content += '        <prop name="mBokehEnabled" type="B8" />\n'
    xml_content += '        <prop name="mBokehFStop" type="F32" />\n'
    xml_content += '        <prop name="mBokehFocalLength" type="F32" />\n'
    xml_content += '        <prop name="mBokehIrisType" type="U32" />\n'
    xml_content += '        <prop name="Roll" type="F32" />\n'
    xml_content += '        <prop name="RollDelay" type="F32" />\n'
    xml_content += '        <prop name="RollTimer" type="F32" />\n'
    xml_content += '        <prop name="Pitch" type="F32" />\n'
    xml_content += '        <prop name="PitchDelay" type="F32" />\n'
    xml_content += '        <prop name="PitchTimer" type="F32" />\n'
    xml_content += '        <prop name="Yaw" type="F32" />\n'
    xml_content += '        <prop name="YawDelay" type="F32" />\n'
    xml_content += '        <prop name="YawTimer" type="F32" />\n'
    xml_content += '        <prop name="CollisionDistance" type="F32" />\n'
    xml_content += '        <prop name="DualViewDistance" type="F32" />\n'
    xml_content += '        <prop name="SimulationSpeed" type="F32" />\n'
    xml_content += '        <prop name="SimulationRange" type="F32" />\n'
    xml_content += '        <prop name="SimulationTimeout" type="F32" />\n'
    xml_content += '        <prop name="Type" type="U32" />\n'
    xml_content += '        <prop name="NearZ" type="F32" />\n'
    xml_content += '        <prop name="FarZ" type="F32" />\n'
    xml_content += '        <prop name="CutOffZ" type="F32" />\n'
    xml_content += '        <prop name="Target" type="S32" />\n'
    xml_content += '        <prop name="TargetOffset" type="Vec3f" />\n'
    xml_content += '        <prop name="LookAt" type="S32" />\n'
    xml_content += '        <prop name="LookAtOffset" type="Vec3f" />\n'
    xml_content += '        <prop name="LookAtCameraRelative" type="B8" />\n'
    xml_content += '        <prop name="ProximityShakeFrequency" type="F32" />\n'
    xml_content += '        <prop name="ProximityShakeMagnitude" type="F32" />\n'
    xml_content += '        <prop name="ProximityShakeMinDistance" type="F32" />\n'
    xml_content += '        <prop name="ProximityShakeMaxDistance" type="F32" />\n'
    xml_content += '        <prop name="ProximityShakeMinSpeed" type="F32" />\n'
    xml_content += '        <prop name="ProximityShakeMaxSpeed" type="F32" />\n'
    xml_content += '        <prop name="ShakeMagnitude" type="F32" />\n'
    xml_content += '        <prop name="ShakeMagnitudeMin" type="F32" />\n'
    xml_content += '        <prop name="ShakeFrequency" type="F32" />\n'
    xml_content += '        <prop name="ShakeFrequencyMin" type="F32" />\n'
    xml_content += '        <prop name="ShakeScreenVelocity" type="F32" />\n'
    xml_content += '        <prop name="ShakeScreenVelocityMin" type="F32" />\n'
    xml_content += '        <prop name="SoundEffect" type="String" />\n'
    xml_content += '        <prop name="LODDistanceMultiplier" type="F32" />\n'
    xml_content += '        <prop name="OverridedBy" type="String" />\n'
    xml_content += '        <prop name="IncidentCam" type="String" />\n'
    xml_content += '        <prop name="UserDataName" type="String" />\n'
    xml_content += '        <prop name="UserDataValue" type="F32" />\n'
    xml_content += '        <prop name="FOVMin" type="F32" />\n'
    xml_content += '        <prop name="FOVMax" type="F32" />\n'
    xml_content += '        <prop name="RenderHelmet" type="B8" />\n'
    xml_content += '        <prop name="RenderCockpit" type="B8" />\n'
    xml_content += '        <prop name="BattleWorn" type="B8" />\n'
    xml_content += '        <prop name="IsVR" type="B8" />\n'
    xml_content += '        <prop name="TrackingAreaEnter" type="S16" />\n'
    xml_content += '        <prop name="TrackingAreaLeave" type="S16" />\n'
    xml_content += '        <prop name="SimulationSpeedArea" type="S16" />\n'
    xml_content += '        <prop name="CollisionArea" type="S16" />\n'
    xml_content += '        <prop name="PPFilter" type="String" />\n'
    xml_content += '        <prop name="MinSpeedIncident" type="F32" />\n'
    xml_content += '        <prop name="ActiveAreas" type="Fct" />\n'
    xml_content += '        <prop name="ShadowTypeIndex" type="U32" />\n'
    xml_content += '        <prop name="CameraPerLapFlags" type="U32" />\n'
    xml_content += '        <prop name="CameraGroup" type="U32" />\n'
    xml_content += '        <prop name="ForceKeep" type="F32" />\n'
    xml_content += '        <prop name="ForceKeepDistance" type="F32" />\n'
    xml_content += '        <prop name="DistanceRand" type="F32" />\n'
    xml_content += '    </class>\n'

    # Static Camera class - second definition
    xml_content += '    <class name="BRTTIRefCount" base="root class" />\n'
    xml_content += '    <class name="BPersistent" base="BRTTIRefCount">\n'
    xml_content += '        <prop name="Name" type="String" />\n'
    xml_content += '    </class>\n'
    xml_content += '    <class name="CStaticCamData" base="BPersistent">\n'
    xml_content += '        <prop name="Pos" type="Vec3f" />\n'
    xml_content += '        <prop name="QuatOri" type="Quatf" />\n'
    xml_content += '        <prop name="FOV" type="F32" />\n'
    xml_content += '        <prop name="ZoomSpeed" type="F32" />\n'
    xml_content += '        <prop name="ZoomCurve0" type="F32" />\n'
    xml_content += '        <prop name="ZoomCurve1" type="F32" />\n'
    xml_content += '        <prop name="ZoomCurve2" type="F32" />\n'
    xml_content += '        <prop name="ZoomCurve3" type="F32" />\n'
    xml_content += '        <prop name="ZoomCurve4" type="F32" />\n'
    xml_content += '        <prop name="ZoomCurve5" type="F32" />\n'
    xml_content += '        <prop name="ZoomCurve6" type="F32" />\n'
    xml_content += '        <prop name="ZoomCurve7" type="F32" />\n'
    xml_content += '        <prop name="FOVDelay" type="F32" />\n'
    xml_content += '        <prop name="FOVManual" type="F32" />\n'
    xml_content += '        <prop name="FOVScalar" type="F32" />\n'
    xml_content += '        <prop name="FOVRadiansQuantisationInShadowMap" type="F32" />\n'
    xml_content += '        <prop name="AutoFocus" type="B8" />\n'
    xml_content += '        <prop name="AutoFocusSlowdownFactor" type="F32" />\n'
    xml_content += '        <prop name="DOFAbsolute" type="B8" />\n'
    xml_content += '        <prop name="DOFSpeed" type="F32" />\n'
    xml_content += '        <prop name="DOF" type="F32" />\n'
    xml_content += '        <prop name="DOFStaticFocusDistance" type="F32" />\n'
    xml_content += '        <prop name="DOFDelay" type="F32" />\n'
    xml_content += '        <prop name="DOFSharpRange" type="F32" />\n'
    xml_content += '        <prop name="DOFBlurRange" type="F32" />\n'
    xml_content += '        <prop name="mBokehEnabled" type="B8" />\n'
    xml_content += '        <prop name="mBokehFStop" type="F32" />\n'
    xml_content += '        <prop name="mBokehFocalLength" type="F32" />\n'
    xml_content += '        <prop name="mBokehIrisType" type="U32" />\n'
    xml_content += '        <prop name="Roll" type="F32" />\n'
    xml_content += '        <prop name="RollDelay" type="F32" />\n'
    xml_content += '        <prop name="RollTimer" type="F32" />\n'
    xml_content += '        <prop name="Pitch" type="F32" />\n'
    xml_content += '        <prop name="PitchDelay" type="F32" />\n'
    xml_content += '        <prop name="PitchTimer" type="F32" />\n'
    xml_content += '        <prop name="Yaw" type="F32" />\n'
    xml_content += '        <prop name="YawDelay" type="F32" />\n'
    xml_content += '        <prop name="YawTimer" type="F32" />\n'
    xml_content += '        <prop name="CollisionDistance" type="F32" />\n'
    xml_content += '        <prop name="DualViewDistance" type="F32" />\n'
    xml_content += '        <prop name="SimulationSpeed" type="F32" />\n'
    xml_content += '        <prop name="SimulationRange" type="F32" />\n'
    xml_content += '        <prop name="SimulationTimeout" type="F32" />\n'
    xml_content += '        <prop name="Type" type="U32" />\n'
    xml_content += '        <prop name="NearZ" type="F32" />\n'
    xml_content += '        <prop name="FarZ" type="F32" />\n'
    xml_content += '        <prop name="CutOffZ" type="F32" />\n'
    xml_content += '        <prop name="Target" type="S32" />\n'
    xml_content += '        <prop name="TargetOffset" type="Vec3f" />\n'
    xml_content += '        <prop name="LookAt" type="S32" />\n'
    xml_content += '        <prop name="LookAtOffset" type="Vec3f" />\n'
    xml_content += '        <prop name="LookAtCameraRelative" type="B8" />\n'
    xml_content += '        <prop name="ProximityShakeFrequency" type="F32" />\n'
    xml_content += '        <prop name="ProximityShakeMagnitude" type="F32" />\n'
    xml_content += '        <prop name="ProximityShakeMinDistance" type="F32" />\n'
    xml_content += '        <prop name="ProximityShakeMaxDistance" type="F32" />\n'
    xml_content += '        <prop name="ProximityShakeMinSpeed" type="F32" />\n'
    xml_content += '        <prop name="ProximityShakeMaxSpeed" type="F32" />\n'
    xml_content += '        <prop name="ShakeMagnitude" type="F32" />\n'
    xml_content += '        <prop name="ShakeMagnitudeMin" type="F32" />\n'
    xml_content += '        <prop name="ShakeFrequency" type="F32" />\n'
    xml_content += '        <prop name="ShakeFrequencyMin" type="F32" />\n'
    xml_content += '        <prop name="ShakeScreenVelocity" type="F32" />\n'
    xml_content += '        <prop name="ShakeScreenVelocityMin" type="F32" />\n'
    xml_content += '        <prop name="SoundEffect" type="String" />\n'
    xml_content += '        <prop name="LODDistanceMultiplier" type="F32" />\n'
    xml_content += '        <prop name="OverridedBy" type="String" />\n'
    xml_content += '        <prop name="IncidentCam" type="String" />\n'
    xml_content += '        <prop name="UserDataName" type="String" />\n'
    xml_content += '        <prop name="UserDataValue" type="F32" />\n'
    xml_content += '        <prop name="FOVMin" type="F32" />\n'
    xml_content += '        <prop name="FOVMax" type="F32" />\n'
    xml_content += '        <prop name="RenderHelmet" type="B8" />\n'
    xml_content += '        <prop name="RenderCockpit" type="B8" />\n'
    xml_content += '        <prop name="BattleWorn" type="B8" />\n'
    xml_content += '        <prop name="IsVR" type="B8" />\n'
    xml_content += '        <prop name="TrackingAreaEnter" type="S16" />\n'
    xml_content += '        <prop name="TrackingAreaLeave" type="S16" />\n'
    xml_content += '        <prop name="SimulationSpeedArea" type="S16" />\n'
    xml_content += '        <prop name="CollisionArea" type="S16" />\n'
    xml_content += '        <prop name="PPFilter" type="String" />\n'
    xml_content += '        <prop name="MinSpeedIncident" type="F32" />\n'
    xml_content += '        <prop name="ActiveAreas" type="Fct" />\n'
    xml_content += '        <prop name="ShadowTypeIndex" type="U32" />\n'
    xml_content += '        <prop name="CameraPerLapFlags" type="U32" />\n'
    xml_content += '        <prop name="CameraGroup" type="U32" />\n'
    xml_content += '        <prop name="ForceKeep" type="F32" />\n'
    xml_content += '        <prop name="ForceKeepDistance" type="F32" />\n'
    xml_content += '        <prop name="DistanceRand" type="F32" />\n'
    xml_content += '    </class>\n'

    # Tracking camera class
    xml_content += '    <class name="CTrackingCamData" base="CStaticCamData">\n'
    xml_content += '        <prop name="MovementRate" type="F32" />\n'
    xml_content += '        <prop name="TrackingRate" type="F32" />\n'
    xml_content += '        <prop name="TrackingMerge" type="F32" />\n'
    xml_content += '        <prop name="TrackingRange" type="F32" />\n'
    xml_content += '        <prop name="TrackingRangeLeave" type="F32" />\n'
    xml_content += '        <prop name="SplineID" type="S32" />\n'
    xml_content += '        <prop name="TargetSplineID" type="S32" />\n'
    xml_content += '        <prop name="bAutoZoom" type="B8" />\n'
    xml_content += '        <prop name="bStaticDirection" type="B8" />\n'
    xml_content += '        <prop name="SplineChaseDir" type="F32" />\n'
    xml_content += '        <prop name="TargetSplineChaseDir" type="F32" />\n'
    xml_content += '        <prop name="TrackingLag" type="F32" />\n'
    xml_content += '        <prop name="TrackingLagSmoothening" type="F32" />\n'
    xml_content += '        <prop name="TrackingErrorFrequency" type="F32" />\n'
    xml_content += '        <prop name="TrackingErrorCorrectionSpeed" type="F32" />\n'
    xml_content += '        <prop name="TrackingErrorMagnitude" type="F32" />\n'
    xml_content += '        <prop name="SplinesRatio" type="F32" />\n'
    xml_content += '        <prop name="bSyncSplines" type="B8" />\n'
    xml_content += '        <prop name="OnSplineEndReached" type="S32" />\n'
    xml_content += '        <prop name="OnTargetSplineEndReached" type="S32" />\n'
    xml_content += '        <prop name="bUniversalGimble" type="B8" />\n'
    xml_content += '        <prop name="bEnableYaw" type="B8" />\n'
    xml_content += '    </class>\n'

    # Spline classes
    xml_content += '    <class name="BRTTIRefCount" base="root class" />\n'
    xml_content += '    <class name="BPersistent" base="BRTTIRefCount">\n'
    xml_content += '        <prop name="Name" type="String" />\n'
    xml_content += '    </class>\n'
    xml_content += '    <class name="CCamSpline" base="BPersistent">\n'
    xml_content += '        <prop name="Name" type="String" />\n'
    xml_content += '        <prop name="NumNodes" type="U32" />\n'
    xml_content += '        <prop name="Length" type="Float" />\n'
    xml_content += '        <prop name="nodes" type="Fct" />\n'
    xml_content += '    </class>\n'
    xml_content += '    <class name="BRTTIRefCount" base="root class" />\n'
    xml_content += '    <class name="BPersistent" base="BRTTIRefCount">\n'
    xml_content += '        <prop name="Name" type="String" />\n'
    xml_content += '    </class>\n'
    xml_content += '    <class name="CCamSplineNode" base="BPersistent">\n'
    xml_content += '        <prop name="Pos" type="Vec3f" />\n'
    xml_content += '        <prop name="MovementRate" type="Float" />\n'
    xml_content += '        <prop name="FOV" type="Float" />\n'
    xml_content += '        <prop name="DOF" type="Float" />\n'
    xml_content += '        <prop name="Roll" type="Float" />\n'
    xml_content += '        <prop name="Pitch" type="Float" />\n'
    xml_content += '        <prop name="Yaw" type="Float" />\n'
    xml_content += '        <prop name="ShakeMagnitude" type="Float" />\n'
    xml_content += '    </class>\n'

    # Sphere area classes
    xml_content += '    <class name="BRTTIRefCount" base="root class" />\n'
    xml_content += '    <class name="BPersistent" base="BRTTIRefCount">\n'
    xml_content += '        <prop name="Name" type="String" />\n'
    xml_content += '    </class>\n'
    xml_content += '    <class name="CCamArea" base="BPersistent" />\n'
    xml_content += '    <class name="CSphereArea" base="CCamArea">\n'
    xml_content += '        <prop name="Centre" type="Vec3f" />\n'
    xml_content += '        <prop name="Radius" type="Float" />\n'
    xml_content += '        <prop name="DebugRenderColor" type="U32" />\n'
    xml_content += '        <prop name="FOV" type="F32" />\n'
    xml_content += '        <prop name="FocusDelay" type="F32" />\n'
    xml_content += '        <prop name="ZoomSpeed" type="F32" />\n'
    xml_content += '        <prop name="CameraGroup" type="U32" />\n'
    xml_content += '    </class>\n'

    # OBB area classes
    xml_content += '    <class name="BRTTIRefCount" base="root class" />\n'
    xml_content += '    <class name="BPersistent" base="BRTTIRefCount">\n'
    xml_content += '        <prop name="Name" type="String" />\n'
    xml_content += '    </class>\n'
    xml_content += '    <class name="CCamArea" base="BPersistent" />\n'
    xml_content += '    <class name="COBBArea" base="CCamArea">\n'
    xml_content += '        <prop name="XForm" type="Mtx4f" />\n'
    xml_content += '        <prop name="Dimensions" type="Vec3f" />\n'
    xml_content += '        <prop name="DebugRenderColor" type="U32" />\n'
    xml_content += '        <prop name="FOV" type="F32" />\n'
    xml_content += '        <prop name="FocusDelay" type="F32" />\n'
    xml_content += '        <prop name="ZoomSpeed" type="F32" />\n'
    xml_content += '    </class>\n'

    # Main data
    xml_content += '    <data class="CCameraDataSet" id="0x86CBFF70">\n'
    xml_content += '        <prop name="Name" data="CameraDataSet" />\n'

    # Cameras section
    xml_content += f'        <prop name="Trackside Cams" elements="{len(cameras)}">\n'
    xml_content += '            <funcpropdata>\n'

    for i, camera in enumerate(cameras):
        camera['id'] = 0xA1C311A0 + i  # Generate unique IDs
        xml_content += generate_camera_xml(camera, areas)

    xml_content += '            </funcpropdata>\n'
    xml_content += '        </prop>\n'

    # Splines section (empty for now)
    xml_content += '        <prop name="Splines" elements="0">\n'
    xml_content += '            <funcpropdata />\n'
    xml_content += '        </prop>\n'

    # Areas section
    xml_content += f'        <prop name="Areas" elements="{len(areas)}">\n'
    xml_content += '            <funcpropdata>\n'

    for i, area in enumerate(areas):
        area_id = 0xA04E2330 + i  # Generate unique IDs
        xml_content += generate_area_xml(area, area_id)

    xml_content += '            </funcpropdata>\n'
    xml_content += '        </prop>\n'

    xml_content += '    </data>\n'
    xml_content += '</Reflection>\n'

    # Write to file
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(xml_content)

    print(f"Environment XML exported to: {filepath}")
    return len(cameras), len(areas)
