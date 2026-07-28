from pathlib import Path
import json
import tempfile


def get_settings_file_path():
    """Get path to settings file for development persistence."""
    temp_dir = tempfile.gettempdir()
    return Path(temp_dir) / "madness_scene_exporter_settings.json"


def load_settings_from_file():
    """Load settings from JSON file (development fallback)."""
    settings_file = get_settings_file_path()
    if settings_file.exists():
        try:
            with open(settings_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def get_addon_preferences(context):
    """Get addon preferences, handling both development and installed scenarios."""
    possible_names = [
        __name__.split(".")[0],  # Get the root module name
        "madness_scene_export",  # Development name
        "madness_scene_exporter",  # Manifest ID
    ]

    # For Blender extensions, try the full module path
    root_module = __name__.split(".")[0]
    if root_module == "bl_ext" and __name__ not in possible_names:
        possible_names.insert(0, __name__)

    for name in possible_names:
        try:
            if name in context.preferences.addons:
                return context.preferences.addons[name].preferences, name
        except (KeyError, AttributeError):
            continue

    available_addons = [
        name for name in context.preferences.addons.keys() if "madness" in name.lower()
    ]
    print(f"Debug: Could not find addon preferences. Available Madness addons: {available_addons}")
    print(f"Debug: Tried names: {possible_names}")

    return None, None
