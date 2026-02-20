import bpy  # type: ignore
from bpy.props import (  # type: ignore
    BoolProperty, FloatProperty, StringProperty, EnumProperty
)
import xml.etree.ElementTree as ET
from pathlib import Path
import os


# Cache for template list to avoid repeated file reads
_template_cache = None

def get_available_dynamic_templates():
    """Load available dynamic object templates from master_dynamic_collisions.xml"""
    global _template_cache
    
    # Return cached results if available
    if _template_cache is not None:
        return _template_cache
    
    # Resolve from madness_scene_export/properties -> madness_scene_export/database
    addon_root = Path(__file__).resolve().parent.parent
    database_path = addon_root / "database" / "master_dynamic_collisions.xml"
    
    templates = [("", "Select Template", "")]
    
    if database_path.exists():
        try:
            tree = ET.parse(database_path)
            root = tree.getroot()
            
            # Extract template names from PxRigidDynamic objects
            for rigid_dynamic in root.findall('PxRigidDynamic'):
                name_elem = rigid_dynamic.find('Name')
                if name_elem is not None and name_elem.text:
                    template_name = name_elem.text
                    # Create enum item (value, name, description)
                    templates.append((template_name, template_name, f"Dynamic object: {template_name}"))
            
            # Sort templates alphabetically (except for the first empty entry)
            if len(templates) > 1:
                first_item = templates[0]
                sorted_templates = sorted(templates[1:], key=lambda x: x[0])
                templates = [first_item] + sorted_templates
                
        except Exception as e:
            print(f"Error loading dynamic templates: {e}")
            # Return basic template list on error
            templates = [("", "Select Template", ""), ("ERROR", "Template Load Error", "Failed to load templates")]
    
    # Cache the results
    _template_cache = templates
    return templates


def update_template_list(self, context):
    """Update the template list when needed"""
    try:
        return get_available_dynamic_templates()
    except Exception as e:
        print(f"Error in update_template_list: {e}")
        # Return safe fallback
        return [("", "Select Template", ""), ("ERROR", "Template Load Error", "Failed to load templates")]


class MadnessDynamicProperties(bpy.types.PropertyGroup):
    """Properties for dynamic physics empties"""

    # Template Selection
    template_name: StringProperty(
        name="Template",
        description="Dynamic object template to use (select from UI)",
        default=""
    )  # type: ignore

    # Mass override
    use_mass_override: BoolProperty(
        name="Override Mass",
        description="Override the default mass of the template",
        default=False
    )  # type: ignore

    mass: FloatProperty(
        name="Mass",
        description="Mass of the dynamic object in kg",
        default=50.0,
        min=0.1,
        max=1000.0
    )  # type: ignore

    # Material override
    use_material_override: BoolProperty(
        name="Override Material",
        description="Override the default physics material",
        default=False
    )  # type: ignore

    physics_material: EnumProperty(
        name="Physics Material",
        description="Physics material for the object",
        items=[
            ("styropor", "Styropor", "Styrofoam material"),
            ("plastic pipe", "Plastic Pipe", "Plastic pipe material"),
            ("plastic solid", "Plastic Solid", "Solid plastic material"),
            ("metal", "Metal", "Metal material"),
            ("concrete", "Concrete", "Concrete material"),
            ("wood", "Wood", "Wood material"),
            ("rubber", "Rubber", "Rubber material"),
            ("glass", "Glass", "Glass material"),
        ],
        default="styropor"
    )  # type: ignore

    # Scale override
    use_scale_override: BoolProperty(
        name="Override Scale",
        description="Override the template scale (affects collision mesh)",
        default=False
    )  # type: ignore

    scale_x: FloatProperty(
        name="Scale X",
        description="Scale factor in X axis",
        default=1.0,
        min=0.1,
        max=10.0
    )  # type: ignore

    scale_y: FloatProperty(
        name="Scale Y",
        description="Scale factor in Y axis",
        default=1.0,
        min=0.1,
        max=10.0
    )  # type: ignore

    scale_z: FloatProperty(
        name="Scale Z",
        description="Scale factor in Z axis",
        default=1.0,
        min=0.1,
        max=10.0
    )  # type: ignore



def is_sms_dynamic(obj):
    """Check if object can be used as a dynamic physics empty."""
    return obj and obj.type == 'EMPTY'


def get_dynamic_name(obj):
    """Get dynamic object display name for exported instance naming."""
    if obj.name.startswith('SMS_DYN_'):
        return obj.name[8:]  # Remove 'SMS_DYN_' prefix
    return obj.name


def refresh_template_list():
    """Force refresh of the cached template list."""
    global _template_cache
    # Clear the cache to force reload
    _template_cache = None


def register():
    try:
        bpy.utils.register_class(MadnessDynamicProperties)
    except ValueError:
        # Already registered, unregister and re-register
        bpy.utils.unregister_class(MadnessDynamicProperties)
        bpy.utils.register_class(MadnessDynamicProperties)
    
    # Add dynamic properties to objects
    if not hasattr(bpy.types.Object, 'madness_dynamic'):
        bpy.types.Object.madness_dynamic = bpy.props.PointerProperty(type=MadnessDynamicProperties)
    
    # Load templates to populate cache
    try:
        templates = get_available_dynamic_templates()
        print(f"Loaded {len(templates)-1} dynamic object templates")
    except Exception as e:
        print(f"Warning: Could not load dynamic templates: {e}")


def unregister():
    if hasattr(bpy.types.Object, 'madness_dynamic'):
        del bpy.types.Object.madness_dynamic
    
    try:
        bpy.utils.unregister_class(MadnessDynamicProperties)
    except RuntimeError:
        pass  # Already unregistered
