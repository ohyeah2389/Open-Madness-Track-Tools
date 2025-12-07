import bpy  # type: ignore
from bpy.props import StringProperty, BoolProperty, FloatProperty, EnumProperty, PointerProperty, CollectionProperty  # type: ignore
from pathlib import Path
import xml.etree.ElementTree as ET
from typing import Optional
from .shader_definitions import (
    SHADER_TECHNIQUES,
    SHADER_DEFINES,
    get_shader_items,
    get_technique_items,
    update_shader_params,
    update_shader_change,
    is_param_required,
    is_define_required,
    get_param_stats,
)
from ..utils import sanitize


def validate_override_path(path_str):
    """Validate an override path for MTX/BMT files.
    
    Args:
        path_str: The file path string to validate
        
    Returns:
        tuple: (is_valid, file_type, error_message, target_extension) where:
               - is_valid: Boolean indicating if path is valid
               - file_type: "MTX", "BMT", or "UNKNOWN"
               - error_message: Error description if not valid, None if valid
               - target_extension: The extension to use in MEB references (.mtx)
    """
    if not path_str:
        return False, "UNKNOWN", "No path specified", None
    
    path = Path(path_str)
    
    if not path.exists():
        return False, "UNKNOWN", f"File not found: {path}", None
    
    file_ext = path.suffix.lower()
    
    # Accept both .mtx and .bmt extensions
    if file_ext not in ['.mtx', '.bmt']:
        return False, "UNKNOWN", f"File must have .mtx or .bmt extension, got {file_ext}", None
    
    # Try to determine file type by extension first, then by content
    if file_ext == '.bmt':
        # BMT file - will be referenced as .mtx in MEB
        return True, "BMT", None, ".mtx"
    elif file_ext == '.mtx':
        # Could be either MTX or BMT, check content to be sure
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read(1024)  # Read first 1KB to check
                if 'BMT' in content.upper() or '<bmt' in content.lower():
                    return True, "BMT", None, ".mtx"
                elif '<material' in content.lower():
                    return True, "MTX", None, ".mtx"
                else:
                    # Assume MTX for .mtx files with unknown content
                    return True, "MTX", None, ".mtx"
        except Exception as e:
            return False, "UNKNOWN", f"Could not read file: {e}", None
    
    return False, "UNKNOWN", "Unexpected file type", None


def resolve_texture_path(texture_path_str, context=None):
    """Resolve a texture path, handling absolute and relative paths.

    Args:
        texture_path_str: The texture path string (absolute or relative to blend file)
        context: Blender context (optional, uses bpy.context if None)

    Returns:
        tuple: (resolved_path, exists) where resolved_path is a Path object
               and exists is a boolean indicating if the file was found
    """
    if not texture_path_str:
        return None, False

    # Import bpy at function level to ensure it's available throughout the function
    import bpy  # type: ignore

    if context is None:
        context = bpy.context

    texture_path = Path(texture_path_str)

    # If absolute path, check directly
    if texture_path.is_absolute():
        return texture_path, texture_path.exists()

    # For relative paths, resolve relative to blend file (if saved)
    if hasattr(bpy, "data") and bpy.data.filepath:
        blend_dir = Path(bpy.data.filepath).parent
        blend_relative_path = blend_dir / texture_path
        return blend_relative_path, blend_relative_path.exists()

    # Blend file not saved, return the relative path as-is (probably doesn't exist)
    return texture_path, False


def texture_value_update(self, context):
    """Update callback to convert absolute paths to plain relative paths when texture_value is set."""
    import bpy  # type: ignore
    
    if not self.texture_value:
        return
    
    texture_path = Path(self.texture_value)
    
    # Skip if already a plain relative path (not absolute)
    if not texture_path.is_absolute():
        # Normalize to forward slashes
        normalized = str(self.texture_value).replace("\\", "/")
        if normalized != self.texture_value:
            self.texture_value = normalized
        return
    
    # Check if blend file is saved
    if not bpy.data.filepath:
        # Can't convert to relative without saved blend file
        return
    
    try:
        # Normalize both paths
        texture_abs = texture_path.resolve()
        blend_dir = Path(bpy.data.filepath).resolve().parent
        
        # Try to make relative to blend file
        relative_path = texture_abs.relative_to(blend_dir)
        # Store as plain relative path with forward slashes
        self.texture_value = str(relative_path).replace("\\", "/")
        
        print(f"[Auto-converted] {texture_abs.name} -> {self.texture_value}")
    except (ValueError, OSError):
        # Path not relative to blend directory - keep as absolute
        pass


