"""
Build a shader database by walking MTX files.

This script scans MTX XML files (across one or more roots) to discover every
shader, technique, define, and parameter (with observed value statistics) and
writes a JSON database that the Blender add-on can consume.
"""

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Iterable, Set, Tuple
import xml.etree.ElementTree as ET


def _add_example(container: List[Any], value: Any, limit: int) -> None:
    """Append value to container if under the limit and not already present."""
    if value in container:
        return
    if len(container) < limit:
        container.append(value)


def _normalize_shader_key(shader_path: str) -> str:
    """Case-insensitive key for shader path; also normalizes slashes."""
    return shader_path.replace("/", "\\").strip().lower()


def _normalize_shader_display(shader_path: str) -> str:
    """Canonical display string for a shader path (keeps casing, fixes slashes)."""
    return shader_path.replace("/", "\\").strip()


class ShaderDatabaseBuilder:
    """Collects shader metadata from MTX files and writes it to JSON."""

    def __init__(
        self, mtx_roots: Iterable[Path], max_examples: int = 5, min_pairing_support: int = 2
    ) -> None:
        self.mtx_roots = list(mtx_roots)
        self.max_examples = max_examples
        self.min_pairing_support = max(1, int(min_pairing_support))
        self.raw_db: Dict[str, Any] = {
            "mtxFiles": 0,
            "shaders": {},
            "errors": [],
        }
        # Map normalized shader key -> canonical display path
        self.shader_canonical: Dict[str, str] = {}
        # Map normalized technique key per shader -> canonical technique string
        self.technique_canonical: Dict[str, Dict[str, str]] = {}

    def build(self) -> Dict[str, Any]:
        for root in self.mtx_roots:
            for path in root.rglob("*.mtx"):
                self.raw_db["mtxFiles"] += 1
                try:
                    self._process_file(path)
                except Exception as exc:  # pragma: no cover - defensive for malformed files
                    self.raw_db["errors"].append({"path": str(path), "error": str(exc)})
                    print(f"[WARN] Failed to read {path}: {exc}")

        return self._serialize()

    def _process_file(self, file_path: Path) -> None:
        tree = ET.parse(file_path)
        root = tree.getroot()

        shader_raw = (root.get("shader") or "UNKNOWN_SHADER")
        shader_key = _normalize_shader_key(shader_raw)
        shader = self.shader_canonical.setdefault(shader_key, _normalize_shader_display(shader_raw))

        technique_raw = (root.get("technique") or "UNKNOWN_TECHNIQUE")
        technique = self._canonicalize_technique(shader_key, technique_raw)

        tech_entry = self._get_technique_entry(shader, technique)
        tech_entry["filesSeen"] += 1

        # Track per-file presence to compute always-on sets
        params_seen_this_file = set()
        defines_seen_this_file = set()
        param_order_this_file = []
        define_order_this_file = []

        for shader_param in root.findall("shaderparam"):
            param_name = shader_param.get("name")
            param_type = shader_param.get("type")

            if not param_name or not param_type:
                continue

            value_elem = shader_param.find("value")
            value_str = value_elem.get("v", "") if value_elem is not None else ""
            self._record_parameter(tech_entry, param_name, param_type, value_str)
            params_seen_this_file.add(param_name)
            param_order_this_file.append(param_name)

        for define_elem in root.findall("define"):
            define_name = define_elem.get("name")
            if define_name:
                tech_entry["defines"].add(define_name)
                defines_seen_this_file.add(define_name)
                define_order_this_file.append(define_name)

        if define_order_this_file:
            self._record_define_order(tech_entry, define_order_this_file)
        if param_order_this_file:
            self._record_param_order(tech_entry, param_order_this_file)
        self._record_option_pairings(tech_entry, params_seen_this_file, defines_seen_this_file)

        # Increment counts for always-on detection
        for pname in params_seen_this_file:
            tech_entry["paramCounts"][pname] = tech_entry["paramCounts"].get(pname, 0) + 1
        for dname in defines_seen_this_file:
            tech_entry["defineCounts"][dname] = tech_entry["defineCounts"].get(dname, 0) + 1

    def _get_technique_entry(self, shader: str, technique: str) -> Dict[str, Any]:
        shader_entry = self.raw_db["shaders"].setdefault(shader, {"techniques": {}})
        return shader_entry["techniques"].setdefault(
            technique,
            {
                "filesSeen": 0,
                "parameters": {},
                "defines": set(),
                "paramCounts": {},
                "defineCounts": {},
                "defineOrderPairs": {},
                "defineFirstSeen": {},
                "defineOrderCounts": {},
                "defineOrderFirstSeen": {},
                "defineOrderPositions": {},
                "paramOrderPositions": {},
                "paramFirstSeen": {},
                "optionCounts": {},
                "optionPairCounts": {},
            },
        )

    def _record_parameter(
        self, technique_entry: Dict[str, Any], name: str, param_type: str, value: str
    ) -> None:
        params = technique_entry["parameters"]
        if name not in params:
            params[name] = {
                "types": set(),
                "floatMin": None,
                "floatMax": None,
                "floatSum": 0.0,
                "floatCount": 0,
                "floatVals": [],
                "intMin": None,
                "intMax": None,
                "vec4Sum": [0.0, 0.0, 0.0, 0.0],
                "vec4Count": 0,
                "vec4Vals": [],
                "vec4Examples": [],
                "textureExtensions": set(),
                "boolValues": set(),
                "sampleValues": [],
            }

        entry = params[name]
        entry["types"].add(param_type)
        self._update_stats(entry, param_type, value)

    def _update_stats(self, entry: Dict[str, Any], param_type: str, value: str) -> None:
        if param_type == "EPT_F32":
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                return

            entry["floatMin"] = numeric if entry["floatMin"] is None else min(entry["floatMin"], numeric)
            entry["floatMax"] = numeric if entry["floatMax"] is None else max(entry["floatMax"], numeric)
            entry["floatSum"] += numeric
            entry["floatCount"] += 1
            entry["floatVals"].append(numeric)
            _add_example(entry["sampleValues"], numeric, self.max_examples)
            return

        if param_type == "EPT_S32":
            try:
                numeric = int(value)
            except (TypeError, ValueError):
                return

            entry["intMin"] = numeric if entry["intMin"] is None else min(entry["intMin"], numeric)
            entry["intMax"] = numeric if entry["intMax"] is None else max(entry["intMax"], numeric)
            _add_example(entry["sampleValues"], numeric, self.max_examples)
            return

        if param_type == "EPT_VEC4":
            try:
                parts = [float(p) for p in value.split() if p]
            except (TypeError, ValueError):
                return

            if len(parts) >= 4:
                vec4 = parts[:4]
                _add_example(entry["vec4Examples"], vec4, self.max_examples)
                entry["vec4Count"] += 1
                for i in range(4):
                    entry["vec4Sum"][i] += vec4[i]
                entry["vec4Vals"].append(vec4)
            return

        if param_type == "EPT_TEXTURE":
            ext = Path(value).suffix.lower()
            if ext:
                entry["textureExtensions"].add(ext)
            if value:
                _add_example(entry["sampleValues"], value, self.max_examples)
            return

        if param_type == "EPT_BOOL":
            normalized = str(value).strip().lower() == "true"
            entry["boolValues"].add(normalized)
            return

        # Unknown type - still keep a sample if available
        if value:
            _add_example(entry["sampleValues"], value, self.max_examples)

    def _canonicalize_technique(self, shader_key: str, technique_raw: str) -> str:
        """Canonicalize technique names case-insensitively per shader."""
        technique_clean = technique_raw.strip() if technique_raw else "UNKNOWN_TECHNIQUE"
        t_norm = technique_clean.lower()
        canon_map = self.technique_canonical.setdefault(shader_key, {})
        if t_norm not in canon_map:
            canon_map[t_norm] = technique_clean
        return canon_map[t_norm]

    def _record_define_order(self, technique_entry: Dict[str, Any], define_order: List[str]) -> None:
        """Capture the observed define ordering for later reconstruction."""
        pairs = technique_entry["defineOrderPairs"]
        first_seen = technique_entry["defineFirstSeen"]
        order_counts = technique_entry["defineOrderCounts"]
        order_first_seen = technique_entry["defineOrderFirstSeen"]
        order_positions = technique_entry["defineOrderPositions"]

        for define_name in define_order:
            if define_name not in first_seen:
                first_seen[define_name] = len(first_seen)

        order_key = tuple(define_order)
        if order_key not in order_counts:
            order_first_seen[order_key] = len(order_first_seen)
        order_counts[order_key] = order_counts.get(order_key, 0) + 1

        for i, before_name in enumerate(define_order):
            before_map = pairs.setdefault(before_name, {})
            for after_name in define_order[i + 1 :]:
                before_map[after_name] = before_map.get(after_name, 0) + 1
            order_positions.setdefault(before_name, []).append(i)

    def _record_param_order(self, technique_entry: Dict[str, Any], param_order: List[str]) -> None:
        """Capture the observed parameter ordering for later reconstruction."""
        first_seen = technique_entry["paramFirstSeen"]
        order_positions = technique_entry["paramOrderPositions"]

        for name in param_order:
            if name not in first_seen:
                first_seen[name] = len(first_seen)

        for i, name in enumerate(param_order):
            order_positions.setdefault(name, []).append(i)

    def _record_option_pairings(
        self,
        technique_entry: Dict[str, Any],
        params_seen_this_file: Set[str],
        defines_seen_this_file: Set[str],
    ) -> None:
        """Track strict co-occurrence counts for per-technique option implications."""
        options_seen: Set[Tuple[str, str]] = set()
        for param_name in params_seen_this_file:
            options_seen.add(("parameter", param_name))
        for define_name in defines_seen_this_file:
            options_seen.add(("define", define_name))
        if not options_seen:
            return

        option_counts = technique_entry["optionCounts"]
        pair_counts = technique_entry["optionPairCounts"]
        for source in options_seen:
            option_counts[source] = option_counts.get(source, 0) + 1
            source_pairs = pair_counts.setdefault(source, {})
            for target in options_seen:
                if target != source:
                    source_pairs[target] = source_pairs.get(target, 0) + 1

    @staticmethod
    def _median_index(indices: List[int]) -> float:
        if not indices:
            return math.inf
        ordered = sorted(indices)
        mid = len(ordered) // 2
        if len(ordered) % 2 == 1:
            return float(ordered[mid])
        return (ordered[mid - 1] + ordered[mid]) / 2.0

    def _resolve_define_order(self, technique_entry: Dict[str, Any]) -> List[str]:
        """Derive a stable define ordering using observed per-file sequences."""
        defines = list(technique_entry["defines"])
        if not defines:
            return []

        first_seen = technique_entry.get("defineFirstSeen", {})
        order_positions = technique_entry.get("defineOrderPositions", {})

        def _sort_key(name: str):
            median_pos = self._median_index(order_positions.get(name, []))
            return (median_pos, first_seen.get(name, math.inf), name.lower())

        return sorted(defines, key=_sort_key)

    def _resolve_param_order(self, technique_entry: Dict[str, Any]) -> List[str]:
        """Derive a stable parameter ordering using observed per-file sequences."""
        params = list(technique_entry["parameters"].keys())
        if not params:
            return []

        first_seen = technique_entry.get("paramFirstSeen", {})
        order_positions = technique_entry.get("paramOrderPositions", {})

        def _sort_key(name: str):
            median_pos = self._median_index(order_positions.get(name, []))
            return (median_pos, first_seen.get(name, math.inf), name.lower())

        return sorted(params, key=_sort_key)

    def _resolve_option_pairings(
        self,
        technique_entry: Dict[str, Any],
        base_params: Set[str],
        base_defines: Set[str],
    ) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """Build strict implication suggestions from observed co-occurrence."""
        option_counts = technique_entry.get("optionCounts", {})
        pair_counts = technique_entry.get("optionPairCounts", {})
        grouped: Dict[str, Dict[str, List[Dict[str, Any]]]] = {"defines": {}, "parameters": {}}

        for source, source_count in option_counts.items():
            if source_count < self.min_pairing_support:
                continue
            source_kind, source_name = source
            if source_kind not in {"define", "parameter"}:
                continue
            source_key = "defines" if source_kind == "define" else "parameters"
            suggestions: List[Dict[str, Any]] = []

            for target, co_count in pair_counts.get(source, {}).items():
                if co_count != source_count:
                    continue
                target_kind, target_name = target
                if target_kind == "parameter" and target_name in base_params:
                    continue
                if target_kind == "define" and target_name in base_defines:
                    continue
                suggestions.append(
                    {
                        "kind": target_kind,
                        "name": target_name,
                        "support": co_count,
                        "confidence": 1.0,
                    }
                )

            if suggestions:
                suggestions.sort(key=lambda item: (item["kind"], item["name"].lower()))
                grouped[source_key][source_name] = suggestions

        grouped["defines"] = dict(sorted(grouped["defines"].items(), key=lambda item: item[0].lower()))
        grouped["parameters"] = dict(
            sorted(grouped["parameters"].items(), key=lambda item: item[0].lower())
        )
        return grouped

    def _serialize(self) -> Dict[str, Any]:
        source_roots = [str(r) for r in self.mtx_roots]

        def median(vals: List[float]):
            if not vals:
                return None
            vals_sorted = sorted(vals)
            n = len(vals_sorted)
            mid = n // 2
            if n % 2 == 1:
                return round(vals_sorted[mid], 1)
            return round((vals_sorted[mid - 1] + vals_sorted[mid]) / 2.0, 1)

        serialized = {
            "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "sourceRoot": source_roots[0] if source_roots else "",
            "sourceRoots": source_roots,
            "mtxFiles": self.raw_db["mtxFiles"],
            "shaders": {},
        }

        if self.raw_db["errors"]:
            serialized["errors"] = self.raw_db["errors"]

        for shader, shader_data in self.raw_db["shaders"].items():
            techniques_out = {}

            for technique, technique_data in shader_data["techniques"].items():
                params_out = {}
                for param_name, param_data in technique_data["parameters"].items():
                    float_avg = None
                    float_median = None
                    if param_data["floatCount"] > 0:
                        avg = param_data["floatSum"] / param_data["floatCount"]
                        float_avg = round(avg, 2)
                        float_median = median(param_data["floatVals"])

                    vec4_avg = None
                    vec4_median = None
                    if param_data["vec4Count"] > 0:
                        vec4_avg = [
                            round((param_data["vec4Sum"][i] / param_data["vec4Count"]), 2)
                            for i in range(4)
                        ]
                        # median per component
                        comps = list(zip(*param_data["vec4Vals"]))
                        vec4_median = [
                            median(list(comps[i]))
                            for i in range(4)
                        ]

                    params_out[param_name] = {
                        "types": sorted(param_data["types"]),
                        "floatMin": param_data["floatMin"],
                        "floatMax": param_data["floatMax"],
                        "floatAvg": float_avg,
                        "floatMedian": float_median,
                        "intMin": param_data["intMin"],
                        "intMax": param_data["intMax"],
                        "vec4Examples": param_data["vec4Examples"],
                        "vec4Avg": vec4_avg,
                        "vec4Median": vec4_median,
                        "textureExtensions": sorted(param_data["textureExtensions"]),
                        "boolValues": sorted(param_data["boolValues"]),
                        "sampleValues": param_data["sampleValues"],
                    }

                base_defines = {
                    d for d, count in technique_data["defineCounts"].items() if count == technique_data["filesSeen"]
                }
                base_params = {
                    p for p, count in technique_data["paramCounts"].items() if count == technique_data["filesSeen"]
                }
                technique_out = {
                    "filesSeen": technique_data["filesSeen"],
                    "defines": sorted(technique_data["defines"]),
                    "defineOrder": self._resolve_define_order(technique_data),
                    "baseDefines": sorted(base_defines),
                    "baseParameters": sorted(base_params),
                    "paramOrder": self._resolve_param_order(technique_data),
                    "parameters": params_out,
                }
                pairings = self._resolve_option_pairings(technique_data, base_params, base_defines)
                if pairings["defines"] or pairings["parameters"]:
                    technique_out["optionPairings"] = pairings
                techniques_out[technique] = technique_out

            serialized["shaders"][shader] = {"techniques": techniques_out}

        return serialized


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate mtx_shader_database.json from MTX files."
    )
    parser.add_argument(
        "--mtx-root",
        required=True,
        type=Path,
        nargs="+",
        help="One or more root directories containing MTX files (scanned recursively).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name("shaders") / "mtx_shader_database.json",
        help="Path to write the JSON database (default: database/shaders/mtx_shader_database.json).",
    )
    parser.add_argument(
        "--max-examples",
        type=int,
        default=5,
        help="Maximum number of example values to keep per parameter.",
    )
    parser.add_argument(
        "--min-pairing-support",
        type=int,
        default=2,
        help="Minimum source occurrences required before emitting strict option pairings.",
    )
    return parser.parse_args()


def resolve_output_path(output_arg: Path) -> Path:
    """Resolve output relative to this script and tolerate `database/...` prefix."""
    output_path = output_arg.expanduser()
    if output_path.is_absolute():
        return output_path

    relative = output_path
    if relative.parts and relative.parts[0].lower() == "database":
        relative = Path(*relative.parts[1:]) if len(relative.parts) > 1 else Path("mtx_shader_database.json")

    return (Path(__file__).resolve().parent / relative).resolve()


def main() -> None:
    args = parse_args()

    roots = [r.expanduser() for r in args.mtx_root]

    for root in roots:
        if not root.exists():
            raise SystemExit(f"MTX root does not exist: {root}")
        if not root.is_dir():
            raise SystemExit(f"MTX root must be a directory: {root}")

    builder = ShaderDatabaseBuilder(
        mtx_roots=roots,
        max_examples=args.max_examples,
        min_pairing_support=args.min_pairing_support,
    )
    database = builder.build()

    output_path = resolve_output_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(database, handle, indent=2)

    print(f"Wrote shader database to {output_path} (files scanned: {database['mtxFiles']})")
    if database.get("errors"):
        print(f"Completed with {len(database['errors'])} warning(s); see JSON for details.")


if __name__ == "__main__":
    main()

