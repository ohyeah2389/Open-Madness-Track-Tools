import bpy  # type: ignore
from pathlib import Path
import xml.etree.ElementTree as ET
from typing import List
from . import mtx_material_system
from .bmt_converter import convertMtxToBmt

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
            mtx_settings = blender_material.mtx_settings
            
            # Check if using override path
            if mtx_settings.use_override_path and mtx_settings.override_path:
                try:
                    from .mtx_material_system import validate_override_path
                    
                    # Validate the override path
                    is_valid, file_type, error_msg, target_ext = validate_override_path(mtx_settings.override_path)
                    
                    if not is_valid:
                        print(f"Error: Invalid override file for {mat_name}: {error_msg}")
                        print(f"Falling back to material generation for {mat_name}")
                    else:
                        # Handle file copying and naming
                        import shutil
                        override_path = Path(mtx_settings.override_path)
                        source_ext = override_path.suffix.lower()
                        
                        if file_type == "BMT":
                            # BMT files: copy with original extension (.bmt) but MEB will reference as .mtx
                            if source_ext == ".bmt":
                                # Copy BMT file keeping its .bmt extension
                                bmt_dest = dest_dir / f"{mat_name.upper()}.bmt"
                                shutil.copy2(override_path, bmt_dest)
                                print(f"Copied BMT file: {bmt_dest.name} (source: {override_path.name})")
                                print(f"  MEB will reference as: {mat_name.upper()}.mtx")
                            else:
                                # BMT file already has .mtx extension, copy as-is
                                shutil.copy2(override_path, dest)
                                print(f"Copied BMT file: {dest.name} (source: {override_path.name})")
                            continue
                        elif file_type == "MTX":
                            # MTX files: copy and update material name
                            shutil.copy2(override_path, dest)
                            try:
                                tree = ET.parse(dest)
                                root = tree.getroot()
                                root.set("name", mat_name.upper())
                                tree.write(dest, encoding="utf-8", xml_declaration=False)
                                print(f"Generated MTX from override file: {dest.name} (source: {override_path.name})")
                            except ET.ParseError as e:
                                print(f"Warning: Could not update material name in {dest.name}: {e}")
                                print(f"Generated MTX from override file: {dest.name} (source: {override_path.name})")
                            continue
                        else:
                            # Unknown file type, copy as-is
                            shutil.copy2(override_path, dest)
                            print(f"Copied file: {dest.name} (source: {override_path.name})")
                            continue
                            
                except Exception as e:
                    print(f"Failed to use override file for {mat_name}: {e}")
                    print(f"Falling back to material generation for {mat_name}")
            
            # Export from Blender material (fallback or normal mode)
            try:
                # Check if we should export as BMT
                shouldExportBmt = getattr(mtx_settings, 'export_as_bmt', True)
                
                if shouldExportBmt:
                    # Generate MTX first, then convert to BMT
                    tempMtxPath = dest
                    mtx_material_system.write_mtx_file(blender_material, tempMtxPath, track_name, texture_mapping)
                    
                    # Convert to BMT
                    bmtDest = dest_dir / f"{mat_name.upper()}.bmt"
                    convertMtxToBmt(tempMtxPath, bmtDest)
                    
                    # Remove temporary MTX file
                    tempMtxPath.unlink()
                    
                    print(f"Generated BMT from material: {bmtDest.name}")
                else:
                    # Export as MTX
                    mtx_material_system.write_mtx_file(blender_material, dest, track_name, texture_mapping)
                    print(f"Generated MTX from material: {dest.name}")
                continue
            except Exception as e:
                print(f"Failed to export material for {mat_name}: {e}")

        # Fall back to placeholder
        if placeholder_path and placeholder_path.exists():
            import shutil
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
