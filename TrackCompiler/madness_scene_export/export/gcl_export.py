import bpy  # type: ignore
import math
import struct
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

FLAG_MAP: Dict[str, int] = {
    "SMS_GCL_ROAD": 0x1,  # Racing surface
    "SMS_GCL_PIT": 0x2,  # Pit area
    "SMS_GCL_EXIT": 0x4,  # Pit exit
    "SMS_GCL_ENTRY": 0xA,  # Pit entry
}

PROP_100M = 10.0
PROP_10M = 1.0
PROP_1M = 0.1

MAX_CELL_REFS = 50
SUBDIVISION_THRESHOLD = 10
EPS = 1e-8

Vec3 = Tuple[float, float, float]
Tri = Tuple[Vec3, Vec3, Vec3, int]
CellCacheEntry = Tuple[float, float, List[int]]


def _f32(value: float) -> float:
    """Round a Python float to IEEE-754 float32."""
    return struct.unpack("<f", struct.pack("<f", float(value)))[0]


# Parent cells with children use the raw uint32 value 10 in both float fields.
SUBDIVISION_MARKER = 10
SUBDIVISION_MARKER_F32 = struct.unpack("<f", struct.pack("<I", SUBDIVISION_MARKER))[0]


def _convert_coordinate(co) -> Vec3:
    """Convert Blender world coordinates to AMS2 coordinates."""
    # Quantize to float32 early so overlap/binning uses exactly what is written.
    return _f32(co.x), _f32(co.z), _f32(co.y)


def collect_scene_triangles(
    scene: bpy.types.Scene, depsgraph: bpy.types.Depsgraph
) -> Tuple[List[Tri], float, List[str], List[str], List[str]]:
    """Collect triangles from named objects in the scene."""
    tris: List[Tri] = []
    missing_objects: List[str] = []
    non_mesh_objects: List[str] = []
    empty_objects: List[str] = []
    min_y = float("inf")

    for name, flag in FLAG_MAP.items():
        obj = scene.objects.get(name)
        if obj is None:
            missing_objects.append(name)
            continue

        if obj.type != "MESH":
            non_mesh_objects.append(name)
            continue

        obj_eval = obj.evaluated_get(depsgraph)
        mesh = obj_eval.to_mesh()
        try:
            mesh.calc_loop_triangles()
            if not mesh.loop_triangles:
                empty_objects.append(name)
                continue

            matrix_world = obj_eval.matrix_world
            for loop_tri in mesh.loop_triangles:
                verts: List[Vec3] = []
                for v_idx in loop_tri.vertices:
                    co = matrix_world @ mesh.vertices[v_idx].co
                    converted = _convert_coordinate(co)
                    verts.append(converted)
                    min_y = min(min_y, converted[1])
                # GCL expects clockwise winding order
                tris.append((verts[0], verts[2], verts[1], flag))
        finally:
            obj_eval.to_mesh_clear()

    return tris, min_y, missing_objects, non_mesh_objects, empty_objects


def point_in_rect(px: float, pz: float, rx0: float, rz0: float, rx1: float, rz1: float) -> bool:
    return (rx0 - EPS) <= px <= (rx1 + EPS) and (rz0 - EPS) <= pz <= (rz1 + EPS)


def point_in_triangle(
    px: float,
    pz: float,
    a: Tuple[float, float],
    b: Tuple[float, float],
    c: Tuple[float, float],
) -> bool:
    # Barycentric check in XZ plane
    v0x, v0z = c[0] - a[0], c[1] - a[1]
    v1x, v1z = b[0] - a[0], b[1] - a[1]
    v2x, v2z = px - a[0], pz - a[1]

    dot00 = v0x * v0x + v0z * v0z
    dot01 = v0x * v1x + v0z * v1z
    dot02 = v0x * v2x + v0z * v2z
    dot11 = v1x * v1x + v1z * v1z
    dot12 = v1x * v2x + v1z * v2z

    denom = dot00 * dot11 - dot01 * dot01
    if abs(denom) < EPS:
        return False
    inv = 1.0 / denom
    u = (dot11 * dot02 - dot01 * dot12) * inv
    v = (dot00 * dot12 - dot01 * dot02) * inv
    return u >= -EPS and v >= -EPS and (u + v) <= 1.0 + EPS


def orient(ax: float, az: float, bx: float, bz: float, cx: float, cz: float) -> float:
    return (bx - ax) * (cz - az) - (bz - az) * (cx - ax)


def on_segment(ax: float, az: float, bx: float, bz: float, cx: float, cz: float) -> bool:
    return (
        (min(ax, bx) - EPS <= cx <= max(ax, bx) + EPS)
        and (min(az, bz) - EPS <= cz <= max(az, bz) + EPS)
    )


