import bpy # type: ignore
from pathlib import Path
import json

# Valid shader/technique combinations based on analysis
SHADER_TECHNIQUES = {
    'Render\\Shaders\\baked_instance_tree.fx': ['Basic_AlphaTest'],
    'Render\\Shaders\\basic.fx': ['Basic', 'Basic_DoubleSided'],
    'Render\\Shaders\\basic_anim.fx': ['Basic'],
    'Render\\Shaders\\basic_instanced.fx': ['Basic'],
    'Render\\Shaders\\basic_translucent.fx': ['Basic_Translucent', 'Basic_Translucent_DoubleSided'],
    'Render\\Shaders\\basic_windows.fx': ['Basic'],
    'Render\\Shaders\\billboard_instance_tree.fx': ['Basic_AlphaTest'],
    'Render\\Shaders\\lightglow_billboard.fx': ['Lightglow'],
    'Render\\Shaders\\locator.fx': ['locator'],
    'Render\\Shaders\\new_ground.fx': ['Ground'],
    'Render\\Shaders\\new_ground_transition.fx': ['Ground_Transition'],
    'Render\\Shaders\\overlay.fx': ['Overlay', 'Overlay_floatingMesh', 'SolidOverlay'],
    'Render\\Shaders\\road_dbv.fx': ['road_dbv'],
    'Render\\Shaders\\skintest.fx': ['skintest'],
    'Render\\Shaders\\water.fx': ['Water'],
}