# MTX Support Classes
class MTXShaderParam(bpy.types.PropertyGroup):
    """Individual shader parameter for MTX materials"""

    name: StringProperty(name="Parameter Name")  # type: ignore
    param_type: EnumProperty(
        name="Type",
        items=[
            ("EPT_F32", "Float", "Single float value"),
            ("EPT_S32", "Integer", "Single integer value"),
            ("EPT_VEC4", "Vector4", "Four float values"),
            ("EPT_TEXTURE", "Texture", "Texture path"),
            ("EPT_BOOL", "Boolean", "Boolean value"),
        ],
    )  # type: ignore

    enabled: BoolProperty(name="Include", default=True)  # type: ignore

    # Value storage for different types
    float_value: FloatProperty(name="Value")  # type: ignore
    int_value: bpy.props.IntProperty(name="Value")  # type: ignore
    vec4_value: bpy.props.FloatVectorProperty(name="Value", size=4)  # type: ignore
    texture_value: StringProperty(
        name="Texture Path",
        description="Texture file path (relative to .blend file by default)",
        update=texture_value_update,
    )  # type: ignore
    bool_value: BoolProperty(name="Value")  # type: ignore


class MTXDefine(bpy.types.PropertyGroup):
    """Shader define for MTX materials"""

    name: StringProperty(name="Define Name")  # type: ignore
    enabled: BoolProperty(name="Enabled", default=False)  # type: ignore


class MTXMaterialSettings(bpy.types.PropertyGroup):
    """MTX material settings attached to Blender materials"""

    # Material name (auto-synced with Blender material)
    material_name: StringProperty(
        name="MTX Name",
        description="Material name in MTX file (auto-synced with material name)",
        get=lambda self: (
            sanitize(bpy.context.material.name).upper() if bpy.context.material else ""
        ),
    )  # type: ignore

    # Export format
    export_as_bmt: BoolProperty(
        name="Export as BMT",
        description="Export material as binary BMT format instead of XML MTX",
        default=False
    )  # type: ignore

    # Override path functionality
    use_override_path: BoolProperty(
        name="Use Override Path",
        description="Use a premade MTX or BMT file instead of generating from UI settings",
        default=False
    )  # type: ignore

    override_path: StringProperty(
        name="Override File Path",
        description="Path to premade MTX or BMT file (BMT paths must end with .mtx)",
        subtype="FILE_PATH",
        default=""
    )  # type: ignore

    shader_path: EnumProperty(
        name="Shader",
        description="Shader file path",
        items=get_shader_items,
        default=0,
        update=update_shader_change,
    )  # type: ignore

    technique: EnumProperty(
        name="Technique",
        description="Shader technique",
        items=get_technique_items,
        update=update_shader_params,
    )  # type: ignore

    # Material flags
    supports_specialised_lighting: BoolProperty(
        name="Supports Specialised Lighting", default=False
    )  # type: ignore

    fog: BoolProperty(name="Fog", default=False)  # type: ignore
    antialias: bpy.props.IntProperty(name="Antialias", default=1, min=0, max=8)  # type: ignore

    cull_mode: EnumProperty(
        name="Cull Mode",
        items=[
            ("EBFCT_ANTICLOCKWISE", "Anticlockwise", "Cull anticlockwise faces"),
            ("EBFCT_CLOCKWISE", "Clockwise", "Cull clockwise faces"),
            ("EBFCT_NONE", "None", "No culling"),
        ],
        default="EBFCT_ANTICLOCKWISE",
    )  # type: ignore

    # Depth parameters
    depth_enabled: BoolProperty(name="Depth Test", default=True)  # type: ignore
    depth_write_enabled: BoolProperty(name="Depth Write", default=True)  # type: ignore

    # Alpha blend parameters
    alpha_blend_enabled: BoolProperty(name="Alpha Blend", default=False)  # type: ignore

    # Collections for dynamic parameters and defines
    shader_params: CollectionProperty(type=MTXShaderParam)  # type: ignore
    defines: CollectionProperty(type=MTXDefine)  # type: ignore

    # Active indices for UI lists
    active_param_index: bpy.props.IntProperty()  # type: ignore
    active_define_index: bpy.props.IntProperty()  # type: ignore


# UI Lists for parameters and defines
class MTX_UL_shader_params(bpy.types.UIList):
    """UI List for shader parameters"""

    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname
    ):
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            row = layout.row(align=True)
            shader = data.shader_path if hasattr(data, "shader_path") else ""
            technique = data.technique if hasattr(data, "technique") else ""
            required = is_param_required(shader, technique, item.name)

            toggle_col = row.column(align=True)
            toggle_col.enabled = not required
            toggle_col.prop(item, "enabled", text="")

            display_name = f"(Req.) {item.name}" if required else item.name or "<unnamed>"
            row.label(text=display_name)
            row.label(text=item.param_type)
            
            # Add copy button on the right
            if len(context.selected_objects) > 1:
                # Find the parameter index for this item
                param_index = -1
                for i, param in enumerate(data.shader_params):
                    if param == item:
                        param_index = i
                        break
                        
                if param_index >= 0:
                    op = row.operator("mtx.copy_param_to_selected", text="", icon="COPYDOWN")
                    op.param_index = param_index
                    
        elif self.layout_type in {"GRID"}:
            layout.alignment = "CENTER"
            layout.label(text="", icon="MATERIAL")


