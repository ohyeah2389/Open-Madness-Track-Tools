import bpy # type: ignore
import mathutils # type: ignore
import xml.etree.ElementTree as ET
import numpy as np
import random
from pathlib import Path
from typing import List, Dict, Tuple
from math import radians
from bpy.props import StringProperty, BoolProperty # type: ignore
from bpy_extras.io_utils import ExportHelper # type: ignore

def calculate_crc32(data_string: str) -> int:
    """Calculate CRC32 using the same algorithm as the game (polynomial 0x4c11db7)"""
    if isinstance(data_string, str):
        data_bytes = data_string.encode('ascii')
    else:
        data_bytes = data_string
        
    crc = 0xFFFFFFFF
    
    for byte in data_bytes:
        # Process each bit of the byte
        for bit in range(8):
            bit_val = (byte >> (7 - bit)) & 1
            if (crc & 0x80000000) != 0:
                crc = ((crc << 1) ^ bit_val ^ 0x04C11DB7) & 0xFFFFFFFF
            else:
                crc = ((crc << 1) ^ bit_val) & 0xFFFFFFFF
    
    return (~crc) & 0xFFFFFFFF

def build_trigger_crc_map() -> Dict[str, int]:
    """Build mapping of trigger type names to CRC32 values"""
    trigger_types = [
        "TRG_START",
        "TRG_CHECKPOINT1", 
        "TRG_CHECKPOINT2",
        "TRG_FINISH",
        "TRG_STOP",
        "TRG_PITIN",
        "TRG_PITOUT", 
        "TRG_DRSDET1",
        "TRG_DRSDET2",
        "TRG_DRSDET3",
        "TRG_DRSZONE1START",
        "TRG_DRSZONE2START", 
        "TRG_DRSZONE3START",
        "TRG_DRSZONE1END",
        "TRG_DRSZONE2END",
        "TRG_DRSZONE3END"
    ]
    
    crc_map = {}
    for trigger_type in trigger_types:
        crc_value = calculate_crc32(trigger_type)
        crc_map[trigger_type] = crc_value
        
    return crc_map

def convert_position_to_madness(blender_pos: Tuple[float, float, float]) -> Tuple[float, float, float]:
    """Convert position from Blender coordinate system to Madness coordinate system"""
    x, y, z = blender_pos
    return (x, z, y)

def convert_rotation_matrix_to_madness(blender_matrix) -> np.ndarray:
    """Convert rotation matrix from Blender to Madness coordinate system"""
    # Convert Blender matrix to numpy array
    rot_3x3 = np.array([[blender_matrix[0][0], blender_matrix[0][1], blender_matrix[0][2]],
                        [blender_matrix[1][0], blender_matrix[1][1], blender_matrix[1][2]],
                        [blender_matrix[2][0], blender_matrix[2][1], blender_matrix[2][2]]])
    
    # Apply coordinate system conversion similar to main exporter
    # Extra rotation to convert Z-up to Y-up
    rx = radians(-90)  # -90 degrees around X axis
    cos_x, sin_x = np.cos(rx), np.sin(rx)
    R_EXTRA = np.array([
        [1, 0, 0],
        [0, cos_x, -sin_x],
        [0, sin_x, cos_x]
    ])
    
    # Apply the coordinate transformation
    converted = R_EXTRA @ rot_3x3 @ R_EXTRA.T
    
    # Apply reflections about X and Z axes (Blender X and Y axes)
    # Reflection about X axis: negate Y and Z columns
    # Reflection about Z axis: negate X and Y columns
    reflection_matrix = np.array([
        [-1, 0, 0],  # Negate X column
        [0, -1, 0],  # Negate Y column  
        [0, 0, 1]    # Keep Z column
    ])
    
    reflected_matrix = reflection_matrix @ converted
    
    # Final step: rotate +90 degrees about Madness Y axis (old Blender Z axis)
    # +90 degree rotation about Y axis:
    # [cos(90°)  0  sin(90°)]   [0  0  1]
    # [   0      1     0    ] = [0  1  0]
    # [-sin(90°) 0  cos(90°)]   [-1 0  0]
    y_rotation_90 = np.array([
        [0, 0, 1],
        [0, 1, 0],
        [-1, 0, 0]
    ])
    
    final_matrix = y_rotation_90 @ reflected_matrix
    return final_matrix

def matrix_to_flat_string(matrix: np.ndarray) -> str:
    """Convert 3x3 matrix to semicolon-separated string in row-major order"""
    flat = matrix.flatten()
    return ";".join(f"{val:.6f}" for val in flat)

def generate_unique_name() -> str:
    """Generate a unique 8-character hex name for trigger"""
    return f"{random.randint(0, 0xFFFFFFFF):08x}"

