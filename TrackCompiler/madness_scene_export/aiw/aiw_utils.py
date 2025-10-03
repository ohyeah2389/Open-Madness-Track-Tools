"""Utility functions for AIW export."""

import numpy as np
from math import sqrt, atan2
from typing import List
from . import aiw_parser


def convert_coords_to_madness(pos: np.ndarray) -> np.ndarray:
    """Convert position from Blender to Madness coordinate system."""
    x, y, z = pos
    return np.array([x, z, y])


def calculate_perpendicular(forward: np.ndarray, right: np.ndarray) -> np.ndarray:
    """Calculate perpendicular vector (right direction) from forward vector."""
    # Normalize the right vector
    right_norm = right / np.linalg.norm(right)
    return right_norm


def calculate_euler_orientation(forward_vec: np.ndarray) -> aiw_parser.Orientation:
    """Calculate Euler orientation from forward vector."""
    # Normalize the forward vector
    forward = -(
        forward_vec / np.linalg.norm(forward_vec)
        if np.linalg.norm(forward_vec) > 0
        else np.array([0, 1, 0])
    )

    # Calculate yaw (rotation around Y axis)
    yaw = atan2(forward[0], forward[2])

    # Calculate pitch (rotation around X axis)
    pitch = atan2(-forward[1], sqrt(forward[0] ** 2 + forward[2] ** 2))

    # Roll is typically 0 for track orientations
    roll = 0.0

    return aiw_parser.Orientation(pitch, yaw, roll)


def find_waypoint_before_position(
    target_pos: np.ndarray,
    waypoints: List[aiw_parser.Waypoint],
) -> int:
    """Find a waypoint that comes BEFORE the target position in track direction."""
    if not waypoints:
        return 0

    # Find the nearest waypoint first
    nearest_idx = 0
    min_distance = float("inf")

    for i, waypoint in enumerate(waypoints):
        wp_pos = np.array(
            [waypoint.position.x, waypoint.position.y, waypoint.position.z]
        )
        distance = np.linalg.norm(target_pos - wp_pos)
        if distance < min_distance:
            min_distance = distance
            nearest_idx = i

    # Get track direction at nearest waypoint
    current_idx = nearest_idx
    next_idx = (current_idx + 1) % len(waypoints)

    current_pos = np.array(
        [
            waypoints[current_idx].position.x,
            waypoints[current_idx].position.y,
            waypoints[current_idx].position.z,
        ]
    )
    next_pos = np.array(
        [
            waypoints[next_idx].position.x,
            waypoints[next_idx].position.y,
            waypoints[next_idx].position.z,
        ]
    )

    # Track direction vector
    track_direction = next_pos - current_pos
    if np.linalg.norm(track_direction) > 0:
        track_direction = track_direction / np.linalg.norm(track_direction)

    # Vector from current waypoint to target
    to_target = target_pos - current_pos

    # Project to_target onto track direction
    projection = np.dot(to_target, track_direction)

    if projection > 0:
        # Target is ahead of current waypoint, so current waypoint is before target
        return current_idx
    else:
        # Target is behind current waypoint, so we need to go back to find a point before
        # Go back 2-3 waypoints to ensure we're properly before the target
        return (current_idx - 2) % len(waypoints)


def find_waypoint_after_position(
    target_pos: np.ndarray,
    waypoints: List[aiw_parser.Waypoint],
) -> int:
    """Find a waypoint that comes AFTER the target position in track direction."""
    if not waypoints:
        return 0

    # Find the nearest waypoint first
    nearest_idx = 0
    min_distance = float("inf")

    for i, waypoint in enumerate(waypoints):
        wp_pos = np.array(
            [waypoint.position.x, waypoint.position.y, waypoint.position.z]
        )
        distance = np.linalg.norm(target_pos - wp_pos)
        if distance < min_distance:
            min_distance = distance
            nearest_idx = i

    # Get track direction at nearest waypoint
    current_idx = nearest_idx
    next_idx = (current_idx + 1) % len(waypoints)

    current_pos = np.array(
        [
            waypoints[current_idx].position.x,
            waypoints[current_idx].position.y,
            waypoints[current_idx].position.z,
        ]
    )
    next_pos = np.array(
        [
            waypoints[next_idx].position.x,
            waypoints[next_idx].position.y,
            waypoints[next_idx].position.z,
        ]
    )

    # Track direction vector
    track_direction = next_pos - current_pos
    if np.linalg.norm(track_direction) > 0:
        track_direction = track_direction / np.linalg.norm(track_direction)

    # Vector from current waypoint to target
    to_target = target_pos - current_pos

    # Project to_target onto track direction
    projection = np.dot(to_target, track_direction)

    if projection < 0:
        # Target is behind current waypoint, so current waypoint is after target
        return current_idx
    else:
        # Target is ahead of current waypoint, so we need to go forward to find a point after
        # Go forward 2-3 waypoints to ensure we're properly after the target
        return (current_idx + 2) % len(waypoints)


def find_nearest_waypoint_behind(
    target_pos: np.ndarray,
    waypoints: List[aiw_parser.Waypoint],
    distance_behind: float = 10.0,
) -> int:
    """Find the nearest waypoint that is approximately distance_behind meters before the target position."""
    if not waypoints:
        return 0

    min_distance = float("inf")
    best_waypoint_idx = 0

    for i, waypoint in enumerate(waypoints):
        wp_pos = np.array(
            [waypoint.position.x, waypoint.position.y, waypoint.position.z]
        )
        distance = np.linalg.norm(target_pos - wp_pos)

        # Prefer waypoints that are roughly the right distance behind
        distance_score = abs(distance - distance_behind)

        if distance_score < min_distance:
            min_distance = distance_score
            best_waypoint_idx = i

    return best_waypoint_idx


