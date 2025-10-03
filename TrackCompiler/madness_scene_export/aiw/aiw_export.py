"""Main AIW export functionality."""

import bpy  # type: ignore
import mathutils  # type: ignore
import numpy as np
from bpy.props import StringProperty, PointerProperty  # type: ignore
from bpy_extras.io_utils import ExportHelper  # type: ignore
from . import aiw_parser
from .aiw_ui import AIW_PT_ScenePanel
from .aiw_waypoint_processor import WaypointProcessor
from .aiw_connections import (
    connect_pit_lane_to_main_line,
    generate_grid_connection_waypoints,
    generate_pit_connection_waypoints,
)
from .aiw_utils import (
    convert_coords_to_madness,
    calculate_euler_orientation,
    find_grid_connection_before_start,
)
from .aiw_writer import write_aiw_file


class AIWExporter(bpy.types.Operator, ExportHelper):
    """Export AIW file."""

    bl_idname = "export_scene.aiw"
    bl_label = "Export AIW"
    bl_description = "Export Madness AIW file"

    filename_ext = ".aiw"

    filter_glob: StringProperty(
        default="*.aiw",
        options={"HIDDEN"},
        maxlen=255,
    )  # type: ignore

    # Export toggles
    export_cut_lines: bpy.props.BoolProperty(
        name="Export Cut Lines",
        description="Export track edge (cut line) widths",
        default=True,
    )  # type: ignore

    export_wall_lines: bpy.props.BoolProperty(
        name="Export Wall Lines",
        description="Export collision boundary (wall line) widths",
        default=True,
    )  # type: ignore

    export_racing_line: bpy.props.BoolProperty(
        name="Export Racing Line",
        description="Export racing line offsets",
        default=True,
    )  # type: ignore

    def execute(self, context):
        try:
            export_aiw(context, self.filepath, self.export_cut_lines, self.export_wall_lines, self.export_racing_line)
            self.report({"INFO"}, f"AIW exported successfully to {self.filepath}")
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, f"AIW export failed: {str(e)}")
            return {"CANCELLED"}

    def draw(self, context):
        """Draw the export options in the file browser dialog."""
        layout = self.layout
        # Export Options
        layout.label(text="Export Options:")
        col = layout.column(align=True)
        col.prop(self, "export_racing_line")
        col.prop(self, "export_cut_lines")
        col.prop(self, "export_wall_lines")


