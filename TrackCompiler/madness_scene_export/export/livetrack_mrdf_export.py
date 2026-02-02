"""
LiveTrack MRDF Exporter for Blender
Exports geometry node attributes to Madness LiveTrack raster format
"""

import bpy # type: ignore
from bpy.props import StringProperty, BoolProperty # type: ignore
from bpy_extras.io_utils import ExportHelper # type: ignore
import struct
import os
from pathlib import Path
from typing import List, Tuple
import mathutils # type: ignore

# Constants
REQUIRED_ATTRS = ['friction', 'height', 'grip', 'flag_0', 'flag_1', 'mask']
INIT_CELLS = [
    (112, 0, 0.000, 0.000, 0.000, 0x00),
    (0, 1, 0.753, 0.024, 0.000, 0x00),
    (0, 1, 0.000, 0.000, 0.078, 0xE2),
    (22, 1, 0.000, 0.000, 0.000, 0x00)
]
HEADER_SIZE = 0x70
CELL_SIZE = 6

# Logging control
_verbose_logging = False

def _log(message: str):
    """Print message only if verbose logging is enabled"""
    if _verbose_logging:
        print(message)

class LiveTrackMRDFExporter(bpy.types.Operator, ExportHelper):
    """Export LiveTrack MRDF from Geometry Nodes attributes"""
    bl_idname = "export_scene.livetrack_mrdf"
    bl_label = "Export LiveTrack MRDF"
    
    filename_ext = ".mrdf"
    
    filter_glob: StringProperty(
        default="*.mrdf",
        options={'HIDDEN'},
        maxlen=255,
    ) # type: ignore
    
    verbose: BoolProperty(
        name="Verbose Logging",
        description="Enable detailed logging output",
        default=False,
    ) # type: ignore
    
    def execute(self, context):
        global _verbose_logging
        _verbose_logging = self.verbose
        
        try:
            obj = context.active_object
            if not obj or obj.type != 'MESH':
                self.report({'ERROR'}, "Please select a mesh object")
                return {'CANCELLED'}
            
            missing = [attr for attr in REQUIRED_ATTRS if attr not in obj.data.attributes]
            if missing:
                self.report({'ERROR'}, f"Missing required attributes: {', '.join(missing)}")
                return {'CANCELLED'}
            
            export_livetrack_mrdf(obj, self.filepath, context)
            self.report({'INFO'}, f"LiveTrack MRDF exported: {self.filepath}")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Export failed: {str(e)}")
            return {'CANCELLED'}

def get_grid_dimensions_and_bounds(obj) -> Tuple[int, int, Tuple[float, float, float, float], float]:
    """Analyze mesh to determine grid dimensions, world bounds, and cell size"""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    mesh = eval_obj.data
    
    if not mesh.vertices:
        raise ValueError("Mesh has no vertices")
    
    world_matrix = obj.matrix_world
    vertices = [(world_matrix @ v.co).xyz for v in mesh.vertices]
    
    x_coords = sorted(set(v[0] for v in vertices))
    y_coords = sorted(set(v[1] for v in vertices))
    width, height = len(x_coords), len(y_coords)
    
    if width < 2 or height < 2:
        raise ValueError(f"Grid too small: {width}×{height}. Need at least 2×2.")
    
    bbox_corners = [world_matrix @ mathutils.Vector(corner) for corner in obj.bound_box]
    min_x = min(c.x for c in bbox_corners)
    max_x = max(c.x for c in bbox_corners)
    min_y = min(c.y for c in bbox_corners)
    max_y = max(c.y for c in bbox_corners)
    
    cell_size_x = (max_x - min_x) / (width - 1) if width > 1 else (max_x - min_x)
    cell_size_y = (max_y - min_y) / (height - 1) if height > 1 else (max_y - min_y)
    cell_size = min(cell_size_x, cell_size_y)
    
    _log(f"Grid: {width}×{height}, Bounds: ({min_x:.3f},{min_y:.3f})-({max_x:.3f},{max_y:.3f}), Cell size: {cell_size:.3f}")
    
    return width, height, (min_x, min_y, max_x, max_y), cell_size

