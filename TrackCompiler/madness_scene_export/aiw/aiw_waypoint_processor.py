"""Waypoint processing for AIW export."""

import bpy # type: ignore
import bmesh # type: ignore
import numpy as np
from typing import List, Dict, Any
from . import aiw_parser
from .aiw_utils import convert_coords_to_madness, calculate_perpendicular


class WaypointProcessor:
    """Process waypoints from mesh objects."""

    @staticmethod
    def get_waypoint_attribute(obj, attr_name: str, default_value, vertex_index: int = None):
        """Get waypoint attribute from object or specific vertex, with fallback to default."""
        if hasattr(obj.data, "attributes") and attr_name in obj.data.attributes:
            attr = obj.data.attributes[attr_name]
            if vertex_index is not None and vertex_index < len(attr.data):
                # Read from specific vertex
                return attr.data[vertex_index].value
            elif len(attr.data) > 0:
                # Read from first vertex (object-level attribute)
                return attr.data[0].value
        return default_value

    @staticmethod
    def get_waypoint_tuple_attribute(obj, attr_name: str, default_value: tuple, vertex_index: int = None):
        """Get tuple waypoint attribute from object or specific vertex."""
        if hasattr(obj.data, "attributes"):
            for i, component in enumerate(["x", "y", "z"][: len(default_value)]):
                full_name = f"{attr_name}_{component}"
                if full_name in obj.data.attributes:
                    attr = obj.data.attributes[full_name]
                    if vertex_index is not None and vertex_index < len(attr.data):
                        # Read from specific vertex
                        result = list(default_value)
                        result[i] = attr.data[vertex_index].value
                        return tuple(result)
                    elif len(attr.data) > 0:
                        # Read from first vertex (object-level attribute)
                        result = list(default_value)
                        result[i] = attr.data[0].value
                        return tuple(result)
        return default_value

    @staticmethod
    def process_centerline_waypoints(
        centerline_obj: bpy.types.Object,
        racing_line_obj: bpy.types.Object = None,
        cut_line_left_obj: bpy.types.Object = None,
        cut_line_right_obj: bpy.types.Object = None,
        wall_line_left_obj: bpy.types.Object = None,
        wall_line_right_obj: bpy.types.Object = None,
        branch_id: int = 0,
    ) -> List[aiw_parser.Waypoint]:
        """Process centerline waypoints with lateral offset calculations."""
        if not centerline_obj or centerline_obj.type != "MESH":
            return []

        # Get centerline vertices using the provided mesh ordering
        centerline_vertices = WaypointProcessor._get_ordered_vertices(centerline_obj)

        if not centerline_vertices:
            return []

        waypoints = []

        for i, centerline_pos in enumerate(centerline_vertices):
            # Calculate lateral offsets from centerline
            lateral_data = WaypointProcessor._calculate_lateral_offsets(
                centerline_pos,
                racing_line_obj,
                cut_line_left_obj,
                cut_line_right_obj,
                wall_line_left_obj,
                wall_line_right_obj,
                centerline_vertices
            )

            # Calculate forward direction
            if len(centerline_vertices) > 1:
                if i < len(centerline_vertices) - 1:
                    next_pos = centerline_vertices[i + 1]
                else:
                    next_pos = centerline_vertices[0]  # Wrap around for closed path

                forward_vec = next_pos - centerline_pos
                if np.linalg.norm(forward_vec) > 0:
                    forward_vec = forward_vec / np.linalg.norm(forward_vec)
                else:
                    forward_vec = np.array([0, 1, 0])  # Default forward
            else:
                forward_vec = np.array([0, 1, 0])  # Default forward

            # Calculate right direction
            up_vec = np.array([0, 0, 1])  # Blender Z-up
            right_vec = np.cross(forward_vec, up_vec)

            if np.linalg.norm(right_vec) > 0:
                right_vec = right_vec / np.linalg.norm(right_vec)
            else:
                right_vec = np.array([1, 0, 0])  # Default right

            # Convert to Madness coordinate system
            madness_pos = convert_coords_to_madness(centerline_pos)
            madness_forward = convert_coords_to_madness(forward_vec)
            madness_right = convert_coords_to_madness(right_vec)

            # Calculate perpendicular (right direction)
            perpendicular = calculate_perpendicular(madness_forward, madness_right)

            # Get waypoint attributes from centerline object
            width = lateral_data['width']
            dwidth = lateral_data['dwidth']
            groove_lat = 0.0
            path_0 = lateral_data['racing_offset']  # Racing line offset goes in path[0]

            # Other attributes - update path[0] with racing line offset
            original_path = WaypointProcessor.get_waypoint_tuple_attribute(
                centerline_obj, "path", (0.0, 0.0), i
            )
            path = (path_0, original_path[1])  # Keep wet line offset as-is
            galpha = WaypointProcessor.get_waypoint_attribute(centerline_obj, "galpha", 0.0, i)

            # Score (sector, lap distance) - calculate lap distance
            sector = WaypointProcessor.get_waypoint_attribute(centerline_obj, "sector", 0, i)
            lap_distance = WaypointProcessor.get_waypoint_attribute(
                centerline_obj, "lap_distance", 0.0, i
            )
            score = (int(sector), lap_distance)

            # Event (corner speed mult, special event, special event data)
            event_speed = WaypointProcessor.get_waypoint_attribute(
                centerline_obj, "event_speed", 1.0, i
            )
            event_type = WaypointProcessor.get_waypoint_attribute(
                centerline_obj, "event_type", 0, i
            )
            event_data = WaypointProcessor.get_waypoint_attribute(
                centerline_obj, "event_data", 0.0, i
            )
            event = (event_speed, int(event_type), event_data)

            bitfields = int(
                WaypointProcessor.get_waypoint_attribute(centerline_obj, "bitfields", 0, i)
            )
            corner_type = int(
                WaypointProcessor.get_waypoint_attribute(centerline_obj, "corner_type", 0, i)
            )
            corner_state = int(
                WaypointProcessor.get_waypoint_attribute(centerline_obj, "corner_state", 0, i)
            )

            # Calculate waypoint pointers based on whether it's a closed or open path
            is_closed_path = branch_id == 0  # Only racing line is closed
            if is_closed_path:
                # Closed path (racing line): wrap around
                prev_wp = (i - 1) if i > 0 else len(centerline_vertices) - 1
                next_wp = (i + 1) if i < len(centerline_vertices) - 1 else 0
            else:
                # Open path (pit line): don't wrap around
                prev_wp = max(0, i - 1)
                next_wp = min(len(centerline_vertices) - 1, i + 1)

            wp_ptrs = (
                prev_wp,
                next_wp,
                -1,
                -1,
            )  # alt_next and branch_merge to be calculated later

            # Create waypoint
            waypoint = aiw_parser.Waypoint(
                index=i,
                position=aiw_parser.Position(
                    madness_pos[0], madness_pos[1], madness_pos[2]
                ),
                perpendicular=aiw_parser.Orientation(
                    perpendicular[0], perpendicular[1], perpendicular[2]
                ),
                width=width,
                dwidth=dwidth,
                path=path,
                galpha=galpha,
                score=score,
                groove_lat=groove_lat,
                event=event,
                branch_id=branch_id,
                bitfields=bitfields,
                corner_type=corner_type,
                corner_state=corner_state,
                wp_ptrs=wp_ptrs,
            )
            waypoints.append(waypoint)

        return waypoints

    @staticmethod
    def _get_ordered_vertices(mesh_obj: bpy.types.Object) -> List[np.ndarray]:
        """Get ordered vertices from a mesh object."""
        if not mesh_obj or mesh_obj.type != "MESH":
            return []

        # Get the evaluated mesh (after applying modifiers)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        eval_obj = mesh_obj.evaluated_get(depsgraph)

        if not eval_obj or not eval_obj.data:
            return []

        # Create bmesh from evaluated mesh
        bm = bmesh.new()
        bm.from_mesh(eval_obj.data)

        # Ensure face indices are valid
        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()

        matrix = mesh_obj.matrix_world

        # Get vertices in world coordinates respecting vertex indices
        ordered_vertices = [
            np.array(matrix @ vert.co)
            for vert in sorted(bm.verts, key=lambda v: v.index)
        ]

        # Clean up bmesh
        bm.free()

        return ordered_vertices

    @staticmethod
    def _calculate_lateral_offsets(
        centerline_pos: np.ndarray,
        racing_line_obj: bpy.types.Object = None,
        cut_line_left_obj: bpy.types.Object = None,
        cut_line_right_obj: bpy.types.Object = None,
        wall_line_left_obj: bpy.types.Object = None,
        wall_line_right_obj: bpy.types.Object = None,
        centerline_vertices: List[np.ndarray] = None
    ) -> Dict[str, Any]:
        """Calculate lateral offsets from centerline to various track geometry lines."""

        # Default values
        racing_offset = 0.0
        width_left = 6.0
        width_right = 6.0
        dwidth_left = 10.0
        dwidth_right = 10.0

        # Calculate racing_offset (distance from centerline to racing line)
        if racing_line_obj:
            racing_distance = WaypointProcessor._calculate_lateral_distance(
                centerline_pos, racing_line_obj, centerline_vertices
            )
            if racing_distance is not None:
                racing_offset = racing_distance

        # Calculate width (distance from centerline to cut lines)
        if cut_line_left_obj:
            left_distance = WaypointProcessor._calculate_lateral_distance(
                centerline_pos, cut_line_left_obj, centerline_vertices
            )
            if left_distance is not None:
                width_left = abs(left_distance)

        if cut_line_right_obj:
            right_distance = WaypointProcessor._calculate_lateral_distance(
                centerline_pos, cut_line_right_obj, centerline_vertices
            )
            if right_distance is not None:
                width_right = abs(right_distance)

        # Calculate dwidth (distance from centerline to wall lines)
        if wall_line_left_obj:
            left_wall_distance = WaypointProcessor._calculate_lateral_distance(
                centerline_pos, wall_line_left_obj, centerline_vertices
            )
            if left_wall_distance is not None:
                dwidth_left = abs(left_wall_distance)

        if wall_line_right_obj:
            right_wall_distance = WaypointProcessor._calculate_lateral_distance(
                centerline_pos, wall_line_right_obj, centerline_vertices
            )
            if right_wall_distance is not None:
                dwidth_right = abs(right_wall_distance)

        return {
            'racing_offset': -racing_offset,
            'width': (width_left, width_right),
            'dwidth': (dwidth_left, dwidth_right)
        }

    @staticmethod
    def _calculate_lateral_distance(
        centerline_pos: np.ndarray,
        target_obj: bpy.types.Object,
        centerline_vertices: List[np.ndarray] = None
    ) -> float:
        """Calculate the lateral distance from centerline position to the first edge intersection on target mesh."""
        if not target_obj or target_obj.type != "MESH":
            return None

        # Get target mesh edges
        edges_2d = WaypointProcessor._get_mesh_edges_2d(target_obj)
        if not edges_2d:
            return None

        # Calculate the track direction at this centerline position
        forward_dir = WaypointProcessor._calculate_local_tangent(
            centerline_pos, centerline_vertices
        )

        if forward_dir is None:
            return None

        # Calculate lateral direction (perpendicular to forward) - in 2D X-Y plane
        up_vec = np.array([0, 0, 1])  # Blender Z-up
        lateral_dir_3d = np.cross(forward_dir, up_vec)

        if np.linalg.norm(lateral_dir_3d) > 0:
            lateral_dir_3d = lateral_dir_3d / np.linalg.norm(lateral_dir_3d)
        else:
            lateral_dir_3d = np.array([1, 0, 0])  # Default lateral direction

        # Convert to 2D (X-Y plane only)
        lateral_dir_2d = np.array([lateral_dir_3d[0], lateral_dir_3d[1]])
        centerline_pos_2d = np.array([centerline_pos[0], centerline_pos[1]])

        if np.linalg.norm(lateral_dir_2d) > 0:
            lateral_dir_2d = lateral_dir_2d / np.linalg.norm(lateral_dir_2d)
        else:
            return None

        # Find the closest point on any edge to the centerline position
        min_distance = float('inf')
        closest_point = None

        for edge_start, edge_end in edges_2d:
            # Find closest point on this edge to the centerline position
            edge_point = WaypointProcessor._closest_point_on_edge_2d(
                centerline_pos_2d, edge_start, edge_end
            )

            if edge_point is not None:
                distance = np.linalg.norm(edge_point - centerline_pos_2d)
                if distance < min_distance:
                    min_distance = distance
                    closest_point = edge_point

        if closest_point is None:
            # Fallback to ray casting approach
            return WaypointProcessor._ray_cast_lateral_distance(
                centerline_pos_2d, lateral_dir_2d, edges_2d
            )

        # Check if the closest point is laterally positioned (not ahead/behind)
        # Project the vector to closest point onto the forward direction
        to_closest = closest_point - centerline_pos_2d
        forward_2d = np.array([forward_dir[0], forward_dir[1]])

        if np.linalg.norm(forward_2d) > 0:
            forward_2d = forward_2d / np.linalg.norm(forward_2d)
            forward_projection = np.dot(to_closest, forward_2d)

            # If the projection is significant, this point is ahead/behind, not lateral
            # Use a more permissive tolerance, especially for start/finish areas
            tolerance = min_distance * 0.8  # Increased tolerance

            # For very close points, be even more permissive
            if min_distance < 1.0:  # Within 1 unit
                tolerance = min_distance * 1.5

            if abs(forward_projection) > tolerance:
                # Debug output for failed cases
                # print(f"Rejected point: dist={min_distance:.3f}, forward_proj={forward_projection:.3f}, tolerance={tolerance:.3f}")
                return None  # Point is too far forward/backward

        # Determine sign based on lateral direction
        # Positive = right side of track, Negative = left side of track
        lateral_projection = np.dot(to_closest, lateral_dir_2d)
        sign = 1 if lateral_projection >= 0 else -1

        return sign * min_distance

    @staticmethod
    def _closest_point_on_edge_2d(
        point: np.ndarray,
        edge_start: np.ndarray,
        edge_end: np.ndarray
    ) -> np.ndarray:
        """Find the closest point on a 2D line segment to a given point."""
        # Vector from edge start to end
        edge_vec = edge_end - edge_start

        # Vector from edge start to point
        point_vec = point - edge_start

        # Length of edge squared
        edge_len_sq = np.dot(edge_vec, edge_vec)

        if edge_len_sq < 1e-10:  # Edge is too short, return endpoint
            return edge_start

        # Parameter along the edge (0 = start, 1 = end)
        t = np.dot(point_vec, edge_vec) / edge_len_sq

        # Clamp t to [0, 1] to stay on the segment
        t = max(0, min(1, t))

        # Calculate closest point
        closest_point = edge_start + t * edge_vec

        return closest_point

    @staticmethod
    def _ray_cast_lateral_distance(
        centerline_pos_2d: np.ndarray,
        lateral_dir_2d: np.ndarray,
        edges_2d: List[tuple]
    ) -> float:
        """Fallback ray casting method for lateral distance calculation."""
        # Cast ray from centerline position in lateral direction
        # Check for intersections with all edges
        min_distance = float('inf')
        closest_intersection = None

        for edge_start, edge_end in edges_2d:
            intersection = WaypointProcessor._ray_edge_intersection_2d(
                centerline_pos_2d, lateral_dir_2d, edge_start, edge_end
            )

            if intersection is not None:
                # Calculate distance from centerline to intersection
                distance = np.linalg.norm(intersection - centerline_pos_2d)
                if distance < min_distance:
                    min_distance = distance
                    closest_intersection = intersection

        if closest_intersection is None:
            # If ray casting fails, try a simple closest edge approach
            simple_closest = WaypointProcessor._simple_closest_edge_distance(
                centerline_pos_2d, edges_2d, lateral_dir_2d
            )
            return simple_closest

        # For ray casting, we know the direction, so positive distance = right side
        return min_distance

    @staticmethod
    def _simple_closest_edge_distance(
        centerline_pos_2d: np.ndarray,
        edges_2d: List[tuple],
        lateral_dir_2d: np.ndarray
    ) -> float:
        """Simple closest edge point distance as final fallback."""
        min_distance = float('inf')
        closest_point = None

        for edge_start, edge_end in edges_2d:
            # Find closest point on this edge
            edge_point = WaypointProcessor._closest_point_on_edge_2d(
                centerline_pos_2d, edge_start, edge_end
            )

            if edge_point is not None:
                distance = np.linalg.norm(edge_point - centerline_pos_2d)
                if distance < min_distance:
                    min_distance = distance
                    closest_point = edge_point

        if closest_point is None:
            return None

        # Determine sign based on lateral direction (no forward/backward filtering)
        to_point = closest_point - centerline_pos_2d
        lateral_projection = np.dot(to_point, lateral_dir_2d)
        sign = 1 if lateral_projection >= 0 else -1

        return sign * min_distance

    @staticmethod
    def _calculate_local_tangent(
        position: np.ndarray,
        vertices: List[np.ndarray],
    ) -> np.ndarray:
        """Calculate the local tangent direction at a given position along the vertex path."""
        if not vertices or len(vertices) < 2:
            return None

        # Find the closest vertex and use the direction between adjacent vertices
        min_distance = float('inf')
        closest_idx = 0

        for i, vertex in enumerate(vertices):
            distance = np.linalg.norm(vertex - position)
            if distance < min_distance:
                min_distance = distance
                closest_idx = i

        # Get the direction from previous to next vertex
        if len(vertices) == 1:
            return np.array([0, 1, 0])  # Default forward

        if closest_idx == 0:
            # At start, use direction to next vertex
            next_idx = 1
            prev_idx = 0
        elif closest_idx == len(vertices) - 1:
            # At end, use direction from previous vertex
            next_idx = len(vertices) - 1
            prev_idx = len(vertices) - 2
        else:
            # In middle, use previous and next
            prev_idx = closest_idx - 1
            next_idx = closest_idx + 1

        # Calculate tangent as direction from prev to next
        tangent = vertices[next_idx] - vertices[prev_idx]
        if np.linalg.norm(tangent) > 0:
            tangent = tangent / np.linalg.norm(tangent)

        return tangent

    @staticmethod
    def _get_mesh_edges_2d(target_obj: bpy.types.Object) -> List[tuple]:
        """Get 2D edges from a mesh object for ray intersection testing."""
        if not target_obj or target_obj.type != "MESH":
            return []

        # Get the evaluated mesh (after applying modifiers)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        eval_obj = target_obj.evaluated_get(depsgraph)

        if not eval_obj or not eval_obj.data:
            return []

        # Create bmesh from evaluated mesh
        bm = bmesh.new()
        bm.from_mesh(eval_obj.data)

        # Ensure face indices are valid
        bm.edges.ensure_lookup_table()

        matrix = target_obj.matrix_world
        edges_2d = []

        # Extract 2D edges (X, Y coordinates only)
        for edge in bm.edges:
            # Get edge vertices in world coordinates
            v1_world = matrix @ edge.verts[0].co
            v2_world = matrix @ edge.verts[1].co

            # Convert to 2D (X, Y only)
            edge_start = np.array([v1_world[0], v1_world[1]])
            edge_end = np.array([v2_world[0], v2_world[1]])

            edges_2d.append((edge_start, edge_end))

        # Clean up bmesh
        bm.free()

        return edges_2d

    @staticmethod
    def _ray_edge_intersection_2d(
        ray_origin: np.ndarray,
        ray_direction: np.ndarray,
        edge_start: np.ndarray,
        edge_end: np.ndarray
    ) -> np.ndarray:
        """Calculate 2D ray-edge intersection point."""
        # Ray: ray_origin + t * ray_direction, t >= 0
        # Edge: edge_start to edge_end

        # Edge direction vector
        edge_dir = edge_end - edge_start

        # Denominator for intersection calculation
        denominator = ray_direction[0] * edge_dir[1] - ray_direction[1] * edge_dir[0]

        # If denominator is zero, ray is parallel to edge
        if abs(denominator) < 1e-10:
            return None

        # Calculate intersection parameters
        to_edge_start = edge_start - ray_origin
        t = (to_edge_start[0] * edge_dir[1] - to_edge_start[1] * edge_dir[0]) / denominator
        u = (to_edge_start[0] * ray_direction[1] - to_edge_start[1] * ray_direction[0]) / denominator

        # Check if intersection is valid:
        # t >= 0 (ray extends forward)
        # 0 <= u <= 1 (intersection is on edge segment)
        if t >= 0 and 0 <= u <= 1:
            # Calculate intersection point
            intersection = ray_origin + t * ray_direction
            return intersection

        return None

    @staticmethod
    def process_waypoint_line(
        mesh_obj: bpy.types.Object, branch_id: int
    ) -> List[aiw_parser.Waypoint]:
        """Process vertices of a mesh object into waypoint data."""
        if not mesh_obj or mesh_obj.type != "MESH":
            return []

        # Get the evaluated mesh (after applying modifiers)
        # Create a new bmesh instance from the evaluated mesh
        bm = bmesh.new()

        # Get the evaluated mesh (with modifiers applied)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        eval_obj = mesh_obj.evaluated_get(depsgraph)

        if not eval_obj or not eval_obj.data:
            return []

        # Create bmesh from evaluated mesh
        bm.from_mesh(eval_obj.data)

        # Ensure face indices are valid
        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()

        matrix = mesh_obj.matrix_world

        # Get vertices in world coordinates from evaluated mesh respecting vertex indices
        ordered_vertices = [
            np.array(matrix @ vert.co)
            for vert in sorted(bm.verts, key=lambda v: v.index)
        ]

        # Determine if this is a closed or open path
        is_closed_path = branch_id == 0  # Only racing line is closed

        # Clean up bmesh
        bm.free()

        waypoints = []

        for i, world_pos in enumerate(ordered_vertices):
            location = world_pos

            # Calculate forward direction from this vertex to the next
            if is_closed_path:
                next_i = (i + 1) % len(ordered_vertices)
            else:
                next_i = min(i + 1, len(ordered_vertices) - 1)

            next_world_pos = ordered_vertices[next_i]

            # Calculate forward direction
            forward_vec = next_world_pos - location
            if np.linalg.norm(forward_vec) > 0:
                forward_vec = forward_vec / np.linalg.norm(forward_vec)
            else:
                forward_vec = np.array([0, 1, 0])  # Default forward

            # Calculate right direction (perpendicular to forward)
            up_vec = np.array([0, 0, 1])  # Blender Z-up
            right_vec = np.cross(forward_vec, up_vec)

            if np.linalg.norm(right_vec) > 0:
                right_vec = right_vec / np.linalg.norm(right_vec)
            else:
                right_vec = np.array([1, 0, 0])  # Default right

            # Convert to Madness coordinate system
            madness_pos = convert_coords_to_madness(location)
            madness_forward = convert_coords_to_madness(forward_vec)
            madness_right = convert_coords_to_madness(right_vec)

            # Calculate perpendicular (right direction)
            perpendicular = calculate_perpendicular(madness_forward, madness_right)

            # Get waypoint attributes (from original mesh object, not individual vertices)
            width = WaypointProcessor.get_waypoint_tuple_attribute(
                mesh_obj, "width", (6.0, 6.0)
            )
            dwidth = WaypointProcessor.get_waypoint_tuple_attribute(
                mesh_obj, "dwidth", (10.0, 10.0)
            )
            path = WaypointProcessor.get_waypoint_tuple_attribute(
                mesh_obj, "path", (0.0, 0.0)
            )
            galpha = WaypointProcessor.get_waypoint_attribute(mesh_obj, "galpha", 0.0)

            # Score (sector, lap distance) - calculate lap distance
            sector = WaypointProcessor.get_waypoint_attribute(mesh_obj, "sector", 0)
            lap_distance = WaypointProcessor.get_waypoint_attribute(
                mesh_obj, "lap_distance", 0.0
            )
            score = (int(sector), lap_distance)

            groove_lat = WaypointProcessor.get_waypoint_attribute(
                mesh_obj, "groove_lat", 0.0
            )

            # Event (corner speed mult, special event, special event data)
            event_speed = WaypointProcessor.get_waypoint_attribute(
                mesh_obj, "event_speed", 1.0
            )
            event_type = WaypointProcessor.get_waypoint_attribute(
                mesh_obj, "event_type", 0
            )
            event_data = WaypointProcessor.get_waypoint_attribute(
                mesh_obj, "event_data", 0.0
            )
            event = (event_speed, int(event_type), event_data)

            bitfields = int(
                WaypointProcessor.get_waypoint_attribute(mesh_obj, "bitfields", 0)
            )
            corner_type = int(
                WaypointProcessor.get_waypoint_attribute(mesh_obj, "corner_type", 0)
            )
            corner_state = int(
                WaypointProcessor.get_waypoint_attribute(mesh_obj, "corner_state", 0)
            )

            # Calculate waypoint pointers based on whether it's a closed or open path
            if is_closed_path:
                # Closed path (racing line): wrap around
                prev_wp = (i - 1) if i > 0 else len(ordered_vertices) - 1
                next_wp = (i + 1) if i < len(ordered_vertices) - 1 else 0
            else:
                # Open path (pit line): don't wrap around
                prev_wp = max(0, i - 1)
                next_wp = min(len(ordered_vertices) - 1, i + 1)

            wp_ptrs = (
                prev_wp,
                next_wp,
                -1,
                -1,
            )  # alt_next and branch_merge to be calculated later

            # Create waypoint
            waypoint = aiw_parser.Waypoint(
                index=i,
                position=aiw_parser.Position(
                    madness_pos[0], madness_pos[1], madness_pos[2]
                ),
                perpendicular=aiw_parser.Orientation(
                    perpendicular[0], perpendicular[1], perpendicular[2]
                ),
                width=width,
                dwidth=dwidth,
                path=path,
                galpha=galpha,
                score=score,
                groove_lat=groove_lat,
                event=event,
                branch_id=branch_id,
                bitfields=bitfields,
                corner_type=corner_type,
                corner_state=corner_state,
                wp_ptrs=wp_ptrs,
            )
            waypoints.append(waypoint)

        return waypoints