# Shader parameters by technique (from analysis)
SHADER_PARAMETERS = {
    'Render\\Shaders\\baked_instance_tree.fx': {
        'Basic_AlphaTest': [
            ('alphaTestParam', 'EPT_F32'),
            ('diffuseTexture', 'EPT_TEXTURE'),
            ('horizontalFramesNr', 'EPT_F32'),
            ('normalTexture', 'EPT_TEXTURE'),
            ('specialNormalMap', 'EPT_BOOL'),
            ('treeThickness', 'EPT_F32'),
        ],
    },
    'Render\\Shaders\\basic.fx': {
        'Basic': [
            ('AOTexture', 'EPT_TEXTURE'),
            ('diffuseTexture', 'EPT_TEXTURE'),
            ('emissiveTexture', 'EPT_TEXTURE'),
            ('emissiveTexture2', 'EPT_TEXTURE'),
            ('emissive_scale', 'EPT_F32'),
            ('fresnelFactor', 'EPT_F32'),
            ('globalEMapFactor', 'EPT_F32'),
            ('globalSpecularFactor', 'EPT_F32'),
            ('logoTexture', 'EPT_TEXTURE'),
            ('maxSpecPower', 'EPT_F32'),
            ('minSpecPower', 'EPT_F32'),
            ('normalTexture', 'EPT_TEXTURE'),
            ('specialNormalMap', 'EPT_BOOL'),
            ('specularTexture', 'EPT_TEXTURE'),
            ('tintAlpha', 'EPT_F32'),
            ('tintColour', 'EPT_VEC4'),
            ('tintForeground', 'EPT_F32'),
            ('tintMaskFromR', 'EPT_F32'),
        ],
        'Basic_DoubleSided': [
            ('diffuseTexture', 'EPT_TEXTURE'),
            ('fresnelFactor', 'EPT_F32'),
            ('globalEMapFactor', 'EPT_F32'),
            ('globalSpecularFactor', 'EPT_F32'),
            ('maxSpecPower', 'EPT_F32'),
            ('minSpecPower', 'EPT_F32'),
            ('normalTexture', 'EPT_TEXTURE'),
            ('specialNormalMap', 'EPT_BOOL'),
            ('specularTexture', 'EPT_TEXTURE'),
        ],
    },
    'Render\\Shaders\\basic_anim.fx': {
        'Basic': [
            ('animationMode', 'EPT_S32'),
            ('diffuseTexture', 'EPT_TEXTURE'),
            ('emissiveTexture', 'EPT_TEXTURE'),
            ('emissive_scale', 'EPT_F32'),
            ('frameDimX', 'EPT_S32'),
            ('frameDimY', 'EPT_S32'),
            ('frameDisplayTime', 'EPT_F32'),
            ('frameInitialTimeOffset', 'EPT_F32'),
            ('frameTransitionTime', 'EPT_F32'),
            ('fresnelFactor', 'EPT_F32'),
            ('globalEMapFactor', 'EPT_F32'),
        ],
    },
    'Render\\Shaders\\basic_translucent.fx': {
        'Basic_Translucent': [
            ('AOTexture', 'EPT_TEXTURE'),
            ('diffuseTexture', 'EPT_TEXTURE'),
            ('fresnelFactor', 'EPT_F32'),
            ('globalEMapFactor', 'EPT_F32'),
            ('globalSpecularFactor', 'EPT_F32'),
            ('maxSpecPower', 'EPT_F32'),
            ('minSpecPower', 'EPT_F32'),
            ('normalTexture', 'EPT_TEXTURE'),
            ('specialNormalMap', 'EPT_BOOL'),
            ('specularTexture', 'EPT_TEXTURE'),
        ],
        'Basic_Translucent_DoubleSided': [
            ('diffuseTexture', 'EPT_TEXTURE'),
            ('fresnelFactor', 'EPT_F32'),
            ('globalSpecularFactor', 'EPT_F32'),
            ('maxSpecPower', 'EPT_F32'),
            ('minSpecPower', 'EPT_F32'),
            ('normalTexture', 'EPT_TEXTURE'),
            ('specialNormalMap', 'EPT_BOOL'),
            ('specularTexture', 'EPT_TEXTURE'),
        ],
    },
    'Render\\Shaders\\basic_windows.fx': {
        'Basic': [
            ('AOTexture', 'EPT_TEXTURE'),
            ('diffuseTexture', 'EPT_TEXTURE'),
            ('emissiveTexture', 'EPT_TEXTURE'),
            ('emissiveTexture2', 'EPT_TEXTURE'),
            ('emissive_scale', 'EPT_F32'),
            ('fresnelFactor', 'EPT_F32'),
            ('globalEMapFactor', 'EPT_F32'),
            ('globalSpecularFactor', 'EPT_F32'),
            ('maxSpecPower', 'EPT_F32'),
            ('minSpecPower', 'EPT_F32'),
            ('normalTexture', 'EPT_TEXTURE'),
            ('specialNormalMap', 'EPT_BOOL'),
            ('specularTexture', 'EPT_TEXTURE'),
            ('tint_maskTexture', 'EPT_TEXTURE'),
            ('tint_tintB', 'EPT_VEC4'),
            ('tint_tintG', 'EPT_VEC4'),
            ('tint_tintR', 'EPT_VEC4'),
        ],
    },
    'Render\\Shaders\\billboard_instance_tree.fx': {
        'Basic_AlphaTest': [
            ('alphaTestParam', 'EPT_F32'),
            ('diffuseTexture', 'EPT_TEXTURE'),
        ],
    },
    'Render\\Shaders\\lightglow_billboard.fx': {
        'Lightglow': [
            ('diffuseTexture', 'EPT_TEXTURE'),
            ('distanceScale', 'EPT_F32'),
        ],
    },
    'Render\\Shaders\\locator.fx': {
        'locator': [],
    },
    'Render\\Shaders\\new_ground.fx': {
        'Ground': [
            ('broadDiffuseTexture', 'EPT_TEXTURE'),
            ('detailDiffuseTexture', 'EPT_TEXTURE'),
            ('detailUScale', 'EPT_F32'),
            ('detailVScale', 'EPT_F32'),
            ('globalSpecularFactor', 'EPT_F32'),
            ('middleDiffuseTexture', 'EPT_TEXTURE'),
            ('normalTexture', 'EPT_TEXTURE'),
            ('puddleTexture', 'EPT_TEXTURE'),
            ('specularTexture', 'EPT_TEXTURE'),
            ('uvScaleForWetMasks', 'EPT_F32'),
        ],
    },
    'Render\\Shaders\\new_ground_transition.fx': {
        'Ground_Transition': [
            ('additiveDetail2', 'EPT_BOOL'),
            ('blendInvert', 'EPT_BOOL'),
            ('blendTexture', 'EPT_TEXTURE'),
            ('broadDiffuseTexture1', 'EPT_TEXTURE'),
            ('broadDiffuseTexture2', 'EPT_TEXTURE'),
            ('detailDiffuseTexture1', 'EPT_TEXTURE'),
            ('detailDiffuseTexture2', 'EPT_TEXTURE'),
            ('detailUScale1', 'EPT_F32'),
            ('detailUScale2', 'EPT_F32'),
            ('detailVScale1', 'EPT_F32'),
            ('detailVScale2', 'EPT_F32'),
            ('globalSpecularFactor1', 'EPT_F32'),
            ('globalSpecularFactor2', 'EPT_F32'),
            ('middleDiffuseTexture1', 'EPT_TEXTURE'),
            ('middleDiffuseTexture2', 'EPT_TEXTURE'),
            ('normalTexture2', 'EPT_TEXTURE'),
            ('puddleTexture', 'EPT_TEXTURE'),
            ('specularTexture1', 'EPT_TEXTURE'),
            ('specularTexture2', 'EPT_TEXTURE'),
            ('uvScaleForWetMasks', 'EPT_F32'),
        ],
    },
    'Render\\Shaders\\overlay.fx': {
        'Overlay': [
            ('blendTexture', 'EPT_TEXTURE'),
            ('diffuseTexture', 'EPT_TEXTURE'),
            ('fresnelFactor', 'EPT_F32'),
            ('globalSpecularFactor', 'EPT_F32'),
            ('maxSpecPower', 'EPT_F32'),
            ('minSpecPower', 'EPT_F32'),
            ('specularTexture', 'EPT_TEXTURE'),
        ],
        'Overlay_floatingMesh': [
            ('blendTexture', 'EPT_TEXTURE'),
            ('diffuseTexture', 'EPT_TEXTURE'),
            ('fresnelFactor', 'EPT_F32'),
            ('globalSpecularFactor', 'EPT_F32'),
            ('maxSpecPower', 'EPT_F32'),
            ('minSpecPower', 'EPT_F32'),
            ('normalTexture', 'EPT_TEXTURE'),
            ('specularTexture', 'EPT_TEXTURE'),
        ],
        'SolidOverlay': [
            ('blendTexture', 'EPT_TEXTURE'),
            ('diffuseTexture', 'EPT_TEXTURE'),
            ('fresnelFactor', 'EPT_F32'),
            ('globalSpecularFactor', 'EPT_F32'),
            ('maxSpecPower', 'EPT_F32'),
            ('minSpecPower', 'EPT_F32'),
            ('specularTexture', 'EPT_TEXTURE'),
        ],
    },
    'Render\\Shaders\\road_dbv.fx': {
        'road_dbv': [
            ('broadNormalStrength', 'EPT_F32'),
            ('globalSpecularFactor', 'EPT_F32'),
            ('specularPower', 'EPT_F32'),
            ('fresnelFactor', 'EPT_F32'),
            ('baseDSTexture', 'EPT_TEXTURE'),
            ('broadNormalTexture', 'EPT_TEXTURE'),
            ('detailDSTexture', 'EPT_TEXTURE'),
            ('detailNormalTexture', 'EPT_TEXTURE'),
            ('puddleTexture', 'EPT_TEXTURE'),
            ('uvScaleForWetMasks', 'EPT_F32'),
        ],
    },
    'Render\\Shaders\\water.fx': {
        'Water': [
            ('diffuseTexture', 'EPT_TEXTURE'),
            ('environmentTexture', 'EPT_TEXTURE'),
            ('fresnelFactor', 'EPT_F32'),
            ('globalEMapFactor', 'EPT_F32'),
            ('globalSpecularFactor', 'EPT_F32'),
            ('maxSpecPower', 'EPT_F32'),
            ('minSpecPower', 'EPT_F32'),
            ('normal1USpeed', 'EPT_F32'),
            ('normal1VSpeed', 'EPT_F32'),
            ('normal2USpeed', 'EPT_F32'),
            ('normal2VSpeed', 'EPT_F32'),
            ('normalTexture1', 'EPT_TEXTURE'),
            ('normalTexture2', 'EPT_TEXTURE'),
            ('riverbedTexture', 'EPT_TEXTURE'),
            ('riverbedTransmissionCoeff', 'EPT_F32'),
            ('specularTexture', 'EPT_TEXTURE'),
        ],
    },
    'Render\\Shaders\\basic_instanced.fx': {
        'Basic': [
            ('diffuseTexture', 'EPT_TEXTURE'),
            ('fresnelFactor', 'EPT_F32'),
            ('globalEMapFactor', 'EPT_F32'),
            ('globalSpecularFactor', 'EPT_F32'),
            ('maxSpecPower', 'EPT_F32'),
            ('minSpecPower', 'EPT_F32'),
            ('normalTexture', 'EPT_TEXTURE'),
            ('specialNormalMap', 'EPT_BOOL'),
            ('specularTexture', 'EPT_TEXTURE'),
            ('tint_maskTexture', 'EPT_TEXTURE'),
            ('tint_tintB', 'EPT_VEC4'),
            ('tint_tintG', 'EPT_VEC4'),
            ('tint_tintR', 'EPT_VEC4'),
        ],
    },
    'Render\\Shaders\\skintest.fx': {
        'skintest': [
            ('colourMultiplier', 'EPT_VEC4'),
            ('diffuseTexture', 'EPT_TEXTURE'),
            ('globalSpecularFactor', 'EPT_F32'),
            ('maxSpecPower', 'EPT_F32'),
            ('minSpecPower', 'EPT_F32'),
            ('normalTexture', 'EPT_TEXTURE'),
            ('specularTexture', 'EPT_TEXTURE'),
        ],
    },
}