def extract_grid_data(obj) -> List[Tuple[int, int, float, float, float, int]]:
    """Extract grid cell data from mesh attributes (masked cells only)"""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    mesh = eval_obj.data
    world_matrix = obj.matrix_world
    
    attrs = {name: mesh.attributes[name] for name in REQUIRED_ATTRS}
    
    # Build grid coordinate mapping
    vertices = [(world_matrix @ v.co).xyz for v in mesh.vertices]
    unique_x = sorted(set(v[0] for v in vertices))
    unique_y = sorted(set(v[1] for v in vertices))
    x_to_grid = {x: i for i, x in enumerate(unique_x)}
    y_to_grid = {y: i for i, y in enumerate(unique_y)}
    
    cells = []
    for idx, vertex in enumerate(mesh.vertices):
        if not attrs['mask'].data[idx].value:
            continue
        
        world_pos = world_matrix @ vertex.co
        grid_x = x_to_grid[world_pos.x]
        grid_y = y_to_grid[world_pos.y]
        
        friction = attrs['friction'].data[idx].value
        height = attrs['height'].data[idx].value
        grip = attrs['grip'].data[idx].value
        
        surface_flags = 0
        if attrs['flag_0'].data[idx].value:
            surface_flags |= 0x01
        if attrs['flag_1'].data[idx].value:
            surface_flags |= 0x02
        
        cells.append((grid_x, grid_y, friction, height, grip, surface_flags))
    
    _log(f"Extracted {len(cells)} cells from {len(mesh.vertices)} vertices")
    return cells

def create_row_offsets(cells: List[Tuple[int, int, float, float, float, int]], height: int) -> Tuple[List[int], List[Tuple[int, int, float, float, float, int]]]:
    """Create row offset table with initialization cells at specific indices"""
    init_positions = [(112, 0), (0, 1), (0, 1), (22, 1)]
    init_cells_map = {}
    user_cells = []
    
    for cell in cells:
        pos = (cell[0], cell[1])
        if pos in init_positions:
            init_cells_map.setdefault(pos, []).append(cell)
        else:
            user_cells.append(cell)
    
    sorted_cells = []
    for pos in init_positions:
        if pos in init_cells_map and init_cells_map[pos]:
            sorted_cells.append(init_cells_map[pos].pop(0))
        else:
            # Add default initialization cells if missing
            if pos == (112, 0):
                sorted_cells.append((112, 0, 0.0, 0.0, 0.0, 0x00))
            elif pos == (0, 1):
                if not any(c[0] == 0 and c[1] == 1 for c in sorted_cells):
                    sorted_cells.append((0, 1, 0.753, 0.024, 0.0, 0x00))
                else:
                    sorted_cells.append((0, 1, 0.0, 0.0, 0.078, 0xE2))
            elif pos == (22, 1):
                sorted_cells.append((22, 1, 0.0, 0.0, 0.0, 0x00))
    
    sorted_cells.extend(sorted(user_cells, key=lambda c: (c[1], c[0])))
    
    row_offsets = [len(sorted_cells)] * (height + 1)
    row_offsets[0] = 0
    
    current_row = 0
    for i, cell in enumerate(sorted_cells):
        while current_row < cell[1] and current_row < height:
            current_row += 1
            row_offsets[current_row] = i
        if cell[1] < height:
            current_row = max(current_row, cell[1])
    
    row_offsets[height] = len(sorted_cells)
    
    _log(f"Row offsets: {len(row_offsets)} entries, {len(sorted_cells)} cells")
    if _verbose_logging and len(sorted_cells) >= 4:
        for i in range(min(4, len(sorted_cells))):
            c = sorted_cells[i]
            _log(f"  Init cell {i}: X={c[0]}, Y={c[1]}, friction={c[2]:.3f}, flags=0x{c[5]:02X}")
    
    return row_offsets, sorted_cells

def add_required_initialization_cells(cells: List[Tuple[int, int, float, float, float, int]]) -> List[Tuple[int, int, float, float, float, int]]:
    """Add required initialization cells, removing conflicts if present"""
    existing_positions = {(x, y) for x, y, _, _, _, _ in cells}
    
    filtered_cells = []
    for cell in cells:
        pos = (cell[0], cell[1])
        if pos not in [(112, 0), (0, 1), (22, 1)]:
            filtered_cells.append(cell)
        elif _verbose_logging:
            _log(f"Removed conflicting cell at {pos}")
    
    return list(INIT_CELLS) + filtered_cells

