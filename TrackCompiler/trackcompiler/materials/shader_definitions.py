from pathlib import Path
from contextlib import contextmanager
from itertools import combinations
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
PACKED_HASHES = {}
PACKED_PARAMS = {}
PACKED_PARAM_BASE = {}
PACKED_AA_SUFFIXES = ("_NO_AA", "_NORMAL_AA", "_HIGH_AA", "_LOW_AA", "")
_UID64_EMPTY = 0x8DB63936938575BF
_PACKED_HELP_CACHE = {}
_PACKED_PARAM_HELP_CACHE = {}

DATABASE_DIR = Path(__file__).resolve().parent.parent / "database"
SHADER_DATABASE_DIR = DATABASE_DIR / "shaders"
DATABASE_REGISTRY = {}
_SUPPRESS_SHADER_UPDATES = 0
SHADER_ENUM_NUMBERS = {}
TECHNIQUE_ENUM_NUMBERS = {}
_SHADER_ITEMS_CACHE = []
_TECHNIQUE_ITEMS_CACHE = []
_DATABASE_ITEMS_CACHE = []
_FROZEN_DATABASE_IDS = (
    "shaders/ams2_shader_database.json",
    "shaders/pc2_shader_database.json",
)


@contextmanager
def suppress_shader_updates():
    """Skip EnumProperty rebuilds while silently remapping shader paths."""
    global _SUPPRESS_SHADER_UPDATES
    _SUPPRESS_SHADER_UPDATES += 1
    try:
        yield
    finally:
        _SUPPRESS_SHADER_UPDATES -= 1


def _mix64(a, b, c):
    m = 0xFFFFFFFFFFFFFFFF
    a = (a - b - c) & m; a ^= c >> 43
    b = (b - c - a) & m; b ^= (a << 9) & m
    c = (c - a - b) & m; c ^= b >> 8
    a = (a - b - c) & m; a ^= c >> 38
    b = (b - c - a) & m; b ^= (a << 23) & m
    c = (c - a - b) & m; c ^= b >> 5
    a = (a - b - c) & m; a ^= c >> 35
    b = (b - c - a) & m; b ^= (a << 49) & m
    c = (c - a - b) & m; c ^= b >> 11
    a = (a - b - c) & m; a ^= c >> 12
    b = (b - c - a) & m; b ^= (a << 18) & m
    c = (c - a - b) & m; c ^= b >> 22
    return a, b, c


def _uid64(data: bytes) -> int:
    if not data:
        return _UID64_EMPTY
    length, m = len(data), 0xFFFFFFFFFFFFFFFF
    a = b = 0
    c = 0x9E3779B97F4A7C13
    i, rem = 0, length
    while rem >= 24:
        a = (a + int.from_bytes(data[i:i + 8], "big")) & m
        b = (b + int.from_bytes(data[i + 8:i + 16], "big")) & m
        c = (c + int.from_bytes(data[i + 16:i + 24], "big")) & m
        a, b, c = _mix64(a, b, c)
        i += 24
        rem -= 24
    c = (c + length) & m
    for n in range(min(rem, 8)):
        a = (a + (data[i + n] << (8 * n))) & m
    for n in range(min(max(rem - 8, 0), 8)):
        b = (b + (data[i + 8 + n] << (8 * n))) & m
    for n in range(min(max(rem - 16, 0), 7)):
        c = (c + (data[i + 16 + n] << (8 * (n + 1)))) & m
    return _mix64(a, b, c)[2]


def _permutation_digest(define_names, suffix="_NO_AA") -> str:
    text = "".join(define_names) + suffix
    if not text:
        return f"{_UID64_EMPTY:016x}"
    return f"{_uid64(text.lower().encode('ascii')):016x}"


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


def _init_new_param_values(param, param_name, param_type, shader, technique):
    """Fill default values for a newly appended parameter without enabling it."""
    param_defaults = DEFAULT_PARAM_VALUES.get(shader, {}).get(technique, {})
    if param_type == "EPT_F32":
        if param_name in param_defaults and param_defaults[param_name][0] == "EPT_F32":
            param.float_value = float(param_defaults[param_name][1])
        elif "Factor" in param_name or "Power" in param_name or "Scale" in param_name:
            param.float_value = 1.0
        else:
            param.float_value = 0.0
    elif param_type == "EPT_S32":
        param.int_value = 1 if "Dim" in param_name else 0
    elif param_type == "EPT_VEC4":
        if param_name in param_defaults and param_defaults[param_name][0] == "EPT_VEC4":
            param.vec4_value = param_defaults[param_name][1]
        else:
            param.vec4_value = (1.0, 1.0, 1.0, 1.0)
    elif param_type == "EPT_BOOL":
        param.bool_value = False


