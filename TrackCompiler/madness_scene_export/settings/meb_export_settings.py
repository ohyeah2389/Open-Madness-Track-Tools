import bpy
from bpy.props import BoolProperty, IntProperty, StringProperty, EnumProperty, PointerProperty, BoolVectorProperty
from typing import List
from .userflags import (
    USERFLAG_CATEGORIES,
    get_userflag_name,
    get_userflag_description,
    userflags_to_bool_vector,
)


def _get_default_userflags():
    """Get default userflags as boolean array."""
    return userflags_to_bool_vector()

class MEBExportSettings(bpy.types.PropertyGroup):
    """MEB Exporter settings attached to mesh objects"""

    # Export Options
    flip_coordinates: BoolProperty(
        name="Flip Coordinates",
        description="Flip coordinate system",
        default=False
    ) # type: ignore

    disable_material: BoolProperty(
        name="Disable Material",
        description="Disable material data export",
        default=False
    ) # type: ignore

    tangent_space: BoolProperty(
        name="Tangent Space",
        description="Generate tangent space data",
        default=True
    ) # type: ignore

    bodywork: BoolProperty(
        name="Bodywork",
        description="Add bodywork-specific data",
        default=False
    ) # type: ignore

    wsection1: BoolProperty(
        name="W Section 1",
        description="Enable W section 1",
        default=False
    ) # type: ignore

    wsection2: BoolProperty(
        name="W Section 2",
        description="Enable W section 2",
        default=False
    ) # type: ignore

    # UV Mapping (1-6, 0=none)
    uv1: IntProperty(
        name="UV Map 1",
        description="UV Map 1 index (1-6, 0=none)",
        default=1,
        min=0,
        max=6
    ) # type: ignore

    uv2: IntProperty(
        name="UV Map 2",
        description="UV Map 2 index (1-6, 0=none)",
        default=0,
        min=0,
        max=6
    ) # type: ignore

    uv3: IntProperty(
        name="UV Map 3",
        description="UV Map 3 index (1-6, 0=none)",
        default=0,
        min=0,
        max=6
    ) # type: ignore

    uv4: IntProperty(
        name="UV Map 4",
        description="UV Map 4 index (1-6, 0=none)",
        default=0,
        min=0,
        max=6
    ) # type: ignore

    uv5: IntProperty(
        name="UV Map 5",
        description="UV Map 5 index (1-6, 0=none)",
        default=0,
        min=0,
        max=6
    ) # type: ignore

    uv6: IntProperty(
        name="UV Map 6",
        description="UV Map 6 index (1-6, 0=none)",
        default=0,
        min=0,
        max=6
    ) # type: ignore

    # W Section UV Mapping
    wuv1: IntProperty(
        name="W Section UV 1",
        description="W Section UV 1 index (1-6, 0=none)",
        default=0,
        min=0,
        max=6
    ) # type: ignore

    wuv2: IntProperty(
        name="W Section UV 2",
        description="W Section UV 2 index (1-6, 0=none)",
        default=0,
        min=0,
        max=6
    ) # type: ignore

    # Custom extra arguments for anything not covered above
    custom_args: StringProperty(
        name="Custom Arguments",
        description="Additional custom arguments for MEB exporter",
        default=""
    ) # type: ignore

    # Userflags - 32-bit bitmask for SGX object flags
    userflags: BoolVectorProperty(
        name="User Flags",
        description="32-bit bitmask for SGX object userflags",
        size=32,
        default=_get_default_userflags()
    ) # type: ignore

def build_meb_args(settings: MEBExportSettings) -> List[str]:
    """Convert MEB export settings to command-line arguments"""
    args = []

    # Add boolean flags
    if settings.flip_coordinates:
        args.append("--flip")

    if settings.disable_material:
        args.append("--disable-material")

    if settings.tangent_space:
        args.append("--tangent-space")

    if settings.bodywork:
        args.append("--bodywork")

    if settings.wsection1:
        args.append("--wsection1")

    if settings.wsection2:
        args.append("--wsection2")

    # Add UV mappings (only if not 0)
    uv_mappings = [
        ("--uv1", settings.uv1),
        ("--uv2", settings.uv2),
        ("--uv3", settings.uv3),
        ("--uv4", settings.uv4),
        ("--uv5", settings.uv5),
        ("--uv6", settings.uv6),
        ("--wuv1", settings.wuv1),
        ("--wuv2", settings.wuv2),
    ]

    for flag, value in uv_mappings:
        if value > 0:
            args.extend([flag, str(value)])

    # Add custom arguments
    if settings.custom_args.strip():
        # Split custom args respecting quotes
        import shlex
        args.extend(shlex.split(settings.custom_args))

    return args

