"""
LiveTrack MRDF Exporter for Blender
Exports geometry node attributes to Madness LiveTrack raster format
"""

import bpy # type: ignore
import bmesh # type: ignore
from bpy.props import StringProperty, FloatProperty, IntProperty # type: ignore
from bpy_extras.io_utils import ExportHelper # type: ignore
import struct
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional
import mathutils # type: ignore

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
    
    def execute(self, context):
        try:
            # Get active object
            obj = context.active_object
            if not obj or obj.type != 'MESH':
                self.report({'ERROR'}, "Please select a mesh object")
                return {'CANCELLED'}
            
            # Check for required attributes
            mesh = obj.data
            required_attrs = ['friction', 'height', 'grip', 'flag_0', 'flag_1', 'mask']
            missing_attrs = []
            
            for attr_name in required_attrs:
                if attr_name not in mesh.attributes:
                    missing_attrs.append(attr_name)
            
            if missing_attrs:
                self.report({'ERROR'}, f"Missing required attributes: {', '.join(missing_attrs)}")
                return {'CANCELLED'}
            
            export_livetrack_mrdf(
                obj=obj,
                filepath=self.filepath,
                context=context
            )
            
            self.report({'INFO'}, f"LiveTrack MRDF exported: {self.filepath}")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Export failed: {str(e)}")
            return {'CANCELLED'}

def get_grid_dimensions_and_bounds(obj) -> Tuple[int, int, Tuple[float, float, float, float], float]:
    """Analyze mesh to determine grid dimensions, world bounds, and calculate cell size"""
    # Get evaluated mesh with modifiers applied
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    mesh = eval_obj.data
    
    # Get vertex positions in world space
    world_matrix = obj.matrix_world
    vertices = [(world_matrix @ v.co).xyz for v in mesh.vertices]
    
    if not vertices:
        raise ValueError("Mesh has no vertices")
    
    # Find unique X and Y coordinates to determine grid dimensions
    x_coords = sorted(set(-v[0] for v in vertices))  # Negate Blender X
    y_coords = sorted(set(-v[1] for v in vertices))  # Negate Blender Y
    
    width = len(x_coords)
    height = len(y_coords)
    
    if width < 2 or height < 2:
        raise ValueError(f"Grid too small: {width} × {height}. Need at least 2×2 grid.")
    
    # Use object's actual bounding box in world space for bounds
    bbox_corners = [world_matrix @ mathutils.Vector(corner) for corner in obj.bound_box]
    bbox_x_coords = [-corner.x for corner in bbox_corners]  # Negate Blender X
    bbox_y_coords = [-corner.y for corner in bbox_corners]  # Negate Blender Y
    
    min_x, max_x = min(bbox_x_coords), max(bbox_x_coords)
    min_y, max_y = min(bbox_y_coords), max(bbox_y_coords)
    
    # Calculate cell size automatically based on grid dimensions and world bounds
    world_width = max_x - min_x
    world_height = max_y - min_y
    
    # Use the smaller of the two cell sizes to maintain square cells
    cell_size_x = world_width / (width - 1) if width > 1 else world_width
    cell_size_y = world_height / (height - 1) if height > 1 else world_height
    cell_size = min(cell_size_x, cell_size_y)
    
    print(f"Grid dimensions: {width} × {height}")
    print(f"Object bounding box: ({min_x:.3f}, {min_y:.3f}) to ({max_x:.3f}, {max_y:.3f})")
    print(f"World size: {world_width:.3f} × {world_height:.3f}")
    print(f"Auto-calculated cell size: {cell_size:.3f}")
    
    return width, height, (min_x, min_y, max_x, max_y), cell_size