def find_nearest_waypoint_ahead(
    target_pos: np.ndarray,
    waypoints: List[aiw_parser.Waypoint],
) -> int:
    """Find the nearest waypoint that is approximately distance_ahead meters ahead of the target position."""
    if not waypoints:
        return 0

    # First, find the nearest waypoint overall
    nearest_idx = 0
    min_distance = float("inf")

    for i, waypoint in enumerate(waypoints):
        wp_pos = np.array(
            [waypoint.position.x, waypoint.position.y, waypoint.position.z]
        )
        distance = np.linalg.norm(target_pos - wp_pos)
        if distance < min_distance:
            min_distance = distance
            nearest_idx = i

    # Then find a waypoint ahead of the nearest one
    # For pit line (open path), just move forward along the line
    ahead_idx = min(nearest_idx + 3, len(waypoints) - 1)  # 3 waypoints ahead

    return ahead_idx


def find_optimal_grid_connection(
    grid_pos: np.ndarray,
    racing_waypoints: List[aiw_parser.Waypoint],
) -> int:
    """Find the optimal connection point on the main racing line for a grid spot."""
    if not racing_waypoints:
        return 0

    # Find the nearest waypoint overall
    nearest_idx = 0
    min_distance = float("inf")

    for i, waypoint in enumerate(racing_waypoints):
        wp_pos = np.array(
            [waypoint.position.x, waypoint.position.y, waypoint.position.z]
        )
        distance = np.linalg.norm(grid_pos - wp_pos)
        if distance < min_distance:
            min_distance = distance
            nearest_idx = i

    # Get the forward direction of the nearest waypoint
    nearest_wp = racing_waypoints[nearest_idx]

    # Find the next waypoint in the racing direction
    next_idx = (nearest_idx + 1) % len(racing_waypoints)
    next_wp = racing_waypoints[next_idx]

    # Calculate the forward direction from nearest to next
    nearest_pos = np.array(
        [nearest_wp.position.x, nearest_wp.position.y, nearest_wp.position.z]
    )
    next_pos = np.array([next_wp.position.x, next_wp.position.y, next_wp.position.z])
    track_direction = next_pos - nearest_pos

    # Calculate vector from nearest waypoint to grid position
    grid_direction = grid_pos - nearest_pos

    # Check if grid is ahead or behind in the track direction
    dot_product = np.dot(grid_direction, track_direction)

    if dot_product > 0:
        # Grid is ahead of the nearest waypoint, so use the next waypoint
        connection_idx = next_idx
    else:
        # Grid is behind the nearest waypoint, so use the nearest waypoint
        connection_idx = nearest_idx

    # For better race starts, we might want to connect to a point slightly ahead
    # to ensure smooth merging after the start
    ahead_offset = 2  # Connect to 2 waypoints ahead for smoother merging
    final_connection_idx = (connection_idx + ahead_offset) % len(racing_waypoints)

    return final_connection_idx


def find_grid_connection_before_start(
    grid_pos: np.ndarray,
    racing_waypoints: List[aiw_parser.Waypoint],
    distance_before: float = 20.0,
    avoid_indices: set = None,
) -> int:
    """Find a waypoint on the main racing line approximately distance_before meters before the grid spot."""
    if not racing_waypoints:
        return 0

    if avoid_indices is None:
        avoid_indices = set()

    # First, find the nearest waypoint to the grid spot
    nearest_idx = 0
    min_distance = float("inf")

    for i, waypoint in enumerate(racing_waypoints):
        if i in avoid_indices:
            continue
        wp_pos = np.array(
            [waypoint.position.x, waypoint.position.y, waypoint.position.z]
        )
        distance = np.linalg.norm(grid_pos - wp_pos)
        if distance < min_distance:
            min_distance = distance
            nearest_idx = i

    # Now find a waypoint approximately distance_before meters before the nearest one
    # We'll walk backwards along the racing line and accumulate distance
    total_distance = 0.0
    current_idx = nearest_idx

    while total_distance < distance_before:
        # Get the previous waypoint index (wrap around for closed track)
        prev_idx = (current_idx - 1) % len(racing_waypoints)

        # Skip if this waypoint is already used
        if prev_idx in avoid_indices:
            # Find the next available waypoint
            for offset in range(1, len(racing_waypoints)):
                candidate_idx = (prev_idx - offset) % len(racing_waypoints)
                if candidate_idx not in avoid_indices:
                    prev_idx = candidate_idx
                    break

        # Calculate distance between current and previous waypoint
        curr_pos = np.array(
            [
                racing_waypoints[current_idx].position.x,
                racing_waypoints[current_idx].position.y,
                racing_waypoints[current_idx].position.z,
            ]
        )
        prev_pos = np.array(
            [
                racing_waypoints[prev_idx].position.x,
                racing_waypoints[prev_idx].position.y,
                racing_waypoints[prev_idx].position.z,
            ]
        )

        segment_distance = np.linalg.norm(curr_pos - prev_pos)
        total_distance += segment_distance

        # Move to the previous waypoint
        current_idx = prev_idx

        # Safety check: don't loop forever
        if current_idx == nearest_idx:
            break

    # Always return a valid index, even if we couldn't find the exact distance
    return current_idx
