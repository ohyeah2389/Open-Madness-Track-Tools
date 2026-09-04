bl_info = {
    "name": "OMTT TrackCompiler",
    "author": "ohyeah2389",
    "description": "Implements export of Madness Engine (AMS2/PC2) track data files of various types.",
    "blender": (4, 0, 0),
    "version": (0, 1, 0),
    "location": "File > Export",
    "warning": "",
    "category": "Import-Export",
}

from pathlib import Path

import bpy  # type: ignore
from bpy.props import BoolProperty, EnumProperty, StringProperty  # type: ignore
from bpy_extras.io_utils import ExportHelper  # type: ignore

from .aiw import export as aiw_export
from .export import livetrack_mrdf_export
from .export import triggers_export
from .export.dynamic_export import export_dynamic_objects
from .export.environment_export import export_environment_xml
from .export.sgx_export import (
    PurgeError,
    SingleMebExportSettings,
    collect_purge_targets,
    export_madness_scene,
    export_single_meb_set,
    validate_purge_request,
)
from .export.gcl_export import export_gcl
from .export.lights_export import export_lights_sgx
from .export.sound_export import export_sounds
from .materials import mtx_material_system
from .properties import area, camera, dynamic, light, lod, sound
from .settings import meb_export_settings
from .settings import empty_meb_settings
from .ui import camera_ui
from .ui import light_ui
from .ui import dynamic_ui
from .ui import lod_ui
from .ui import sound_ui


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

    export_mtx_files: BoolProperty(
        name="Export MTX Files",
        description="Write MTX material files next to the exported SGX and MEB files",
        default=True,
    )  # type: ignore

    purge_mtx: BoolProperty(
        name="Purge MTX",
        description="Delete leftover .mtx files in the SGX export folder before writing new ones",
        default=False,
        options={"SKIP_SAVE"},
    )  # type: ignore

    purge_meb: BoolProperty(
        name="Purge MEB",
        description="Delete leftover .meb files in the SGX export folder before writing new ones",
        default=False,
        options={"SKIP_SAVE"},
    )  # type: ignore

    purge_dds: BoolProperty(
        name="Purge DDS",
        description="Delete leftover .dds files in the track textures folder before copying new ones",
        default=False,
        options={"SKIP_SAVE"},
    )  # type: ignore

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "export_mtx_files")
        layout.separator()
        layout.prop(self, "purge_mtx")
        layout.prop(self, "purge_meb")
        layout.prop(self, "purge_dds")
        if not (self.purge_mtx or self.purge_meb or self.purge_dds):
            return
        box = layout.box()
        box.alert = True
        box.label(text="Permanent delete, cannot be undone")
        if not self.filepath:
            box.label(text="Choose the SGX path first")
            return
        try:
            track_dir, texture_dir = validate_purge_request(
                self.filepath, self.purge_mtx, self.purge_meb, self.purge_dds
            )
            counts = []
            if self.purge_mtx or self.purge_meb:
                box.label(text=str(track_dir), translate=False)
            if self.purge_dds:
                box.label(text=str(texture_dir), translate=False)
            if self.purge_mtx:
                counts.append(f"{len(collect_purge_targets(track_dir, '.mtx'))} MTX")
            if self.purge_meb:
                counts.append(f"{len(collect_purge_targets(track_dir, '.meb'))} MEB")
            if self.purge_dds:
                counts.append(f"{len(collect_purge_targets(texture_dir, '.dds'))} DDS")
            if counts:
                box.label(text="Will delete: " + ", ".join(counts))
        except PurgeError as exc:
            box.label(text=str(exc), translate=False)
        except Exception as exc:
            box.label(text=f"Purge preview failed: {exc}", translate=False)

    def execute(self, context):
        # Derive resource prefix from output filename
        output_path = Path(self.filepath)
        track_name = output_path.stem
        resource_prefix = f"tracks/{track_name}/"

        try:
            export_result = export_madness_scene(
                filepath=self.filepath,
                resource_prefix=resource_prefix,
                context=context,
                export_mtx_files=self.export_mtx_files,
                purge_mtx=self.purge_mtx,
                purge_meb=self.purge_meb,
                purge_dds=self.purge_dds,
            )
            self.report({"INFO"}, "Madness scene exported successfully")
            purged = export_result.get("purged", {}) if isinstance(export_result, dict) else {}
            purge_parts = []
            if self.purge_mtx:
                purge_parts.append(f"{int(purged.get('mtx', 0))} MTX")
            if self.purge_meb:
                purge_parts.append(f"{int(purged.get('meb', 0))} MEB")
            if self.purge_dds:
                purge_parts.append(f"{int(purged.get('dds', 0))} DDS")
            if purge_parts:
                self.report({"INFO"}, "Purged leftover files: " + ", ".join(purge_parts))
            texture_warnings = export_result.get("texture_warnings", {}) if isinstance(export_result, dict) else {}
            missing = int(texture_warnings.get("missing", 0))
            unsupported = int(texture_warnings.get("unsupported", 0))
            if missing or unsupported:
                warning_parts = []
                if missing:
                    warning_parts.append(f"{missing} unresolved/unfilled texture path(s)")
                if unsupported:
                    warning_parts.append(f"{unsupported} unsupported texture format/file(s)")
                self.report(
                    {"WARNING"},
                    "Texture warnings on exported materials: " + ", ".join(warning_parts),
                )
                self.report({"WARNING"}, "Problem materials (shader | material | issue counts | objects):")
                for detail in texture_warnings.get("details", []):
                    issue_parts = []
                    if detail.get("missing", 0):
                        issue_parts.append(f"missing={detail['missing']}")
                    if detail.get("unsupported", 0):
                        issue_parts.append(f"unsupported={detail['unsupported']}")
                    objects = detail.get("objects", [])[:3]
                    object_list = ", ".join(objects) if objects else "<unknown object>"
                    self.report(
                        {"WARNING"},
                        f"{detail.get('shader', '<unknown shader>')} | "
                        f"{detail.get('material', '<unknown material>')} | "
                        f"{', '.join(issue_parts)} | "
                        f"{object_list}",
                    )
            mesh_warnings = export_result.get("mesh_warnings", {}) if isinstance(export_result, dict) else {}
            mesh_count = int(mesh_warnings.get("meshes", 0))
            issue_count = int(mesh_warnings.get("issues", 0))
            if mesh_count or issue_count:
                self.report(
                    {"WARNING"},
                    f"Mesh validation warnings: {issue_count} issue(s) across {mesh_count} mesh(es)",
                )
                self.report({"WARNING"}, "Problem meshes (mesh | issues):")
                for detail in mesh_warnings.get("details", []):
                    issues = "; ".join(detail.get("issues", []))
                    self.report(
                        {"WARNING"},
                        f"{detail.get('mesh', '<unknown mesh>')} | {issues}",
                    )
            return {"FINISHED"}
        except PurgeError as e:
            self.report({"ERROR"}, f"Purge refused: {e}")
            return {"CANCELLED"}
        except Exception as e:
            self.report({"ERROR"}, f"Export failed: {str(e)}")
            return {"CANCELLED"}


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


