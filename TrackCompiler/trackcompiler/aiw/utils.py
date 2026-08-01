"""Utility functions for AIW export."""

import re

import numpy as np
from math import sqrt, atan2
from typing import List
from . import parser

GARAGE_RE = re.compile(r"^SMS_AIW_GARAGE_(\d+)([A-Za-z])")


def derive_spot_counts(scene):
    """Count start/pit/garage objects in the scene."""
    starting_grid = 0
    pit_spots = 0
    garages_by_team = {}
    for obj in scene.objects:
        name = obj.name
        if name.startswith("SMS_AIW_START_"):
            starting_grid += 1
        elif name.startswith("SMS_AIW_PITBOX_"):
            pit_spots += 1
        else:
            match = GARAGE_RE.match(name)
            if match:
                team = int(match.group(1))
                letter = match.group(2).upper()
                garages_by_team.setdefault(team, set()).add(letter)
    garage_spots = max((len(letters) for letters in garages_by_team.values()), default=0)
    return starting_grid, pit_spots, garage_spots


def convert_coords_to_madness(pos: np.ndarray) -> np.ndarray:
    """Convert position from Blender to Madness coordinate system."""
    x, y, z = pos
    return np.array([x, z, y])


def calculate_perpendicular(forward: np.ndarray, right: np.ndarray) -> np.ndarray:
    """Calculate perpendicular vector (right direction) from forward vector."""
    # Normalize the right vector
    right_norm = right / np.linalg.norm(right)
    return right_norm


def calculate_euler_orientation(forward_vec: np.ndarray) -> parser.Orientation:
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

    return parser.Orientation(pitch, yaw, roll)


def find_waypoint_before_position(
    target_pos: np.ndarray,
    waypoints: List[parser.Waypoint],
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
    waypoints: List[parser.Waypoint],
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


def find_grid_connection_before_start(
    grid_pos: np.ndarray,
    racing_waypoints: List[parser.Waypoint],
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