def _shader_display_name(shader_value):
    """Return a safe display name for shader enum labels."""
    shader_text = str(shader_value or "").replace("/", "\\")
    if not shader_text:
        return "unknown"
    leaf = shader_text.rsplit("\\", 1)[-1]
    return leaf[:-3] if leaf.lower().endswith(".fx") else leaf


def get_shader_items(self, context):
    """Shader list from the active database only."""
    global _SHADER_ITEMS_CACHE
    _SHADER_ITEMS_CACHE = [
        (shader, _shader_display_name(shader), shader, SHADER_ENUM_NUMBERS.get(shader, index))
        for index, shader in enumerate(sorted(SHADER_TECHNIQUES))
    ]
    return _SHADER_ITEMS_CACHE or [('Render\\Shaders\\basic.fx', 'basic', 'Render\\Shaders\\basic.fx', 0)]


def get_shader_database_items(self, context):
    """List available shader databases from database/shaders."""
    global _DATABASE_ITEMS_CACHE
    _discover_shader_databases()
    items = []
    for number, db_id in enumerate(_FROZEN_DATABASE_IDS):
        db_info = DATABASE_REGISTRY.get(db_id)
        if db_info:
            items.append((db_id, db_info["label"], str(db_info["path"]), number))
    next_number = len(_FROZEN_DATABASE_IDS)
    for db_id, db_info in DATABASE_REGISTRY.items():
        if db_id in _FROZEN_DATABASE_IDS:
            continue
        items.append((db_id, db_info["label"], str(db_info["path"]), next_number))
        next_number += 1
    _DATABASE_ITEMS_CACHE = items or [("builtin", "Built-in", "Built-in shader table", 0)]
    return _DATABASE_ITEMS_CACHE


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


def _match_name(wanted, names):
    names = list(names)
    if wanted in names:
        return wanted
    key = _norm_name(wanted)
    return next((name for name in names if _norm_name(name) == key), None)


def _canonical_technique(shader, technique):
    return _match_name(technique, SHADER_TECHNIQUES.get(shader) or SHADER_PARAMETERS.get(shader, {}))


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
            if path.name.endswith("_packed_hashes.json") or path.name.endswith("_packed_params.json"):
                continue
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
    _load_packed_sidecars(database_id)
    _assign_enum_numbers(database_id)

    print(f"Loaded shader database: {len(SHADER_TECHNIQUES)} shaders from {db_path}")
    return True


def _stable_enum_ids(preferred, current):
    mapping = {}
    current = list(current)
    for name in list(preferred) + current:
        if name in current and name not in mapping:
            mapping[name] = len(mapping)
    return mapping


def _assign_enum_numbers(database_id):
    """Keep Blender enum integers stable so pre-merge .blend files still resolve."""
    SHADER_ENUM_NUMBERS.clear()
    TECHNIQUE_ENUM_NUMBERS.clear()
    legacy_shaders = {}
    if "ams2" in str(database_id or "").lower():
        legacy_path = SHADER_DATABASE_DIR / "ams2_shader_database_legacy.json"
    elif "pc2" in str(database_id or "").lower():
        legacy_path = SHADER_DATABASE_DIR / "pc2_shader_database_legacy.json"
    else:
        legacy_path = None
    if legacy_path and legacy_path.exists():
        try:
            legacy_shaders = json.loads(legacy_path.read_text(encoding="utf-8")).get("shaders") or {}
        except Exception as exc:
            print(f"Failed to read legacy shader enum order at {legacy_path}: {exc}")

    preferred = []
    legacy_techs = {}
    for path in sorted(legacy_shaders):
        canonical = SHADER_ALIASES.get(_norm_shader_path(path))
        if not canonical:
            continue
        preferred.append(canonical)
        legacy_techs[canonical] = sorted((legacy_shaders[path] or {}).get("techniques") or {})
    SHADER_ENUM_NUMBERS.update(_stable_enum_ids(preferred, sorted(SHADER_TECHNIQUES)))
    for shader, techniques in SHADER_TECHNIQUES.items():
        preferred_techs = []
        for name in legacy_techs.get(shader, []):
            matched = _match_name(name, techniques)
            if matched:
                preferred_techs.append(matched)
        TECHNIQUE_ENUM_NUMBERS[shader] = _stable_enum_ids(preferred_techs, techniques)


