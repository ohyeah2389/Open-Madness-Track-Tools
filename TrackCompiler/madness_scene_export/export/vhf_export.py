"""Writer for VHF instance hierarchies.

A VHF is a mini-scenegraph that binds a name to a mesh resource. Dynamic objects need
one because the engine resolves a physics body's appearance through the hierarchy rather
than by loading a MEB directly. The format resembles SGX but uses its own element set,
and the two are not interchangeable.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

EXPORTER_VERSION = "Phx Staging Tools v1.280"

# Stock VHFs draw every LOD out to this distance, and dynamic objects only ever
# define one, so there is nothing to fall back to beyond it.
LOD_DISTANCE = 1000


def _sphere(parent, center, radius):
    ET.SubElement(
        parent,
        "SPHERE",
        Centre=f"{center[0]:.6f} {center[1]:.6f} {center[2]:.6f} 1.000000",
        Radius=f"{radius:.6f}",
    )


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