class MadnessSingleMebExporter(bpy.types.Operator, ExportHelper):
    """Export standalone MEB mesh files (and matching MTX files)"""

    bl_idname = "export_scene.madness_single_meb"
    bl_label = "Export Single MEB"

    filename_ext = ".meb"

    filter_glob: StringProperty(
        default="*.meb",
        options={"HIDDEN"},
        maxlen=255,
    )  # type: ignore

    export_scope: EnumProperty(
        name="Objects",
        description="Choose whether to export selected objects or all visible scene objects",
        items=[
            ("SELECTED", "Export Selected", "Export selected mesh objects"),
            ("ALL", "Export All", "Export all visible mesh objects"),
        ],
        default="SELECTED",
    )  # type: ignore

    transform_mode: EnumProperty(
        name="Transform Handling",
        description="Choose whether to bake object transforms into vertices",
        items=[
            ("APPLY", "Apply Transforms", "Bake transforms into exported vertices"),
            ("RESET", "Reset Transforms", "Export vertices in object-local space"),
        ],
        default="APPLY",
    )  # type: ignore

    export_textures: BoolProperty(
        name="Copy Textures",
        description=(
            "Copy referenced textures to the game scaffold textures folder "
            "(same behavior/path logic as Scene Graph export)"
        ),
        default=False,
    )  # type: ignore

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "export_scope")
        layout.prop(self, "transform_mode")
        layout.prop(self, "export_textures")

    def execute(self, context):
        try:
            settings = SingleMebExportSettings(
                export_scope=self.export_scope,
                transform_mode=self.transform_mode,
                export_textures=self.export_textures,
            )
            result = export_single_meb_set(
                filepath=self.filepath,
                context=context,
                settings=settings,
            )

            exported_count = int(result.get("exported", 0))
            material_count = int(result.get("materials", 0))
            self.report(
                {"INFO"},
                f"Single MEB export finished: {exported_count} file, {material_count} MTX material(s)",
            )
            skipped_count = int(result.get("skipped_objects", 0))
            if skipped_count:
                skipped_names = ", ".join(result.get("skipped_object_names", []))
                self.report(
                    {"WARNING"},
                    f"Skipped {skipped_count} non-exportable object(s): {skipped_names}",
                )

            mesh_warnings = result.get("mesh_warnings", {}) if isinstance(result, dict) else {}
            mesh_count = int(mesh_warnings.get("meshes", 0))
            issue_count = int(mesh_warnings.get("issues", 0))
            if mesh_count or issue_count:
                self.report(
                    {"WARNING"},
                    f"Mesh validation warnings: {issue_count} issue(s) across {mesh_count} mesh(es)",
                )
                for detail in mesh_warnings.get("details", []):
                    issues = "; ".join(detail.get("issues", []))
                    self.report(
                        {"WARNING"},
                        f"{detail.get('mesh', '<unknown mesh>')} | {issues}",
                    )
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, f"Single MEB export failed: {str(e)}")
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

    def execute(self, context):
        try:
            results = export_dynamic_objects(self.filepath)

            if results["collisions"] == 0 and results["environment"] == 0:
                self.report(
                    {"WARNING"},
                    "No dynamic empties with definitions found in scene. Assign a definition to one or more empties first.",
                )
                return {"CANCELLED"}

            # Create a success message with actual file paths
            message = (
                f"Dynamic objects exported successfully! "
                f"{results['collisions']} templates, {results['environment']} instances, {results['registered']} registered type(s). "
                f"Files: {results.get('collisions_path', 'N/A')} and {results.get('env_path', 'N/A')}"
            )

            self.report({"INFO"}, message)
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, f"Dynamic objects export failed: {str(e)}")
            return {"CANCELLED"}