def export_aiw(context, filepath: str, export_cut_lines: bool = True, export_wall_lines: bool = True, export_racing_line: bool = True):
    """Main AIW export function."""
    scene = context.scene

    # Ensure AIW properties exist
    if not hasattr(scene, "aiw_properties"):
        raise Exception(
            "AIW properties not found. Please configure AIW settings first."
        )

    aiw_props = scene.aiw_properties
    aiw_props.ensure_rolling_starts()

    # Collect waypoint objects
    centerline_obj = None
    racing_line_obj = None
    cut_line_left_obj = None
    cut_line_right_obj = None
    wall_line_left_obj = None
    wall_line_right_obj = None
    pit_line_obj = None
    alt_line_objects = {}

    grid_objects = []
    teleport_objects = []
    pit_box_objects = []
    garage_objects = []
    safety_car_obj = None  # Add safety car object

    for obj in scene.objects:
        if obj.type not in ["MESH", "EMPTY"]:
            continue

        name = obj.name

        # Check for track geometry objects
        if name == "SMS_AIW_CENTERLINE":
            centerline_obj = obj
            print(f"Found centerline: {name}")  # Debug output
        elif name == "SMS_AIW_RACINGLINE":
            racing_line_obj = obj
            print(f"Found racing line: {name}")  # Debug output
        elif name == "SMS_AIW_CUTLINE_LEFT":
            cut_line_left_obj = obj
            print(f"Found cut line left: {name}")  # Debug output
        elif name == "SMS_AIW_CUTLINE_RIGHT":
            cut_line_right_obj = obj
            print(f"Found cut line right: {name}")  # Debug output
        elif name == "SMS_AIW_WALLLINE_LEFT":
            wall_line_left_obj = obj
            print(f"Found wall line left: {name}")  # Debug output
        elif name == "SMS_AIW_WALLLINE_RIGHT":
            wall_line_right_obj = obj
            print(f"Found wall line right: {name}")  # Debug output
        elif name.startswith("SMS_AIW_PITLINE"):
            pit_line_obj = obj
            print(f"Found pit line: {name}")  # Debug output
        elif name.startswith("SMS_AIW_ALTLINE_"):
            # Extract alt line number
            alt_num = name.split("_")[-1]
            try:
                alt_id = int(alt_num)
                alt_line_objects[alt_id] = obj
            except ValueError:
                pass
        # Check for marker objects (can be mesh or empty)
        elif name.startswith("SMS_AIW_START_"):
            grid_objects.append(obj)
        elif name.startswith("SMS_AIW_TELEPORT_"):
            teleport_objects.append(obj)
        elif name.startswith("SMS_AIW_PITBOX_"):
            pit_box_objects.append(obj)
            print(f"Found pit box: {name}")  # Debug output
        elif name == "SMS_AIW_SAFETYCAR":
            safety_car_obj = obj
            print(f"Found safety car: {name}")  # Debug output
        elif name.startswith("SMS_AIW_GARAGE_"):
            garage_objects.append(obj)

    print(f"Total pit boxes found: {len(pit_box_objects)}")  # Debug output

    # Process waypoints
    all_waypoints = []
    racing_waypoints = []
    pit_waypoints = []

    # Main racing line (branch_id 0) - use centerline for positions
    if centerline_obj:
        # Print export settings
        if not export_racing_line:
            print("Racing line export disabled - path values will be 0")
        if not export_cut_lines:
            print("Cut lines export disabled - width values will be 0")
        if not export_wall_lines:
            print("Wall lines export disabled - dwidth values will be 0")

        racing_waypoints = WaypointProcessor.process_centerline_waypoints(
            centerline_obj,
            racing_line_obj if export_racing_line else None,
            cut_line_left_obj if export_cut_lines else None,
            cut_line_right_obj if export_cut_lines else None,
            wall_line_left_obj if export_wall_lines else None,
            wall_line_right_obj if export_wall_lines else None,
            0,
            True  # Default clockwise - will be auto-detected from centerline
        )
        all_waypoints.extend(racing_waypoints)
        print(f"Processed {len(racing_waypoints)} racing waypoints from centerline")

    # Pit line (branch_id 1) - use pit line as before
    if pit_line_obj:
        pit_waypoints = WaypointProcessor.process_waypoint_line(
            pit_line_obj, 1, True  # Default clockwise for pit line processing
        )
        all_waypoints.extend(pit_waypoints)

        # Connect pit lane to main line
        main_connection_idx = connect_pit_lane_to_main_line(
            pit_waypoints, racing_waypoints
        )

    # Alternative racing lines (branch_id 999 and descending)
    alt_waypoints_dict = {}
    for alt_id in sorted(alt_line_objects.keys()):
        branch_id = 999 - alt_id  # 999, 998, 997, etc.
        alt_waypoints = WaypointProcessor.process_waypoint_line(
            alt_line_objects[alt_id],
            branch_id,
            True,  # Default clockwise for alt line processing
        )
        alt_waypoints_dict[branch_id] = alt_waypoints
        all_waypoints.extend(alt_waypoints)

    # Store connection waypoints separately to update pointers later
    connection_waypoints = []

    # Track which main line waypoints are already used for connections
    used_main_waypoints = set()

    # Process grid spots first (branch IDs 2, 3, 4, ...)
    for i, obj in enumerate(sorted(grid_objects, key=lambda x: x.name)):
        branch_id = i + 2  # Grid spots start at branch ID 2

        # Get grid spot position for connection finding
        matrix = obj.matrix_world
        grid_pos = convert_coords_to_madness(np.array(matrix.translation))

        # Find connection point, avoiding already used waypoints
        connection_idx = find_grid_connection_before_start(
            grid_pos, racing_waypoints, 20.0, used_main_waypoints
        )

        # If we couldn't find a connection, use nearest available waypoint
        if connection_idx is None or connection_idx in used_main_waypoints:
            for j in range(len(racing_waypoints)):
                if j not in used_main_waypoints:
                    connection_idx = j
                    break

        # Mark this waypoint as used
        used_main_waypoints.add(connection_idx)

        waypoint, _ = generate_grid_connection_waypoints(
            obj, racing_waypoints, branch_id
        )
        if waypoint:
            connection_waypoints.append(("grid", waypoint, connection_idx))
            all_waypoints.append(waypoint)

    # Process pit spots with correct branch IDs starting at 106
    for i, obj in enumerate(sorted(pit_box_objects, key=lambda x: x.name)):
        # Pit boxes get branch IDs starting from 106 (not 100)
        branch_id = 106 + i

        waypoint, pit_behind_idx, pit_ahead_idx = generate_pit_connection_waypoints(
            obj, pit_waypoints, branch_id
        )
        if waypoint:
            connection_waypoints.append(
                ("pit", waypoint, pit_behind_idx, pit_ahead_idx)
            )
            all_waypoints.append(waypoint)

    # Process safety car as pit box index 63 (64th pit box)
    if safety_car_obj:
        branch_id = 106 + 63  # Safety car gets branch ID 169 (106 + 63)

        waypoint, pit_behind_idx, pit_ahead_idx = generate_pit_connection_waypoints(
            safety_car_obj, pit_waypoints, branch_id
        )
        if waypoint:
            connection_waypoints.append(
                ("pit", waypoint, pit_behind_idx, pit_ahead_idx)
            )
            all_waypoints.append(waypoint)

    # Renumber waypoints to be sequential across all lines
    for i, waypoint in enumerate(all_waypoints):
        waypoint.index = i

    # Update waypoint pointers after renumbering
    main_line_offset = 0
    pit_line_offset = len(racing_waypoints)

    # Update main line pointers
    for i, waypoint in enumerate(racing_waypoints):
        # Check if this waypoint should point to first pit waypoint
        if (
            pit_waypoints and waypoint.wp_ptrs[2] == 0
        ):  # This was marked to point to first pit
            first_pit_final_idx = pit_line_offset  # First pit waypoint's final index
            waypoint.wp_ptrs = (
                main_line_offset + ((i - 1) if i > 0 else len(racing_waypoints) - 1),
                main_line_offset + ((i + 1) if i < len(racing_waypoints) - 1 else 0),
                first_pit_final_idx,  # alt_next points to first pit waypoint
                0,  # branch_merge (main line)
            )
        else:
            waypoint.wp_ptrs = (
                main_line_offset + ((i - 1) if i > 0 else len(racing_waypoints) - 1),
                main_line_offset + ((i + 1) if i < len(racing_waypoints) - 1 else 0),
                -1,  # alt_next (no connection)
                0,  # branch_merge (main line)
            )

    # Update pit line pointers
    for i, waypoint in enumerate(pit_waypoints):
        # Get the original values before adjusting
        original_next = waypoint.wp_ptrs[1]
        original_alt_next = waypoint.wp_ptrs[2]

        if i == 0:
            # first pit waypoint: prev points back to main line waypoint that connects to it
            final_main_connection_idx = (
                main_line_offset + main_connection_idx
                if main_connection_idx != -1
                else -1
            )
            new_next = pit_line_offset + min(len(pit_waypoints) - 1, i + 1)

            waypoint.wp_ptrs = (
                final_main_connection_idx,  # prev (points back to main line waypoint)
                new_next,  # next (within pit lane)
                -1,  # alt_next (no connection for first pit waypoint)
                1,  # branch_merge (pit lane)
            )
        elif i == len(pit_waypoints) - 1:
            # Last pit waypoint: both next and alt_next point to main spline
            final_main_idx = (
                main_line_offset + original_next
                if original_next < len(racing_waypoints)
                else original_next
            )
            waypoint.wp_ptrs = (
                pit_line_offset + max(0, i - 1),  # prev (within pit lane)
                final_main_idx,  # next (PRIMARY next to main spline)
                final_main_idx,  # alt_next (also to main spline)
                1,  # branch_merge (pit lane)
            )
        else:
            # Regular pit waypoint
            new_prev = pit_line_offset + max(0, i - 1)
            new_next = pit_line_offset + min(len(pit_waypoints) - 1, i + 1)

            # Adjust alt_next if it points to a main line waypoint
            new_alt_next = original_alt_next
            if original_alt_next != -1 and original_alt_next < len(racing_waypoints):
                new_alt_next = main_line_offset + original_alt_next

            waypoint.wp_ptrs = (
                new_prev,
                new_next,
                new_alt_next,
                1,  # branch_merge (pit lane)
            )

    # Update connection waypoint pointers with correct indices
    for connection_data in connection_waypoints:
        if connection_data[0] == "grid":
            # Grid connection: (type, waypoint, main_line_waypoint_index)
            _, waypoint, main_connection_idx = connection_data
            # Convert main line index to final waypoint index
            final_main_idx = main_line_offset + main_connection_idx
            # Grid spots: prev=main_line_waypoint, next=self, alt_next=-1, branch_merge=branch_id
            waypoint.wp_ptrs = (final_main_idx, waypoint.index, -1, waypoint.branch_id)

            # Set the main line waypoint's alt_next to point to this grid spot
            racing_waypoints[main_connection_idx].wp_ptrs = (
                racing_waypoints[main_connection_idx].wp_ptrs[0],  # prev
                racing_waypoints[main_connection_idx].wp_ptrs[1],  # next
                waypoint.index,  # alt_next -> grid spot
                racing_waypoints[main_connection_idx].wp_ptrs[3],  # branch_merge
            )

        elif connection_data[0] == "pit":
            # Pit connection: (type, waypoint, pit_behind_idx, pit_ahead_idx)
            _, waypoint, pit_behind_idx, pit_ahead_idx = connection_data
            # Convert pit line indices to final waypoint indices
            final_behind_idx = pit_line_offset + pit_behind_idx
            final_ahead_idx = pit_line_offset + pit_ahead_idx
            # Pit spots: prev=pit_line_behind, next=self, alt_next=pit_line_ahead, branch_merge=branch_id
            waypoint.wp_ptrs = (
                final_behind_idx,
                waypoint.index,
                final_ahead_idx,
                waypoint.branch_id,
            )

            # Set the pit line waypoint's alt_next to point to this pit box
            pit_waypoints[pit_behind_idx].wp_ptrs = (
                pit_waypoints[pit_behind_idx].wp_ptrs[0],  # prev
                pit_waypoints[pit_behind_idx].wp_ptrs[1],  # next
                waypoint.index,  # alt_next -> pit box
                pit_waypoints[pit_behind_idx].wp_ptrs[3],  # branch_merge
            )

    waypoint_span = aiw_props.track_features.waypoint_span

    # Calculate lap length and sector lengths
    lap_length = 0.0
    sector_1_length = 0.0
    sector_2_length = 0.0
    sector_3_length = 0.0

    if racing_waypoints:
        # Auto-assign sectors if not properly set
        if all(wp.score[0] == 0 for wp in racing_waypoints):
            # Divide track into 3 equal sectors
            total_waypoints = len(racing_waypoints)
            sector_size = total_waypoints // 3

            for i, wp in enumerate(racing_waypoints):
                if i < sector_size:
                    sector = 0
                elif i < 2 * sector_size:
                    sector = 1
                else:
                    sector = 2
                wp.score = (sector, wp.score[1])

        # First pass: calculate cumulative distances
        cumulative_distance = 0.0
        for i in range(len(racing_waypoints)):
            curr_wp = racing_waypoints[i]
            next_wp = racing_waypoints[(i + 1) % len(racing_waypoints)]

            curr_pos = np.array(
                [curr_wp.position.x, curr_wp.position.y, curr_wp.position.z]
            )
            next_pos = np.array(
                [next_wp.position.x, next_wp.position.y, next_wp.position.z]
            )

            distance = np.linalg.norm(next_pos - curr_pos)

            # Update waypoint lap distance BEFORE adding to cumulative
            curr_wp.score = (curr_wp.score[0], cumulative_distance)

            # Add to cumulative distance and lap length
            cumulative_distance += distance
            lap_length += distance

            # Calculate sector lengths based on current waypoint's sector
            curr_sector = curr_wp.score[0]
            if curr_sector == 0:
                sector_1_length += distance
            elif curr_sector == 1:
                sector_2_length += distance
            elif curr_sector == 2:
                sector_3_length += distance

    # Process grid spots
    grid_spots = []
    for obj in sorted(grid_objects, key=lambda x: x.name):
        # Extract grid index from object name
        grid_index = 0
        try:
            grid_index = int(obj.name.split("_")[-1])
        except ValueError:
            print(f"Could not parse grid index from {obj.name}")

        matrix = obj.matrix_world
        location = convert_coords_to_madness(np.array(matrix.translation))

        # Calculate orientation using proper Euler angles
        forward = np.array(matrix.to_3x3() @ mathutils.Vector([0, 1, 0]))
        madness_forward = convert_coords_to_madness(forward)

        orientation = calculate_euler_orientation(madness_forward)

        grid_spot = aiw_parser.GridSpot(
            index=grid_index,  # Use parsed index from name
            position=aiw_parser.Position(location[0], location[1], location[2]),
            orientation=orientation,
        )
        grid_spots.append(grid_spot)

    # Sort grid spots by index to ensure correct order
    grid_spots.sort(key=lambda x: x.index)

    # Process teleport spots
    teleport_spots = []
    for obj in sorted(teleport_objects, key=lambda x: x.name):
        # Extract teleport index from object name
        teleport_index = 0
        try:
            teleport_index = int(obj.name.split("_")[-1])
        except ValueError:
            print(f"Could not parse teleport index from {obj.name}")

        matrix = obj.matrix_world
        location = convert_coords_to_madness(np.array(matrix.translation))

        forward = np.array(matrix.to_3x3() @ mathutils.Vector([0, 1, 0]))
        madness_forward = convert_coords_to_madness(forward)

        orientation = calculate_euler_orientation(madness_forward)

        teleport_spot = aiw_parser.TeleportSpot(
            index=teleport_index,  # Use parsed index from name
            position=aiw_parser.Position(location[0], location[1], location[2]),
            orientation=orientation,
        )
        teleport_spots.append(teleport_spot)

    # Sort teleport spots by index to ensure correct order
    teleport_spots.sort(key=lambda x: x.index)

    # Process pit spots
    pit_spots = []
    print(f"Processing {len(pit_box_objects)} pit box objects...")  # Debug

    for obj in sorted(pit_box_objects, key=lambda x: x.name):
        # Extract team index from name
        team_index = 0
        try:
            team_index = int(obj.name.split("_")[-1])
            print(
                f"Processing pit box {obj.name} with team index {team_index}"
            )  # Debug
        except ValueError:
            print(f"Could not parse team index from {obj.name}")  # Debug
            pass

        matrix = obj.matrix_world
        location = convert_coords_to_madness(np.array(matrix.translation))

        forward = np.array(matrix.to_3x3() @ mathutils.Vector([0, 1, 0]))
        madness_forward = convert_coords_to_madness(forward)

        orientation = calculate_euler_orientation(madness_forward)

        # Find associated garage objects
        garage_positions = []
        garage_orientations = []

        print(
            f"Looking for garage objects with prefix SMS_AIW_GARAGE_{team_index}"
        )  # Debug

        for garage_obj in garage_objects:
            if garage_obj.name.startswith(f"SMS_AIW_GARAGE_{team_index}"):
                print(f"Found garage: {garage_obj.name}")  # Debug
                garage_matrix = garage_obj.matrix_world
                garage_location = convert_coords_to_madness(
                    np.array(garage_matrix.translation)
                )

                garage_forward = np.array(
                    garage_matrix.to_3x3() @ mathutils.Vector([0, 1, 0])
                )
                garage_madness_forward = convert_coords_to_madness(garage_forward)

                garage_orientation = calculate_euler_orientation(garage_madness_forward)

                garage_positions.append(
                    aiw_parser.Position(
                        garage_location[0], garage_location[1], garage_location[2]
                    )
                )
                garage_orientations.append(garage_orientation)

        print(
            f"Found {len(garage_positions)} garage positions for team {team_index}"
        )  # Debug

        pit_spot = aiw_parser.PitSpot(
            team_index=team_index,
            left_handed=aiw_props.track_features.left_handed_pits,  # Use scene setting
            position=aiw_parser.Position(location[0], location[1], location[2]),
            orientation=orientation,
            garage_positions=garage_positions,
            garage_orientations=garage_orientations,
        )
        pit_spots.append(pit_spot)
        print(f"Created pit spot for team {team_index} at position {location}")  # Debug

    # Process safety car as pit spot index 63
    if safety_car_obj:
        matrix = safety_car_obj.matrix_world
        location = convert_coords_to_madness(np.array(matrix.translation))

        forward = np.array(matrix.to_3x3() @ mathutils.Vector([0, 1, 0]))
        madness_forward = convert_coords_to_madness(forward)

        orientation = calculate_euler_orientation(madness_forward)

        # Safety car typically doesn't have garage objects, but check anyway
        garage_positions = []
        garage_orientations = []

        for garage_obj in garage_objects:
            if garage_obj.name.startswith(
                "SMS_AIW_GARAGE_63"
            ):  # Safety car garage index
                garage_matrix = garage_obj.matrix_world
                garage_location = convert_coords_to_madness(
                    np.array(garage_matrix.translation)
                )

                garage_forward = np.array(
                    garage_matrix.to_3x3() @ mathutils.Vector([0, 1, 0])
                )
                garage_madness_forward = convert_coords_to_madness(garage_forward)

                garage_orientation = calculate_euler_orientation(garage_madness_forward)

                garage_positions.append(
                    aiw_parser.Position(
                        garage_location[0], garage_location[1], garage_location[2]
                    )
                )
                garage_orientations.append(garage_orientation)

        safety_car_pit_spot = aiw_parser.PitSpot(
            team_index=63,  # Safety car is always team index 63
            left_handed=aiw_props.track_features.left_handed_pits,  # Use scene setting
            position=aiw_parser.Position(location[0], location[1], location[2]),
            orientation=orientation,
            garage_positions=garage_positions,
            garage_orientations=garage_orientations,
        )
        pit_spots.append(safety_car_pit_spot)
        print(f"Created safety car pit spot at position {location}")  # Debug

    print(f"Total pit spots created: {len(pit_spots)}")  # Debug

    # Create track features
    features = aiw_parser.TrackFeatures(
        waypoint_span=waypoint_span,
        pitlanes=aiw_props.track_features.pitlanes,
        starting_grid=len(grid_spots),
        pit_spots=len(pit_spots),
        garage_spots=aiw_props.track_features.garage_spots,
        clipping_points=0,
        drift_version=0,
        corner_marker_version=1,
        track_difficulty=aiw_props.track_features.track_difficulty,
        oval=aiw_props.track_features.oval,
        rallycross=aiw_props.track_features.rallycross,
        ice_track=aiw_props.track_features.ice_track,
        ice_track_solo=False,
        narrow_track=aiw_props.track_features.narrow_track,
        race_start_disabled=0.0,
        ai_late_braking_fraction=aiw_props.track_features.ai_late_braking_fraction,
        ai_setup_gearing=aiw_props.track_features.ai_setup_gearing,
        ai_setup_downforce=aiw_props.track_features.ai_setup_downforce,
        ai_setup_balance=aiw_props.track_features.ai_setup_balance,
        anticipation_dist_min=40.0,
        anticipation_dist_off_road=80.0,
        anticipation_dist_wall=160.0,
    )

    # Create rolling starts
    rolling_starts = []
    for rs in aiw_props.rolling_starts:
        rolling_start = aiw_parser.RollingStart(
            race_type=rs.race_type,
            distance_behind_grid=rs.distance_behind_grid,
            distance_between_rows=rs.distance_between_rows,
            cars_in_row=rs.cars_in_row,
            start_speed=rs.start_speed,
            max_speed=rs.max_speed,
        )
        rolling_starts.append(rolling_start)

    # Create waypoint metadata
    waypoint_metadata = aiw_parser.WaypointMetadata(
        trackstate=467,  # Default
        times=(
            340282346638528859811704183484516925440.0000,
            340282346638528859811704183484516925440.0000,
        ),  # ???? not sure if required?
        number_waypoints=len(all_waypoints),
        lap_length=lap_length,
        sector_1_length=sector_1_length,
        sector_2_length=sector_2_length,
        fuel_use=aiw_props.waypoint_metadata.fuel_use,
        groove_width=aiw_props.waypoint_metadata.groove_width,
        groove_width_wet=aiw_props.waypoint_metadata.groove_width_wet,
        intermediate_fog_level=0.0,
        intermediate_fog_planes=(0.0, 0.0),
        rainy_fog_planes=(0.0, 0.0),
        intermediate_fog_color=(0.0, 0.0, 0.0),
        rainy_fog_color=(0.0, 0.0, 0.0),
        fog_density=(0.0, 0.0),
        rainy_darkness=(0.0, 0.0),
        garage_depth=aiw_props.waypoint_metadata.garage_depth,
        pit_stop_space_front=aiw_props.waypoint_metadata.pit_stop_space_front,
        pit_stop_space_back=aiw_props.waypoint_metadata.pit_stop_space_back,
        pit_stop_join_in=aiw_props.waypoint_metadata.pit_stop_join_in,
        pit_stop_join_out=aiw_props.waypoint_metadata.pit_stop_join_out,
        use_line_blend_speed=1,
    )

    # Create track data
    track_data = aiw_parser.TrackData(
        features=features,
        grid_spots=grid_spots,
        rolling_starts=rolling_starts,
        teleport_spots=teleport_spots,
        pit_spots=pit_spots,
        waypoints=all_waypoints,
        waypoint_metadata=waypoint_metadata,
    )

    # Export to file
    write_aiw_file(track_data, filepath)


