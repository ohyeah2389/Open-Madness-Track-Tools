import bpy
from pathlib import Path
from bpy.props import StringProperty, PointerProperty, FloatProperty, BoolVectorProperty


class EmptyMEBSettings(bpy.types.PropertyGroup):
    """MEB file reference settings for Empty objects"""

    meb_file_path: StringProperty(
        name="MEB File Path",
        description="Path to MEB file relative to game installation",
        default="",
        subtype="FILE_PATH",
    )  # type: ignore

    sphere_radius: FloatProperty(
        name="Sphere Radius",
        description="Bounding sphere radius for the MEB object",
        default=10.0,
        min=0.1,
        max=1000.0,
    )  # type: ignore

    # Userflags - 32-bit bitmask for SGX object flags
    userflags: BoolVectorProperty(
        name="User Flags",
        description="32-bit bitmask for SGX object userflags",
        size=32,
        default=[False] * 32,
    )  # type: ignore


def get_empty_userflags_value(settings) -> int:
    """Convert userflags boolean vector to integer value."""
    value = 0
    for i, flag in enumerate(settings.userflags):
        if flag:
            value |= 1 << i
    return value


def convert_to_relative_game_path(absolute_path: str, game_folder: str = None) -> str:
    """Convert absolute path to relative game path format for MEB files.

    Args:
        absolute_path: Full path like "G:\SteamLibrary\steamapps\common\Automobilista 2\tracks\_data\instances\..."
        game_folder: Game installation folder (optional, will try to detect)

    Returns:
        Relative path like "tracks/_data/instances/..." (forward slashes, no leading slash)
    """
    if not absolute_path:
        return ""

    path = Path(absolute_path)
    path_str = str(path)

    # If we have a game folder, use it for conversion
    if game_folder:
        game_path = Path(game_folder)
        try:
            # Get relative path from game folder
            rel_path = path.relative_to(game_path)
            return str(rel_path).replace("\\", "/")
        except ValueError:
            # Path is not relative to game folder, continue with auto-detection
            pass

    # Convert to forward slashes for easier processing
    path_parts = Path(path_str).parts

    # PRIORITY 1: Look for "tracks" folder specifically (handles extracted files)
    # This should catch cases like "S:\...\Extracted\tracks\_data\..."
    tracks_index = -1
    for i, part in enumerate(path_parts):
        if part.lower() == "tracks":
            tracks_index = i
            break

    if tracks_index >= 0:
        # Get everything from "tracks" onwards
        relative_parts = path_parts[tracks_index:]
        return "/".join(relative_parts)

    # PRIORITY 2: Auto-detect game folder by looking for common patterns
    # Look for "Automobilista 2" or similar game folder patterns
    game_folder_candidates = [
        "Automobilista 2",
        "Automobilista2",
        "AMS2",
        "Project CARS 2",
        "ProjectCARS2",
        "PC2",
    ]

    game_folder_index = -1
    for i, part in enumerate(path_parts):
        if any(
            candidate.lower() in part.lower() for candidate in game_folder_candidates
        ):
            game_folder_index = i
            break

    if game_folder_index >= 0:
        # Get everything after the game folder
        relative_parts = path_parts[game_folder_index + 1 :]
        if relative_parts:
            return "/".join(relative_parts)

    # PRIORITY 3: Look for _data folder pattern (common in extracted files)
    # This handles cases where tracks folder might be missing but we have _data
    for i, part in enumerate(path_parts):
        if part.lower() == "_data":
            # Reconstruct as tracks/_data/...
            remaining_parts = path_parts[i:]
            return "tracks/" + "/".join(remaining_parts)

    # If all else fails, return the filename with a warning prefix
    return "UNKNOWN_PATH/" + path.name


