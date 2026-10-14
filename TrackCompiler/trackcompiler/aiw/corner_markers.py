"""Label centerline corner type and state from placed empties at export time."""

import numpy as np

# Name prefixes
# Blender suffixes such as ".001" are ignored by startswith
STATE_PREFIXES = (
    ("SMS_AIW_CS_APEXSTART", "apexstart"),
    ("SMS_AIW_CS_APEXEND", "apexend"),
    ("SMS_AIW_CS_ENTRY", "entry"),
    ("SMS_AIW_CS_EXIT", "exit"),
)
TYPE_PREFIXES = (
    ("SMS_AIW_CT_LOOSECHIC", 5),
    ("SMS_AIW_CT_TIGHTCHIC", 6),
    ("SMS_AIW_CT_LEFT", 3),
    ("SMS_AIW_CT_RIGHT", 4),
)
FAR_MARKER_DISTANCE = 25.0


def classify_corner_marker(name):
    """Return ('state', role) or ('type', corner_type), or None."""
    if name.startswith("SMS_AIW_CS_"):
        for prefix, role in STATE_PREFIXES:
            if name.startswith(prefix):
                return ("state", role)
        raise ValueError(
            f"{name} is not a corner state marker. "
            "Use SMS_AIW_CS_ENTRY, APEXSTART, APEXEND, or EXIT"
        )
    if name.startswith("SMS_AIW_CT_"):
        for prefix, corner_type in TYPE_PREFIXES:
            if name.startswith(prefix):
                return ("type", corner_type)
        raise ValueError(
            f"{name} is not a corner type marker. "
            "Use SMS_AIW_CT_LEFT, RIGHT, LOOSECHIC, or TIGHTCHIC"
        )
    return None


def apply_corner_markers(objects, vertices, waypoints, warnings):
    """
    Override centerline corner fields from SMS_AIW_CS_* and SMS_AIW_CT_* empties.
    When no such empties exist, vertex attributes already copied onto the waypoints are left unchanged.
    """
    markers = []
    for obj in objects:
        if obj.type != "EMPTY":
            continue
        kind = classify_corner_marker(obj.name)
        if kind is None:
            continue
        markers.append((obj.name, np.array(obj.matrix_world.translation, dtype=float), kind))
    if not markers:
        return
    if len(vertices) < 2:
        raise ValueError("Corner markers need an SMS_AIW_CENTERLINE mesh to project onto")

    labels, notes = corner_labels(vertices, markers)
    warnings.extend(notes)
    if len(labels) != len(waypoints):
        raise ValueError(
            f"Corner marker labeling produced {len(labels)} waypoints "
            f"for a centerline of {len(waypoints)}"
        )
    for waypoint, (corner_type, corner_state) in zip(waypoints, labels):
        waypoint.corner_type = corner_type
        waypoint.corner_state = corner_state