def segments_intersect(
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    q1: Tuple[float, float],
    q2: Tuple[float, float],
) -> bool:
    o1 = orient(p1[0], p1[1], p2[0], p2[1], q1[0], q1[1])
    o2 = orient(p1[0], p1[1], p2[0], p2[1], q2[0], q2[1])
    o3 = orient(q1[0], q1[1], q2[0], q2[1], p1[0], p1[1])
    o4 = orient(q1[0], q1[1], q2[0], q2[1], p2[0], p2[1])

    if (o1 * o2 < -EPS) and (o3 * o4 < -EPS):
        return True

    if abs(o1) <= EPS and on_segment(p1[0], p1[1], p2[0], p2[1], q1[0], q1[1]):
        return True
    if abs(o2) <= EPS and on_segment(p1[0], p1[1], p2[0], p2[1], q2[0], q2[1]):
        return True
    if abs(o3) <= EPS and on_segment(q1[0], q1[1], q2[0], q2[1], p1[0], p1[1]):
        return True
    if abs(o4) <= EPS and on_segment(q1[0], q1[1], q2[0], q2[1], p2[0], p2[1]):
        return True

    return False


def triangle_intersects_rect(
    v0: Tuple[float, float],
    v1: Tuple[float, float],
    v2: Tuple[float, float],
    rx0: float,
    rz0: float,
    rx1: float,
    rz1: float,
) -> bool:
    # Fast AABB reject
    tminx = min(v0[0], v1[0], v2[0])
    tmaxx = max(v0[0], v1[0], v2[0])
    tminz = min(v0[1], v1[1], v2[1])
    tmaxz = max(v0[1], v1[1], v2[1])
    if tmaxx <= rx0 or rx1 <= tminx or tmaxz <= rz0 or rz1 <= tminz:
        return False

    # Any triangle vertex inside rect?
    if point_in_rect(v0[0], v0[1], rx0, rz0, rx1, rz1):
        return True
    if point_in_rect(v1[0], v1[1], rx0, rz0, rx1, rz1):
        return True
    if point_in_rect(v2[0], v2[1], rx0, rz0, rx1, rz1):
        return True

    # Any rect corner inside triangle?
    if point_in_triangle(rx0, rz0, v0, v1, v2):
        return True
    if point_in_triangle(rx1, rz0, v0, v1, v2):
        return True
    if point_in_triangle(rx1, rz1, v0, v1, v2):
        return True
    if point_in_triangle(rx0, rz1, v0, v1, v2):
        return True

    # Any edge intersects?
    tri_edges = [(v0, v1), (v1, v2), (v2, v0)]
    r00 = (rx0, rz0)
    r10 = (rx1, rz0)
    r11 = (rx1, rz1)
    r01 = (rx0, rz1)
    rect_edges = [(r00, r10), (r10, r11), (r11, r01), (r01, r00)]
    for e1 in tri_edges:
        for e2 in rect_edges:
            if segments_intersect(e1[0], e1[1], e2[0], e2[1]):
                return True

    return False


def aabb_of_triangle(tri: Tri) -> Tuple[float, float, float, float]:
    (x0, _, z0), (x1, _, z1), (x2, _, z2), _ = tri
    min_x = min(x0, x1, x2)
    max_x = max(x0, x1, x2)
    min_z = min(z0, z1, z2)
    max_z = max(z0, z1, z2)
    return min_x, min_z, max_x, max_z


def align_grid(min_v: float, max_v: float, cell: float) -> Tuple[float, float, int]:
    a = math.floor(min_v / cell) * cell
    b = math.ceil(max_v / cell) * cell
    n = max(1, int(round((b - a) / cell)))
    if a + n * cell < b - 1e-6:
        n += 1
        b = a + n * cell
    return a, b, n


def floor_to_100(value: float) -> float:
    """Round a value down to the nearest 100."""
    return math.floor(value / 100.0) * 100.0


def rects_overlap(ax0, az0, ax1, az1, bx0, bz0, bx1, bz1) -> bool:
    return not (ax1 <= bx0 or bx1 <= ax0 or az1 <= bz0 or bz1 <= az0)


def clamp_refs(refs: List[int]) -> List[int]:
    if len(refs) <= MAX_CELL_REFS:
        return refs
    return sorted(refs)[:MAX_CELL_REFS]