class EMPTY_PT_meb_reference(bpy.types.Panel):
    """MEB Reference Panel for Empty objects"""

    bl_label = "Madness MEB Asset Reference"
    bl_idname = "EMPTY_PT_meb_reference"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "data"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        # Only show when we have an empty object selected
        return context.object and context.object.type == "EMPTY"

    def draw(self, context):
        layout = self.layout
        obj = context.object

        if not hasattr(obj, "empty_meb_settings"):
            layout.label(text="MEB reference settings not available")
            return

        settings = obj.empty_meb_settings

        # MEB file path input
        box = layout.box()
        box.label(text="MEB Asset Reference", icon="LINK_BLEND")

        col = box.column()
        col.prop(settings, "meb_file_path", text="MEB File")

        # Show sphere radius setting
        col.separator()
        radius_row = col.row()
        radius_row.label(text="Sphere Radius:")
        radius_row.prop(settings, "sphere_radius", text="")

        # User Flags - 32-bit bitmask
        box = layout.box()
        box.label(text="User Flags (32-bit bitmask)", icon="SETTINGS")

        # Show the current value in both binary and decimal
        userflags_value = get_empty_userflags_value(settings)
        binary_str = format(userflags_value, "032b")
        box.label(text=f"Value: {userflags_value} (0b{binary_str})")

        # Create a 4x8 grid of checkboxes for the 32 bits
        for row in range(4):
            row_layout = box.row()
            for col_idx in range(8):
                bit_index = row * 8 + col_idx
                row_layout.prop(
                    settings, "userflags", index=bit_index, text=f"{bit_index}"
                )

        # Show path conversion preview
        if settings.meb_file_path:
            converted_path = convert_to_relative_game_path(settings.meb_file_path)

            col.separator()
            col.label(text="Export Path Preview:")
            if converted_path.startswith("UNKNOWN_PATH/"):
                col.label(text=converted_path, icon="ERROR")
                col.label(text="⚠ Could not auto-detect path pattern!")
                col.label(text="Ensure path contains 'tracks' or game folder.")
            else:
                col.label(text=converted_path, icon="CHECKMARK")

        # Copy to selected button
        if len(context.selected_objects) > 1:
            col.separator()
            op = col.operator("object.copy_empty_meb_settings", text="Copy To Selected")


class OBJECT_OT_copy_empty_meb_settings(bpy.types.Operator):
    """Copy Empty MEB settings to selected objects"""

    bl_idname = "object.copy_empty_meb_settings"
    bl_label = "Copy MEB Settings"
    bl_description = "Copy MEB reference settings to all selected Empty objects"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return (
            context.object
            and context.object.type == "EMPTY"
            and len(context.selected_objects) > 1
        )

    def execute(self, context):
        active_obj = context.object
        if not hasattr(active_obj, "empty_meb_settings"):
            self.report({"ERROR"}, "Active object has no MEB settings")
            return {"CANCELLED"}

        source_settings = active_obj.empty_meb_settings
        copied_count = 0

        for obj in context.selected_objects:
            if obj != active_obj and obj.type == "EMPTY":
                if hasattr(obj, "empty_meb_settings"):
                    target_settings = obj.empty_meb_settings
                    # Copy MEB properties
                    target_settings.meb_file_path = source_settings.meb_file_path
                    target_settings.sphere_radius = source_settings.sphere_radius
                    # Copy userflags
                    for i in range(32):
                        target_settings.userflags[i] = source_settings.userflags[i]
                    copied_count += 1

        self.report({"INFO"}, f"Copied MEB settings to {copied_count} objects")
        return {"FINISHED"}


def register():
    bpy.utils.register_class(EmptyMEBSettings)
    bpy.utils.register_class(EMPTY_PT_meb_reference)
    bpy.utils.register_class(OBJECT_OT_copy_empty_meb_settings)

    # Add MEB settings to Empty objects
    bpy.types.Object.empty_meb_settings = PointerProperty(type=EmptyMEBSettings)


def unregister():
    del bpy.types.Object.empty_meb_settings

    bpy.utils.unregister_class(OBJECT_OT_copy_empty_meb_settings)
    bpy.utils.unregister_class(EMPTY_PT_meb_reference)
    bpy.utils.unregister_class(EmptyMEBSettings)