def corner_labels(vertices, markers):
    """
    Build per-vertex (corner_type, corner_state) from projected markers.
    markers: (name, world xyz, ('state', role) or ('type', type id))
    Spans run along the closed centerline. 
    A waypoint on a boundary belongs to the phase that starts there.
    EXIT is the first waypoint after the corner.
    """
    if len(vertices) < 2:
        raise ValueError("Centerline needs at least two vertices to place corner markers")

    arcs, total = _path_arcs(vertices)
    if total <= 0.0:
        raise ValueError("Centerline length is zero; corner markers cannot be placed")

    projected = []
    notes = []
    for name, position, kind in markers:
        arc, distance = _project_arc(position, vertices, arcs)
        projected.append((name, arc, kind))
        if distance > FAR_MARKER_DISTANCE:
            notes.append(
                f"{name} is {distance:.1f}m from the centerline; "
                "it was still projected to the nearest point"
            )

    entries = [m for m in projected if m[2] == ("state", "entry")]
    exits = [m for m in projected if m[2] == ("state", "exit")]
    apex_starts = [m for m in projected if m[2] == ("state", "apexstart")]
    apex_ends = [m for m in projected if m[2] == ("state", "apexend")]
    types = [m for m in projected if m[2][0] == "type"]

    if not entries and not exits and not apex_starts and not apex_ends:
        raise ValueError("Corner type empties were found without SMS_AIW_CS_ENTRY / APEXSTART / APEXEND / EXIT markers")

    used_exits = set()
    spans = []
    for entry in sorted(entries, key=lambda m: m[1]):
        candidates = [
            exit_marker
            for exit_marker in exits
            if exit_marker[0] not in used_exits
            and _forward(entry[1], exit_marker[1], total) > 1e-4
        ]
        if not candidates:
            raise ValueError(f"{entry[0]} has no SMS_AIW_CS_EXIT ahead of it on the centerline")
        exit_marker = min(candidates, key=lambda m: _forward(entry[1], m[1], total))
        used_exits.add(exit_marker[0])
        spans.append((entry, exit_marker))

    for exit_marker in exits:
        if exit_marker[0] not in used_exits:
            raise ValueError(f"{exit_marker[0]} is not paired with an SMS_AIW_CS_ENTRY")

    corners = []
    for entry, exit_marker in spans:
        entry_arc, exit_arc = entry[1], exit_marker[1]
        if any(_contains(other[1], entry_arc, exit_arc, total) for other, _ in spans if other is not entry):
            raise ValueError(f"Corner span {entry[0]} to {exit_marker[0]} overlaps another ENTRY")
        apex_start = _one_inside(apex_starts, entry_arc, exit_arc, total, entry[0], "SMS_AIW_CS_APEXSTART")
        apex_end = _one_inside(apex_ends, entry_arc, exit_arc, total, entry[0], "SMS_AIW_CS_APEXEND")
        if _forward(entry_arc, apex_start[1], total) >= _forward(entry_arc, apex_end[1], total):
            raise ValueError(f"{apex_start[0]} must lie between {entry[0]} and {apex_end[0]} along the centerline")
        type_marker = _one_inside(types, entry_arc, exit_arc, total, entry[0], "corner type empty")
        corners.append((entry_arc, apex_start[1], apex_end[1], exit_arc, type_marker[2][1]))

    for marker in apex_starts + apex_ends + types:
        if not any(_contains(marker[1], c[0], c[3], total) for c in corners):
            raise ValueError(f"{marker[0]} does not lie between an ENTRY and EXIT")

    labels = []
    for arc in arcs:
        corner_type = 0
        corner_state = 0
        for entry_arc, apex_start, apex_end, exit_arc, type_id in corners:
            if not _contains(arc, entry_arc, exit_arc, total):
                continue
            corner_type = type_id
            if _contains(arc, entry_arc, apex_start, total):
                corner_state = 1
            elif _contains(arc, apex_start, apex_end, total):
                corner_state = 2
            else:
                corner_state = 3
            break
        labels.append((corner_type, corner_state))
    return labels, notes


def _one_inside(markers, start, end, total, entry_name, label):
    inside = [marker for marker in markers if _contains(marker[1], start, end, total)]
    if len(inside) != 1:
        raise ValueError(f"Corner at {entry_name} needs exactly one {label} between ENTRY and EXIT (found {len(inside)})")
    return inside[0]


def _path_arcs(vertices):
    arcs = [0.0]
    for index in range(1, len(vertices)):
        arcs.append(arcs[-1] + float(np.linalg.norm(vertices[index] - vertices[index - 1])))
    total = arcs[-1] + float(np.linalg.norm(vertices[0] - vertices[-1]))
    return arcs, total


def _project_arc(point, vertices, arcs):
    best_distance = float("inf")
    best_arc = 0.0
    count = len(vertices)
    for index in range(count):
        start = vertices[index]
        end = vertices[(index + 1) % count]
        edge = end - start
        length = float(np.linalg.norm(edge))
        if length < 1e-9:
            closest = start
            travelled = 0.0
        else:
            factor = float(np.dot(point - start, edge) / (length * length))
            factor = min(1.0, max(0.0, factor))
            closest = start + edge * factor
            travelled = factor * length
        distance = float(np.linalg.norm(point - closest))
        if distance < best_distance:
            best_distance = distance
            best_arc = arcs[index] + travelled
    return best_arc, best_distance


def _forward(start, end, total):
    return (end - start) % total


def _contains(position, start, end, total):
    """True when position is on the travel arc [start, end)."""
    span = _forward(start, end, total)
    if span <= 1e-4:
        return False
    return _forward(start, position, total) < span
