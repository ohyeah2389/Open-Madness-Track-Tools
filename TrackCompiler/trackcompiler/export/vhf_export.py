"""Writer for VHF instance hierarchies.

A VHF is a mini-scenegraph. Dynamic objects use a single LOD around one mesh.
Vehicle files use a root hierarchy of matrices, each placing an object, a LOD
group, or a damage pair. LOD groups reuse the SMS_LOD_ controls. A mesh named
``<part>_dmg`` is the damaged twin of ``<part>`` and is wrapped in a DAMAGE node.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

EXPORTER_VERSION = "Phx Staging Tools v1.280"

# Stock dynamic VHFs draw their only LOD out to this distance.
LOD_DISTANCE = 1000

DAMAGE_SUFFIX = "_dmg"


def _fmt(value) -> str:
    return f"{float(value):.6f}"


def _vec3(values) -> str:
    return " ".join(_fmt(v) for v in values)


def _sphere(parent, center, radius):
    ET.SubElement(
        parent,
        "SPHERE",
        Centre=f"{_vec3(center)} 1.000000",
        Radius=_fmt(radius),
    )


def _quat_rotate(quat_xyzw, point):
    qx, qy, qz, qw = quat_xyzw
    x, y, z = point
    tx = 2.0 * (qy * z - qz * y)
    ty = 2.0 * (qz * x - qx * z)
    tz = 2.0 * (qx * y - qy * x)
    return (
        x + qw * tx + (qy * tz - qz * ty),
        y + qw * ty + (qz * tx - qx * tz),
        z + qw * tz + (qx * ty - qy * tx),
    )


def _transform_center(offset, quat_xyzw, center):
    rotated = _quat_rotate(quat_xyzw, center)
    return (rotated[0] + offset[0], rotated[1] + offset[1], rotated[2] + offset[2])


def _union_spheres(spheres):
    """Bounding sphere around (center, radius) pairs."""
    if not spheres:
        return (0.0, 0.0, 0.0), 0.0
    mins = [min(c[i] - r for c, r in spheres) for i in range(3)]
    maxs = [max(c[i] + r for c, r in spheres) for i in range(3)]
    center = tuple((mins[i] + maxs[i]) * 0.5 for i in range(3))
    radius = 0.0
    for sphere_center, sphere_radius in spheres:
        dist = sum((sphere_center[i] - center[i]) ** 2 for i in range(3)) ** 0.5
        radius = max(radius, dist + sphere_radius)
    return center, radius


def _object_node(parent, spec, matrix_number):
    attrib = {
        "type": "OBJECT",
        "Name": spec["name"],
        "MatrixNumber": str(matrix_number),
        "instances": "1",
        "userflags": str(spec["userflags"]),
    }
    if spec.get("modifiable"):
        attrib["Modifiable"] = "1"
    node = ET.SubElement(parent, "NODE", attrib)
    ET.SubElement(node, "RESOURCE", Filename=spec["resource"])
    _sphere(node, spec["center"], spec["radius"])
    return node


def _damage_node(parent, spec, matrix_number):
    node = ET.SubElement(
        parent,
        "NODE",
        type="DAMAGE",
        Name=spec["name"],
        MatrixNumber=str(matrix_number),
        subobjects=str(len(spec["objects"])),
    )
    center, radius = _union_spheres([(obj["center"], obj["radius"]) for obj in spec["objects"]])
    _sphere(node, center, radius)
    for obj in spec["objects"]:
        _object_node(node, obj, matrix_number)
    return center, radius


def _lod_node(parent, spec, matrix_number):
    node = ET.SubElement(
        parent,
        "NODE",
        type="LOD",
        Name=spec["name"],
        MatrixNumber=str(matrix_number),
        subobjects=str(len(spec["levels"])),
    )
    child_spheres = []
    for level in spec["levels"]:
        if level["kind"] == "damage":
            center, radius = _damage_node(node, level, matrix_number)
        else:
            _object_node(node, level, matrix_number)
            center, radius = level["center"], level["radius"]
        child_spheres.append((center, radius))
    center, radius = _union_spheres(child_spheres)
    # Stock LOD nodes put the sphere before their children.
    node.insert(0, node.makeelement("SPHERE", {
        "Centre": f"{_vec3(center)} 1.000000",
        "Radius": _fmt(radius),
    }))
    distances = " ".join(f"{float(level['distance']):g}" for level in spec["levels"])
    ET.SubElement(node, "CONTROL", Distances=f"{distances} ")
    return center, radius


def _part_sphere(part):
    node = part["node"]
    if node["kind"] == "object":
        return node["center"], node["radius"]
    if node["kind"] == "damage":
        return _union_spheres([(obj["center"], obj["radius"]) for obj in node["objects"]])
    spheres = []
    for level in node["levels"]:
        if level["kind"] == "damage":
            spheres.append(_union_spheres([(obj["center"], obj["radius"]) for obj in level["objects"]]))
        else:
            spheres.append((level["center"], level["radius"]))
    return _union_spheres(spheres)


def build_vehicle_vhf(name: str, parts: list) -> ET.Element:
    """Build a vehicle VHF. Each part is one matrix plus an object, damage pair, or LOD."""
    root = ET.Element("CAR", Name=name, ExporterVersion=EXPORTER_VERSION)
    hierarchy = ET.SubElement(
        root,
        "NODE",
        type="HIERARCHY",
        Name="Root",
        MatrixNumber="0",
        matrices=str(len(parts) + 1),
        subobjects=str(len(parts)),
    )

    world_spheres = []
    for index, part in enumerate(parts, start=1):
        offset = part["offset"]
        quat = part["orientation"]
        local_center, local_radius = _part_sphere(part)
        world_center = _transform_center(offset, quat, local_center)
        world_spheres.append((world_center, local_radius))

    center, radius = _union_spheres(world_spheres)
    _sphere(hierarchy, center, radius)
    ET.SubElement(
        hierarchy,
        "MATRIX",
        id="0",
        Offset="0.000000 0.000000 0.000000",
        Orientation="0.000000 0.000000 0.000000 1.000000",
        Scale="1.000000",
    )
    for index, part in enumerate(parts, start=1):
        qx, qy, qz, qw = part["orientation"]
        ET.SubElement(
            hierarchy,
            "MATRIX",
            id=str(index),
            Offset=_vec3(part["offset"]),
            Orientation=f"{_fmt(qx)} {_fmt(qy)} {_fmt(qz)} {_fmt(qw)}",
            Scale="1.000000",
            parent="0",
        )
        node = part["node"]
        if node["kind"] == "lod":
            _lod_node(hierarchy, node, index)
        elif node["kind"] == "damage":
            _damage_node(hierarchy, node, index)
        else:
            _object_node(hierarchy, node, index)
    return root


def write_vehicle_vhf(path: Path, name: str, parts: list) -> None:
    """Write a vehicle VHF hierarchy."""
    root = build_vehicle_vhf(name, parts)
    ET.indent(root, space="    ")
    body = ET.tostring(root, encoding="unicode")
    Path(path).write_text(f'<?xml version="1.0" encoding="utf-8"?>\n{body}\n', encoding="utf-8")


def build_vhf(name: str, resource: str, sphere_center, sphere_radius: float, userflags: int) -> ET.Element:
    """Build a single-LOD VHF hierarchy around one mesh resource."""
    root = ET.Element("CAR", Name=name, ExporterVersion=EXPORTER_VERSION)

    lod_name = f"{name.upper().removesuffix('_LODA')}_LOD0"
    lod = ET.SubElement(
        root, "NODE", matrices="1", type="LOD", Name=lod_name, MatrixNumber="-1", subobjects="1"
    )
    _sphere(lod, sphere_center, sphere_radius)
    ET.SubElement(
        lod,
        "MATRIX",
        Offset="0.000000 0.000000 0.000000",
        Orientation="0.000000 0.000000 0.000000 1.000000",
        Scale="1.000000",
    )

    obj = ET.SubElement(
        lod, "NODE", type="OBJECT", Name=name, MatrixNumber="0", instances="1", userflags=str(userflags)
    )
    ET.SubElement(obj, "RESOURCE", Filename=resource)
    _sphere(obj, sphere_center, sphere_radius)

    ET.SubElement(lod, "CONTROL", Distances=f"{LOD_DISTANCE} ")
    return root


def write_vhf(path: Path, name: str, resource: str, bounds, userflags: int) -> None:
    """Write a VHF describing one mesh, using the bounds returned by the MEB writer."""
    root = build_vhf(name, resource, bounds.sphere_center, bounds.sphere_radius, userflags)
    ET.indent(root, space="    ")
    body = ET.tostring(root, encoding="unicode")
    Path(path).write_text(f'<?xml version="1.0" encoding="utf-8"?>\n{body}\n', encoding="utf-8")


def _is_vehicle_mesh(obj) -> bool:
    if not obj or getattr(obj, "type", None) != "MESH":
        return False
    if obj.name.startswith(("SMS_LOD_", "TEMP_MESH", "TEMP_CURVE_MESH", "TEMP_COMBINED")):
        return False
    data = getattr(obj, "data", None)
    return bool(data and data.polygons)


def _object_spec(name, resource, bounds, userflags, modifiable):
    return {
        "kind": "object",
        "name": name,
        "resource": resource,
        "center": tuple(float(v) for v in bounds.sphere_center),
        "radius": float(bounds.sphere_radius),
        "userflags": int(userflags),
        "modifiable": bool(modifiable),
    }


def _export_mesh(obj, anchor, out_dir: Path, resource_dir: str, car_name: str):
    """Export one mesh in the anchor's local space and return its VHF object spec."""
    from ..meshes.blender_meb_export import export_object_to_meb
    from ..utils import sanitize
    import mathutils  # type: ignore

    from .sgx_export import _build_export_mesh_stem, _build_maybe_overridden_options, _get_userflags

    mesh_name = sanitize(obj.name)
    options = _build_maybe_overridden_options(obj, f"vehicles/{car_name}/")
    options.vertex_transform_mode = "NONE"
    options.bake_matrix = mathutils.Matrix.Translation(anchor.matrix_world.to_translation()).inverted() @ obj.matrix_world
    stem = _build_export_mesh_stem(mesh_name, options.skip_uv_compression)
    bounds = export_object_to_meb(
        obj,
        out_dir / f"{stem}.meb",
        mesh_name=stem,
        options=options,
        uppercase_name=False,
    )
    settings = getattr(getattr(obj, "data", None), "meb_export_settings", None)
    modifiable = bool(getattr(settings, "vhf_modifiable", False))
    resource = f"{resource_dir}\\{stem}.meb"
    return _object_spec(stem, resource, bounds, _get_userflags(obj), modifiable), obj