def menu_func_export(self, context):
    self.layout.operator(AIWExporter.bl_idname, text="Madness AIW (.aiw)")


def register():
    # Import property classes from aiw_properties
    from .aiw_properties import (
        AIWTrackFeatures,
        AIWRollingStart,
        AIWWaypointMetadata,
        AIWSceneProperties,
    )

    bpy.utils.register_class(AIWTrackFeatures)
    bpy.utils.register_class(AIWRollingStart)
    bpy.utils.register_class(AIWWaypointMetadata)
    bpy.utils.register_class(AIWSceneProperties)
    bpy.utils.register_class(AIW_PT_ScenePanel)
    bpy.utils.register_class(AIWExporter)

    bpy.types.Scene.aiw_properties = PointerProperty(type=AIWSceneProperties)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)

    if hasattr(bpy.types.Scene, "aiw_properties"):
        del bpy.types.Scene.aiw_properties

    bpy.utils.unregister_class(AIWExporter)
    bpy.utils.unregister_class(AIW_PT_ScenePanel)

    # Import property classes from aiw_properties for unregistration
    from .aiw_properties import (
        AIWTrackFeatures,
        AIWRollingStart,
        AIWWaypointMetadata,
        AIWSceneProperties,
    )

    bpy.utils.unregister_class(AIWSceneProperties)
    bpy.utils.unregister_class(AIWWaypointMetadata)
    bpy.utils.unregister_class(AIWRollingStart)
    bpy.utils.unregister_class(AIWTrackFeatures)


if __name__ == "__main__":
    register()