def extract_trigger_objects(context) -> List[Dict]:
    """Extract trigger objects from the scene"""
    trigger_crc_map = build_trigger_crc_map()
    trigger_objects = []
    
    for obj in context.scene.objects:
        if obj.type != 'MESH':
            continue
            
        # Check if object name matches any trigger type
        obj_name = obj.name.upper()
        trigger_type = None
        
        # Direct match or prefix match
        for trig_type in trigger_crc_map.keys():
            if obj_name == trig_type or obj_name.startswith(trig_type + "_") or obj_name.startswith(trig_type + "."):
                trigger_type = trig_type
                break
        
        if not trigger_type:
            continue
            
        print(f"Found trigger object: {obj.name} -> {trigger_type}")
        
        # Get object transform data
        world_matrix = obj.matrix_world
        location = world_matrix.translation
        scale = world_matrix.to_scale()
        
        # Get pure rotation matrix (normalized by scale)
        rotation_matrix_scaled = world_matrix.to_3x3()
        # Normalize each column to remove scale influence
        col0 = rotation_matrix_scaled.col[0].normalized()
        col1 = rotation_matrix_scaled.col[1].normalized() 
        col2 = rotation_matrix_scaled.col[2].normalized()
        rotation_matrix = mathutils.Matrix([
            [col0.x, col1.x, col2.x],
            [col0.y, col1.y, col2.y],
            [col0.z, col1.z, col2.z]
        ])
        
        # Get object dimensions in LOCAL coordinate system (before world transform)
        # Map dimensions according to coordinate system conversion:
        # Blender (x,y,z) -> Madness (-x,z,-y)
        # Width = Y axis extent (Blender Y -> Madness Z)
        # Length = X axis extent (Blender X -> Madness X) 
        # Height = Z axis extent (Blender Z -> Madness Y)
        if obj.data and obj.data.vertices:
            # Get local space bounding box (no world matrix applied)
            local_coords = [v.co for v in obj.data.vertices]
            xs = [v.x for v in local_coords]
            ys = [v.y for v in local_coords]
            zs = [v.z for v in local_coords]
            
            # Calculate local dimensions, then scale by object scale
            local_length = (max(xs) - min(xs)) * scale.x  # X axis extent -> Length
            local_width = (max(ys) - min(ys)) * scale.y   # Y axis extent -> Width  
            local_height = (max(zs) - min(zs)) * scale.z  # Z axis extent -> Height
            
            length = local_length
            width = local_width
            height = local_height
        else:
            # Fallback to object dimensions if no vertices
            length = obj.dimensions.x   # X axis extent -> Length
            width = obj.dimensions.y    # Y axis extent -> Width
            height = obj.dimensions.z   # Z axis extent -> Height
        
        # Convert coordinates
        madness_position = convert_position_to_madness((location.x, location.y, location.z))
        madness_rotation = convert_rotation_matrix_to_madness(rotation_matrix)
        
        trigger_data = {
            'name': generate_unique_name(),
            'trigger_type': trigger_type,
            'material_crc': trigger_crc_map[trigger_type],
            'position': madness_position,
            'orientation': madness_rotation,
            'width': width,
            'height': height,
            'length': length,
            'blender_object': obj.name
        }
        
        trigger_objects.append(trigger_data)
    
    return trigger_objects

