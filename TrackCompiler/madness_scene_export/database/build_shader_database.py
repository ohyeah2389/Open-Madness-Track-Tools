"""
Build a shader database by walking MTX files.

This script scans MTX XML files (across one or more roots) to discover every
shader, technique, define, and parameter (with observed value statistics) and
writes a JSON database that the Blender add-on can consume.
"""

import argparse
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Iterable
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

    def __init__(self, mtx_roots: Iterable[Path], max_examples: int = 5) -> None:
        self.mtx_roots = list(mtx_roots)
        self.max_examples = max_examples
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

        for shader_param in root.findall("shaderparam"):
            param_name = shader_param.get("name")
            param_type = shader_param.get("type")

            if not param_name or not param_type:
                continue

            value_elem = shader_param.find("value")
            value_str = value_elem.get("v", "") if value_elem is not None else ""
            self._record_parameter(tech_entry, param_name, param_type, value_str)
            params_seen_this_file.add(param_name)

        for define_elem in root.findall("define"):
            define_name = define_elem.get("name")
            if define_name:
                tech_entry["defines"].add(define_name)
                defines_seen_this_file.add(define_name)

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
            "generatedAt": datetime.utcnow().isoformat() + "Z",
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

                techniques_out[technique] = {
                    "filesSeen": technique_data["filesSeen"],
                    "defines": sorted(technique_data["defines"]),
                    "baseDefines": sorted(
                        d for d, count in technique_data["defineCounts"].items() if count == technique_data["filesSeen"]
                    ),
                    "baseParameters": sorted(
                        p for p, count in technique_data["paramCounts"].items() if count == technique_data["filesSeen"]
                    ),
                    "parameters": params_out,
                }

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
        default=Path(__file__).with_name("mtx_shader_database.json"),
        help="Path to write the JSON database (default: database/mtx_shader_database.json).",
    )
    parser.add_argument(
        "--max-examples",
        type=int,
        default=5,
        help="Maximum number of example values to keep per parameter.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    roots = [r.expanduser() for r in args.mtx_root]

    for root in roots:
        if not root.exists():
            raise SystemExit(f"MTX root does not exist: {root}")
        if not root.is_dir():
            raise SystemExit(f"MTX root must be a directory: {root}")

    builder = ShaderDatabaseBuilder(mtx_roots=roots, max_examples=args.max_examples)
    database = builder.build()

    output_path = args.output.expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(database, handle, indent=2)

    print(f"Wrote shader database to {output_path} (files scanned: {database['mtxFiles']})")
    if database.get("errors"):
        print(f"Completed with {len(database['errors'])} warning(s); see JSON for details.")


if __name__ == "__main__":
    main()

