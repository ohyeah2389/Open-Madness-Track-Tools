from pathlib import Path
import json

SHADER_TECHNIQUES = {}
SHADER_PARAMETERS = {}
SHADER_DEFINES = {}
SHADER_ALIASES = {}
SHADER_LEAF_ALIASES = {}

ALWAYS_ON_PARAMETERS = {}
ALWAYS_ON_DEFINES = {}
DEFAULT_PARAM_VALUES = {}
PARAM_METADATA = {}
OPTION_PAIRINGS = {}

DATABASE_DIR = Path(__file__).resolve().parent.parent / "database"
SHADER_DATABASE_DIR = DATABASE_DIR / "shaders"
DATABASE_REGISTRY = {}


def _norm_name(value: str) -> str:
    return str(value or "").strip().lower()


def _norm_shader_path(value: str) -> str:
    return str(value or "").replace("/", "\\").strip().lower()


def _shader_leaf_keys(value: str):
    shader_norm = _norm_shader_path(value)
    if not shader_norm:
        return []
    leaf = shader_norm.rsplit("\\", 1)[-1]
    keys = [leaf]
    if leaf.endswith(".fx"):
        keys.append(leaf[:-3])
    return keys


def _coerce_param_value(existing, param_type):
    if param_type == "EPT_F32":
        if existing["old_type"] == "EPT_F32":
            return {"float_value": existing["float_value"]}
        if existing["old_type"] == "EPT_S32":
            return {"float_value": float(existing["int_value"])}
        if existing["old_type"] == "EPT_BOOL":
            return {"float_value": 1.0 if existing["bool_value"] else 0.0}
    elif param_type == "EPT_S32":
        if existing["old_type"] == "EPT_S32":
            return {"int_value": existing["int_value"]}
        if existing["old_type"] == "EPT_F32":
            return {"int_value": int(existing["float_value"])}
        if existing["old_type"] == "EPT_BOOL":
            return {"int_value": 1 if existing["bool_value"] else 0}
    elif param_type == "EPT_VEC4":
        if existing["old_type"] == "EPT_VEC4":
            return {"vec4_value": existing["vec4_value"]}
        if existing["old_type"] == "EPT_F32":
            f = float(existing["float_value"])
            return {"vec4_value": (f, f, f, f)}
        if existing["old_type"] == "EPT_S32":
            f = float(existing["int_value"])
            return {"vec4_value": (f, f, f, f)}
        if existing["old_type"] == "EPT_BOOL":
            f = 1.0 if existing["bool_value"] else 0.0
            return {"vec4_value": (f, f, f, f)}
    elif param_type == "EPT_BOOL":
        if existing["old_type"] == "EPT_BOOL":
            return {"bool_value": existing["bool_value"]}
        if existing["old_type"] == "EPT_F32":
            return {"bool_value": bool(existing["float_value"])}
        if existing["old_type"] == "EPT_S32":
            return {"bool_value": bool(existing["int_value"])}
    elif param_type == "EPT_TEXTURE" and existing["old_type"] == "EPT_TEXTURE":
        return {"texture_value": existing["texture_value"]}
    return {}


def _shader_display_name(shader_value):
    """Return a safe display name for shader enum labels."""
    shader_text = str(shader_value or "").replace("/", "\\")
    if not shader_text:
        return "unknown"
    leaf = shader_text.rsplit("\\", 1)[-1]
    return leaf[:-3] if leaf.lower().endswith(".fx") else leaf


def get_shader_items(self, context):
    """Shader list from the active database only."""
    items = [
        (shader, _shader_display_name(shader), shader)
        for shader in sorted(str(shader_path) for shader_path in SHADER_TECHNIQUES.keys())
    ]
    return items or [('Render\\Shaders\\basic.fx', 'basic', 'Render\\Shaders\\basic.fx')]


def get_shader_database_items(self, context):
    """List available shader databases from database/shaders."""
    _discover_shader_databases()
    return [
        (db_id, db_info["label"], str(db_info["path"]))
        for db_id, db_info in DATABASE_REGISTRY.items()
    ] or [("builtin", "Built-in", "Built-in shader table")]