def create_triggers_xml(trigger_objects: List[Dict], output_path: Path):
    """Create the triggers.xml file"""
    # Create root structure with proper namespaces
    root = ET.Element("Reflection")
    
    # Add class definitions (as shown in the example)
    # First set of class definitions
    class1 = ET.SubElement(root, "class", name="BRTTIRefCount", base="root class")
    
    class2 = ET.SubElement(root, "class", name="BPersistent", base="BRTTIRefCount")
    ET.SubElement(class2, "prop", name="Name", type="String")
    
    class3 = ET.SubElement(root, "class", name="TriggerObjectManager", base="BPersistent")
    ET.SubElement(class3, "prop", name="Shapes", type="Fct")
    
    # Second set of class definitions (duplicated as in example)
    class4 = ET.SubElement(root, "class", name="BRTTIRefCount", base="root class")
    
    class5 = ET.SubElement(root, "class", name="BPersistent", base="BRTTIRefCount")
    ET.SubElement(class5, "prop", name="Name", type="String")
    
    class6 = ET.SubElement(root, "class", name="ShapeDesc", base="BPersistent")
    ET.SubElement(class6, "prop", name="Format", type="U32")
    ET.SubElement(class6, "prop", name="Type", type="U32")
    ET.SubElement(class6, "prop", name="Width", type="F32")
    ET.SubElement(class6, "prop", name="Height", type="F32")
    ET.SubElement(class6, "prop", name="Length", type="F32")
    ET.SubElement(class6, "prop", name="Mass", type="F32")
    ET.SubElement(class6, "prop", name="Material CRC", type="U32")
    ET.SubElement(class6, "prop", name="Relative Position", type="Vec3f")
    ET.SubElement(class6, "prop", name="Relative Orientation", type="Mtx3f")
    ET.SubElement(class6, "prop", name="Mesh Data Size", type="U32")
    ET.SubElement(class6, "prop", name="Vertex Count", type="U32")
    ET.SubElement(class6, "prop", name="Trigger", type="Bool")
    ET.SubElement(class6, "prop", name="Vertices", type="Fct")
    ET.SubElement(class6, "prop", name="Mesh Data", type="Fct")
    
    # Create data section
    trigger_manager = ET.SubElement(root, "data", **{"class": "TriggerObjectManager", "id": "0x65994AB0"})
    ET.SubElement(trigger_manager, "prop", name="Name", data="")
    
    shapes_prop = ET.SubElement(trigger_manager, "prop", name="Shapes", elements=str(len(trigger_objects)))
    funcpropdata = ET.SubElement(shapes_prop, "funcpropdata")
    
    # Add each trigger object
    for i, trigger in enumerate(trigger_objects):
        # Generate a unique ID for this shape
        shape_id = f"0xF328{4000 + i * 120:04X}"
        
        shape_data = ET.SubElement(funcpropdata, "data", **{"class": "ShapeDesc", "id": shape_id})
        
        # Add all required properties
        ET.SubElement(shape_data, "prop", name="Name", data=trigger['name'])
        ET.SubElement(shape_data, "prop", name="Format", data="0")
        ET.SubElement(shape_data, "prop", name="Type", data="0")
        ET.SubElement(shape_data, "prop", name="Width", data=f"{trigger['width']:.6f}")
        ET.SubElement(shape_data, "prop", name="Height", data=f"{trigger['height']:.6f}")
        ET.SubElement(shape_data, "prop", name="Length", data=f"{trigger['length']:.6f}")
        ET.SubElement(shape_data, "prop", name="Mass", data="0")
        ET.SubElement(shape_data, "prop", name="Material CRC", data=str(trigger['material_crc']))
        
        # Position as semicolon-separated string
        pos_str = f"{trigger['position'][0]:.6f};{trigger['position'][1]:.6f};{trigger['position'][2]:.6f}"
        ET.SubElement(shape_data, "prop", name="Relative Position", data=pos_str)
        
        # Orientation as flattened 3x3 matrix
        orient_str = matrix_to_flat_string(trigger['orientation'])
        ET.SubElement(shape_data, "prop", name="Relative Orientation", data=orient_str)
        
        ET.SubElement(shape_data, "prop", name="Mesh Data Size", data="0")
        ET.SubElement(shape_data, "prop", name="Vertex Count", data="0")
        ET.SubElement(shape_data, "prop", name="Trigger", data="false")
        
        # Empty vertices and mesh data
        vertices_prop = ET.SubElement(shape_data, "prop", name="Vertices", elements="0")
        ET.SubElement(vertices_prop, "funcpropdata")
        
        mesh_prop = ET.SubElement(shape_data, "prop", name="Mesh Data", elements="0")
        ET.SubElement(mesh_prop, "funcpropdata")
    
    # Write the XML file
    ET.indent(root, space="    ")
    tree = ET.ElementTree(root)
    
    # Write with XML declaration
    with open(output_path, 'wb') as f:
        tree.write(f, encoding="utf-8", xml_declaration=True)
    
    print(f"Exported {len(trigger_objects)} triggers to {output_path}")

class TriggersExporter(bpy.types.Operator, ExportHelper):
    """Export Triggers XML"""
    bl_idname = "export_scene.triggers"
    bl_label = "Export Triggers"
    
    filename_ext = ".xml"
    
    filter_glob: StringProperty(
        default="*.xml",
        options={'HIDDEN'},
        maxlen=255,
    ) # type: ignore
    
    def execute(self, context):
        try:
            # Extract trigger objects from scene
            trigger_objects = extract_trigger_objects(context)
            
            if not trigger_objects:
                self.report({'WARNING'}, "No trigger objects found in scene. Objects should be named with trigger types like TRG_START, TRG_FINISH, etc.")
                return {'CANCELLED'}
            
            # Create triggers.xml
            output_path = Path(self.filepath)
            create_triggers_xml(trigger_objects, output_path)
            
            # Print summary
            trigger_summary = {}
            for trigger in trigger_objects:
                ttype = trigger['trigger_type']
                if ttype not in trigger_summary:
                    trigger_summary[ttype] = 0
                trigger_summary[ttype] += 1
            
            summary_text = ", ".join([f"{count}x {ttype}" for ttype, count in trigger_summary.items()])
            self.report({'INFO'}, f"Exported triggers: {summary_text}")
            
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Export failed: {str(e)}")
            return {'CANCELLED'}

def menu_func_export(self, context):
    self.layout.operator(TriggersExporter.bl_idname, text="Madness Triggers (.xml)")

def register():
    bpy.utils.register_class(TriggersExporter)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

def unregister():
    bpy.utils.unregister_class(TriggersExporter)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)

if __name__ == "__main__":
    register() 