class MTX_UL_defines(bpy.types.UIList):
    """UI List for shader defines"""

    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname
    ):
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            row = layout.row(align=True)
            shader = data.shader_path if hasattr(data, "shader_path") else ""
            technique = data.technique if hasattr(data, "technique") else ""
            required = is_define_required(shader, technique, item.name)

            toggle_col = row.column(align=True)
            toggle_col.enabled = not required
            toggle_col.prop(item, "enabled", text="")

            display_name = f"(Req.) {item.name}" if required else item.name or "<unnamed>"
            row.label(text=display_name)
            
            # Add copy button on the right
            if len(context.selected_objects) > 1:
                # Find the define index for this item
                define_index = -1
                for i, define in enumerate(data.defines):
                    if define == item:
                        define_index = i
                        break
                        
                if define_index >= 0:
                    op = row.operator("mtx.copy_define_to_selected", text="", icon="COPYDOWN")
                    op.define_index = define_index
                    
        elif self.layout_type in {"GRID"}:
            layout.alignment = "CENTER"
            layout.label(text="", icon="CHECKMARK" if item.enabled else "X")


# Material Properties Panel
class MTX_PT_material_settings(bpy.types.Panel):
    """MTX Material Settings Panel"""

    bl_label = "Madness MTX Settings"
    bl_idname = "MTX_PT_material_settings"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return context.material is not None

    def draw(self, context):
        layout = self.layout
        material = context.material

        if not hasattr(material, "mtx_settings"):
            layout.label(text="MTX settings not available")
            return

        mtx = material.mtx_settings

        # Basic settings
        box = layout.box()
        box.label(text="Basic Settings", icon="MATERIAL")

        # Show material name (read-only, auto-synced)
        row = box.row()
        row.label(text="MTX Name:")
        row.label(text=mtx.material_name)

        # Export format option
        box.prop(mtx, "export_as_bmt")

        # Override path settings
        override_box = box.box()
        override_box.prop(mtx, "use_override_path")
        if mtx.use_override_path:
            col = override_box.column()
            
            # File path input
            col.prop(mtx, "override_path", text="File Path")
            
            # Show validation and status info
            if mtx.override_path:
                is_valid, file_type, error_msg, target_ext = validate_override_path(mtx.override_path)
                
                if is_valid:
                    if file_type == "BMT":
                        col.label(text="BMT file", icon="CHECKMARK")
                    elif file_type == "MTX":
                        col.label(text="MTX file", icon="CHECKMARK")
                    else:
                        col.label(text="Valid file", icon="CHECKMARK")
                else:
                    col.label(text=f"{error_msg}", icon="ERROR")
            else:
                col.label(text="Please select an MTX or BMT file", icon="INFO")
        else:
            # Only show shader settings when not using override
            box.prop(mtx, "shader_path")
            box.prop(mtx, "technique")

        # Material flags (only show when not using override)
        if not mtx.use_override_path:
            col = box.column()
            col.prop(mtx, "supports_specialised_lighting")
            col.prop(mtx, "fog")
            col.prop(mtx, "antialias")
            col.prop(mtx, "cull_mode")

            # Depth and alpha settings
            row = box.row()
            subcol = row.column()
            subcol.label(text="Depth:")
            subcol.prop(mtx, "depth_enabled")
            subcol.prop(mtx, "depth_write_enabled")

            subcol = row.column()
            subcol.label(text="Alpha:")
            subcol.prop(mtx, "alpha_blend_enabled")


