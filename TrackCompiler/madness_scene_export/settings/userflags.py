"""Shared SGX userflag definitions and helpers."""

from typing import List, Tuple


DEFAULT_USERFLAGS = 0b00000000000100000000000001110101


def userflags_to_bool_vector(value: int = DEFAULT_USERFLAGS) -> List[bool]:
    return [bool(value & (1 << i)) for i in range(32)]


def bool_vector_to_userflags(flags) -> int:
    """Convert a 32-element boolean sequence to an integer bitmask."""
    value = 0
    for i, flag in enumerate(flags):
        if flag:
            value |= 1 << i
    return value


# Index in this list maps directly to the bit index (0-31).
USERFLAG_DEFINITIONS: List[Tuple[str, str]] = [
    ("Far Distant Mesh", "Draws beyond the usual automatic LOD cutoff limits."),
    ("Garage Node Placeholder", "Node placeholder where cars are positioned."),
    ("Cannot Cull", "Cannot be culled using radius-over-distance rules."),
    ("Underpass", "Road underpass mesh (removed for reflections)."),
    ("Casts Shadows", "Casts shadows."),
    ("Receives Shadows", "Receives shadows cast by other objects."),
    ("Render In Dynamic Envmap", "Renders this object in dynamic envmaps."),
    ("Damageable", "Can receive mesh damage via MeshDamageManager."),
    ("Distortion", "Renders as distortion only; usually set by code, not art."),
    ("High Detail", "Excluded when using Medium and Low Detail settings."),
    ("Dummy For Shadow Casting", "Renders only when casting shadows."),
    ("Animated Ads", "Registers this mesh with the AnimatedAds system."),
    ("Billboard Mesh", "Mesh contains billboarded polygons."),
    ("Needs Height Occlusion Tests", "Always performs full height occlusion tests."),
    ("Force Render Shadows", "Forces this object's shadows to render."),
    ("Mesh Has Flares", "Mesh contains flares."),
    ("Mesh Has Video", "Mesh contains video surfaces."),
    ("Swappable Decoration", "Mesh is swappable decoration."),
    ("Physics Mesh", "Mesh participates in physics."),
    ("Grassy Terrain", "Marks this mesh as grassy terrain."),
    ("Render In Reflection", "Renders this mesh in reflections."),
    ("God Ray Occluder", "Blocks god rays."),
    ("Lower Emap Cull", "Reserved / future expansion."),
    ("Hide In Spring", "Does not render in spring."),
    ("Hide In Summer", "Does not render in summer."),
    ("Hide In Autumn", "Does not render in autumn."),
    ("Hide In Winter", "Does not render in winter."),
    ("Hide In Snow", "Does not render in snow."),
    ("Medium Detail", "Excluded when using Low Detail settings."),
    ("Grass Blade Renderable", "Marks this as a grass blade mesh."),
    ("Trees", "Marks this as a tree mesh."),
    ("Dont Render In Static Envmap", "Forces object to not render in static envmaps."),
]


USERFLAG_CATEGORIES: List[Tuple[str, List[int]]] = [
    (
        "Rendering",
        [0, 2, 3, 6, 8, 9, 10, 12, 13, 20, 22, 28, 31],
    ),
    (
        "Shadows",
        [4, 5, 14, 21],
    ),
    (
        "Systems",
        [1, 7, 11, 15, 16, 17, 18],
    ),
    (
        "Environment",
        [19, 29, 30],
    ),
    (
        "Seasons",
        [23, 24, 25, 26, 27],
    ),
]


def get_userflag_name(bit_index: int) -> str:
    """Return the user-facing name for a bit index."""
    if 0 <= bit_index < len(USERFLAG_DEFINITIONS):
        return USERFLAG_DEFINITIONS[bit_index][0]
    return f"Unknown Flag {bit_index}"


def get_userflag_description(bit_index: int) -> str:
    """Return the tooltip description for a bit index."""
    if 0 <= bit_index < len(USERFLAG_DEFINITIONS):
        return USERFLAG_DEFINITIONS[bit_index][1]
    return "Unknown userflag."
