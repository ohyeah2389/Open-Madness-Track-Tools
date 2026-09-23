# SPDX-License-Identifier: GPL-3.0-or-later

"""Imports a SplineRecorder CSV as a poly curve named SMS_AIW_RACINGLINE"""

import csv
from pathlib import Path

import bpy  # pyright: ignore[reportMissingImports]
from bpy_extras.io_utils import ImportHelper  # pyright: ignore[reportMissingImports]
from bpy.props import StringProperty  # pyright: ignore[reportMissingImports]
from bpy.types import Operator  # pyright: ignore[reportMissingImports]

bl_info = {
    "name": "SplineRecorder Importer",
    "author": "ohyeah2389",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "File > Import > SplineRecorder CSV",
    "description": "Import an AMS2 recorded racing line as a poly curve",
    "category": "Import-Export",
}


def _points(path: Path):
    points = []
    with path.open(newline="", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip() or line.startswith("#"):
                continue
            row = next(csv.reader([line]))
            if not row or row[0] == "x":
                continue
            # Madness (x, y up, z) -> Blender (x, y, z up)
            x, y, z = (float(row[0]), float(row[1]), float(row[2]))
            points.append((x, z, y))
    return points


class ImportSplineRecorderCSV(Operator, ImportHelper):
    bl_idname = "import_scene.spline_recorder"
    bl_label = "Import Spline Recorder CSV"
    bl_description = "Import a recorded racing line as a poly curve"
    filename_ext = ".csv"
    filter_glob: StringProperty(default="*.csv", options={"HIDDEN"})

    def execute(self, context):
        points = _points(Path(self.filepath))
        if len(points) < 2:
            self.report({"ERROR"}, "The CSV does not contain a valid line")
            return {"CANCELLED"}

        previous = bpy.data.objects.get("SMS_AIW_RACINGLINE")
        if previous is not None:
            previous.name = "SMS_AIW_RACINGLINE_prev"

        curve = bpy.data.curves.new("SMS_AIW_RACINGLINE", type="CURVE")
        curve.dimensions = "3D"
        spline = curve.splines.new("POLY")
        spline.points.add(len(points) - 1)
        for index, point in enumerate(points):
            spline.points[index].co = (point[0], point[1], point[2], 1.0)

        obj = bpy.data.objects.new("SMS_AIW_RACINGLINE", curve)
        context.collection.objects.link(obj)
        self.report({"INFO"}, "Imported SMS_AIW_RACINGLINE")
        return {"FINISHED"}


def _menu(self, _context):
    self.layout.operator(ImportSplineRecorderCSV.bl_idname, text="SplineRecorder CSV (.csv)")


def register():
    bpy.utils.register_class(ImportSplineRecorderCSV)
    bpy.types.TOPBAR_MT_file_import.append(_menu)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(_menu)
    bpy.utils.unregister_class(ImportSplineRecorderCSV)


if __name__ == "__main__":
    register()
    bpy.ops.import_scene.spline_recorder("INVOKE_DEFAULT")