class MTX_PT_shader_parameters(bpy.types.Panel):
    """MTX Shader Parameters Panel"""

    bl_label = "Shader Parameters"
    bl_idname = "MTX_PT_shader_parameters"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_parent_id = "MTX_PT_material_settings"

    @classmethod
    def poll(cls, context):
        if not context.material or not hasattr(context.material, "mtx_settings"):
            return False
        return not context.material.mtx_settings.use_override_path

    def draw(self, context):
        layout = self.layout
        material = context.material

        if not hasattr(material, "mtx_settings"):
            layout.label(text="MTX settings not available")
            return

        mtx = material.mtx_settings

        # Parameters list
        row = layout.row()
        row.template_list(
            "MTX_UL_shader_params",
            "",
            mtx,
            "shader_params",
            mtx,
            "active_param_index",
            rows=len(mtx.shader_params),
        )

        # Parameter value editor
        if mtx.shader_params and mtx.active_param_index < len(mtx.shader_params):
            param = mtx.shader_params[mtx.active_param_index]
            box = layout.box()
            
            box.label(text=f"Type: {param.param_type}")

            # Show observed statistics if available
            stats = get_param_stats(mtx.shader_path, mtx.technique, param.name)
            if stats:
                if param.param_type == "EPT_F32":
                    stats_line = []
                    if stats.get("floatMin") is not None:
                        stats_line.append(f"min {stats['floatMin']:.2f}")
                    if stats.get("floatMax") is not None:
                        stats_line.append(f"max {stats['floatMax']:.2f}")
                    if stats.get("floatAvg") is not None:
                        stats_line.append(f"avg {stats['floatAvg']:.2f}")
                    if stats.get("floatMedian") is not None:
                        stats_line.append(f"med {stats['floatMedian']:.2f}")
                    if stats_line:
                        box.label(text="Stats: " + ", ".join(stats_line))
                elif param.param_type == "EPT_VEC4":
                    if stats.get("vec4Avg") is not None:
                        avg = stats["vec4Avg"]
                        box.label(text=f"Avg: ({avg[0]:.2f}, {avg[1]:.2f}, {avg[2]:.2f}, {avg[3]:.2f})")
                    if stats.get("vec4Median") is not None:
                        med = stats["vec4Median"]
                        box.label(text=f"Med: ({med[0]:.2f}, {med[1]:.2f}, {med[2]:.2f}, {med[3]:.2f})")

            if param.param_type == "EPT_F32":
                box.prop(param, "float_value", text="Value")
            elif param.param_type == "EPT_S32":
                box.prop(param, "int_value", text="Value")
            elif param.param_type == "EPT_VEC4":
                box.prop(param, "vec4_value", text="Value")
            elif param.param_type == "EPT_TEXTURE":
                col = box.column()
                col.prop(param, "texture_value", text="DDS File")

                button_row = col.row(align=True)
                browse_op = button_row.operator(
                    "mtx.pick_texture", text="Browse...", icon="FILE_FOLDER"
                )
                browse_op.param_index = mtx.active_param_index

                clear_row = button_row.row(align=True)
                clear_row.enabled = bool(param.texture_value)
                clear_op = clear_row.operator("mtx.clear_texture", text="Clear", icon="X")
                clear_op.param_index = mtx.active_param_index

                # Show preview info if texture is set
                if param.texture_value:
                    resolved_path, exists = resolve_texture_path(
                        param.texture_value, context
                    )
                    original_path = Path(param.texture_value)

                    if exists and resolved_path:
                        col.label(
                            text=f"Found: {resolved_path.name}", icon="CHECKMARK"
                        )
                        col.label(
                            text=f"Size: {resolved_path.stat().st_size / 1024:.1f} KB"
                        )
                    else:
                        col.label(
                            text=f"Not found: {original_path.name}", icon="ERROR"
                        )
                        if not original_path.is_absolute():
                            col.label(
                                text="(Try absolute path or relative to .blend file)"
                            )

                # Clear button
                # (Handled by button row above)
            elif param.param_type == "EPT_BOOL":
                box.prop(param, "bool_value", text="Value")


class MTX_PT_shader_defines(bpy.types.Panel):
    """MTX Shader Defines Panel"""

    bl_label = "Shader Defines"
    bl_idname = "MTX_PT_shader_defines"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_parent_id = "MTX_PT_material_settings"

    @classmethod
    def poll(cls, context):
        if not context.material or not hasattr(context.material, "mtx_settings"):
            return False
        return not context.material.mtx_settings.use_override_path

    def draw(self, context):
        layout = self.layout
        material = context.material

        if not hasattr(material, "mtx_settings"):
            layout.label(text="MTX settings not available")
            return

        mtx = material.mtx_settings

        # Defines list
        layout.template_list(
            "MTX_UL_defines", "", mtx, "defines", mtx, "active_define_index", rows=len(mtx.defines)
        )


