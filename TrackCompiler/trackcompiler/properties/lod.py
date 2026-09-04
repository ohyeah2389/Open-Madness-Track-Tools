import bpy  # type: ignore
from bpy.props import CollectionProperty, FloatProperty, PointerProperty  # type: ignore


LOD_PREFIX = "SMS_LOD_"


def is_sms_lod(obj):
    """Check if object is an SMS LOD control empty."""
    return bool(obj) and obj.type == "EMPTY" and obj.name.startswith(LOD_PREFIX)


def get_lod_name(obj):
    """Get LOD node name without the SMS_LOD_ prefix."""
    if obj.name.startswith(LOD_PREFIX):
        rest = obj.name[len(LOD_PREFIX) :]
        return rest or obj.name
    return obj.name


def _is_lod_exportable(obj):
    if not obj or getattr(obj, "type", None) not in {"MESH", "CURVE"}:
        return False
    if obj.name.startswith(LOD_PREFIX) or obj.name.split(".", 1)[0].startswith(
        ("TEMP_MESH", "TEMP_CURVE_MESH", "TEMP_COMBINED")
    ):
        return False
    if obj.type == "MESH":
        data = getattr(obj, "data", None)
        return bool(data and data.polygons)
    return bool(getattr(getattr(obj, "data", None), "bevel_depth", 0) > 0)


def _iter_lod_slots(lod):
    yield lod.target_0, lod.distance_0
    yield lod.target_1, lod.distance_1
    for level in lod.extra_levels:
        yield level.target, level.distance


def _make_target_poll(attr):
    def poll(self, candidate):
        if not _is_lod_exportable(candidate):
            return False
        if getattr(bpy.context, "object", None) is candidate:
            return False
        if getattr(self, attr, None) is candidate:
            return True
        for obj in bpy.data.objects:
            lod = getattr(obj, "madness_lod", None)
            if not lod:
                continue
            for target, _distance in _iter_lod_slots(lod):
                if target is candidate:
                    return False
        return True

    return poll


class MadnessLODLevel(bpy.types.PropertyGroup):
    """An extra detail level beyond the two default slots."""

    target: PointerProperty(
        name="LOD Object",
        description="Mesh used for this detail level",
        type=bpy.types.Object,
        poll=_make_target_poll("target"),
    )  # type: ignore

    distance: FloatProperty(
        name="Switch Distance",
        description="Farthest camera distance at which this LOD level renders",
        default=50.0,
        min=0.0,
        soft_max=10000.0,
        unit="LENGTH",
    )  # type: ignore


class MadnessLODProperties(bpy.types.PropertyGroup):
    """Properties for SMS_LOD_ prefixed empty objects."""

    target_0: PointerProperty(
        name="LOD 0",
        description="Highest-detail mesh",
        type=bpy.types.Object,
        poll=_make_target_poll("target_0"),
    )  # type: ignore

    distance_0: FloatProperty(
        name="Switch Distance",
        description="Farthest camera distance at which this LOD level renders",
        default=50.0,
        min=0.0,
        soft_max=10000.0,
        unit="LENGTH",
    )  # type: ignore

    target_1: PointerProperty(
        name="LOD 1",
        description="Next detail mesh",
        type=bpy.types.Object,
        poll=_make_target_poll("target_1"),
    )  # type: ignore

    distance_1: FloatProperty(
        name="Switch Distance",
        description="Farthest camera distance at which this LOD level renders",
        default=100.0,
        min=0.0,
        soft_max=10000.0,
        unit="LENGTH",
    )  # type: ignore

    extra_levels: CollectionProperty(type=MadnessLODLevel)  # type: ignore


def assigned_lod_levels(obj):
    """Return unique (target, distance) pairs for filled LOD slots."""
    lod = getattr(obj, "madness_lod", None)
    if not lod:
        return []
    seen = set()
    assigned = []
    for target, distance in _iter_lod_slots(lod):
        if not target or not _is_lod_exportable(target):
            continue
        ptr = target.as_pointer()
        if ptr in seen:
            continue
        seen.add(ptr)
        assigned.append((target, float(distance)))
    return assigned


def register():
    for cls in (MadnessLODLevel, MadnessLODProperties):
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            bpy.utils.unregister_class(cls)
            bpy.utils.register_class(cls)
    bpy.types.Object.madness_lod = PointerProperty(type=MadnessLODProperties)


def unregister():
    if hasattr(bpy.types.Object, "madness_lod"):
        del bpy.types.Object.madness_lod
    for cls in (MadnessLODProperties, MadnessLODLevel):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
