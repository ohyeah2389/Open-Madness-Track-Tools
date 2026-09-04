import bpy  # type: ignore
from bpy.props import IntProperty  # type: ignore

from ..properties.lod import is_sms_lod


def _draw_level(layout, data, target_prop, distance_prop, label, remove_index=None):
    row = layout.row(align=True)
    row.prop(data, target_prop, text=label)
    row.prop(data, distance_prop, text="Distance")
    if remove_index is not None:
        op = row.operator("madness_lod.remove_level", text="", icon="X")
        op.index = remove_index


class MADNESS_LOD_OT_add_level(bpy.types.Operator):
    """Add another LOD level slot to the active control empty."""

    bl_idname = "madness_lod.add_level"
    bl_label = "Add LOD Level"
    bl_description = "Add another detail level to this LOD control"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return is_sms_lod(context.object)

    def execute(self, context):
        lod = context.object.madness_lod
        prev = lod.extra_levels[-1].distance if lod.extra_levels else lod.distance_1
        item = lod.extra_levels.add()
        item.distance = prev + 50.0
        return {"FINISHED"}


class MADNESS_LOD_OT_remove_level(bpy.types.Operator):
    """Remove a LOD level slot from the active control empty."""

    bl_idname = "madness_lod.remove_level"
    bl_label = "Remove LOD Level"
    bl_description = "Remove this extra detail level"
    bl_options = {"REGISTER", "UNDO"}

    index: IntProperty(default=0, min=0)  # type: ignore

    @classmethod
    def poll(cls, context):
        return is_sms_lod(context.object) and context.object.madness_lod.extra_levels

    def execute(self, context):
        extras = context.object.madness_lod.extra_levels
        if self.index < 0 or self.index >= len(extras):
            return {"CANCELLED"}
        extras.remove(self.index)
        return {"FINISHED"}


class LOD_PT_MadnessLODPanel(bpy.types.Panel):
    """Panel for Madness LOD control empties."""

    bl_label = "Madness LOD Control"
    bl_idname = "DATA_PT_madness_lod"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "data"

    @classmethod
    def poll(cls, context):
        return is_sms_lod(context.object)

    def draw(self, context):
        layout = self.layout
        lod = context.object.madness_lod
        _draw_level(layout, lod, "target_0", "distance_0", "LOD 0")
        _draw_level(layout, lod, "target_1", "distance_1", "LOD 1")
        for i, level in enumerate(lod.extra_levels):
            _draw_level(layout, level, "target", "distance", f"LOD {i + 2}", remove_index=i)
        layout.operator("madness_lod.add_level", icon="ADD")


_CLASSES = (
    MADNESS_LOD_OT_add_level,
    MADNESS_LOD_OT_remove_level,
    LOD_PT_MadnessLODPanel,
)


def register():
    for cls in _CLASSES:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            bpy.utils.unregister_class(cls)
            bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