# MTX File I/O Functions
def write_mtx_file(material, filepath: Path, track_name: str = None, texture_mapping: dict = None):
    """Write MTX file from Blender material settings
    
    Args:
        material: Blender material with mtx_settings
        filepath: Path to write MTX file to
        track_name: Name of the track (optional)
        texture_mapping: Dict mapping (material_name, param_name) to (resolved_src_path, game_relative_path)
    """
    if not hasattr(material, "mtx_settings"):
        raise RuntimeError(f"Material {material.name} has no MTX settings")

    mtx = material.mtx_settings

    # Use the actual material name (sanitized)
    material_name = sanitize(material.name).upper()

    # Count enabled parameters - include all enabled parameters regardless of texture value
    enabled_params = [p for p in mtx.shader_params if p.enabled]

    # Sort parameters by type: floats, then bools, then textures
    param_order = {"EPT_F32": 0, "EPT_VEC4": 1, "EPT_BOOL": 2, "EPT_TEXTURE": 3}
    enabled_params.sort(key=lambda p: param_order.get(p.param_type, 4))

    # Create material element
    material_elem = ET.Element(
        "material",
        VERSION="v1.0.0.1",
        name=material_name,
        shader=mtx.shader_path,
        technique=mtx.technique,
        supportsSpecialisedLighting=str(mtx.supports_specialised_lighting).lower(),
        fog=str(mtx.fog).lower(),
        antialias=str(mtx.antialias),
        numparams=str(len(enabled_params)),
        cull=mtx.cull_mode,
    )

    # Add shader parameters
    for param in enabled_params:
        param_elem = ET.SubElement(
            material_elem, "shaderparam", name=param.name, type=param.param_type
        )

        if param.param_type == "EPT_F32":
            value_elem = ET.SubElement(param_elem, "value", v=str(param.float_value))
        elif param.param_type == "EPT_S32":
            value_elem = ET.SubElement(param_elem, "value", v=str(param.int_value))
        elif param.param_type == "EPT_VEC4":
            vec_str = f"{param.vec4_value[0]} {param.vec4_value[1]} {param.vec4_value[2]} {param.vec4_value[3]}"
            value_elem = ET.SubElement(param_elem, "value", v=vec_str)
        elif param.param_type == "EPT_TEXTURE":
            type_elem = ET.SubElement(param_elem, "type", t="ET_STANDARD")

            # Use game-relative path from texture_mapping if available, otherwise use param value as-is
            texture_path = ""
            if texture_mapping:
                key = (sanitize(material.name), param.name)
                if key in texture_mapping:
                    _, game_path = texture_mapping[key]
                    texture_path = game_path
                else:
                    texture_path = param.texture_value if param.texture_value else ""
            else:
                texture_path = param.texture_value if param.texture_value else ""

            value_elem = ET.SubElement(param_elem, "value", v=texture_path)
        elif param.param_type == "EPT_BOOL":
            value_elem = ET.SubElement(
                param_elem, "value", v=str(param.bool_value).lower()
            )

    # Add depth parameters
    depth_elem = ET.SubElement(material_elem, "depthparams")
    ET.SubElement(depth_elem, "enabled", e=str(mtx.depth_enabled).lower())
    ET.SubElement(depth_elem, "writeenabled", w=str(mtx.depth_write_enabled).lower())

    # Add alpha blend parameters
    alpha_elem = ET.SubElement(material_elem, "alphablendparams")
    ET.SubElement(alpha_elem, "enabled", e=str(mtx.alpha_blend_enabled).lower())

    # Add shader defines
    normalized_shader_path = mtx.shader_path.replace("\\\\", "\\")

    if (
        normalized_shader_path in SHADER_DEFINES
        and mtx.technique in SHADER_DEFINES[normalized_shader_path]
    ):
        predefined_order = SHADER_DEFINES[normalized_shader_path][mtx.technique]
        enabled_defines_map = {d.name: d for d in mtx.defines if d.enabled}

        for define_name in predefined_order:
            if define_name in enabled_defines_map:
                ET.SubElement(material_elem, "define", name=define_name)

    # Write file
    ET.indent(material_elem, space="  ", level=0)
    tree = ET.ElementTree(material_elem)
    with open(filepath, "wb") as f:
        tree.write(f, encoding="utf-8", xml_declaration=False)
        f.write(b"\n")