def write_mrdf_file(filepath: str, width: int, height: int, world_bounds: Tuple[float, float, float, float], 
                   cell_size: float, cells: List[Tuple[int, int, float, float, float, int]]):
    """Write MRDF file in binary format
    
    Format: MRDF container with three sections:
    - PRIMARY_DATA (0x01): Grid metadata + cell data + row offset table
    - POINTER_RELOCATION (0x10): Pointers requiring game engine relocation
    - RASTER_CELLS (0x50): Material type definitions
    """
    from io import BytesIO
    
    cells_with_init = add_required_initialization_cells(cells)
    row_offsets, sorted_cells = create_row_offsets(cells_with_init, height)
    
    _log(f"Writing {len(sorted_cells)} cells ({len(cells)} user + {len(sorted_cells) - len(cells)} init)")
    
    # PRIMARY_DATA section (0x01): Grid metadata (0x70 bytes header)
    primary_buffer = BytesIO()
    min_x, min_y, max_x, max_y = world_bounds
    
    # Grid metadata structure:
    primary_buffer.write(b'\x00' * 8)                                    # 0x00: Header prefix (flags/version)
    primary_buffer.write(struct.pack('<4f', min_x, min_y, max_x, max_y)) # 0x08: World bounds (4 floats)
    primary_buffer.write(struct.pack('<2I', width, height))              # 0x18: Grid dimensions (2 uint32)
    primary_buffer.write(struct.pack('<If', 0, cell_size))               # 0x20: Unknown + cell_size (uint32, float)
    primary_buffer.write(struct.pack('<I', len(sorted_cells)))           # 0x28: Total cell count (uint32)
    primary_buffer.write(struct.pack('<f', cell_size))                   # 0x2C: Cell size duplicate (float)
    primary_buffer.write(b'\x00' * 40)                                   # 0x30: Padding
    
    # Calculate pointers (relocated by game at runtime)
    cell_data_offset = HEADER_SIZE
    cell_data_size = len(sorted_cells) * CELL_SIZE
    padding_needed = (4 - (cell_data_size % 4)) % 4
    row_table_offset = cell_data_offset + cell_data_size + padding_needed
    
    primary_buffer.write(struct.pack('<Q', cell_data_offset))  # 0x58: Pointer to cell data (uint64)
    primary_buffer.write(b'\x00' * 8)                          # 0x60: Padding
    primary_buffer.write(struct.pack('<Q', row_table_offset))  # 0x68: Pointer to row offset table (uint64)
    
    # Cell data array (6 bytes per cell): sorted by Y then X for binary search
    # Format: X (uint16) + friction (uint8) + height (uint8) + grip (uint8) + flags (uint8)
    for i, (grid_x, grid_y, friction, height_val, grip, surface_flags) in enumerate(sorted_cells):
        friction_u8 = max(0, min(255, int(friction * 255)))
        height_u8 = max(0, min(255, int(height_val * 255)))
        grip_u8 = max(0, min(255, int(grip * 255)))
        
        if _verbose_logging and i < 4:
            _log(f"  Cell {i}: X={grid_x:04X} F={friction_u8:02X} H={height_u8:02X} G={grip_u8:02X} Flags={surface_flags:02X}")
        
        primary_buffer.write(struct.pack('<H', grid_x))
        primary_buffer.write(bytes([friction_u8, height_u8, grip_u8, surface_flags]))
    
    # 4-byte alignment padding before row offset table
    if padding_needed:
        primary_buffer.write(b'\x00' * padding_needed)
    
    # Row offset table: (height + 1) entries, each uint32 points to first cell in that row
    for offset in row_offsets:
        primary_buffer.write(struct.pack('<I', offset))
    
    primary_data = primary_buffer.getvalue()
    
    # POINTER_RELOCATION section (0x10): Offsets within PRIMARY_DATA requiring relocation
    # Format: pairs of (offset uint32, padding uint32) for each pointer location
    pointer_data = b''
    for offset in [0x58, 0x68]:  # Cell data ptr and row table ptr locations
        pointer_data += struct.pack('<II', offset, 0)
    
    # RASTER_CELLS section (0x50): Material type definitions
    # Material types (0-15) are encoded in cell surface flags (bits 2-5)
    # Format: [material_type (uint32), property_value (float)] repeated, then total_count (uint32)
    raster_data = b''
    material_defs = {3: [0.01608, 0.0, 0.0]}  # Placeholder from stock MRDF
    total_entries = sum(len(props) for props in material_defs.values())
    for mat_type, props in material_defs.items():
        for prop in props:
            raster_data += struct.pack('<If', mat_type, prop)
    raster_data += struct.pack('<I', total_entries)
    
    # Calculate file structure
    section_count = 3
    extended_header_size = 8
    total_header_size = 16 + (section_count * 8) + extended_header_size
    total_file_size = total_header_size + len(primary_data) + 12 + len(pointer_data) + len(raster_data) + 4
    
    _log(f"File structure: header={total_header_size}b, primary={len(primary_data)}b, pointer={len(pointer_data)}b, raster={len(raster_data)}b")
    
    # Write MRDF file
    with open(filepath, 'wb') as f:
        # MRDF header (16 bytes)
        f.write(b'Q')                                                    # 0x00: Magic byte
        f.write(bytes([0x02, 0x01, section_count, extended_header_size]))# 0x01-04: Format flags, version, section count, extended header size
        f.write(struct.pack('<H', 256))                                  # 0x05: Min sections requirement
        f.write(bytes([0x04]))                                           # 0x07: Max sections limit
        f.write(os.urandom(8))                                           # 0x08: Unique identifier per export
        
        # Section directory (8 bytes per section)
        # Format: size (uint32) + type (uint8) + padding[0] = trailing padding bytes + padding[1:2]
        f.write(struct.pack('<I', len(primary_data)))  # PRIMARY_DATA section
        f.write(bytes([0x01]))                         # Section type: PRIMARY_DATA
        f.write(b'\x0c\x00\x00')                       # Trailing padding: 12 bytes
        
        f.write(struct.pack('<I', len(pointer_data)))  # POINTER_RELOCATION section
        f.write(bytes([0x10]))                         # Section type: POINTER_RELOCATION
        f.write(b'\x00\x00\x00')                       # Trailing padding: 0 bytes
        
        f.write(struct.pack('<I', len(raster_data)))   # RASTER_CELLS section
        f.write(bytes([0x50]))                         # Section type: RASTER_CELLS
        f.write(b'\x04\x00\x00')                       # Trailing padding: 4 bytes
        
        # Extended header (8 bytes, unused here)
        f.write(b'\x00' * 8)
        
        # Section data with trailing padding
        f.write(primary_data)
        f.write(b'\x00' * 12)  # PRIMARY_DATA trailing padding
        f.write(pointer_data)
        f.write(raster_data)
        f.write(b'\x00' * 4)   # RASTER_CELLS trailing padding
    
    actual_size = Path(filepath).stat().st_size
    if actual_size != total_file_size:
        raise RuntimeError(f"File size mismatch: expected {total_file_size}, got {actual_size}")
    
    print(f"Exported {len(sorted_cells)} cells to {Path(filepath).name} ({actual_size:,} bytes)")

def export_livetrack_mrdf(obj, filepath: str, context):
    """Main export function"""
    width, height, world_bounds, cell_size = get_grid_dimensions_and_bounds(obj)
    cells = extract_grid_data(obj)
    
    if not cells:
        raise ValueError("No masked cells found. Check 'mask' attribute has True values.")
    
    coverage = len(cells) / (width * height) * 100
    _log(f"Grid: {width}×{height} ({width * height} capacity), {len(cells)} masked ({coverage:.1f}% coverage)")
    
    write_mrdf_file(filepath, width, height, world_bounds, cell_size, cells)

def menu_func_export(self, context):
    self.layout.operator(LiveTrackMRDFExporter.bl_idname, text="Madness LiveTrack Data (.mrdf)")

def register():
    bpy.utils.register_class(LiveTrackMRDFExporter)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

def unregister():
    bpy.utils.unregister_class(LiveTrackMRDFExporter)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)

if __name__ == "__main__":
    register() 