def export_vehicle_vhf(filepath: str, context, export_scope: str = "ALL", export_mtx: bool = True) -> dict:
    """Export the scene as a vehicle VHF plus the MEBs it references."""
    import bpy  # type: ignore
    import numpy as np

    from ..materials.mtx_processor import prepare_mtx_files_from_materials
    from ..properties.lod import assigned_lod_levels, get_lod_name, is_sms_lod
    from ..utils import effective_materials_for_object, sanitize
    from ..utils.coordinate_transforms import decompose_matrix
    from .object_export import iter_visible_scene_objects
    from .sgx_export import export_textures, prepare_texture_mapping

    output_path = Path(filepath)
    out_dir = output_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    car_name = sanitize(output_path.stem) or "vehicle"
    resource_dir = f"vehicles\\{car_name}"

    visible = list(iter_visible_scene_objects(context.view_layer))
    if export_scope == "SELECTED":
        selected = {obj.as_pointer() for obj in context.selected_objects}
        source = [obj for obj in visible if obj.as_pointer() in selected]
    else:
        source = visible

    by_name = {obj.name: obj for obj in visible if _is_vehicle_mesh(obj)}

    def damage_twin(obj):
        twin = by_name.get(f"{obj.name}{DAMAGE_SUFFIX}")
        if twin is None or twin.as_pointer() == obj.as_pointer():
            return None
        return twin

    lod_groups = {}
    claimed = set()
    for obj in source:
        if not is_sms_lod(obj):
            continue
        levels = []
        for target, distance in assigned_lod_levels(obj):
            if not _is_vehicle_mesh(target):
                print(f"Skipping {target.name}: not an exportable VHF mesh")
                continue
            if target.as_pointer() in claimed:
                print(f"  Warning: {target.name} is already used by another LOD group; skipping in {obj.name}")
                continue
            claimed.add(target.as_pointer())
            twin = damage_twin(target)
            if twin is not None:
                claimed.add(twin.as_pointer())
            levels.append((target, twin, float(distance)))
        if not levels:
            print(f"Skipping {obj.name}: LOD control has no exportable meshes")
            continue
        lod_groups[obj.as_pointer()] = levels
        print(f"LOD group {get_lod_name(obj)}: {len(levels)} level(s)")

    anchors = []
    for obj in source:
        if obj.as_pointer() in lod_groups:
            anchors.append(obj)
            continue
        if not _is_vehicle_mesh(obj) or obj.as_pointer() in claimed:
            continue
        if obj.name.endswith(DAMAGE_SUFFIX) and obj.name[: -len(DAMAGE_SUFFIX)] in by_name:
            continue
        twin = damage_twin(obj)
        if twin is not None:
            claimed.add(twin.as_pointer())
        claimed.add(obj.as_pointer())
        anchors.append(obj)

    if not anchors:
        raise RuntimeError("No exportable vehicle meshes found")

    parts = []
    exported_objects = []
    for anchor in anchors:
        matrix = np.array(anchor.matrix_world)
        offset, _ = decompose_matrix(matrix)
        part = {"offset": tuple(float(v) for v in offset), "orientation": (0.0, 0.0, 0.0, 1.0)}
        if anchor.as_pointer() in lod_groups:
            levels = []
            for target, twin, distance in lod_groups[anchor.as_pointer()]:
                spec, exported = _export_mesh(target, anchor, out_dir, resource_dir, car_name)
                exported_objects.append(exported)
                spec["distance"] = distance
                if twin is None:
                    levels.append(spec)
                    continue
                damaged, damaged_obj = _export_mesh(twin, anchor, out_dir, resource_dir, car_name)
                exported_objects.append(damaged_obj)
                levels.append({
                    "kind": "damage",
                    "name": spec["name"],
                    "objects": [spec, damaged],
                    "distance": distance,
                })
            part["node"] = {
                "kind": "lod",
                "name": sanitize(get_lod_name(anchor)),
                "levels": levels,
            }
        else:
            spec, exported = _export_mesh(anchor, anchor, out_dir, resource_dir, car_name)
            exported_objects.append(exported)
            twin = damage_twin(anchor)
            level = spec
            if twin is not None:
                damaged, damaged_obj = _export_mesh(twin, anchor, out_dir, resource_dir, car_name)
                exported_objects.append(damaged_obj)
                level = {"kind": "damage", "name": spec["name"], "objects": [spec, damaged]}
            level["distance"] = 0
            lod_name = f"{spec['name'].upper().removesuffix('_LODA')}_LOD0"
            part["node"] = {"kind": "lod", "name": lod_name, "levels": [level]}
        parts.append(part)

    write_vehicle_vhf(output_path, car_name, parts)

    materials = []
    for obj in exported_objects:
        materials.extend(sanitize(mat.name) for mat in effective_materials_for_object(obj) if mat)
    materials = sorted(set(materials))
    if materials and export_mtx:
        texture_dir = out_dir.parent / "textures" / car_name
        texture_mapping = prepare_texture_mapping(
            materials,
            out_dir,
            texture_dir,
            car_name,
            context,
            game_texture_dir=f"vehicles\\{car_name}",
        )
        prepare_mtx_files_from_materials(
            materials, out_dir, context, track_name=car_name, texture_mapping=texture_mapping
        )
        if texture_mapping:
            export_textures(texture_mapping, texture_dir)

    print(f"Exported vehicle VHF {output_path.name}: {len(parts)} part(s), {len(exported_objects)} mesh(es)")
    return {
        "parts": len(parts),
        "meshes": len(exported_objects),
        "materials": len(materials) if export_mtx else 0,
        "path": str(output_path),
    }