class MadnessSoundExporter(bpy.types.Operator, ExportHelper):
    """Export Sound Definitions (LSD)"""

    bl_idname = "export_scene.madness_sounds"
    bl_label = "Export Sound Definitions"

    filename_ext = ".lsd"

    filter_glob: StringProperty(
        default="*.lsd",
        options={"HIDDEN"},
        maxlen=255,
    )  # type: ignore

    def execute(self, context):
        try:
            results = export_sounds(self.filepath)

            if results["sounds"] == 0:
                self.report(
                    {"WARNING"},
                    "No SMS_SOUND objects found in scene. Create empties named SMS_SOUND_[name] first.",
                )
                return {"CANCELLED"}

            # Create a success message with actual file paths
            message = (
                f"Sound definitions exported successfully! "
                f"{results['sounds']} sound objects. "
                f"File: {results.get('lsd_path', 'N/A')}"
            )

            self.report({"INFO"}, message)
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, f"Sound definitions export failed: {str(e)}")
            return {"CANCELLED"}


class MadnessGclExporter(bpy.types.Operator, ExportHelper):
    """Export LiveTrack Cells (GCL)"""

    bl_idname = "export_scene.madness_gcl"
    bl_label = "Export GCL"

    filename_ext = ".gcl"

    filter_glob: StringProperty(
        default="*.gcl",
        options={"HIDDEN"},
        maxlen=255,
    )  # type: ignore

    def execute(self, context):
        try:
            result = export_gcl(filepath=self.filepath, context=context)
        except Exception as exc:
            self.report({"ERROR"}, f"GCL export failed: {exc}")
            return {"CANCELLED"}

        grid_x, grid_z = result["grid"]
        message = (
            f"GCL exported: {result['triangles']} triangles, grid {grid_x}x{grid_z}, "
            f"elevation {result['elevation']:.3f}m"
        )
        self.report({"INFO"}, message)
        return {"FINISHED"}


def menu_func_export(self, context):
    self.layout.operator(
        MadnessSceneExporter.bl_idname, text="Madness Scene (.sgx, .meb, .mtx)"
    )
    self.layout.operator(
        MadnessEnvironmentExporter.bl_idname, text="Madness Cameras (.xml)"
    )
    self.layout.operator(
        MadnessSingleMebExporter.bl_idname, text="Madness Single MEB (.meb + .mtx)"
    )
    self.layout.operator(
        MadnessLightsExporter.bl_idname, text="Madness Lights (_lights.sgx)"
    )
    self.layout.operator(
        MadnessDynamicObjectsExporter.bl_idname,
        text="Madness Dynamic Objects (collision & env)",
    )
    self.layout.operator(
        MadnessSoundExporter.bl_idname,
        text="Madness Sound Definitions (.lsd)",
    )
    self.layout.operator(
        MadnessGclExporter.bl_idname,
        text="Madness LiveTrack Cells (.gcl)",
    )


def register():
    meb_export_settings.register()
    mtx_material_system.register()
    empty_meb_settings.register()
    aiw_export.register()
    livetrack_mrdf_export.register()
    triggers_export.register()
    camera.register()
    area.register()
    camera_ui.register()
    light.register()
    light_ui.register()
    dynamic.register()
    dynamic_ui.register()
    sound.register()
    sound_ui.register()
    lod.register()
    lod_ui.register()

    main_classes = [
        MadnessSceneExporter,
        MadnessEnvironmentExporter,
        MadnessSingleMebExporter,
        MadnessLightsExporter,
        MadnessGclExporter,
        MadnessDynamicObjectsExporter,
        MadnessSoundExporter,
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
        MadnessSoundExporter,
        MadnessDynamicObjectsExporter,
        MadnessLightsExporter,
        MadnessSingleMebExporter,
        MadnessEnvironmentExporter,
        MadnessSceneExporter,
        MadnessGclExporter,
    ]

    for cls in main_classes:
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass  # Already unregistered

    lod_ui.unregister()
    lod.unregister()
    dynamic_ui.unregister()
    dynamic.unregister()
    sound_ui.unregister()
    sound.unregister()
    light_ui.unregister()
    light.unregister()
    camera_ui.unregister()
    area.unregister()
    camera.unregister()
    triggers_export.unregister()
    livetrack_mrdf_export.unregister()
    aiw_export.unregister()
    empty_meb_settings.unregister()
    mtx_material_system.unregister()
    meb_export_settings.unregister()


if __name__ == "__main__":
    register()