def read_mtx_file(filepath: Path, material):
    """Read MTX file and populate Blender material settings"""
    if not filepath.exists():
        return

    if not hasattr(material, "mtx_settings"):
        return

    tree = ET.parse(filepath)
    root = tree.getroot()

    mtx = material.mtx_settings

    # Read basic attributes
    mtx.shader_path = root.get("shader", "Render\\Shaders\\basic.fx")
    mtx.technique = root.get("technique", "Basic")

    # Validate technique
    if mtx.shader_path in SHADER_TECHNIQUES:
        valid_techniques = SHADER_TECHNIQUES[mtx.shader_path]
        if mtx.technique not in valid_techniques:
            mtx.technique = valid_techniques[0] if valid_techniques else "Basic"

    # Update other properties
    mtx.supports_specialised_lighting = (
        root.get("supportsSpecialisedLighting", "false").lower() == "true"
    )
    mtx.fog = root.get("fog", "false").lower() == "true"
    mtx.antialias = int(root.get("antialias", "1"))
    mtx.cull_mode = root.get("cull", "EBFCT_ANTICLOCKWISE")

    # Initialize parameters and defines
    update_shader_change(mtx, bpy.context)

    # No longer using hardcoded game folder for texture resolution

    # Read shader parameters
    found_params = set()
    for shaderparam in root.findall("shaderparam"):
        param_name = shaderparam.get("name")
        param_type = shaderparam.get("type")
        found_params.add(param_name)

        for param in mtx.shader_params:
            if param.name == param_name:
                param.enabled = True
                value_elem = shaderparam.find("value")
                if value_elem is not None:
                    value_str = value_elem.get("v", "")

                    if param_type == "EPT_F32":
                        try:
                            param.float_value = float(value_str)
                        except ValueError:
                            pass
                    elif param_type == "EPT_S32":
                        try:
                            param.int_value = int(value_str)
                        except ValueError:
                            pass
                    elif param_type == "EPT_VEC4":
                        try:
                            values = [float(x) for x in value_str.split()]
                            if len(values) >= 4:
                                param.vec4_value = values[:4]
                        except ValueError:
                            pass
                    elif param_type == "EPT_TEXTURE":
                        param.texture_value = value_str
                    elif param_type == "EPT_BOOL":
                        param.bool_value = value_str.lower() == "true"
                break

    # Disable parameters not in file
    for param in mtx.shader_params:
        if param.name not in found_params:
            param.enabled = False

    # Read depth parameters
    depth_elem = root.find("depthparams")
    if depth_elem is not None:
        enabled_elem = depth_elem.find("enabled")
        if enabled_elem is not None:
            mtx.depth_enabled = enabled_elem.get("e", "true").lower() == "true"

        write_elem = depth_elem.find("writeenabled")
        if write_elem is not None:
            mtx.depth_write_enabled = write_elem.get("w", "true").lower() == "true"

    # Read alpha blend parameters
    alpha_elem = root.find("alphablendparams")
    if alpha_elem is not None:
        enabled_elem = alpha_elem.find("enabled")
        if enabled_elem is not None:
            mtx.alpha_blend_enabled = enabled_elem.get("e", "false").lower() == "true"

    # Read defines
    found_defines = set()
    for define_elem in root.findall("define"):
        define_name = define_elem.get("name")
        if define_name:
            found_defines.add(define_name)

    # Enable defines found in file
    for define in mtx.defines:
        define.enabled = define.name in found_defines


# Operators for MTX operations
class MTX_OT_load_mtx(bpy.types.Operator):
    """Load MTX file into material"""

    bl_idname = "mtx.load_mtx"
    bl_label = "Load MTX"
    bl_description = "Load MTX file into current material"

    filepath: StringProperty(subtype="FILE_PATH")  # type: ignore

    def execute(self, context):
        if context.material:
            try:
                read_mtx_file(Path(self.filepath), context.material)
                self.report({"INFO"}, f"Loaded MTX: {Path(self.filepath).name}")
            except Exception as e:
                self.report({"ERROR"}, f"Failed to load MTX: {str(e)}")
        else:
            self.report({"ERROR"}, "No active material")
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


class MTX_OT_save_mtx(bpy.types.Operator):
    """Save material as MTX file"""

    bl_idname = "mtx.save_mtx"
    bl_label = "Save MTX"
    bl_description = "Save current material as MTX file"

    filepath: StringProperty(subtype="FILE_PATH")  # type: ignore

    def execute(self, context):
        if context.material:
            try:
                filepath = Path(self.filepath)
                if not filepath.suffix:
                    filepath = filepath.with_suffix(".mtx")
                write_mtx_file(context.material, filepath)
                self.report({"INFO"}, f"Saved MTX: {filepath.name}")
            except Exception as e:
                self.report({"ERROR"}, f"Failed to save MTX: {str(e)}")
        else:
            self.report({"ERROR"}, "No active material")
        return {"FINISHED"}

    def invoke(self, context, event):
        if context.material:
            material_name = sanitize(context.material.name).upper()
            self.filepath = f"{material_name}.mtx"
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


