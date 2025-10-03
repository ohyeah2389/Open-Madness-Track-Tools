import bpy # type: ignore
from bpy.props import StringProperty # type: ignore
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
            with open(settings_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}

def save_settings_to_file(settings):
    """Save settings to JSON file (development fallback)."""
    settings_file = get_settings_file_path()
    try:
        with open(settings_file, 'w') as f:
            json.dump(settings, f, indent=2)
    except IOError:
        print(f"Warning: Could not save settings to {settings_file}")

def get_addon_preferences(context):
    """Get addon preferences, handling both development and installed scenarios."""
    # Try different possible addon names
    possible_names = [
        __name__.split('.')[0],  # Get the root module name
        "madness_scene_export",  # Development name
        "madness_scene_exporter",  # Manifest ID
    ]
    
    # Add the full addon name if it looks like a Blender extension
    root_module = __name__.split('.')[0]
    if root_module == "bl_ext":
        # For Blender extensions, try the full module path
        full_module_name = '.'.join(__name__.split('.')[:-1])  # Remove the current module name
        if full_module_name not in possible_names:
            possible_names.insert(0, full_module_name)
    
    for name in possible_names:
        try:
            if name in context.preferences.addons:
                return context.preferences.addons[name].preferences, name
        except (KeyError, AttributeError):
            continue
    
    # If nothing found, print debug info
    available_addons = [name for name in context.preferences.addons.keys() if "madness" in name.lower()]
    print(f"Debug: Could not find addon preferences. Available Madness addons: {available_addons}")
    print(f"Debug: Tried names: {possible_names}")
    
    return None, None

def get_exporter_path(context):
    """Get exporter path from preferences or fallback file."""
    preferences, addon_name = get_addon_preferences(context)
    
    if preferences and preferences.exporter_exe and preferences.exporter_exe != "MEBExporterExtended.exe":
        # Found valid preferences with non-default value
        return preferences.exporter_exe, f"preferences ({addon_name})"
    
    # Fall back to JSON file
    settings = load_settings_from_file()
    if "exporter_exe" in settings:
        return settings["exporter_exe"], "settings file"
    
    # Final fallback
    return "MEBExporterExtended.exe", "default"

def set_exporter_path(context, path):
    """Set exporter path in both preferences and fallback file."""
    # Try to save to preferences
    preferences, addon_name = get_addon_preferences(context)
    if preferences and not getattr(preferences, '_updating', False):
        preferences._updating = True
        try:
            preferences.exporter_exe = path
            print(f"Saved exporter path to preferences ({addon_name})")
        finally:
            preferences._updating = False
    
    # Always save to fallback file for development
    settings = load_settings_from_file()
    settings["exporter_exe"] = path
    save_settings_to_file(settings)
    print(f"Saved exporter path to settings file: {get_settings_file_path()}") 