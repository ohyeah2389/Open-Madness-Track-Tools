# Settings and configuration module for OMTT TrackCompiler

from .empty_meb_settings import convert_to_relative_game_path
from . import meb_export_settings

__all__ = [
    "convert_to_relative_game_path",
    "meb_export_settings",
]