class MTX_OT_pick_texture(bpy.types.Operator):
    """Pick DDS texture file"""

    bl_idname = "mtx.pick_texture"
    bl_label = "Browse Texture"
    bl_description = "Select a DDS texture file"

    filepath: StringProperty(subtype="FILE_PATH")  # type: ignore
    filter_glob: StringProperty(default="*.dds", options={"HIDDEN"})  # type: ignore
    param_index: bpy.props.IntProperty(default=-1)  # type: ignore

    def _resolve_existing_path(self, path_value: str) -> Optional[Path]:
        import bpy  # type: ignore

        if not path_value:
            return None

        path_obj = Path(path_value)
        if path_obj.is_absolute():
            try:
                return path_obj.resolve()
            except OSError:
                return path_obj

        if bpy.data.filepath:
            blend_dir = Path(bpy.data.filepath).resolve().parent
            try:
                return (blend_dir / path_obj).resolve()
            except OSError:
                return blend_dir / path_obj

        return path_obj

    def invoke(self, context, event):
        import bpy  # type: ignore

        if context.material and hasattr(context.material, "mtx_settings"):
            mtx = context.material.mtx_settings
            index = self.param_index
            if index < 0 or index >= len(mtx.shader_params):
                index = mtx.active_param_index

            if 0 <= index < len(mtx.shader_params):
                param = mtx.shader_params[index]
                existing_path = self._resolve_existing_path(param.texture_value)

                if existing_path and existing_path.exists():
                    self.filepath = str(existing_path)
                elif bpy.data.filepath:
                    self.filepath = str(Path(bpy.data.filepath).resolve().parent)

                self.param_index = index

        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        import bpy  # type: ignore

        if context.material and hasattr(context.material, "mtx_settings"):
            mtx = context.material.mtx_settings
            index = self.param_index
            if index < 0 or index >= len(mtx.shader_params):
                index = mtx.active_param_index

            if 0 <= index < len(mtx.shader_params):
                param = mtx.shader_params[index]
                selected_path = Path(self.filepath)

                try:
                    normalized = selected_path.resolve()
                except OSError:
                    normalized = selected_path

                stored_value = str(normalized).replace("\\", "/")

                if bpy.data.filepath:
                    blend_dir = Path(bpy.data.filepath).resolve().parent
                    try:
                        relative_path = normalized.relative_to(blend_dir)
                        stored_value = str(relative_path).replace("\\", "/")
                        self.report({"INFO"}, f"Stored relative path: {relative_path}")
                    except ValueError:
                        self.report(
                            {"WARNING"},
                            "Texture is outside the blend directory; storing absolute path",
                        )

                param.texture_value = stored_value

        return {"FINISHED"}


class MTX_OT_clear_texture(bpy.types.Operator):
    """Clear selected texture"""

    bl_idname = "mtx.clear_texture"
    bl_label = "Clear Texture"
    bl_description = "Clear the selected texture path"

    param_index: bpy.props.IntProperty()  # type: ignore

    def execute(self, context):
        if context.material and hasattr(context.material, "mtx_settings"):
            mtx = context.material.mtx_settings
            if self.param_index < len(mtx.shader_params):
                param = mtx.shader_params[self.param_index]
                param.texture_value = ""
                self.report({"INFO"}, "Cleared texture path")
            else:
                self.report({"WARNING"}, "Invalid parameter index")
        return {"FINISHED"}


class MTX_OT_copy_param_to_selected(bpy.types.Operator):
    """Copy shader parameter to selected objects"""

    bl_idname = "mtx.copy_param_to_selected"
    bl_label = "Copy to Selected"
    bl_description = "Copy this parameter to materials in the same slot on selected objects"

    param_index: bpy.props.IntProperty()  # type: ignore

    def execute(self, context):
        if not context.material or not hasattr(context.material, "mtx_settings"):
            self.report({"ERROR"}, "No active material with MTX settings")
            return {"CANCELLED"}

        source_material = context.material
        source_mtx = source_material.mtx_settings
        
        if self.param_index >= len(source_mtx.shader_params):
            self.report({"ERROR"}, "Invalid parameter index")
            return {"CANCELLED"}

        source_param = source_mtx.shader_params[self.param_index]
        
        # Find the material slot index of the source material
        source_slot_index = None
        if context.object and context.object.material_slots:
            for i, slot in enumerate(context.object.material_slots):
                if slot.material == source_material:
                    source_slot_index = i
                    break
        
        if source_slot_index is None:
            self.report({"ERROR"}, "Could not find source material slot")
            return {"CANCELLED"}

        copied_count = 0
        
        # Copy to selected objects
        for obj in context.selected_objects:
            if obj == context.object:  # Skip source object
                continue
                
            if not obj.material_slots or len(obj.material_slots) <= source_slot_index:
                continue
                
            target_material = obj.material_slots[source_slot_index].material
            if not target_material or not hasattr(target_material, "mtx_settings"):
                continue
                
            target_mtx = target_material.mtx_settings
            
            # Find matching parameter by name and type
            for target_param in target_mtx.shader_params:
                if (target_param.name == source_param.name and 
                    target_param.param_type == source_param.param_type):
                    
                    # Copy all values
                    target_param.enabled = source_param.enabled
                    target_param.float_value = source_param.float_value
                    target_param.int_value = source_param.int_value
                    target_param.vec4_value = source_param.vec4_value
                    target_param.texture_value = source_param.texture_value
                    target_param.bool_value = source_param.bool_value
                    copied_count += 1
                    break

        if copied_count > 0:
            self.report({"INFO"}, f"Copied parameter '{source_param.name}' to {copied_count} objects")
        else:
            self.report({"WARNING"}, "No matching parameters found in selected objects")
            
        return {"FINISHED"}


