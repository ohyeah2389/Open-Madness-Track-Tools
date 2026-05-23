"""Utility functions shared across the addon"""

from ..settings import settings_manager


def get_game_folder(context):
    """Get game folder path from preferences or fallback file."""
    preferences, addon_name = settings_manager.get_addon_preferences(context)

    if preferences and preferences.madness_folder:
        return preferences.madness_folder, f"preferences ({addon_name})"

    settings = settings_manager.load_settings_from_file()
    if "madness_folder" in settings:
        return settings["madness_folder"], "settings file"

    return "", "not set"


def sanitize(name: str) -> str:
    """Replace characters that upset either Windows or Madness Engine."""
    import re
    return re.sub(r"[^A-Za-z0-9_-]", "_", name)


def effective_materials_for_object(obj, fallback_materials=None):
    """Return per-slot materials honoring OBJECT-linked overrides."""
    if not obj:
        return list(fallback_materials) if fallback_materials else []

    slots = getattr(obj, "material_slots", None)
    if not slots:
        return list(fallback_materials) if fallback_materials else []

    effective_materials = [slot.material for slot in slots]
    if fallback_materials and len(fallback_materials) > len(effective_materials):
        effective_materials.extend(fallback_materials[len(effective_materials):])
    return effective_materials