# Shader defines (by shader and technique)
SHADER_DEFINES = {
    'Render\\Shaders\\baked_instance_tree.fx': {
        'Basic_AlphaTest': [
            'USE_ALPHATESTPARAM',
            'LOCK_Z',
            'USE_CAMERA_DEPENDET_ANIMATION',
            'USE_NORMAL_COLOURING_LERP',
            'NORMAL_MAPPING',
        ],
    },
    'Render\\Shaders\\basic.fx': {
        'Basic': [
            'USE_ALPHATEST',
            'USE_ANISO',
            'USE_SPECULAR',
            'NORMAL_MAPPING',
            'USE_FRESNEL',
            'USE_AO_MAP',
            'ENVMAP_SCALED_SPEC_A',
        ],
        'Basic_DoubleSided': [
            'USE_ALPHATEST',
            'USE_ANISO',
            'USE_SPECULAR',
            'NORMAL_MAPPING',
            'USE_FRESNEL',
        ],
    },
    'Render\\Shaders\\basic_anim.fx': {
        'Basic': [
            'USE_ANISO',
            'USE_LIGHT_CONTROL',
            'USE_EXTRA_WTC_EMISSIVE_SCALER',
            'ENV_MAPPING',
            'USE_FRESNEL',
            'SCALE_EMISSIVE',
        ],
    },
    'Render\\Shaders\\basic_instanced.fx': {
        'Basic': [
            'NORMAL_MAPPING',
            'ENV_MAPPING',
            'TINT_USE_TINT',
            'TINT_USE_SIMPLE',
            'USE_FRESNEL',
            'ENVMAP_SCALED_SPEC_A',
        ],
    },
    'Render\\Shaders\\basic_translucent.fx': {
        'Basic_Translucent': [
            'USE_ALPHATEST',
            'USE_COLOURISATION',
            'USE_SPECULAR',
            'USE_FRESNEL',
            'USE_AO_MAP',
        ],
        'Basic_Translucent_DoubleSided': [
            'USE_ANISO',
            'USE_SPECULAR',
            'NORMAL_MAPPING',
            'USE_FRESNEL',
        ],
    },
    'Render\\Shaders\\basic_windows.fx': {
        'Basic': [
            'TINT_USE_SIMPLE',
            'USE_EMISSIVEASLIGHTMAP',
            'USE_COLOURISATION',
            'USE_ANISO',
        ],
    },
    'Render\\Shaders\\billboard_instance_tree.fx': {
        'Basic_AlphaTest': [
            'USE_ALPHATESTPARAM',
            'LOCK_YAW_PITCH',
        ],
    },
    'Render\\Shaders\\lightglow_billboard.fx': {
        'Lightglow': [
            'TRACKSIDE_LIGHT',
        ],
    },
    'Render\\Shaders\\locator.fx': {
        'locator': [],
    },
    'Render\\Shaders\\new_ground.fx': {
        'Ground': [
            'USE_COLOURISATION',
            'USE_SPECULAR',
            'NORMAL_MAPPING',
            'APPLYLIVETRACKMASKS',
            'UVSCALEFORWETMASKS',
            'USESURFACECAMERAFACINGNORMALBIAS',
        ],
    },
    'Render\\Shaders\\new_ground_transition.fx': {
        'Ground_Transition': [
            'USE_SPECULAR_1',
            'BROAD_NORMAL_MAP_1',
            'USE_SPECULAR_2',
            'BROAD_NORMAL_MAP_2',
            'GRASSLIVETRACKRENDERING',
            'APPLYLIVETRACKMASKS',
            'UVSCALEFORWETMASKS',
            'USESURFACECAMERAFACINGNORMALBIAS',
        ],
    },
    'Render\\Shaders\\overlay.fx': {
        'Overlay': [
            'USE_SPECULAR',
            'USE_FRESNEL',
            'DEFAULTLIVETRACKRENDERING',
            'USESURFACECAMERAFACINGNORMALBIAS',
        ],
        'Overlay_floatingMesh': [
            'USE_SPECULAR',
            'USE_FRESNEL',
            'DEFAULTLIVETRACKRENDERING',
            'USESURFACECAMERAFACINGNORMALBIAS',
        ],
        'SolidOverlay': [
            'USE_SPECULAR',
            'USE_FRESNEL',
            'GRASSLIVETRACKRENDERING',
            'USESURFACECAMERAFACINGNORMALBIAS',
        ],
    },
    'Render\\Shaders\\road_dbv.fx': {
        'road_dbv': [
            'BROAD_NORMAL_MAPPING',
            'NORMAL_MAPPING',
            'USE_FRESNEL',
            'DEFAULTLIVETRACKRENDERING',
            'APPLYLIVETRACKMASKS',
            'UVSCALEFORWETMASKS',
            'USESURFACECAMERAFACINGNORMALBIAS',
            'FULL_TANGENT',
            'COLOURED_DETAIL',
        ],
    },
    'Render\\Shaders\\skintest.fx': {
        'skintest': [
            'USE_SPECULAR',
            'NORMAL_MAPPING',
            'TINT_USE_SIMPLE',
        ],
    },
    'Render\\Shaders\\water.fx': {
        'Water': [],
    },
}