def build_spatial_bins(
    tris: List[Tri],
    grid_min_x: float,
    grid_min_z: float,
    grid_100_x: int,
    grid_100_z: int,
) -> Dict[Tuple[int, int], List[int]]:
    bins: Dict[Tuple[int, int], List[int]] = defaultdict(list)
    for ti, t in enumerate(tris):
        tminx, tminz, tmaxx, tmaxz = aabb_of_triangle(t)
        ix0 = max(0, int((math.floor((tminx - grid_min_x) / 100.0))))
        iz0 = max(0, int((math.floor((tminz - grid_min_z) / 100.0))))
        ix1 = min(grid_100_x - 1, int((math.floor((tmaxx - grid_min_x) / 100.0))))
        iz1 = min(grid_100_z - 1, int((math.floor((tmaxz - grid_min_z) / 100.0))))
        for ix in range(ix0, ix1 + 1):
            for iz in range(iz0, iz1 + 1):
                bins[(ix, iz)].append(ti)
    return bins


def write_header(
    f,
    version: int,
    tri_count: int,
    hundred: float,
    origin_x: float,
    origin_y: float,
    origin_z: float,
    grid_100_x: int,
    grid_100_z: int,
):
    # Canonical header layout:
    # values[2]=hundred, values[3]=origin_x, values[4]=origin_y, values[5]=origin_z
    # values[6]=grid_cells_x, values[7]=grid_cells_z
    header = struct.pack(
        "<2I4f2I",
        version,
        tri_count,
        float(hundred),
        float(origin_x),
        float(origin_y),
        float(origin_z),
        int(grid_100_x),
        int(grid_100_z),
    )
    f.write(header)


def write_triangles(f, tris: List[Tri]):
    for (v0, v1, v2, flag) in tris:
        data = struct.pack(
            "<9fI",
            v0[0],
            v0[1],
            v0[2],
            v1[0],
            v1[1],
            v1[2],
            v2[0],
            v2[1],
            v2[2],
            int(flag),
        )
        f.write(data)


def write_cell(
    f,
    center_x: float,
    center_z: float,
    elevation: float,
    prop: float,
    refs: Optional[List[int]] = None,
    parameter: float = 0.0,
    float_1: float = 0.0,
):
    refs = clamp_refs(refs or [])
    f.write(struct.pack("<I", len(refs)))
    f.write(
        struct.pack(
            "<6f",
            float(parameter),
            float(float_1),
            float(center_x),
            float(elevation),
            float(center_z),
            float(prop),
        )
    )
    if refs:
        f.write(struct.pack(f"<{len(refs)}I", *refs))


def triangle_overlaps_cell(
    tri: Tri, cx0: float, cz0: float, cx1: float, cz1: float
) -> bool:
    (x0, _, z0), (x1, _, z1), (x2, _, z2), _ = tri
    return triangle_intersects_rect((x0, z0), (x1, z1), (x2, z2), cx0, cz0, cx1, cz1)


def build_and_write_dectree(
    f,
    tris: List[Tri],
    grid_min_x: float,
    grid_min_z: float,
    grid_100_x: int,
    grid_100_z: int,
    elevation: float = 0.0,
) -> Dict[str, int]:
    bins_100 = build_spatial_bins(tris, grid_min_x, grid_min_z, grid_100_x, grid_100_z)
    cell_counts = {"100m": 0, "10m": 0, "1m": 0}

    def write_parent_cell_with_marker(
        has_children: bool, x: float, z: float, prop: float
    ) -> None:
        if has_children:
            write_cell(
                f,
                x,
                z,
                elevation,
                prop,
                refs=[],
                parameter=SUBDIVISION_MARKER_F32,
                float_1=SUBDIVISION_MARKER_F32,
            )
        else:
            write_cell(f, x, z, elevation, prop, refs=[])

    for ix100 in range(0, grid_100_x):
        for iz100 in range(0, grid_100_z):
            cell_min_x = grid_min_x + ix100 * 100.0
            cell_min_z = grid_min_z + iz100 * 100.0

            tri_candidates = bins_100.get((ix100, iz100), [])
            if not tri_candidates:
                write_parent_cell_with_marker(False, cell_min_x, cell_min_z, PROP_100M)
                cell_counts["100m"] += 1
                continue

            has_any_10m_overlap = False
            c10_cache: List[CellCacheEntry] = []
            for ix10 in range(0, 10):
                for iz10 in range(0, 10):
                    c10_min_x = cell_min_x + ix10 * 10.0
                    c10_min_z = cell_min_z + iz10 * 10.0
                    c10_max_x = c10_min_x + 10.0
                    c10_max_z = c10_min_z + 10.0

                    c10_tris: List[int] = []
                    for ti in tri_candidates:
                        if triangle_overlaps_cell(
                            tris[ti], c10_min_x, c10_min_z, c10_max_x, c10_max_z
                        ):
                            c10_tris.append(ti)
                    if c10_tris:
                        has_any_10m_overlap = True
                    c10_cache.append((c10_min_x, c10_min_z, c10_tris))

            # 100m parent cells with children have marker values in parameter/float_1.
            write_parent_cell_with_marker(has_any_10m_overlap, cell_min_x, cell_min_z, PROP_100M)
            cell_counts["100m"] += 1

            if not has_any_10m_overlap:
                continue

            for c10_min_x, c10_min_z, c10_tris in c10_cache:
                if not c10_tris:
                    write_cell(f, c10_min_x, c10_min_z, elevation, PROP_10M, refs=[])
                    cell_counts["10m"] += 1
                    continue

                if len(c10_tris) <= SUBDIVISION_THRESHOLD:
                    write_cell(f, c10_min_x, c10_min_z, elevation, PROP_10M, refs=c10_tris)
                    cell_counts["10m"] += 1
                    continue

                # 10m parent cells with 1m children carry the same marker pattern.
                write_parent_cell_with_marker(True, c10_min_x, c10_min_z, PROP_10M)
                cell_counts["10m"] += 1

                for ix1 in range(0, 10):
                    for iz1 in range(0, 10):
                        c1_min_x = c10_min_x + ix1 * 1.0
                        c1_min_z = c10_min_z + iz1 * 1.0
                        c1_max_x = c1_min_x + 1.0
                        c1_max_z = c1_min_z + 1.0

                        refs: List[int] = []
                        for ti in c10_tris:
                            if triangle_overlaps_cell(
                                tris[ti],
                                c1_min_x,
                                c1_min_z,
                                c1_max_x,
                                c1_max_z,
                            ):
                                refs.append(ti)

                        write_cell(f, c1_min_x, c1_min_z, elevation, PROP_1M, refs=refs)
                        cell_counts["1m"] += 1

    return cell_counts