def _load_packed_sidecars(database_id):
    """Load packed PB1 hashes and parameter tables for the active database."""
    PACKED_HASHES.clear()
    PACKED_PARAMS.clear()
    PACKED_PARAM_BASE.clear()
    _PACKED_HELP_CACHE.clear()
    _PACKED_PARAM_HELP_CACHE.clear()
    name = str(database_id or "").lower()
    if "ams2" in name:
        prefix = "ams2"
    elif "pc2" in name:
        prefix = "pc2"
    else:
        return
    hash_path = SHADER_DATABASE_DIR / f"{prefix}_packed_hashes.json"
    param_path = SHADER_DATABASE_DIR / f"{prefix}_packed_params.json"
    if hash_path.exists():
        try:
            payload = json.loads(hash_path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"Failed to read packed shader hashes at {hash_path}: {exc}")
        else:
            for shader, hashes in (payload.get("shaders") or {}).items():
                PACKED_HASHES[_norm_shader_path(shader)] = {str(digest).lower() for digest in hashes}
    if not param_path.exists():
        return
    try:
        payload = json.loads(param_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Failed to read packed shader parameters at {param_path}: {exc}")
        return
    catalog = payload.get("names") or []
    for shader, tables in (payload.get("shaders") or {}).items():
        resolved = {}
        for digest, indices in (tables or {}).items():
            names = tuple(catalog[index] for index in indices if 0 <= int(index) < len(catalog))
            resolved[str(digest).lower()] = names
        if not resolved:
            continue
        key = _norm_shader_path(shader)
        PACKED_PARAMS[key] = resolved
        PACKED_PARAM_BASE[key] = set.intersection(*(set(names) for names in resolved.values()))


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


def _combo_is_packed(hashes, names):
    return any(_permutation_digest(names, suffix) in hashes for suffix in PACKED_AA_SUFFIXES)


def _packed_define_order(shader, technique):
    techs = SHADER_DEFINES.get(shader) or {}
    matched = _match_name(technique, techs)
    if matched:
        return list(techs[matched])
    return list(max(techs.values(), key=len)) if techs else []


def _format_define_list(names, limit=4):
    names = list(names)
    if not names:
        return "(none)"
    extra = f" +{len(names) - limit}" if len(names) > limit else ""
    return ", ".join(names[:limit]) + extra


def _suggestion_label(current, suggested):
    cur_set, sug_set = set(current), set(suggested)
    off = [name for name in current if name not in sug_set]
    on = [name for name in suggested if name not in cur_set]
    if not off and not on:
        return "Reorder defines to packed order" if suggested else "Clear all defines"
    parts = []
    if off:
        parts.append("Disable " + _format_define_list(off))
    if on:
        parts.append("Enable " + _format_define_list(on))
    kept = [name for name in current if name in sug_set]
    if kept != [name for name in suggested if name in cur_set]:
        parts.append("reorder")
    return "; ".join(parts)


def _define_orders(target, current, define_order):
    target = set(target)
    kept = [name for name in current if name in target]
    canonical = [name for name in define_order if name in target]
    canonical += [name for name in target if name not in set(define_order)]
    orders = []
    for names in (kept + [name for name in canonical if name not in set(current)], canonical):
        if names not in orders:
            orders.append(names)
    return orders


def get_packed_permutation_help(shader, technique, define_names, limit=3):
    """Return warning plus nearby packed define suggestions, or None if valid."""
    if not PACKED_HASHES:
        return None
    resolved = resolve_shader_path(shader)
    hashes = PACKED_HASHES.get(_norm_shader_path(resolved)) if resolved else None
    if not hashes:
        return None
    names = [str(name) for name in (define_names or []) if name]
    cache_key = (_norm_shader_path(resolved), str(technique or ""), tuple(names))
    if cache_key in _PACKED_HELP_CACHE:
        cached = _PACKED_HELP_CACHE[cache_key]
        return None if not cached else {"warning": cached["warning"], "suggestions": cached["suggestions"][:limit]}

    def store(value):
        if len(_PACKED_HELP_CACHE) > 256:
            _PACKED_HELP_CACHE.clear()
        _PACKED_HELP_CACHE[cache_key] = value
        return None if not value else {"warning": value["warning"], "suggestions": value["suggestions"][:limit]}

    if _combo_is_packed(hashes, names):
        return store(None)

    define_order = _packed_define_order(resolved, technique)
    current_set = set(names)
    enabled = list(names)
    disabled = [name for name in dict.fromkeys([*define_order, *names]) if name not in current_set]
    best = {}

    def record(ordered, n_off, n_on):
        if not _combo_is_packed(hashes, ordered):
            return
        score = (n_off + n_on, n_on, int(ordered != names))
        key = frozenset(ordered)
        if key not in best or score < best[key][0]:
            best[key] = (score, list(ordered))

    for ordered in _define_orders(current_set, names, define_order):
        if ordered != names:
            record(ordered, 0, 0)
    for budget in (1, 2, 3):
        if best:
            break
        for n_off in range(budget + 1):
            n_on = budget - n_off
            if n_off > min(3, len(enabled)) or n_on > min(2, len(disabled)):
                continue
            for off in combinations(enabled, n_off) if n_off else [()]:
                for on in combinations(disabled, n_on) if n_on else [()]:
                    target = (current_set - set(off)) | set(on)
                    for ordered in _define_orders(target, names, define_order):
                        record(ordered, n_off, n_on)

    return store({
        "warning": "This define combination is not a packed permutation",
        "suggestions": [
            {"label": _suggestion_label(names, defines), "defines": defines}
            for _, defines in sorted(best.values())[:3]
        ],
    })


def get_packed_permutation_warning(shader, define_names, technique=""):
    """Return a warning if enabled defines are not a packed permutation."""
    help_info = get_packed_permutation_help(shader, technique, define_names, limit=1)
    if not help_info:
        return None
    suggestions = help_info["suggestions"]
    if suggestions:
        return f"{help_info['warning']}. Try: {suggestions[0]['label']}"
    return help_info["warning"]


def _shader_param_names(shader, technique):
    techs = SHADER_PARAMETERS.get(shader) or {}
    matched = _match_name(technique, techs)
    if matched:
        return [name for name, _ in techs[matched]]
    ordered, seen = [], set()
    for items in techs.values():
        for name, _ in items:
            if name not in seen:
                seen.add(name)
                ordered.append(name)
    return ordered


def _packed_param_names(shader_key, define_names):
    tables = PACKED_PARAMS.get(shader_key)
    hashes = PACKED_HASHES.get(shader_key)
    if not tables or not hashes:
        return None
    matched = []
    for suffix in PACKED_AA_SUFFIXES:
        digest = _permutation_digest(define_names, suffix)
        if digest not in hashes:
            continue
        params = tables.get(digest)
        if params is None:
            return None
        matched.append(set(params))
    if not matched:
        return None
    return set.intersection(*matched)


def get_packed_param_help(shader, technique, define_names, enabled_params):
    """Return missing packed-permutation parameters, or None if the combo is valid."""
    if not PACKED_PARAMS:
        return None
    resolved = resolve_shader_path(shader)
    shader_key = _norm_shader_path(resolved) if resolved else ""
    if not shader_key or shader_key not in PACKED_PARAMS:
        return None
    names = [str(name) for name in (define_names or []) if name]
    enabled = [str(name) for name in (enabled_params or []) if name]
    cache_key = (shader_key, str(technique or ""), tuple(names), tuple(sorted(_norm_name(name) for name in enabled)))
    if cache_key in _PACKED_PARAM_HELP_CACHE:
        cached = _PACKED_PARAM_HELP_CACHE[cache_key]
        return None if not cached else dict(cached)

    def store(value):
        if len(_PACKED_PARAM_HELP_CACHE) > 256:
            _PACKED_PARAM_HELP_CACHE.clear()
        _PACKED_PARAM_HELP_CACHE[cache_key] = value
        return None if not value else dict(value)

    hashes = PACKED_HASHES.get(shader_key)
    if not hashes or not _combo_is_packed(hashes, names):
        return store(None)
    packed = _packed_param_names(shader_key, names)
    if packed is None:
        return store(None)
    db_names = _shader_param_names(resolved, technique)
    packed_keys = {_norm_name(name) for name in packed}
    always_keys = {_norm_name(name) for name in PACKED_PARAM_BASE.get(shader_key, set())}
    enabled_keys = {_norm_name(name) for name in enabled}
    missing = [
        name for name in db_names
        if _norm_name(name) in packed_keys and _norm_name(name) not in always_keys and _norm_name(name) not in enabled_keys
    ]
    if not missing:
        return store(None)
    return store({
        "warning": "This packed permutation expects additional parameters",
        "suggestions": [{
            "label": "Enable " + _format_define_list(missing),
            "parameters": missing,
        }],
    })


def get_packed_param_warning(shader, technique, define_names, enabled_params):
    """Return a warning if enabled params omit packed permutation requirements."""
    help_info = get_packed_param_help(shader, technique, define_names, enabled_params)
    if not help_info:
        return None
    suggestions = help_info["suggestions"]
    if suggestions:
        return f"{help_info['warning']}. Try: {suggestions[0]['label']}"
    return help_info["warning"]


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
    global _TECHNIQUE_ITEMS_CACHE
    shader = ""
    try:
        value = self.shader_path
        if isinstance(value, str):
            shader = value
    except Exception:
        shader = ""

    shader_key = resolve_shader_path(shader) or shader
    techniques = SHADER_TECHNIQUES.get(shader_key, [])
    numbers = TECHNIQUE_ENUM_NUMBERS.get(shader_key, {})
    if not techniques:
        _TECHNIQUE_ITEMS_CACHE = [('Basic', 'Basic', 'Fallback technique', 0)]
    else:
        _TECHNIQUE_ITEMS_CACHE = [
            (name, name, f'{name} technique', numbers.get(name, index))
            for index, name in enumerate(techniques)
        ]
    return _TECHNIQUE_ITEMS_CACHE

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

def migrate_material_options(settings, context=None):
    """Add new database options to an existing material, safely"""
    if not hasattr(settings, "shader_params") or not hasattr(settings, "defines"):
        return
    shader = resolve_shader_path(settings.shader_path) or settings.shader_path
    if shader not in SHADER_PARAMETERS:
        return
    technique = _canonical_technique(shader, settings.technique)
    if not technique or technique not in SHADER_PARAMETERS[shader]:
        return
    if not settings.shader_params and not settings.defines:
        return

    existing_params = {_norm_name(param.name) for param in settings.shader_params}
    for param_name, param_type in SHADER_PARAMETERS[shader][technique]:
        if _norm_name(param_name) in existing_params:
            continue
        param = settings.shader_params.add()
        param.name = param_name
        param.param_type = param_type
        param.enabled = False
        _init_new_param_values(param, param_name, param_type, shader, technique)
        existing_params.add(_norm_name(param_name))

    existing_defines = {_norm_name(define.name) for define in settings.defines}
    for define_name in SHADER_DEFINES.get(shader, {}).get(technique, []):
        if _norm_name(define_name) in existing_defines:
            continue
        define = settings.defines.add()
        define.name = define_name
        define.enabled = False
        existing_defines.add(_norm_name(define_name))

    settings["_last_shader_path"] = shader
    settings["_last_shader_technique"] = technique


def update_shader_change(self, context):
    """Update technique, parameters, and defines when shader changes"""
    if _SUPPRESS_SHADER_UPDATES:
        return
    prev_shader = str(self.get("_last_shader_path", ""))
    prev_technique = str(self.get("_last_shader_technique", ""))
    shader = resolve_shader_path(self.shader_path)

    if not shader or shader not in SHADER_TECHNIQUES or not SHADER_TECHNIQUES[shader]:
        return
    if self.shader_path != shader:
        self.shader_path = shader

    valid_techniques = list(SHADER_TECHNIQUES[shader])
    if self.technique not in valid_techniques:
        self.technique = _canonical_technique(shader, self.technique) or valid_techniques[0]

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
    if _SUPPRESS_SHADER_UPDATES:
        return
    _update_shader_params_impl(self, context, preserve_unmapped=False)


def update_shader_defines(self, context):
    """Helper exposed for callers that want define refresh."""
    _update_shader_defines_impl(self, context, preserve_unmapped=False)
