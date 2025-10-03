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
