import bpy
from bpy.props import BoolProperty, IntProperty, StringProperty, EnumProperty, PointerProperty, BoolVectorProperty
from typing import List

def _get_default_userflags():
    """Get default userflags as boolean array."""
    # Default value: 0b10000000000100000001000001110100
    default_value = 0b10000000000100000001000001110100
    flags = [False] * 32
    for i in range(32):
        if default_value & (1 << i):
            flags[i] = True
    return flags

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
        
        # Create a 4x8 grid of checkboxes for the 32 bits
        for row in range(4):
            row_layout = box.row()
            for col in range(8):
                bit_index = row * 8 + col
                row_layout.prop(settings, "userflags", index=bit_index, text=f"{bit_index}")
        
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
        bpy.utils.unregister_class(MEBExportSettings)
    except RuntimeError:
        pass  # Already unregistered 