def get_userflags_value(settings: MEBExportSettings) -> int:
    """Convert userflags boolean vector to integer value."""
    value = 0
    for i, flag in enumerate(settings.userflags):
        if flag:
            value |= (1 << i)
    return value


class MEB_OT_toggle_userflag(bpy.types.Operator):
    """Toggle a mesh userflag bit."""
    bl_idname = "meb.toggle_userflag"
    bl_label = "Toggle User Flag"
    bl_options = {"UNDO"}

    bit_index: IntProperty(default=0, min=0, max=31)  # type: ignore

    @classmethod
    def description(cls, context, properties):
        return get_userflag_description(properties.bit_index)

    def execute(self, context):
        mesh = context.object.data if context.object else None
        if not mesh or not hasattr(mesh, "meb_export_settings"):
            return {"CANCELLED"}

        settings = mesh.meb_export_settings
        settings.userflags[self.bit_index] = not settings.userflags[self.bit_index]
        return {"FINISHED"}


class OBJECT_OT_copy_mesh_userflag(bpy.types.Operator):
    """Copy one mesh userflag to selected mesh objects."""
    bl_idname = "object.copy_mesh_userflag"
    bl_label = "Copy User Flag"
    bl_description = "Copy one userflag to all selected Mesh objects"
    bl_options = {"REGISTER", "UNDO"}

    bit_index: IntProperty(default=0, min=0, max=31)  # type: ignore

    @classmethod
    def poll(cls, context):
        return (
            context.object
            and context.object.type == "MESH"
            and len(context.selected_objects) > 1
            and hasattr(context.object.data, "meb_export_settings")
        )

    @classmethod
    def description(cls, context, properties):
        return f"Copy '{get_userflag_name(properties.bit_index)}' to selected mesh objects"

    def execute(self, context):
        active_obj = context.object
        if not active_obj or active_obj.type != "MESH":
            return {"CANCELLED"}

        if not hasattr(active_obj.data, "meb_export_settings"):
            self.report({"ERROR"}, "Active mesh has no MEB export settings")
            return {"CANCELLED"}

        source_settings = active_obj.data.meb_export_settings
        copied_count = 0

        for obj in context.selected_objects:
            if obj == active_obj or obj.type != "MESH" or not obj.data:
                continue
            if not hasattr(obj.data, "meb_export_settings"):
                continue

            target_settings = obj.data.meb_export_settings
            target_settings.userflags[self.bit_index] = source_settings.userflags[self.bit_index]
            copied_count += 1

        self.report(
            {"INFO"},
            f"Copied {get_userflag_name(self.bit_index)} to {copied_count} objects",
        )
        return {"FINISHED"}


