bl_info = {
    "name": "Madness Scene Exporter",
    "author": "Madness Scene Exporter",
    "description": "Export AMS2/PC2 SGXs, MEB/MTXs, auto-copy textures, generate AIW and trigger files, and Environment XML camera sets",
    "blender": (4, 0, 0),
    "version": (0, 1, 0),
    "location": "File > Export",
    "warning": "",
    "category": "Import-Export",
}

import bpy  # type: ignore
from bpy.props import StringProperty  # type: ignore
from bpy_extras.io_utils import ExportHelper  # type: ignore
from pathlib import Path
from .settings import meb_export_settings
from .materials import mtx_material_system
from .settings.settings_manager import (
    load_settings_from_file,
    save_settings_to_file,
    get_settings_file_path,
    get_exporter_path,
    get_addon_preferences,
)
from .aiw import aiw_export
from .export import livetrack_mrdf_export
from .export import triggers_export
from .settings import empty_meb_settings
from .properties import camera_properties
from .properties import area_properties
from .ui import camera_ui
from .properties import light_properties
from .ui import light_ui
from .properties import dynamic_properties
from .ui import dynamic_ui
from .export.exporter import export_madness_scene
from .export.environment_export import export_environment_xml
from .export.lights_export import export_lights_sgx
from .export.dynamic_export import export_dynamic_objects


# Module-level update functions that work with class registration
def _update_exporter_exe(self, context):
    """Update callback to sync with file."""
    if getattr(self, "_updating", False):
        return

    self._updating = True
    try:
        if self.exporter_exe and self.exporter_exe != "MEBExporterExtended.exe":
            # Only save to file, don't modify preferences (avoid recursion)
            settings = load_settings_from_file()
            settings["exporter_exe"] = self.exporter_exe
            save_settings_to_file(settings)
            print(f"Saved exporter path to settings file: {get_settings_file_path()}")
    finally:
        self._updating = False


class MadnessSceneExporterPreferences(bpy.types.AddonPreferences):
    """Addon preferences for Madness Scene Exporter"""

    bl_idname = __name__

    _updating = False  # Recursion guard

    exporter_exe: StringProperty(
        name="MEB Exporter Path",
        description="Path to MEBExporterExtended.exe",
        default="MEBExporterExtended.exe",
        subtype="FILE_PATH",
        update=_update_exporter_exe,
    )  # type: ignore

    def draw(self, context):
        layout = self.layout
        layout.label(text="Madness Scene Exporter Settings:")

        # Load current values from file if preferences are default
        if self.exporter_exe == "MEBExporterExtended.exe":
            settings = load_settings_from_file()
            if "exporter_exe" in settings:
                self._updating = True
                try:
                    self.exporter_exe = settings["exporter_exe"]
                finally:
                    self._updating = False

        layout.prop(self, "exporter_exe")

        # Show current effective paths
        exporter_path, exporter_source = get_exporter_path(context)

        layout.separator()
        layout.label(text=f"Current MEB Exporter: {exporter_path}")
        layout.label(text=f"  Source: {exporter_source}")

        # Validation
        if not Path(exporter_path).exists():
            layout.label(text="⚠ MEB Exporter not found!", icon="ERROR")

        # Manual sync button
        layout.separator()
        op = layout.operator("madness_scene.sync_settings", text="Sync Settings")


class MadnessSceneSyncSettings(bpy.types.Operator):
    """Sync settings between preferences and file"""

    bl_idname = "madness_scene.sync_settings"
    bl_label = "Sync Settings"
    bl_description = "Sync settings between preferences and development file"

    def execute(self, context):
        preferences, addon_name = get_addon_preferences(context)
        if preferences:
            # Save current preferences to file
            settings = load_settings_from_file()
            settings["exporter_exe"] = preferences.exporter_exe
            save_settings_to_file(settings)
            print(f"Synced settings: exporter={preferences.exporter_exe}")
            self.report({"INFO"}, "Settings synced")
        else:
            self.report({"WARNING"}, "Could not find preferences")
        return {"FINISHED"}


class MadnessSceneExporter(bpy.types.Operator, ExportHelper):
    """Export Scene Graph XML"""

    bl_idname = "export_scene.madness"
    bl_label = "Export Scene Graph"

    filename_ext = ".sgx"

    filter_glob: StringProperty(
        default="*.sgx",
        options={"HIDDEN"},
        maxlen=255,
    )  # type: ignore

    placeholder_mtx: StringProperty(
        name="Placeholder MTX",
        description="Path to template MTX file",
        default="S:\Assorted Project Files\Synced Projects\AMS2 Track RevEng\placeholder_grass.mtx",
        subtype="FILE_PATH",
    )  # type: ignore

    def execute(self, context):
        # Get exporter path using our robust system
        exporter_path, source = get_exporter_path(context)
        exporter_exe = Path(exporter_path)

        print(f"Debug: Using exporter from {source}: {exporter_exe}")

        if not exporter_exe.exists():
            self.report({"ERROR"}, f"MEB Exporter not found at: {exporter_exe}")
            return {"CANCELLED"}

        # Derive resource prefix from output filename
        output_path = Path(self.filepath)
        track_name = output_path.stem
        resource_prefix = f"tracks/{track_name}/"

        try:
            export_madness_scene(
                filepath=self.filepath,
                exporter_exe=exporter_exe,
                placeholder_mtx=Path(self.placeholder_mtx),
                resource_prefix=resource_prefix,
                context=context,
            )
            self.report({"INFO"}, "Madness scene exported successfully")
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, f"Export failed: {str(e)}")
            return {"CANCELLED"}

    def draw(self, context):
        layout = self.layout