def resolve_shader_path(shader: str) -> str:
    """Resolve shader names robustly across database rebuilds/casing changes."""
    shader_text = str(shader or "").replace("/", "\\").strip()
    if not shader_text:
        return ""
    if shader_text in SHADER_TECHNIQUES:
        return shader_text

    shader_norm = _norm_shader_path(shader_text)
    mapped = SHADER_ALIASES.get(shader_norm)
    if mapped:
        return mapped

    for leaf_key in _shader_leaf_keys(shader_text):
        candidates = SHADER_LEAF_ALIASES.get(leaf_key, set())
        if len(candidates) == 1:
            return next(iter(candidates))

    return ""


def _normalize_loaded_database(db_dict):
    """Convert the external JSON database format into the structures used by the UI."""
    techniques = {}
    parameters = {}
    defines = {}
    always_params = {}
    always_defines = {}
    default_param_values = {}
    param_metadata = {}
    option_pairings = {}

    shaders = db_dict.get("shaders", {})
    for shader_path, shader_data in shaders.items():
        tech_map = shader_data.get("techniques", {})
        if not tech_map:
            continue

        techniques[shader_path] = sorted(tech_map.keys())
        params_by_tech = {}
        defines_by_tech = {}
        base_params_by_tech = {}
        base_defines_by_tech = {}
        default_values_by_tech = {}
        metadata_by_tech = {}
        pairings_by_tech = {}

        for technique, technique_data in tech_map.items():
            raw_params = technique_data.get("parameters", {})
            ordered_param_names = []
            seen_params = set()
            if technique_data.get("paramOrder"):
                for name in technique_data["paramOrder"]:
                    if name in raw_params and name not in seen_params:
                        seen_params.add(name)
                        ordered_param_names.append(name)
            for name in sorted(raw_params.keys()):
                if name not in seen_params:
                    seen_params.add(name)
                    ordered_param_names.append(name)

            param_list = []
            defaults_for_tech = {}
            metadata_for_tech = {}

            for param_name in ordered_param_names:
                param_details = raw_params.get(param_name)
                # Support either a single type string or a list of types (pick the first)
                param_type = None
                float_avg = None
                vec4_avg = None
                float_min = None
                float_max = None
                float_median = None
                vec4_median = None
                if isinstance(param_details, dict):
                    if isinstance(param_details.get("types"), list):
                        param_type = param_details["types"][0] if param_details["types"] else None
                    elif isinstance(param_details.get("type"), str):
                        param_type = param_details["type"]
                    float_avg = param_details.get("floatAvg")
                    float_min = param_details.get("floatMin")
                    float_max = param_details.get("floatMax")
                    float_median = param_details.get("floatMedian")
                    vec4_avg = param_details.get("vec4Avg")
                    vec4_median = param_details.get("vec4Median")
                elif isinstance(param_details, str):
                    param_type = param_details

                if not param_type:
                    continue

                param_list.append((param_name, param_type))
                if float_median is not None:
                    defaults_for_tech[param_name] = ("EPT_F32", float_median)
                elif vec4_median is not None:
                    defaults_for_tech[param_name] = ("EPT_VEC4", tuple(vec4_median))
                elif float_avg is not None:
                    defaults_for_tech[param_name] = ("EPT_F32", float_avg)
                elif vec4_avg is not None:
                    defaults_for_tech[param_name] = ("EPT_VEC4", tuple(vec4_avg))

                metadata_for_tech[param_name] = {
                    "floatMin": float_min,
                    "floatMax": float_max,
                    "floatAvg": float_avg,
                    "floatMedian": float_median,
                    "vec4Avg": tuple(vec4_avg) if vec4_avg is not None else None,
                    "vec4Median": tuple(vec4_median) if vec4_median is not None else None,
                }

            params_by_tech[technique] = param_list
            default_values_by_tech[technique] = defaults_for_tech
            metadata_by_tech[technique] = metadata_for_tech

            define_list = technique_data.get("defineOrder") or technique_data.get("defines", [])
            seen_defines = set()
            ordered_defines = []
            for define_name in define_list:
                if define_name not in seen_defines:
                    seen_defines.add(define_name)
                    ordered_defines.append(define_name)
            if technique_data.get("defines"):
                for define_name in sorted(set(technique_data["defines"])):
                    if define_name not in seen_defines:
                        seen_defines.add(define_name)
                        ordered_defines.append(define_name)
            defines_by_tech[technique] = ordered_defines

            base_params_by_tech[technique] = set(technique_data.get("baseParameters", []))
            base_defines_by_tech[technique] = set(technique_data.get("baseDefines", []))
            raw_pairings = technique_data.get("optionPairings", {})
            defines_pairings = {}
            params_pairings = {}
            for source_name, targets in raw_pairings.get("defines", {}).items():
                if not isinstance(targets, list):
                    continue
                cleaned = []
                for target in targets:
                    if not isinstance(target, dict):
                        continue
                    target_kind = target.get("kind")
                    target_name = target.get("name")
                    if target_kind not in {"define", "parameter"} or not target_name:
                        continue
                    cleaned.append(
                        {
                            "kind": target_kind,
                            "name": str(target_name),
                            "support": int(target.get("support", 0) or 0),
                            "confidence": float(target.get("confidence", 1.0) or 0.0),
                        }
                    )
                if cleaned:
                    defines_pairings[str(source_name)] = cleaned
            for source_name, targets in raw_pairings.get("parameters", {}).items():
                if not isinstance(targets, list):
                    continue
                cleaned = []
                for target in targets:
                    if not isinstance(target, dict):
                        continue
                    target_kind = target.get("kind")
                    target_name = target.get("name")
                    if target_kind not in {"define", "parameter"} or not target_name:
                        continue
                    cleaned.append(
                        {
                            "kind": target_kind,
                            "name": str(target_name),
                            "support": int(target.get("support", 0) or 0),
                            "confidence": float(target.get("confidence", 1.0) or 0.0),
                        }
                    )
                if cleaned:
                    params_pairings[str(source_name)] = cleaned
            pairings_by_tech[technique] = {
                "defines": defines_pairings,
                "parameters": params_pairings,
            }

        parameters[shader_path] = params_by_tech
        defines[shader_path] = defines_by_tech
        always_params[shader_path] = base_params_by_tech
        always_defines[shader_path] = base_defines_by_tech
        default_param_values[shader_path] = default_values_by_tech
        param_metadata[shader_path] = metadata_by_tech
        option_pairings[shader_path] = pairings_by_tech

    return (
        techniques,
        parameters,
        defines,
        always_params,
        always_defines,
        default_param_values,
        param_metadata,
        option_pairings,
    )