class MEB_PT_export_settings(bpy.types.Panel):
    """MEB Export Settings Panel"""
    bl_label = "MEB Export Settings"
    bl_idname = "MEB_PT_export_settings"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        # Only show when we have a mesh object selected
        return context.object and context.object.type == 'MESH' and context.object.data

    def draw(self, context):
        layout = self.layout
        mesh = context.object.data

        if not hasattr(mesh, 'meb_export_settings'):
            layout.label(text="MEB export settings not available")
            return

        settings = mesh.meb_export_settings

        # Export options
        box = layout.box()
        box.label(text="Export Options", icon='EXPORT')

        col = box.column()
        col.prop(settings, "flip_coordinates")
        col.prop(settings, "disable_material")
        col.prop(settings, "tangent_space")
        col.prop(settings, "bodywork")

        row = col.row()
        row.prop(settings, "wsection1")
        row.prop(settings, "wsection2")

        # UV Mapping
        box = layout.box()
        box.label(text="UV Mapping", icon='UV')

        # Main UV channels
        col = box.column()
        col.label(text="Main UV Channels:")
        row = col.row()
        row.prop(settings, "uv1")
        row.prop(settings, "uv2")
        row.prop(settings, "uv3")

        row = col.row()
        row.prop(settings, "uv4")
        row.prop(settings, "uv5")
        row.prop(settings, "uv6")

        # W Section UV channels
        col.separator()
        col.label(text="W Section UV Channels:")
        row = col.row()
        row.prop(settings, "wuv1")
        row.prop(settings, "wuv2")

        # User Flags - 32-bit bitmask
        box = layout.box()
        box.label(text="User Flags (32-bit bitmask)", icon='SETTINGS')

        # Show the current value in both binary and decimal
        userflags_value = get_userflags_value(settings)
        binary_str = format(userflags_value, '032b')
        box.label(text=f"Value: {userflags_value} (0b{binary_str})")

        # Clean single-column category layout with tooltip descriptions.
        flags_col = box.column(align=True)
        for category_name, bit_indices in USERFLAG_CATEGORIES:
            category_box = flags_col.box()
            category_box.label(text=category_name)
            category_col = category_box.column(align=True)
            for bit_index in bit_indices:
                row = category_col.row(align=True)
                icon = "CHECKBOX_HLT" if settings.userflags[bit_index] else "CHECKBOX_DEHLT"
                op = row.operator(
                    "meb.toggle_userflag",
                    text=get_userflag_name(bit_index),
                    icon=icon,
                    depress=settings.userflags[bit_index],
                )
                op.bit_index = bit_index
                if len(context.selected_objects) > 1:
                    copy_op = row.operator(
                        "object.copy_mesh_userflag",
                        text="",
                        icon="COPYDOWN",
                    )
                    copy_op.bit_index = bit_index

        # Custom arguments
        box = layout.box()
        box.label(text="Custom Arguments", icon='CONSOLE')
        box.prop(settings, "custom_args", text="")

        # Preview of generated arguments
        args = build_meb_args(settings)
        if args:
            box.separator()
            box.label(text="Generated Arguments:")
            # Split long argument lists across multiple lines
            args_str = " ".join(args)
            if len(args_str) > 60:
                # Split into chunks for readability
                words = args_str.split()
                lines = []
                current_line = ""
                for word in words:
                    if len(current_line + " " + word) > 60:
                        if current_line:
                            lines.append(current_line)
                        current_line = word
                    else:
                        current_line = current_line + " " + word if current_line else word
                if current_line:
                    lines.append(current_line)

                for line in lines:
                    box.label(text=line)
            else:
                box.label(text=args_str)


def register():
    try:
        bpy.utils.register_class(MEBExportSettings)
    except ValueError:
        # Already registered, unregister and re-register
        bpy.utils.unregister_class(MEBExportSettings)
        bpy.utils.register_class(MEBExportSettings)

    try:
        bpy.utils.register_class(MEB_OT_toggle_userflag)
    except ValueError:
        bpy.utils.unregister_class(MEB_OT_toggle_userflag)
        bpy.utils.register_class(MEB_OT_toggle_userflag)

    try:
        bpy.utils.register_class(OBJECT_OT_copy_mesh_userflag)
    except ValueError:
        bpy.utils.unregister_class(OBJECT_OT_copy_mesh_userflag)
        bpy.utils.register_class(OBJECT_OT_copy_mesh_userflag)

    try:
        bpy.utils.register_class(MEB_PT_export_settings)
    except ValueError:
        # Already registered, unregister and re-register
        bpy.utils.unregister_class(MEB_PT_export_settings)
        bpy.utils.register_class(MEB_PT_export_settings)

    # Add MEB settings to mesh objects
    if not hasattr(bpy.types.Mesh, 'meb_export_settings'):
        bpy.types.Mesh.meb_export_settings = PointerProperty(type=MEBExportSettings)


def unregister():
    if hasattr(bpy.types.Mesh, 'meb_export_settings'):
        del bpy.types.Mesh.meb_export_settings

    try:
        bpy.utils.unregister_class(MEB_PT_export_settings)
    except RuntimeError:
        pass  # Already unregistered

    try:
        bpy.utils.unregister_class(OBJECT_OT_copy_mesh_userflag)
    except RuntimeError:
        pass  # Already unregistered

    try:
        bpy.utils.unregister_class(MEB_OT_toggle_userflag)
    except RuntimeError:
        pass  # Already unregistered

    try:
        bpy.utils.unregister_class(MEBExportSettings)
    except RuntimeError:
        pass  # Already unregistered
