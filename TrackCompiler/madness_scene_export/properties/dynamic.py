import bpy  # type: ignore
from bpy.props import BoolProperty, EnumProperty, FloatProperty, PointerProperty, StringProperty  # type: ignore


# Physics material names recognised by the Madness engine.
PHYSICS_MATERIALS = [
    "styropor",
    "plastic pipe",
    "plastic solid",
    "rubber tyre",
    "metal and tin",
    "Wood",
    "Wood white",
    "hay",
    "bouncy",
]

PHYSICS_MATERIAL_ITEMS = [(name, name, f"Physics material: {name}") for name in PHYSICS_MATERIALS]


def is_dynamic_definition(obj):
    """Check if an object is the root of a dynamic object definition."""
    return bool(obj) and obj.madness_dynamic_def.is_definition


def _definition_poll(self, obj):
    return is_dynamic_definition(obj)


def get_definition_shapes(definition):
    """Collect the mesh objects making up a definition's collision shapes."""
    shapes = [definition] if definition.type == "MESH" else []
    shapes.extend(child for child in definition.children_recursive if child.type == "MESH")
    return shapes


def get_definition_name(definition):
    """Get the name a definition is exported under."""
    return definition.madness_dynamic_def.export_name or definition.name


class MadnessDynamicDefinition(bpy.types.PropertyGroup):
    """Authoring properties for a dynamic physics object definition."""

    is_definition: BoolProperty(
        name="Dynamic Object Definition",
        description=(
            "Treat this object as a dynamic physics object definition. Its mesh, and the "
            "meshes of any children, become collision shapes"
        ),
        default=False,
    )  # type: ignore

    export_name: StringProperty(
        name="Export Name",
        description="Name written to dynamic_collisions.xml (defaults to the object name)",
        default="",
    )  # type: ignore

    physics_material: EnumProperty(
        name="Physics Material",
        description="Physics material applied to this collision shape",
        items=PHYSICS_MATERIAL_ITEMS,
        default="plastic solid",
    )  # type: ignore

    mass: FloatProperty(
        name="Mass",
        description="Mass of this collision shape in kg",
        default=50.0,
        min=0.001,
        soft_max=1000.0,
    )  # type: ignore


class MadnessDynamicProperties(bpy.types.PropertyGroup):
    """Properties for a placed instance of a dynamic object definition."""

    definition: PointerProperty(
        name="Definition",
        description="Dynamic object definition to place at this empty",
        type=bpy.types.Object,
        poll=_definition_poll,
    )  # type: ignore

    use_scale_override: BoolProperty(
        name="Override Scale",
        description="Override the empty's transform scale for this instance",
        default=False,
    )  # type: ignore

    scale_x: FloatProperty(name="Scale X", default=1.0, min=0.01, soft_max=10.0)  # type: ignore
    scale_y: FloatProperty(name="Scale Y", default=1.0, min=0.01, soft_max=10.0)  # type: ignore
    scale_z: FloatProperty(name="Scale Z", default=1.0, min=0.01, soft_max=10.0)  # type: ignore


def is_sms_dynamic(obj):
    """Check if object can be used as a dynamic physics placement."""
    return bool(obj) and obj.type == "EMPTY"


def get_dynamic_name(obj):
    """Get dynamic object display name for exported instance naming."""
    if obj.name.startswith("SMS_DYN_"):
        return obj.name[8:]
    return obj.name


def register():
    for cls in (MadnessDynamicDefinition, MadnessDynamicProperties):
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            bpy.utils.unregister_class(cls)
            bpy.utils.register_class(cls)

    bpy.types.Object.madness_dynamic_def = PointerProperty(type=MadnessDynamicDefinition)
    bpy.types.Object.madness_dynamic = PointerProperty(type=MadnessDynamicProperties)


def unregister():
    for attr in ("madness_dynamic", "madness_dynamic_def"):
        if hasattr(bpy.types.Object, attr):
            delattr(bpy.types.Object, attr)

    for cls in (MadnessDynamicProperties, MadnessDynamicDefinition):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