def _discover_shader_databases():
    """Populate shader database registry from database/shaders."""
    DATABASE_REGISTRY.clear()

    if SHADER_DATABASE_DIR.exists():
        for path in sorted(SHADER_DATABASE_DIR.glob("*.json")):
            db_id = f"shaders/{path.name}"
            label = path.stem.replace("_", " ").replace("-", " ").upper()
            DATABASE_REGISTRY[db_id] = {"path": path, "label": label}


def get_default_shader_database_id():
    """Get the preferred default database id."""
    _discover_shader_databases()
    if DATABASE_REGISTRY:
        return next(iter(DATABASE_REGISTRY))
    return "builtin"


def load_shader_database(database_id=None):
    """Load shader data from selected database. Returns True on success."""
    _discover_shader_databases()
    if database_id is None or database_id == "builtin":
        database_id = get_default_shader_database_id()
    if database_id == "builtin":
        return False
    if database_id not in DATABASE_REGISTRY:
        database_id = get_default_shader_database_id()
        if database_id == "builtin":
            return False

    db_path = DATABASE_REGISTRY[database_id]["path"]
    try:
        with open(db_path, "r", encoding="utf-8") as file_handle:
            db_content = json.load(file_handle)
    except Exception as exc:
        print(f"Failed to read shader database at {db_path}: {exc}")
        return False

    try:
        (
            techniques,
            parameters,
            defines,
            always_params,
            always_defines,
            default_param_values,
            param_metadata,
            option_pairings,
        ) = _normalize_loaded_database(db_content)
    except Exception as exc:
        print(f"Failed to normalize shader database from {db_path}: {exc}")
        return False

    if not techniques:
        return False

    SHADER_TECHNIQUES.clear()
    SHADER_TECHNIQUES.update(techniques)
    SHADER_PARAMETERS.clear()
    SHADER_PARAMETERS.update(parameters)
    SHADER_DEFINES.clear()
    SHADER_DEFINES.update(defines)
    SHADER_ALIASES.clear()
    SHADER_LEAF_ALIASES.clear()
    for shader_name in SHADER_TECHNIQUES.keys():
        shader_norm = _norm_shader_path(shader_name)
        if shader_norm and shader_norm not in SHADER_ALIASES:
            SHADER_ALIASES[shader_norm] = shader_name
        for leaf_key in _shader_leaf_keys(shader_name):
            SHADER_LEAF_ALIASES.setdefault(leaf_key, set()).add(shader_name)
    ALWAYS_ON_PARAMETERS.clear()
    ALWAYS_ON_PARAMETERS.update(always_params)
    ALWAYS_ON_DEFINES.clear()
    ALWAYS_ON_DEFINES.update(always_defines)
    DEFAULT_PARAM_VALUES.clear()
    DEFAULT_PARAM_VALUES.update(default_param_values)
    PARAM_METADATA.clear()
    PARAM_METADATA.update(param_metadata)
    OPTION_PAIRINGS.clear()
    OPTION_PAIRINGS.update(option_pairings)

    print(f"Loaded shader database: {len(SHADER_TECHNIQUES)} shaders from {db_path}")
    return True


