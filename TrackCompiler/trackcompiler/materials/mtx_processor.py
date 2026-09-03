import bpy  # type: ignore
from pathlib import Path
import shutil
from typing import List
import xml.etree.ElementTree as ET
from . import mtx_material_system

def prepare_mtx_files_from_materials(
    material_names: List[str], dest_dir: Path, context, track_name: str = None, texture_mapping: dict = None
):
    """Create MTX files from Blender materials or use placeholder, overwriting existing files."""
    placeholder_path = None

    # Try to find a suitable placeholder in the project
    mtx_dir = Path(__file__).parent.parent / "MTXs"
    if mtx_dir.exists():
        placeholder_candidates = list(mtx_dir.glob("*.mtx"))
        if placeholder_candidates:
            placeholder_path = placeholder_candidates[0]

    for mat_name in material_names:
        dest = dest_dir / f"{mat_name.upper()}.mtx"

        # Try to find corresponding Blender material
        blender_material = None
        for mat in bpy.data.materials:
            if mat.name == mat_name:
                blender_material = mat
                break

        if blender_material and hasattr(blender_material, "mtx_settings"):
            try:
                mtx_material_system.write_mtx_file(
                    blender_material, dest, track_name, texture_mapping
                )
                warning = mtx_material_system.packed_permutation_warning_for_settings(
                    blender_material.mtx_settings
                )
                if warning:
                    print(f"Warning: {dest.name}: {warning}")
                print(f"Generated MTX from material: {dest.name}")
                continue
            except Exception as e:
                print(f"Failed to export material for {mat_name}: {e}")

        # Fall back to placeholder
        if placeholder_path and placeholder_path.exists():
            shutil.copy2(placeholder_path, dest)
            # Update material name in MTX file
            try:
                tree = ET.parse(dest)
                root = tree.getroot()
                root.set("name", mat_name.upper())
                tree.write(dest, encoding="utf-8", xml_declaration=False)
            except Exception as e:
                print(f"Warning: Could not patch MTX name in {dest}: {e}")
            print(f"Generated MTX from placeholder: {dest.name}")
        else:
            print(f"Warning: No placeholder MTX found for {mat_name}")
