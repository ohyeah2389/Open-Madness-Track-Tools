import bpy  # type: ignore
from ..properties.dynamic import (
    get_definition_name,
    get_definition_shapes,
    get_definition_visual,
    is_dynamic_definition,
    is_sms_dynamic,
)


def _find_definition_root(obj):
    """Walk up the parent chain to the definition this object belongs to."""
    while obj:
        if is_dynamic_definition(obj):
            return obj
        obj = obj.parent
    return None


class MadnessDynamicDefinitionPanel(bpy.types.Panel):
    """Panel for authoring a dynamic physics object definition"""
    bl_label = "Madness Dynamic Definition"
    bl_idname = "OBJECT_PT_madness_dynamic_definition"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type in {'MESH', 'EMPTY'}

    def draw(self, context):
        layout = self.layout
        obj = context.object
        props = obj.madness_dynamic_def

        layout.prop(props, "is_definition")

        if props.is_definition:
            box = layout.box()
            box.prop(props, "export_name", placeholder=obj.name)
            box.label(text=f"Exports as {get_definition_name(obj)}", icon='FILE_3D')
            shapes = get_definition_shapes(obj)
            if shapes:
                box.label(text=f"{len(shapes)} collision shape(s)", icon='MESH_ICOSPHERE')
            else:
                box.label(text="No mesh shapes found", icon='ERROR')

            box.prop(props, "visual_mesh", placeholder="This object's mesh")
            if not get_definition_visual(obj):
                box.label(text="No visual mesh: nothing will be drawn", icon='ERROR')

        if obj.type != 'MESH':
            return

        definition_root = _find_definition_root(obj)
        if definition_root is None:
            return

        shape_box = layout.box()
        shape_box.label(text="Collision Shape", icon='PHYSICS')
        if definition_root is not obj:
            shape_box.label(text=f"Part of: {get_definition_name(definition_root)}", icon='INFO')
        shape_box.prop(props, "physics_material")
        shape_box.prop(props, "mass")
        shape_box.label(text="Exported as a convex hull of this mesh", icon='MESH_ICOSPHERE')


class MadnessDynamicPanel(bpy.types.Panel):
    """Panel for placing an instance of a dynamic object definition"""
    bl_label = "Madness Dynamic Object"
    bl_idname = "OBJECT_PT_madness_dynamic"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"

    @classmethod
    def poll(cls, context):
        return is_sms_dynamic(context.object)

    def draw(self, context):
        layout = self.layout
        obj = context.object
        dynamic_props = obj.madness_dynamic

        main_box = layout.box()
        main_box.label(text="Definition", icon='LIBRARY_DATA_DIRECT')
        main_box.prop(dynamic_props, "definition", text="")

        if not is_dynamic_definition(dynamic_props.definition):
            main_box.label(text="Assign a definition to place an object here", icon='INFO')
            return

        selected_empties = [o for o in context.selected_objects if o.type == 'EMPTY']
        if len(selected_empties) > 1:
            main_box.operator(
                "madness_dynamic.copy_definition_to_selected",
                text=f"Copy Definition To {len(selected_empties)} Selected Empties",
                icon='DUPLICATE'
            )

        scale_box = layout.box()
        scale_box.label(text="Instance Scale", icon='FULLSCREEN_ENTER')
        scale_box.prop(dynamic_props, "use_scale_override")
        if dynamic_props.use_scale_override:
            col = scale_box.column(align=True)
            col.prop(dynamic_props, "scale_x")
            col.prop(dynamic_props, "scale_y")
            col.prop(dynamic_props, "scale_z")
        else:
            scale_box.label(text="Using object transform scale", icon='INFO')


class MADNESS_DYNAMIC_OT_copy_definition_to_selected(bpy.types.Operator):
    """Copy the active empty's definition to all selected empties"""
    bl_idname = "madness_dynamic.copy_definition_to_selected"
    bl_label = "Copy Definition To Selected"
    bl_description = "Copy the active empty's definition to all selected empties"

    def execute(self, context):
        active_obj = context.object
        if not is_sms_dynamic(active_obj):
            self.report({'ERROR'}, "Active object is not an empty")
            return {'CANCELLED'}

        definition = active_obj.madness_dynamic.definition
        if not is_dynamic_definition(definition):
            self.report({'WARNING'}, "Active empty has no definition assigned")
            return {'CANCELLED'}

        selected_empties = [obj for obj in context.selected_objects if obj.type == 'EMPTY']
        for obj in selected_empties:
            obj.madness_dynamic.definition = definition

        self.report(
            {'INFO'},
            f"Applied definition '{get_definition_name(definition)}' to {len(selected_empties)} empties"
        )
        return {'FINISHED'}


_CLASSES = [
    MadnessDynamicDefinitionPanel,
    MadnessDynamicPanel,
    MADNESS_DYNAMIC_OT_copy_definition_to_selected,
]


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