load_shader_database()


def is_param_required(shader: str, technique: str, param_name: str) -> bool:
    """Return True if the parameter is marked always-on in the database."""
    shader_key = resolve_shader_path(shader) or shader
    return param_name in ALWAYS_ON_PARAMETERS.get(shader_key, {}).get(technique, set())


def is_define_required(shader: str, technique: str, define_name: str) -> bool:
    """Return True if the define is marked always-on in the database."""
    shader_key = resolve_shader_path(shader) or shader
    return define_name in ALWAYS_ON_DEFINES.get(shader_key, {}).get(technique, set())


def get_param_stats(shader: str, technique: str, param_name: str):
    """Return metadata for a parameter (min/max/avg values) if available."""
    shader_key = resolve_shader_path(shader) or shader
    return PARAM_METADATA.get(shader_key, {}).get(technique, {}).get(param_name, None)


def get_option_pairings(shader: str, technique: str, option_kind: str, option_name: str):
    """Return strict pairing suggestions for one option."""
    shader_key = resolve_shader_path(shader) or shader
    kind_key = "defines" if option_kind == "define" else "parameters"
    return (
        OPTION_PAIRINGS
        .get(shader_key, {})
        .get(technique, {})
        .get(kind_key, {})
        .get(option_name, [])
    )


def get_missing_pairings(
    shader: str,
    technique: str,
    option_kind: str,
    option_name: str,
    enabled_defines,
    enabled_params,
):
    """Return pairings that are not currently enabled/present in the material."""
    enabled_define_set = set(enabled_defines or [])
    enabled_param_set = set(enabled_params or [])
    missing = []
    for pairing in get_option_pairings(shader, technique, option_kind, option_name):
        if pairing["kind"] == "define" and pairing["name"] not in enabled_define_set:
            missing.append(pairing)
        elif pairing["kind"] == "parameter" and pairing["name"] not in enabled_param_set:
            missing.append(pairing)
    return missing

def get_technique_items(self, context):
    """Technique list for the currently selected shader."""
    shader = ""
    try:
        value = self.shader_path
        if isinstance(value, str):
            shader = value
    except Exception:
        shader = ""

    shader_key = resolve_shader_path(shader) or shader
    techniques = SHADER_TECHNIQUES.get(shader_key, [])
    if not techniques:
        return [('Basic', 'Basic', 'Fallback technique')]
    return [(name, name, f'{name} technique') for name in techniques]