class MTX_OT_copy_define_to_selected(bpy.types.Operator):
    """Copy shader define to selected objects"""

    bl_idname = "mtx.copy_define_to_selected"
    bl_label = "Copy to Selected"
    bl_description = "Copy this define to materials in the same slot on selected objects"

    define_index: bpy.props.IntProperty()  # type: ignore

    def execute(self, context):
        if not context.material or not hasattr(context.material, "mtx_settings"):
            self.report({"ERROR"}, "No active material with MTX settings")
            return {"CANCELLED"}

        source_material = context.material
        source_mtx = source_material.mtx_settings
        
        if self.define_index >= len(source_mtx.defines):
            self.report({"ERROR"}, "Invalid define index")
            return {"CANCELLED"}

        source_define = source_mtx.defines[self.define_index]
        
        # Find the material slot index of the source material
        source_slot_index = None
        if context.object and context.object.material_slots:
            for i, slot in enumerate(context.object.material_slots):
                if slot.material == source_material:
                    source_slot_index = i
                    break
        
        if source_slot_index is None:
            self.report({"ERROR"}, "Could not find source material slot")
            return {"CANCELLED"}

        copied_count = 0
        
        # Copy to selected objects
        for obj in context.selected_objects:
            if obj == context.object:  # Skip source object
                continue
                
            if not obj.material_slots or len(obj.material_slots) <= source_slot_index:
                continue
                
            target_material = obj.material_slots[source_slot_index].material
            if not target_material or not hasattr(target_material, "mtx_settings"):
                continue
                
            target_mtx = target_material.mtx_settings
            
            # Find matching define by name
            for target_define in target_mtx.defines:
                if target_define.name == source_define.name:
                    target_define.enabled = source_define.enabled
                    copied_count += 1
                    break

        if copied_count > 0:
            self.report({"INFO"}, f"Copied define '{source_define.name}' to {copied_count} objects")
        else:
            self.report({"WARNING"}, "No matching defines found in selected objects")
            
        return {"FINISHED"}


class MTX_PT_operations(bpy.types.Panel):
    """MTX Operations Panel"""

    bl_label = "MTX Operations"
    bl_idname = "MTX_PT_operations"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_parent_id = "MTX_PT_material_settings"

    def draw(self, context):
        layout = self.layout

        row = layout.row()
        row.operator("mtx.load_mtx", text="Load MTX")
        row.operator("mtx.save_mtx", text="Save MTX")


def register():
    bpy.utils.register_class(MTXShaderParam)
    bpy.utils.register_class(MTXDefine)
    bpy.utils.register_class(MTXMaterialSettings)
    bpy.utils.register_class(MTX_UL_shader_params)
    bpy.utils.register_class(MTX_UL_defines)
    bpy.utils.register_class(MTX_PT_material_settings)
    bpy.utils.register_class(MTX_PT_shader_parameters)
    bpy.utils.register_class(MTX_PT_shader_defines)
    bpy.utils.register_class(MTX_PT_operations)
    bpy.utils.register_class(MTX_OT_load_mtx)
    bpy.utils.register_class(MTX_OT_save_mtx)
    bpy.utils.register_class(MTX_OT_pick_texture)
    bpy.utils.register_class(MTX_OT_clear_texture)
    bpy.utils.register_class(MTX_OT_copy_param_to_selected)
    bpy.utils.register_class(MTX_OT_copy_define_to_selected)

    # Add MTX settings to materials
    bpy.types.Material.mtx_settings = PointerProperty(type=MTXMaterialSettings)


def unregister():
    del bpy.types.Material.mtx_settings

    bpy.utils.unregister_class(MTX_OT_copy_define_to_selected)
    bpy.utils.unregister_class(MTX_OT_copy_param_to_selected)
    bpy.utils.unregister_class(MTX_OT_clear_texture)
    bpy.utils.unregister_class(MTX_OT_pick_texture)
    bpy.utils.unregister_class(MTX_OT_save_mtx)
    bpy.utils.unregister_class(MTX_OT_load_mtx)
    bpy.utils.unregister_class(MTX_PT_operations)
    bpy.utils.unregister_class(MTX_PT_shader_defines)
    bpy.utils.unregister_class(MTX_PT_shader_parameters)
    bpy.utils.unregister_class(MTX_PT_material_settings)
    bpy.utils.unregister_class(MTX_UL_defines)
    bpy.utils.unregister_class(MTX_UL_shader_params)
    bpy.utils.unregister_class(MTXMaterialSettings)
    bpy.utils.unregister_class(MTXDefine)
    bpy.utils.unregister_class(MTXShaderParam)
