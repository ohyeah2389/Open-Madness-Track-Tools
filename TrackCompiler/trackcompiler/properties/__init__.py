# Properties module for OMTT TrackCompiler

from .dynamic import (
    get_definition_name,
    get_definition_shapes,
    get_definition_visual,
    is_dynamic_definition,
    is_sms_dynamic,
    get_dynamic_name
)
from .light import is_sms_light
from .camera import is_sms_camera
from .area import is_sms_area, get_area_name
from .sound import is_sms_sound, get_sound_name

__all__ = [
    'get_definition_name',
    'get_definition_shapes',
    'get_definition_visual',
    'is_dynamic_definition',
    'is_sms_dynamic',
    'get_dynamic_name',
    'is_sms_light',
    'is_sms_camera',
    'is_sms_area',
    'get_area_name',
    'is_sms_sound',
    'get_sound_name'
]