def get_technique_items(self, context):
    """Dynamic technique items based on selected shader"""
    shader = self.shader_path
    if shader in SHADER_TECHNIQUES:
        return [(name, name, f'{name} technique') for name in SHADER_TECHNIQUES[shader]]
    return [('Basic', 'Basic', 'Basic technique')]

def update_shader_params(self, context):
    """Update available parameters when technique changes"""
    if not context.material or not hasattr(context.material, 'mtx_settings'):
        return
        
    mtx_settings = context.material.mtx_settings
    shader = mtx_settings.shader_path
    technique = mtx_settings.technique
    
    print(f"Updating parameters for {shader} / {technique}")
    
    # Preserve existing parameter values by name and type
    existing_params = {}
    for param in mtx_settings.shader_params:
        key = (param.name, param.param_type)
        existing_params[key] = {
            'enabled': param.enabled,
            'float_value': param.float_value,
            'int_value': param.int_value,
            'vec4_value': tuple(param.vec4_value),
            'texture_value': param.texture_value,
            'bool_value': param.bool_value
        }
    
    # Clear existing parameters
    mtx_settings.shader_params.clear()
    
    # Define common parameters to be enabled by default
    common_params = {
        'diffuseTexture', 'normalTexture', 'specularTexture', 'blendTexture',
        'baseDSTexture', 'broadDiffuseTexture', 'detailDiffuseTexture'
    }
    
    # Add parameters for current shader/technique combination
    if shader in SHADER_PARAMETERS and technique in SHADER_PARAMETERS[shader]:
        for param_name, param_type in SHADER_PARAMETERS[shader][technique]:
            param = mtx_settings.shader_params.add()
            param.name = param_name
            param.param_type = param_type
            
            # Check if we have existing values for this parameter
            key = (param_name, param_type)
            if key in existing_params:
                # Restore existing values
                existing = existing_params[key]
                param.enabled = existing['enabled']
                param.float_value = existing['float_value']
                param.int_value = existing['int_value']
                param.vec4_value = existing['vec4_value']
                param.texture_value = existing['texture_value']
                param.bool_value = existing['bool_value']
                print(f"Carried over parameter: {param_name} ({param_type})")
            else:
                # Set default values for new parameters
                param.enabled = param_name in common_params
                
                if param_type == 'EPT_F32':
                    if 'Factor' in param_name or 'Power' in param_name:
                        param.float_value = 1.0
                    elif 'Scale' in param_name:
                        param.float_value = 1.0
                    else:
                        param.float_value = 0.0
                elif param_type == 'EPT_S32':
                    if 'Mode' in param_name:
                        param.int_value = 0
                    elif 'Dim' in param_name:
                        param.int_value = 1
                    else:
                        param.int_value = 0
                elif param_type == 'EPT_VEC4':
                    param.vec4_value = (1.0, 1.0, 1.0, 1.0)
                elif param_type == 'EPT_BOOL':
                    param.bool_value = False
                # EPT_TEXTURE gets empty string by default