def extract_grid_data(obj) -> List[Tuple[int, int, float, float, float, int]]:
    """Extract grid cell data from mesh attributes"""
    # Get evaluated mesh with modifiers applied
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    mesh = eval_obj.data
    
    # Get attribute data
    friction_attr = mesh.attributes['friction']
    height_attr = mesh.attributes['height']
    grip_attr = mesh.attributes['grip']
    flag_0_attr = mesh.attributes['flag_0']
    flag_1_attr = mesh.attributes['flag_1']
    mask_attr = mesh.attributes['mask']
    
    # Get vertex positions in world space
    world_matrix = obj.matrix_world
    x_coords = []
    y_coords = []
    
    for i, vertex in enumerate(mesh.vertices):
        world_pos = world_matrix @ vertex.co
        x, y = -world_pos.x, -world_pos.y  # Negate both X and Y
        x_coords.append(x)
        y_coords.append(y)
    
    # Get unique coordinates for grid indexing
    unique_x = sorted(set(x_coords))
    unique_y = sorted(set(y_coords))
    
    # Create coordinate to grid index mapping
    x_to_grid = {x: i for i, x in enumerate(unique_x)}
    y_to_grid = {y: i for i, y in enumerate(unique_y)}
    
    # Extract cell data (only for masked cells)
    cells = []
    total_vertices = len(mesh.vertices)
    masked_count = 0
    
    for vert_idx, vertex in enumerate(mesh.vertices):
        # Check mask first
        is_masked = mask_attr.data[vert_idx].value
        if not is_masked:
            continue  # Skip unmasked cells
        
        masked_count += 1
        
        world_pos = world_matrix @ vertex.co
        x, y = -world_pos.x, -world_pos.y  # Negate both X and Y
        grid_x = x_to_grid[x]
        grid_y = y_to_grid[y]
        
        # Get attribute values
        friction = friction_attr.data[vert_idx].value
        height = height_attr.data[vert_idx].value
        grip = grip_attr.data[vert_idx].value
        flag_0 = flag_0_attr.data[vert_idx].value
        flag_1 = flag_1_attr.data[vert_idx].value
        
        # Pack surface flags (use bits 0 and 1 for the boolean flags)
        surface_flags = 0
        if flag_0:
            surface_flags |= 0x01  # Set bit 0
        if flag_1:
            surface_flags |= 0x02  # Set bit 1
        
        cells.append((grid_x, grid_y, friction, height, grip, surface_flags))
    
    print(f"Extracted {len(cells)} grid cells from {masked_count} masked vertices ({total_vertices} total)")
    if masked_count != len(cells):
        print(f"Warning: Masked count ({masked_count}) doesn't match extracted cells ({len(cells)})")
    
    return cells

def create_row_offsets(cells: List[Tuple[int, int, float, float, float, int]], height: int) -> List[int]:
    """Create row offset table for binary search
    
    CRITICAL: The initialization cells must appear at specific indices in the sorted array:
    - Index 0: X=112, Y=0 (initialization marker)
    - Index 1: X=0, Y=1 (first calibration point)  
    - Index 2: X=0, Y=1 (second calibration point)
    - Index 3: X=22, Y=1 (third calibration point)
    """
    
    # Separate initialization cells from user cells
    init_cells = []
    user_cells = []
    
    # Define the required initialization cells with their expected indices
    required_init_positions = [
        (112, 0),  # Index 0
        (0, 1),    # Index 1  
        (0, 1),    # Index 2 (duplicate X=0, Y=1)
        (22, 1)    # Index 3
    ]
    
    for cell in cells:
        x, y = cell[0], cell[1]
        if (x, y) in required_init_positions:
            init_cells.append(cell)
        else:
            user_cells.append(cell)
    
    # Sort user cells by Y coordinate, then X coordinate
    user_cells_sorted = sorted(user_cells, key=lambda c: (c[1], c[0]))
    
    # Create final sorted list with initialization cells at the beginning
    # This ensures they appear at indices 0, 1, 2, 3 as required
    sorted_cells = []
    
    # Add initialization cells first (these MUST be at the beginning)
    init_cells_by_position = {}
    for cell in init_cells:
        key = (cell[0], cell[1])
        if key not in init_cells_by_position:
            init_cells_by_position[key] = []
        init_cells_by_position[key].append(cell)
    
    # Add init cells in the exact order required
    for pos in required_init_positions:
        if pos in init_cells_by_position and init_cells_by_position[pos]:
            sorted_cells.append(init_cells_by_position[pos].pop(0))
        else:
            # If missing, add a default initialization cell
            if pos == (112, 0):
                sorted_cells.append((112, 0, 0.000, 0.000, 0.000, 0x00))
            elif pos == (0, 1):
                if len([c for c in sorted_cells if c[0] == 0 and c[1] == 1]) == 0:
                    sorted_cells.append((0, 1, 0.753, 0.024, 0.000, 0x00))
                else:
                    sorted_cells.append((0, 1, 0.000, 0.000, 0.078, 0xE2))
            elif pos == (22, 1):
                sorted_cells.append((22, 1, 0.000, 0.000, 0.000, 0x00))
    
    # Add remaining user cells
    sorted_cells.extend(user_cells_sorted)
    
    # Build row offset table - must have exactly height + 1 entries
    row_offsets = [0] * (height + 1)
    
    # Initialize all row offsets to point to end of data (no cells)
    for i in range(height + 1):
        row_offsets[i] = len(sorted_cells)
    
    # Set the first row offset
    row_offsets[0] = 0
    
    # Find the start of each row
    current_row = 0
    for i, (grid_x, grid_y, _, _, _, _) in enumerate(sorted_cells):
        # If we've moved to a new row, update all intermediate row offsets
        while current_row < grid_y and current_row < height:
            current_row += 1
            row_offsets[current_row] = i
        
        # Update current row to match the cell's row
        if grid_y < height:
            current_row = max(current_row, grid_y)
    
    # Ensure the final offset points to the end
    row_offsets[height] = len(sorted_cells)
    
    print(f"Created row offset table with {len(row_offsets)} entries for {height} rows")
    print(f"Row offset range: {row_offsets[0]} to {row_offsets[-1]}")
    print(f"First 8 cells in sorted array:")
    for i in range(min(8, len(sorted_cells))):
        cell = sorted_cells[i]
        print(f"  Index {i}: X={cell[0]}, Y={cell[1]}, friction={cell[2]:.3f}, flags=0x{cell[5]:02X}")
    
    return row_offsets, sorted_cells