class MadnessEnvironmentExporter(bpy.types.Operator, ExportHelper):
    """Export Environment XML"""

    bl_idname = "export_scene.madness_environment"
    bl_label = "Export Environment XML"

    filename_ext = ".xml"

    filter_glob: StringProperty(
        default="*.xml",
        options={"HIDDEN"},
        maxlen=255,
    )  # type: ignore

    def execute(self, context):
        try:
            camera_count, area_count = export_environment_xml(
                Path(self.filepath), context.scene
            )
            self.report(
                {"INFO"},
                f"Environment XML exported successfully: {camera_count} cameras, {area_count} areas",
            )
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, f"Environment XML export failed: {str(e)}")
            return {"CANCELLED"}


class MadnessLightsExporter(bpy.types.Operator, ExportHelper):
    """Export Lights SGX"""

    bl_idname = "export_scene.madness_lights"
    bl_label = "Export Lights SGX"

    filename_ext = ".sgx"

    filter_glob: StringProperty(
        default="*_lights.sgx",
        options={"HIDDEN"},
        maxlen=255,
    )  # type: ignore

    def execute(self, context):
        try:
            light_count = export_lights_sgx(self.filepath)
            self.report(
                {"INFO"}, f"Lights SGX exported successfully: {light_count} lights"
            )
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, f"Lights SGX export failed: {str(e)}")
            return {"CANCELLED"}


class MadnessDynamicObjectsExporter(bpy.types.Operator, ExportHelper):
    """Export Dynamic Objects (generates both dynamic_collisions.xml and env.xml)"""

    bl_idname = "export_scene.madness_dynamic"
    bl_label = "Export Dynamic Objects"

    filename_ext = ".xml"

    def draw(self, context):
        layout = self.layout

        # Add helpful information about what will be exported
        box = layout.box()
        box.label(text="Export Information:", icon="INFO")
        box.label(text="This will generate TWO files:")
        box.label(text="1. physics/dynamic_collisions.xml (collision meshes)")
        box.label(text="2. _data/dynamic/physics/[track].env.xml (object placements)")
        box.separator()
        box.label(
            text="Choose any filename - the paths will be determined automatically"
        )
        box.label(text="based on the track structure.")

    def execute(self, context):
        try:
            results = export_dynamic_objects(self.filepath)

            if results["collisions"] == 0 and results["environment"] == 0:
                self.report(
                    {"WARNING"},
                    "No SMS_DYN objects found in scene. Create empties named SMS_DYN_[name] first.",
                )
                return {"CANCELLED"}

            # Create a success message with actual file paths
            message = (
                f"Dynamic objects exported successfully! "
                f"{results['collisions']} templates, {results['environment']} instances. "
                f"Files: {results.get('collisions_path', 'N/A')} and {results.get('env_path', 'N/A')}"
            )

            self.report({"INFO"}, message)
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, f"Dynamic objects export failed: {str(e)}")
            return {"CANCELLED"}


def menu_func_export(self, context):
    self.layout.operator(
        MadnessSceneExporter.bl_idname, text="Madness Scene (.sgx, .meb, .mtx)"
    )
    self.layout.operator(
        MadnessEnvironmentExporter.bl_idname, text="Madness Cameras (.xml)"
    )
    self.layout.operator(
        MadnessLightsExporter.bl_idname, text="Madness Lights (_lights.sgx)"
    )
    self.layout.operator(
        MadnessDynamicObjectsExporter.bl_idname,
        text="Madness Dynamic Objects (collision & env)",
    )


def register():
    meb_export_settings.register()
    mtx_material_system.register()
    empty_meb_settings.register()
    aiw_export.register()
    livetrack_mrdf_export.register()
    triggers_export.register()
    camera_properties.register()
    area_properties.register()
    camera_ui.register()
    light_properties.register()
    light_ui.register()
    dynamic_properties.register()
    dynamic_ui.register()

    main_classes = [
        MadnessSceneExporterPreferences,
        MadnessSceneSyncSettings,
        MadnessSceneExporter,
        MadnessEnvironmentExporter,
        MadnessLightsExporter,
        MadnessDynamicObjectsExporter,
    ]

    for cls in main_classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            # Already registered, unregister and re-register
            bpy.utils.unregister_class(cls)
            bpy.utils.register_class(cls)

    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)

    main_classes = [
        MadnessDynamicObjectsExporter,
        MadnessLightsExporter,
        MadnessEnvironmentExporter,
        MadnessSceneExporter,
        MadnessSceneSyncSettings,
        MadnessSceneExporterPreferences,
    ]

    for cls in main_classes:
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass  # Already unregistered

    dynamic_ui.unregister()
    dynamic_properties.unregister()
    light_ui.unregister()
    light_properties.unregister()
    camera_ui.unregister()
    area_properties.unregister()
    camera_properties.unregister()
    triggers_export.unregister()
    livetrack_mrdf_export.unregister()
    aiw_export.unregister()
    empty_meb_settings.unregister()
    mtx_material_system.unregister()
    meb_export_settings.unregister()


if __name__ == "__main__":
    register()