def export_gcl(
    filepath: str,
    context: bpy.types.Context,
    version: int = 0x10000001,
    elevation_override: Optional[float] = None,
) -> Dict[str, object]:
    depsgraph = context.evaluated_depsgraph_get()
    tris, min_y, missing, non_mesh, empty = collect_scene_triangles(
        context.scene, depsgraph
    )

    if not tris:
        message = "No triangles found in SMS_GCL_ROAD/_PIT/_ENTRY/_EXIT objects."
        if missing:
            message += f" Missing objects: {', '.join(missing)}."
        raise ValueError(message)

    base_elevation = elevation_override if elevation_override is not None else min_y
    elevation = floor_to_100(base_elevation)

    min_x = min(min(t[0][0], t[1][0], t[2][0]) for t in tris)
    max_x = max(max(t[0][0], t[1][0], t[2][0]) for t in tris)
    min_z = min(min(t[0][2], t[1][2], t[2][2]) for t in tris)
    max_z = max(max(t[0][2], t[1][2], t[2][2]) for t in tris)

    grid_min_x, grid_max_x, grid_100_x = align_grid(min_x, max_x, 100.0)
    grid_min_z, grid_max_z, grid_100_z = align_grid(min_z, max_z, 100.0)

    Path(filepath).parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, "wb") as f:
        write_header(
            f,
            version=version,
            tri_count=len(tris),
            hundred=100.0,
            origin_x=grid_min_x,
            origin_y=elevation,
            origin_z=grid_min_z,
            grid_100_x=grid_100_x,
            grid_100_z=grid_100_z,
        )
        write_triangles(f, tris)
        cell_counts = build_and_write_dectree(
            f,
            tris=tris,
            grid_min_x=grid_min_x,
            grid_min_z=grid_min_z,
            grid_100_x=grid_100_x,
            grid_100_z=grid_100_z,
            elevation=base_elevation,
        )

    print(f"GCL export: wrote {len(tris)} triangles to {filepath}")
    print(
        f"GCL bounds X[{grid_min_x},{grid_max_x}] Z[{grid_min_z},{grid_max_z}] "
        f"grid {grid_100_x} x {grid_100_z}"
    )
    print(
        f"GCL elevation {base_elevation:.3f}m | cells 100m={cell_counts['100m']} 10m={cell_counts['10m']} 1m={cell_counts['1m']}"
    )
    if missing:
        print(f"GCL export warning: missing objects: {', '.join(missing)}")
    if non_mesh:
        print(f"GCL export warning: non-mesh objects skipped: {', '.join(non_mesh)}")
    if empty:
        print(f"GCL export warning: objects with no geometry: {', '.join(empty)}")

    return {
        "triangles": len(tris),
        "grid": (grid_100_x, grid_100_z),
        "header_grid": (grid_100_x, grid_100_z),
        "bounds": {
            "min_x": grid_min_x,
            "max_x": grid_max_x,
            "min_z": grid_min_z,
            "max_z": grid_max_z,
        },
        "elevation": base_elevation,
        "cell_counts": cell_counts,
        "missing_objects": missing,
        "non_mesh_objects": non_mesh,
        "empty_objects": empty,
        "version": version,
    }


__all__ = ["export_gcl", "collect_scene_triangles"]