def add_required_initialization_cells(cells: List[Tuple[int, int, float, float, float, int]], width: int, height: int) -> List[Tuple[int, int, float, float, float, int]]:
    """Add required initialization cells that the game expects to find"""
    
    # Define the required initialization cells based on stock MRDF analysis
    required_cells = [
        (112, 0, 0.000, 0.000, 0.000, 0x00),  # Index 0: Init marker in row 0
        (0, 1, 0.753, 0.024, 0.000, 0x00),    # Index 1: Calibration with friction
        (0, 1, 0.000, 0.000, 0.078, 0xE2),    # Index 2: Calibration with grip + flags  
        (22, 1, 0.000, 0.000, 0.000, 0x00)    # Index 3: Additional calibration
    ]
    
    # Check for conflicts with existing cells
    existing_positions = {(x, y) for x, y, _, _, _, _ in cells}
    
    for req_x, req_y, _, _, _, _ in required_cells:
        if (req_x, req_y) in existing_positions:
            print(f"Warning: Removing existing cell at ({req_x},{req_y}) to make room for required initialization cell")
            cells = [(x, y, f, h, g, s) for x, y, f, h, g, s in cells if not (x == req_x and y == req_y)]
    
    # Add required cells
    all_cells = list(required_cells) + cells
    
    print(f"Added {len(required_cells)} required initialization cells")
    return all_cells

