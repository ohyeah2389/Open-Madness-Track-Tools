"""Connection functions for pit lanes, grid spots, and waypoint linking."""

import bpy  # type: ignore
import mathutils  # type: ignore
import numpy as np
from typing import List, Tuple, Optional
from . import parser
from .utils import (
    convert_coords_to_madness,
    calculate_perpendicular,
    find_grid_connection_before_start,
    find_waypoint_before_position,
    find_waypoint_after_position,
)


def connect_pit_lane_to_main_line(
    pit_waypoints: List[parser.Waypoint],
    main_waypoints: List[parser.Waypoint],
) -> int:
    """Connect pit lane waypoints to nearest main line waypoints.
    Returns the index of the main waypoint that connects to the first pit waypoint."""
    if not pit_waypoints or not main_waypoints:
        return -1

    # FIRST PIT SPLINE POINT: Find main spline point that comes BEFORE pit spline start
    first_pit_pos = np.array(
        [
            pit_waypoints[0].position.x,
            pit_waypoints[0].position.y,
            pit_waypoints[0].position.z,
        ]
    )

    main_before_pit_idx = find_waypoint_before_position(
        first_pit_pos, main_waypoints
    )

    # Make the main spline point TO the first pit spline point
    main_waypoints[main_before_pit_idx].wp_ptrs = (
        main_waypoints[main_before_pit_idx].wp_ptrs[0],  # prev
        main_waypoints[main_before_pit_idx].wp_ptrs[1],  # next
        0,  # alt_next points to first pit waypoint (will be adjusted after renumbering)
        0,  # branch_merge (main line)
    )

    # LAST PIT SPLINE POINT: Find main spline point that comes AFTER pit spline end
    last_pit_idx = len(pit_waypoints) - 1
    last_pit_pos = np.array(
        [
            pit_waypoints[last_pit_idx].position.x,
            pit_waypoints[last_pit_idx].position.y,
            pit_waypoints[last_pit_idx].position.z,
        ]
    )

    main_after_pit_idx = find_waypoint_after_position(
        last_pit_pos, main_waypoints
    )

    # Set the last pit spline point's primary next AND alternate next to main spline
    pit_waypoints[last_pit_idx].wp_ptrs = (
        max(0, last_pit_idx - 1),  # prev (within pit lane)
        main_after_pit_idx,  # next (PRIMARY next to main spline - point AFTER pit end)
        main_after_pit_idx,  # alt_next (also to main spline)
        1,  # branch_merge (pit lane)
    )

    # Track used main waypoints to ensure unique assignments
    used_main_waypoints = {main_before_pit_idx, main_after_pit_idx}

    # Connect middle pit spline points to main spline (excluding first and last)
    connection_zone = min(10, len(pit_waypoints) // 3)  # First ~10 or 1/3 of pit lane

    for i in range(1, len(pit_waypoints) - 1):  # Skip first and last
        if i < connection_zone or i >= len(pit_waypoints) - connection_zone:
            # Entry/exit areas - connect to main line with unique waypoints
            pit_pos = np.array(
                [
                    pit_waypoints[i].position.x,
                    pit_waypoints[i].position.y,
                    pit_waypoints[i].position.z,
                ]
            )

            # Find the nearest main waypoint that hasn't been used yet
            best_main_idx = -1
            min_distance = float("inf")

            for j, main_wp in enumerate(main_waypoints):
                if j in used_main_waypoints:
                    continue  # Skip already used waypoints

                main_pos = np.array(
                    [main_wp.position.x, main_wp.position.y, main_wp.position.z]
                )
                distance = np.linalg.norm(pit_pos - main_pos)

                if distance < min_distance:
                    min_distance = distance
                    best_main_idx = j

            if best_main_idx != -1:
                used_main_waypoints.add(best_main_idx)
                pit_waypoints[i].wp_ptrs = (
                    pit_waypoints[i].wp_ptrs[0],  # prev (within pit lane)
                    pit_waypoints[i].wp_ptrs[1],  # next (within pit lane)
                    best_main_idx,  # alt_next (unique connection to main line)
                    1,  # branch_merge (pit lane)
                )
            else:
                # Fallback: no connection if no unique waypoint available
                pit_waypoints[i].wp_ptrs = (
                    pit_waypoints[i].wp_ptrs[0],  # prev (within pit lane)
                    pit_waypoints[i].wp_ptrs[1],  # next (within pit lane)
                    -1,  # alt_next (no connection)
                    1,  # branch_merge (pit lane)
                )
        else:
            # Middle section (pits area) - no connection to main line
            pit_waypoints[i].wp_ptrs = (
                pit_waypoints[i].wp_ptrs[0],  # prev (within pit lane)
                pit_waypoints[i].wp_ptrs[1],  # next (within pit lane)
                -1,  # alt_next (no connection during pits)
                1,  # branch_merge (pit lane)
            )

    # Other main line waypoints should have alt_next set to -1 (except the one pointing to first pit)
    for i, main_wp in enumerate(main_waypoints):
        if i != main_before_pit_idx:  # Don't overwrite the connection to first pit
            main_wp.wp_ptrs = (
                main_wp.wp_ptrs[0],  # prev
                main_wp.wp_ptrs[1],  # next
                -1,  # alt_next (no connection)
                0,  # branch_merge (main line)
            )

    return main_before_pit_idx


def generate_grid_connection_waypoints(
    grid_obj: bpy.types.Object,
    racing_waypoints: List[parser.Waypoint],
    branch_id: int,
) -> Tuple[parser.Waypoint, int]:
    """Generate connection waypoints for a grid spot (connects from warmup lap to grid position)."""
    if not racing_waypoints:
        # Return a default waypoint if no racing waypoints exist
        default_waypoint = parser.Waypoint(
            index=0,
            position=parser.Position(0, 0, 0),
            perpendicular=parser.Orientation(0, 0, 0),
            width=(0, 0),
            dwidth=(0, 0),
            path=(0, 0),
            galpha=0.288,
            score=(2, 0.0),
            groove_lat=0.0,
            event=(1.0, 0, 0.0),
            branch_id=branch_id,
            bitfields=1,
            corner_type=0,
            corner_state=0,
            wp_ptrs=(-1, -1, -1, branch_id),
        )
        return (default_waypoint, 0)

    # Get grid spot position
    matrix = grid_obj.matrix_world
    grid_pos = convert_coords_to_madness(np.array(matrix.translation))

    # Find connection point 20 meters before the grid spot
    connection_idx = find_grid_connection_before_start(grid_pos, racing_waypoints, 20.0)
    if connection_idx is None:
        # Fallback to nearest waypoint if distance-based search fails
        connection_idx = 0
        min_distance = float("inf")
        for i, waypoint in enumerate(racing_waypoints):
            wp_pos = np.array(
                [waypoint.position.x, waypoint.position.y, waypoint.position.z]
            )
            distance = np.linalg.norm(grid_pos - wp_pos)
            if distance < min_distance:
                min_distance = distance
                connection_idx = i

    # Create single connection waypoint at grid position
    forward = np.array(matrix.to_3x3() @ mathutils.Vector([0, 1, 0]))
    madness_forward = convert_coords_to_madness(forward)

    # Calculate right direction
    up_vec = np.array([0, 0, 1])
    right_vec = np.cross(madness_forward, up_vec)
    if np.linalg.norm(right_vec) > 0:
        right_vec = right_vec / np.linalg.norm(right_vec)
    else:
        right_vec = np.array([1, 0, 0])

    perpendicular = calculate_perpendicular(madness_forward, right_vec)

    # Create waypoint
    waypoint = parser.Waypoint(
        index=0,  # Will be renumbered later
        position=parser.Position(grid_pos[0], grid_pos[1], grid_pos[2]),
        perpendicular=parser.Orientation(
            perpendicular[0], perpendicular[1], perpendicular[2]
        ),
        width=(0.0, 0.0),
        dwidth=(0.0, 0.0),
        path=(0.0, 0.0),
        galpha=0.288,
        score=(2, 0.0),  # Sector 2, distance will be calculated
        groove_lat=0.0,
        event=(1.0, 0, 0.0),
        branch_id=branch_id,
        bitfields=1,
        corner_type=0,
        corner_state=0,
        wp_ptrs=(-1, -1, -1, branch_id),  # Will be updated later
    )

    return (waypoint, connection_idx)


def generate_pit_connection_waypoints(
    pit_obj: bpy.types.Object, pit_waypoints: List[parser.Waypoint], branch_id: int
) -> Tuple[parser.Waypoint, int, int]:
    """Generate connection waypoints for a pit spot (connects to/from pit line)."""
    if not pit_waypoints:
        return None, -1, -1

    # Get pit spot position
    matrix = pit_obj.matrix_world
    pit_pos = convert_coords_to_madness(np.array(matrix.translation))

    # Find nearest waypoint on pit line
    nearest_idx = 0
    min_distance = float("inf")

    for i, waypoint in enumerate(pit_waypoints):
        wp_pos = np.array(
            [waypoint.position.x, waypoint.position.y, waypoint.position.z]
        )
        distance = np.linalg.norm(pit_pos - wp_pos)
        if distance < min_distance:
            min_distance = distance
            nearest_idx = i

    # Get behind and ahead waypoints
    nearest_behind_idx = max(0, nearest_idx - 2)  # 2 waypoints behind
    nearest_ahead_idx = min(
        len(pit_waypoints) - 1, nearest_idx + 2
    )  # 2 waypoints ahead

    # Create connection waypoint at pit position
    forward = np.array(matrix.to_3x3() @ mathutils.Vector([0, 1, 0]))
    madness_forward = convert_coords_to_madness(forward)

    # Calculate right direction
    up_vec = np.array([0, 0, 1])
    right_vec = np.cross(madness_forward, up_vec)
    if np.linalg.norm(right_vec) > 0:
        right_vec = right_vec / np.linalg.norm(right_vec)
    else:
        right_vec = np.array([1, 0, 0])

    perpendicular = calculate_perpendicular(madness_forward, right_vec)

    # Create waypoint
    waypoint = parser.Waypoint(
        index=0,  # Will be renumbered later
        position=parser.Position(pit_pos[0], pit_pos[1], pit_pos[2]),
        perpendicular=parser.Orientation(
            perpendicular[0], perpendicular[1], perpendicular[2]
        ),
        width=(5.0, 5.0),
        dwidth=(5.0, 5.0),
        path=(5.0, 0.0),
        galpha=0.288,
        score=(2, 0.0),  # Sector 2, distance will be calculated
        groove_lat=0.0,
        event=(1.0, 0, 0.0),
        branch_id=branch_id,
        bitfields=1,
        corner_type=0,
        corner_state=0,
        wp_ptrs=(
            nearest_behind_idx,
            nearest_ahead_idx,
            -1,
            branch_id,
        ),  # Connects to pit line
    )

    return (waypoint, nearest_behind_idx, nearest_ahead_idx)
