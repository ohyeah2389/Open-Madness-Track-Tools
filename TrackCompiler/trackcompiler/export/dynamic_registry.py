"""Registration of a track's dynamic objects as engine object types.

Placements in <track>.env.xml only resolve to a rigid body for object types the engine
knows about, and those are declared by a pair of files: dynamic.sys.xml lists each type
with its bounding sphere, and dynamic.obj.bml holds the hulls the engine cooks at load.
Stock tracks each ship the full set of shipped objects; a track built here registers
only its own, which shadows the stock pair while the track is loaded.
"""

import math
import zlib
from pathlib import Path
from typing import Any, Dict, List

from .bml import BmlWriter, Node

# Type tags used by the descriptors; 3 is a convex shape, 4 a dynamic object.
CONVEX_SHAPE, DYNAMIC_OBJECT = 3.0, 4.0

# Object types are named for their collision resource rather than their mesh.
PREFIX = "COLLISION_CONVEX_"

IDENTITY_3X3 = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]

# Stock ids read like object addresses and only need to be unique within the file.
_ID_BASE = 0x10000000
_ID_STRIDE = 0x28


class _Ids:
    def __init__(self):
        self.value = _ID_BASE

    def next(self) -> str:
        self.value += _ID_STRIDE
        return f"0x{self.value:08X}"


def material_crc(name: str) -> float:
    """Hash a PhysX material name for a ShapeDesc.

    Stock values are u32 hashes stored in a float32 pool, so their low bits are already
    lost by the time the engine reads them back; the exact algorithm is unknown and
    surfaces fall back to their defaults when it does not match.
    """
    return float(zlib.crc32(name.encode()))


def bounding_sphere(points) -> List[float]:
    """Centre and radius of a sphere enclosing every hull point."""
    axes = list(zip(*points))
    centre = [(min(axis) + max(axis)) / 2 for axis in axes]
    radius = max(math.dist(point, centre) for point in points)
    return [*centre, radius]


def format_floats(values) -> str:
    """Format floats the way stock Reflection XML does: fixed decimal, never scientific."""
    return ";".join(f"{float(v):.6f}".rstrip("0").rstrip(".") or "0" for v in values)


def quantize(value, digits: int = 6) -> float:
    """Match the 6-decimal rounding used in dynamic_collisions.xml."""
    return round(float(value), digits)


def quantize_vec(values, digits: int = 6):
    return [quantize(v, digits) for v in values]


def _shape_desc(name: str, shape: Dict[str, Any], ids: _Ids) -> Node:
    points = [quantize_vec(point) for point in shape["points"]]
    vertices = [
        Node("data", [("class", "Vertex"), ("id", ids.next())], [
            Node("prop", [("name", "Name"), ("data", f"id{index}")]),
            Node("prop", [("name", "Vertex"), ("data", point)]),
        ])
        for index, point in enumerate(points)
    ]
    props = [
        ("Name", name),
        ("Format", 0.0),
        ("Type", CONVEX_SHAPE),
        ("Width", 1.0),
        ("Height", 1.0),
        ("Length", 1.0),
        ("Mass", quantize(shape["mass"])),
        ("Material CRC", material_crc(shape["material"])),
        ("Relative Position", quantize_vec(shape.get("position", (0.0, 0.0, 0.0)))),
        ("Relative Orientation", quantize_vec(shape.get("orientation", IDENTITY_3X3))),
        ("Mesh Data Size", 0.0),
        ("Vertex Count", float(len(points))),
        ("Trigger", False),
    ]
    return Node("data", [("class", "ShapeDesc"), ("id", ids.next())], [
        *(Node("prop", [("name", key), ("data", value)]) for key, value in props),
        Node("prop", [("name", "Vertices"), ("elements", float(len(points)))],
             [Node("funcpropdata", [], vertices)]),
    ])


def _class_declarations() -> List[Node]:
    """The RTTI preamble, which a Reflection document repeats before each class."""
    def persistent():
        return [
            Node("class", [("name", "BRTTIRefCount"), ("base", "root class")]),
            Node("class", [("name", "BPersistent"), ("base", "BRTTIRefCount")],
                 [Node("prop", [("name", "Name"), ("type", "String")])]),
        ]

    shape_props = [
        ("Format", "U32"), ("Type", "U32"), ("Width", "F32"), ("Height", "F32"),
        ("Length", "F32"), ("Mass", "F32"), ("Material CRC", "U32"),
        ("Relative Position", "Vec3f"), ("Relative Orientation", "Mtx3f"),
        ("Mesh Data Size", "U32"), ("Vertex Count", "U32"), ("Trigger", "Bool"),
        ("Vertices", "Fct"), ("Mesh Data", "Fct"),
    ]
    return [
        *persistent(),
        Node("class", [("name", "DynamicObjectsDescManager"), ("base", "BPersistent")],
             [Node("prop", [("name", "List"), ("type", "Fct")])]),
        *persistent(),
        Node("class", [("name", "ShapeDesc"), ("base", "BPersistent")],
             [Node("prop", [("name", key), ("type", kind)]) for key, kind in shape_props]),
        *persistent(),
        Node("class", [("name", "DynamicObjectDesc"), ("base", "BPersistent")], [
            Node("prop", [("name", "Type"), ("type", "U32")]),
            Node("prop", [("name", "BoundingSphere"), ("type", "Vec4f")]),
            Node("prop", [("name", "Shapes"), ("type", "Fct")]),
        ]),
        *persistent(),
        Node("class", [("name", "Vertex"), ("base", "BPersistent")],
             [Node("prop", [("name", "Vertex"), ("type", "Vec3f")])]),
    ]