def write_mrdf_file(filepath: str, width: int, height: int, world_bounds: Tuple[float, float, float, float], 
                   cell_size: float, cells: List[Tuple[int, int, float, float, float, int]]):
    """Write MRDF file in the correct binary format matching game requirements"""
    
    # Add required initialization cells that the game expects
    cells_with_init = add_required_initialization_cells(cells, width, height)
    
    # Create row offsets and sort cells
    row_offsets, sorted_cells = create_row_offsets(cells_with_init, height)
    
    print(f"Debug: Writing {len(sorted_cells)} total cells ({len(cells)} user + {len(cells_with_init) - len(cells)} initialization)")
    
    # Debug: verify the first few cells in the binary output
    print("Debug: First 8 cells that will be written to binary:")
    for i in range(min(8, len(sorted_cells))):
        grid_x, grid_y, friction, height_val, grip, surface_flags = sorted_cells[i]
        friction_uint8 = max(0, min(255, int(friction * 255)))
        height_uint8 = max(0, min(255, int(height_val * 255)))
        grip_uint8 = max(0, min(255, int(grip * 255)))
        print(f"  Binary cell {i}: X={grid_x} (0x{grid_x:04X}), "
              f"friction={friction_uint8} (0x{friction_uint8:02X}), "
              f"height={height_uint8} (0x{height_uint8:02X}), "
              f"grip={grip_uint8} (0x{grip_uint8:02X}), "
              f"flags=0x{surface_flags:02X}")
    
    # Write to temporary buffers to calculate exact sizes
    import io
    
    # PRIMARY_DATA section (0x01)
    primary_buffer = io.BytesIO()
    min_x, min_y, max_x, max_y = world_bounds
    
    # Grid metadata (0x58 bytes)
    primary_buffer.write(b'\x00' * 8)  # Unknown/padding
    primary_buffer.write(struct.pack('<4f', min_x, min_y, max_x, max_y))  # World bounds
    primary_buffer.write(struct.pack('<2I', width, height))  # Grid dimensions
    primary_buffer.write(b'\x00' * 8)  # Unknown/padding
    primary_buffer.write(struct.pack('<I', len(sorted_cells)))  # Total cell count
    primary_buffer.write(b'\x00' * 4)  # Unknown/padding
    primary_buffer.write(struct.pack('<f', cell_size))  # Cell size
    primary_buffer.write(b'\x00' * 36)  # Additional padding to reach 0x58
    
    # Write grid cell data (6 bytes per cell)
    print("Debug: Writing cell data to binary buffer...")
    for i, (grid_x, grid_y, friction, height_val, grip, surface_flags) in enumerate(sorted_cells):
        friction_uint8 = max(0, min(255, int(friction * 255)))
        height_uint8 = max(0, min(255, int(height_val * 255)))
        grip_uint8 = max(0, min(255, int(grip * 255)))
        
        if i < 8:  # Debug first 8 cells
            print(f"  Writing cell {i}: X={grid_x:04X} friction={friction_uint8:02X} height={height_uint8:02X} grip={grip_uint8:02X} flags={surface_flags:02X}")
            
            # Show exact bytes being written
            x_bytes = struct.pack('<H', grid_x)
            cell_bytes = x_bytes + bytes([friction_uint8, height_uint8, grip_uint8, surface_flags])
            print(f"    Bytes: {' '.join(f'{b:02X}' for b in cell_bytes)}")
        
        primary_buffer.write(struct.pack('<H', grid_x))  # X coordinate (uint16)
        primary_buffer.write(bytes([friction_uint8]))  # Friction (uint8)
        primary_buffer.write(bytes([height_uint8]))  # Height (uint8)
        primary_buffer.write(bytes([grip_uint8]))  # Grip (uint8)
        primary_buffer.write(bytes([surface_flags]))  # Surface flags (uint8)
    
    # Write row offset table (4 bytes per offset)
    for offset in row_offsets:
        primary_buffer.write(struct.pack('<I', offset))
    
    primary_data = primary_buffer.getvalue()
    primary_size = len(primary_data)
    
    # POINTER_RELOCATION section (0x10) - Two 8-byte pointer entries
    pointer_data = struct.pack('<QQ', 0, 0x58)  # Two 8-byte pointer entries: [0, 88]
    pointer_size = len(pointer_data)
    
    # Ensure 4-byte alignment as required by game validation
    while pointer_size % 4 != 0:
        pointer_data += b'\x00'
        pointer_size = len(pointer_data)
    
    # RASTER_CELLS section (0x50) - Exact Indianapolis 2022 RC pattern
    raster_data = b'\x59\xcf\xd2\x3a\x03\x00\x00\x00\x26\x3d\x21\x04\x03\x00\x00\x00\xf0\xa3\xfc\x9e\x03\x00\x00\x00\x00\x00\x00\x00'
    raster_size = len(raster_data)  # Should be exactly 28 bytes
    
    # Calculate total file size
    extended_header_size = 8  # Extended header data
    section_count = 3
    section_directory_size = section_count * 8  # 8 bytes per section entry
    total_header_size = 16 + section_directory_size + extended_header_size
    
    total_file_size = total_header_size + primary_size + pointer_size + raster_size
    
    print(f"Debug: File structure:")
    print(f"  Header + directory + extended: {total_header_size} bytes")
    print(f"  PRIMARY_DATA: {primary_size} bytes")
    print(f"  POINTER_RELOCATION: {pointer_size} bytes")
    print(f"  RASTER_CELLS: {raster_size} bytes")
    print(f"  Total file size: {total_file_size} bytes")
    
    # Write the final file
    with open(filepath, 'wb') as f:
        # Write MRDF header (16 bytes) - matching stock MRDF format
        f.write(b'Q')  # Magic
        f.write(bytes([0x02]))  # Format flags (bit 1 set, bit 0 clear)
        f.write(bytes([0x01]))  # Version
        f.write(bytes([section_count]))  # Section count (3)
        f.write(bytes([extended_header_size]))  # Extended header size (8)
        f.write(struct.pack('<H', 256))  # Min sections requirement (256, from stock)
        f.write(bytes([0x04]))  # Max sections limit (4, from stock)
        f.write(b'\x8d\xdb\x49\xee\x95\x8a\x25\x73')  # Reserved bytes (Indianapolis 2022 RC pattern)
        
        # Write section directory (8 bytes per section)
        section_data_start = total_header_size
        
        # Section 0: PRIMARY_DATA (0x01)
        f.write(struct.pack('<I', primary_size))  # Section size
        f.write(bytes([0x01]))  # Section type (PRIMARY_DATA)
        f.write(b'\x0c\x00\x00')  # Validation bytes (Indianapolis pattern)
        
        # Section 1: POINTER_RELOCATION (0x10)
        f.write(struct.pack('<I', pointer_size))  # Section size
        f.write(bytes([0x10]))  # Section type (POINTER_RELOCATION)
        f.write(b'\x00' * 3)  # Padding
        
        # Section 2: RASTER_CELLS (0x50)
        f.write(struct.pack('<I', raster_size))  # Section size
        f.write(bytes([0x50]))  # Section type (RASTER_CELLS)
        f.write(b'\x00' * 3)  # Padding
        
        # Write extended header data (8 bytes)
        f.write(b'\x00' * 8)  # Extended header (all zeros for now)
        
        # Write section data
        f.write(primary_data)  # PRIMARY_DATA section
        f.write(pointer_data)  # POINTER_RELOCATION section
        f.write(raster_data)   # RASTER_CELLS section
    
    # Verify file size
    actual_file_size = Path(filepath).stat().st_size
    
    print(f"MRDF file written: {filepath}")
    print(f"  Grid: {width} × {height} cells")
    print(f"  Cell data: {len(sorted_cells)} cells")
    print(f"  Row offsets: {len(row_offsets)} entries")
    print(f"  Expected file size: {total_file_size:,} bytes")
    print(f"  Actual file size: {actual_file_size:,} bytes")
    
    if actual_file_size != total_file_size:
        print(f"  ERROR: File size mismatch!")
    else:
        print(f"  File size verification: PASS")

def export_livetrack_mrdf(obj, filepath: str, context):
    """Main export function"""
    print(f"Exporting LiveTrack MRDF: {filepath}")
    print("=" * 60)
    
    # Analyze mesh to get grid dimensions, bounds, and auto-calculated cell size
    width, height, world_bounds, cell_size = get_grid_dimensions_and_bounds(obj)
    
    # Extract grid data from mesh attributes (only masked cells)
    cells = extract_grid_data(obj)
    
    # Calculate expected vs actual cells
    total_possible_cells = width * height
    print(f"Grid capacity: {total_possible_cells} cells")
    print(f"Masked cells: {len(cells)} cells ({len(cells)/total_possible_cells*100:.1f}% coverage)")
    
    if len(cells) == 0:
        raise ValueError("No masked cells found! Check that the 'mask' attribute has some True values.")
    
    # Write MRDF file
    write_mrdf_file(filepath, width, height, world_bounds, cell_size, cells)
    
    print("=" * 60)
    print("LiveTrack MRDF export completed successfully!")

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