def _update_shader_params_impl(self, context, preserve_unmapped=False):
    """Update available parameters when technique changes"""
    if not hasattr(self, "shader_params"):
        return

    mtx_settings = self
    shader = resolve_shader_path(mtx_settings.shader_path) or mtx_settings.shader_path
    technique = mtx_settings.technique

    if shader not in SHADER_PARAMETERS or technique not in SHADER_PARAMETERS[shader]:
        return
    
    # Preserve existing parameter values by name and type
    existing_params = {}
    existing_params_by_name = {}
    for param in mtx_settings.shader_params:
        key = (param.name, param.param_type)
        existing = {
            'enabled': param.enabled,
            'float_value': param.float_value,
            'int_value': param.int_value,
            'vec4_value': tuple(param.vec4_value),
            'texture_value': param.texture_value,
            'bool_value': param.bool_value,
            'old_type': param.param_type,
        }
        existing_params[key] = existing
        existing_params_by_name[_norm_name(param.name)] = existing
    
    # Clear existing parameters
    mtx_settings.shader_params.clear()
    
    # Define common parameters to be enabled by default
    common_params = {
        'diffuseTexture', 'normalTexture', 'specularTexture', 'blendTexture',
        'baseDSTexture', 'broadDiffuseTexture', 'detailDiffuseTexture'
    }
    
    # Add parameters for current shader/technique combination
    param_entries = list(SHADER_PARAMETERS[shader][technique])
    type_order = {
        "EPT_TEXTURE": 0,
        "EPT_F32": 1,
        "EPT_VEC4": 2,
        "EPT_BOOL": 3,
    }
    param_entries.sort(
        key=lambda item: (
            type_order.get(item[1], 4),
            0 if is_param_required(shader, technique, item[0]) else 1,
            item[0].lower(),
        )
    )
    matched_param_keys = set()
    matched_param_names_ci = set()

    for param_name, param_type in param_entries:
        param = mtx_settings.shader_params.add()
        param.name = param_name
        param.param_type = param_type
        param_defaults = DEFAULT_PARAM_VALUES.get(shader, {}).get(technique, {})
        
        # Check if we have existing values for this parameter
        key = (param_name, param_type)
        if key in existing_params:
            # Restore existing values
            existing = existing_params[key]
            matched_param_keys.add(key)
            matched_param_names_ci.add(_norm_name(param_name))
            param.enabled = existing['enabled']
            param.float_value = existing['float_value']
            param.int_value = existing['int_value']
            param.vec4_value = existing['vec4_value']
            param.texture_value = existing['texture_value']
            param.bool_value = existing['bool_value']
        elif _norm_name(param_name) in existing_params_by_name:
            existing = existing_params_by_name[_norm_name(param_name)]
            matched_param_names_ci.add(_norm_name(param_name))
            param.enabled = existing['enabled']
            coerced = _coerce_param_value(existing, param_type)
            if "float_value" in coerced:
                param.float_value = coerced["float_value"]
            if "int_value" in coerced:
                param.int_value = coerced["int_value"]
            if "vec4_value" in coerced:
                param.vec4_value = coerced["vec4_value"]
            if "texture_value" in coerced:
                param.texture_value = coerced["texture_value"]
            if "bool_value" in coerced:
                param.bool_value = coerced["bool_value"]
        else:
            # Set default values for new parameters
            param.enabled = param_name in common_params
            
            if param_type == 'EPT_F32':
                if param_name in param_defaults and param_defaults[param_name][0] == 'EPT_F32':
                    param.float_value = float(param_defaults[param_name][1])
                elif 'Factor' in param_name or 'Power' in param_name:
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
                if param_name in param_defaults and param_defaults[param_name][0] == 'EPT_VEC4':
                    param.vec4_value = param_defaults[param_name][1]
                else:
                    param.vec4_value = (1.0, 1.0, 1.0, 1.0)
            elif param_type == 'EPT_BOOL':
                param.bool_value = False
            # EPT_TEXTURE gets empty string by default

        # Force always-on parameters
        always_params = ALWAYS_ON_PARAMETERS.get(shader, {}).get(technique, set())
        if param.name in always_params:
            param.enabled = True

    # Preserve legacy/unmapped params only during same shader+technique refreshes.
    if preserve_unmapped:
        for (old_name, old_type), existing in existing_params.items():
            if (old_name, old_type) in matched_param_keys:
                continue
            if _norm_name(old_name) in matched_param_names_ci:
                continue
            param = mtx_settings.shader_params.add()
            param.name = old_name
            param.param_type = old_type
            param.enabled = existing['enabled']
            param.float_value = existing['float_value']
            param.int_value = existing['int_value']
            param.vec4_value = existing['vec4_value']
            param.texture_value = existing['texture_value']
            param.bool_value = existing['bool_value']

