# Properties module for OMTT TrackCompiler

from .dynamic_properties import (
    get_available_dynamic_templates,
    is_sms_dynamic,
    get_dynamic_name,
    refresh_template_list
)
from .light_properties import is_sms_light
from .camera_properties import is_sms_camera
from .area_properties import is_sms_area, get_area_name

__all__ = [
    'get_available_dynamic_templates',
    'is_sms_dynamic',
    'get_dynamic_name',
    'refresh_template_list',
    'is_sms_light',
    'is_sms_camera',
    'is_sms_area',
    'get_area_name'
]