def _all_points(body: Dict[str, Any]):
    """Every hull point of a body, offset by the shape it belongs to."""
    for shape in body["shapes"]:
        offset = shape.get("position", (0.0, 0.0, 0.0))
        for point in shape["points"]:
            yield tuple(float(p) + float(o) for p, o in zip(point, offset))


def build_obj_bml(bodies: List[Dict[str, Any]]) -> bytes:
    ids = _Ids()
    descs = []
    for body in bodies:
        name = PREFIX + body["name"]
        shapes = body["shapes"]
        descs.append(Node("data", [("class", "DynamicObjectDesc"), ("id", ids.next())], [
            Node("prop", [("name", "Name"), ("data", name)]),
            Node("prop", [("name", "Type"), ("data", DYNAMIC_OBJECT)]),
            Node("prop", [("name", "BoundingSphere"),
                          ("data", quantize_vec(bounding_sphere(list(_all_points(body)))))]),
            Node("prop", [("name", "Shapes"), ("elements", float(len(shapes)))],
                 [Node("funcpropdata", [], [_shape_desc(name, s, ids) for s in shapes])]),
        ]))

    root = Node("Reflection", [], [
        *_class_declarations(),
        Node("data", [("class", "DynamicObjectsDescManager"), ("id", "0x307DC520")], [
            Node("prop", [("name", "Name"), ("data", "Objects Export Pool")]),
            Node("prop", [("name", "List"), ("elements", float(len(descs)))],
                 [Node("funcpropdata", [], descs)]),
        ]),
    ])
    return BmlWriter().build(root)


def build_sys_xml(bodies: List[Dict[str, Any]]) -> str:
    ids = _Ids()
    entries = []
    for body in bodies:
        name = PREFIX + body["name"]
        sphere = format_floats(bounding_sphere(list(_all_points(body))))
        entries.append(
            f'                <data class="DynamicSystemDesc" id="{ids.next()}">\n'
            f'                    <prop name="Name" data="{name}" />\n'
            f'                    <prop name="BoundingSphere" data="{sphere}" />\n'
            f'                    <prop name="Dynamic System Descs Object Array" elements="1">\n'
            f'                        <funcpropdata ObjectNumber0="{name}" />\n'
            f'                    </prop>\n'
            f'                </data>'
        )
    return (
        '<?xml version="1.0" ?>\n'
        '<Reflection>\n'
        '    <class name="BRTTIRefCount" base="root class" />\n'
        '    <class name="BPersistent" base="BRTTIRefCount">\n'
        '        <prop name="Name" type="String" />\n'
        '    </class>\n'
        '    <class name="DynamicSystemDesc" base="BPersistent">\n'
        '        <prop name="BoundingSphere" type="Vec4f" />\n'
        '        <prop name="Dynamic System Descs Object Array" type="Fct" />\n'
        '    </class>\n'
        '    <class name="BRTTIRefCount" base="root class" />\n'
        '    <class name="BPersistent" base="BRTTIRefCount">\n'
        '        <prop name="Name" type="String" />\n'
        '    </class>\n'
        '    <class name="DynamicSystemDescManager" base="BPersistent">\n'
        '        <prop name="Dynamic System Descs Array" type="Fct" />\n'
        '    </class>\n'
        '    <data class="DynamicSystemDescManager" id="0x307C5C00">\n'
        '        <prop name="Name" data="DynamicSystemDescs Manager" />\n'
        f'        <prop name="Dynamic System Descs Array" elements="{len(bodies)}">\n'
        '            <funcpropdata>\n'
        + "\n".join(entries) + "\n"
        '            </funcpropdata>\n'
        '        </prop>\n'
        '    </data>\n'
        '</Reflection>\n'
    )


def export_dynamic_registry(bodies: List[Dict[str, Any]], physics_dir: Path) -> int:
    """Write the registry pair next to the track's env.xml."""
    bodies = [b for b in bodies if any(s["points"] for s in b["shapes"])]
    if not bodies:
        return 0

    physics_dir.mkdir(parents=True, exist_ok=True)
    (physics_dir / "dynamic.obj.bml").write_bytes(build_obj_bml(bodies))
    (physics_dir / "dynamic.sys.xml").write_text(build_sys_xml(bodies), encoding="utf-8")
    print(f"Registered {len(bodies)} dynamic object type(s) in {physics_dir}")
    return len(bodies)