def _update_shader_defines_impl(self, context, preserve_unmapped=False):
    """Update shader defines based on selected shader and technique."""
    if not hasattr(self, "defines"):
        return

    settings = self
    shader = resolve_shader_path(settings.shader_path) or settings.shader_path
    technique = settings.technique

    if shader not in SHADER_DEFINES or technique not in SHADER_DEFINES[shader]:
        return
    
    # Preserve existing define states by name
    existing_defines = {}
    existing_defines_ci = {}
    for define in settings.defines:
        existing_defines[define.name] = define.enabled
        existing_defines_ci[_norm_name(define.name)] = define.enabled
    
    # Clear existing defines
    settings.defines.clear()
    matched_defines = set()
    matched_defines_ci = set()
    
    # Get defines for the specific shader and technique
    if shader in SHADER_DEFINES and technique in SHADER_DEFINES[shader]:
        for define_name in SHADER_DEFINES[shader][technique]:
            new_define = settings.defines.add()
            new_define.name = define_name
            
            # Check if we have existing state for this define
            if define_name in existing_defines:
                # Restore existing state
                new_define.enabled = existing_defines[define_name]
                matched_defines.add(define_name)
                matched_defines_ci.add(_norm_name(define_name))
            elif _norm_name(define_name) in existing_defines_ci:
                new_define.enabled = existing_defines_ci[_norm_name(define_name)]
                matched_defines_ci.add(_norm_name(define_name))
            else:
                # Default to disabled; always-on set will override below
                new_define.enabled = False

            always_defines = ALWAYS_ON_DEFINES.get(shader, {}).get(technique, set())
            if define_name in always_defines:
                new_define.enabled = True

    # Preserve legacy/unmapped defines only during same shader+technique refreshes.
    if preserve_unmapped:
        for old_name, old_enabled in existing_defines.items():
            if old_name in matched_defines:
                continue
            if _norm_name(old_name) in matched_defines_ci:
                continue
            old_define = settings.defines.add()
            old_define.name = old_name
            old_define.enabled = old_enabled

def update_shader_change(self, context):
    """Update technique, parameters, and defines when shader changes"""
    prev_shader = str(self.get("_last_shader_path", ""))
    prev_technique = str(self.get("_last_shader_technique", ""))
    shader = resolve_shader_path(self.shader_path)

    if not shader or shader not in SHADER_TECHNIQUES or not SHADER_TECHNIQUES[shader]:
        return
    if self.shader_path != shader:
        self.shader_path = shader

    valid_techniques = list(SHADER_TECHNIQUES[shader])
    if self.technique not in valid_techniques:
        desired = _norm_name(self.technique)
        matched = next((name for name in valid_techniques if _norm_name(name) == desired), None)
        self.technique = matched or valid_techniques[0]

    same_shader = prev_shader and _norm_shader_path(prev_shader) == _norm_shader_path(shader)
    same_technique = prev_technique and _norm_name(prev_technique) == _norm_name(self.technique)
    preserve_unmapped = bool(same_shader and same_technique)

    # Update both parameters and defines
    _update_shader_params_impl(self, context, preserve_unmapped=preserve_unmapped)
    _update_shader_defines_impl(self, context, preserve_unmapped=preserve_unmapped)
    self["_last_shader_path"] = shader
    self["_last_shader_technique"] = self.technique


def update_shader_params(self, context):
    """Blender property callback (must be exactly 2 args)."""
    _update_shader_params_impl(self, context, preserve_unmapped=False)


def update_shader_defines(self, context):
    """Helper exposed for callers that want define refresh."""
    _update_shader_defines_impl(self, context, preserve_unmapped=False)