def update_shader_defines(self, context):
    """Update shader defines based on selected shader and technique."""
    material = context.material
    if not material or not hasattr(material, 'mtx_settings'):
        return
    
    settings = material.mtx_settings
    shader = settings.shader_path
    technique = settings.technique
    
    # Preserve existing define states by name
    existing_defines = {}
    for define in settings.defines:
        existing_defines[define.name] = define.enabled
    
    # Clear existing defines
    settings.defines.clear()
    
    # Define common defines to be enabled by default
    common_defines = {
        'NORMAL_MAPPING', 'USE_SPECULAR', 'USE_FRESNEL', 'ENV_MAPPING'
    }
    
    # Get defines for the specific shader and technique
    if shader in SHADER_DEFINES and technique in SHADER_DEFINES[shader]:
        for define_name in SHADER_DEFINES[shader][technique]:
            new_define = settings.defines.add()
            new_define.name = define_name
            
            # Check if we have existing state for this define
            if define_name in existing_defines:
                # Restore existing state
                new_define.enabled = existing_defines[define_name]
                print(f"Carried over define: {define_name} (enabled: {new_define.enabled})")
            else:
                # Set default state for new defines
                new_define.enabled = define_name in common_defines

def update_shader_change(self, context):
    """Update technique, parameters, and defines when shader changes"""
    shader = self.shader_path
    
    print(f"Shader changed to: {shader}")
    
    # Reset technique to first valid option for this shader
    if shader in SHADER_TECHNIQUES and SHADER_TECHNIQUES[shader]:
        self.technique = SHADER_TECHNIQUES[shader][0]
    
    # Update both parameters and defines
    update_shader_params(self, context)
    update_shader_defines(self, context) 