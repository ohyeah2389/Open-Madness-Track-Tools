from pathlib import Path
import subprocess
import shlex
import re
import itertools
from math import inf
import numpy as np
from typing import List, Tuple
from ..utils import sanitize

# Blender imports for console output
try:
    import bpy  # type: ignore
    BLENDER_AVAILABLE = True
except ImportError:
    BLENDER_AVAILABLE = False


def print_to_blender_console(message: str):
    """Print message to Blender console if available."""
    if BLENDER_AVAILABLE:
        print(message)  # This goes to Blender's console
    else:
        print(message)  # Fallback to regular print


def run_exporter(
    exporter_exe: Path,
    fbx_file: Path,
    output_dir: Path,
    extra_args: List[str],
    resource_prefix: str = "",
) -> Tuple[Path, str]:
    """Run the Madness exporter on one file."""
    cmd = [str(exporter_exe), str(fbx_file), "-o", str(output_dir)]

    if resource_prefix:
        material_dir = resource_prefix.strip("/")
        if not material_dir.startswith("\\"):
            material_dir = "\\" + material_dir
        if not material_dir.endswith("\\"):
            material_dir = material_dir + "\\"
        cmd.extend(["--material-dir", material_dir])

    cmd.extend(extra_args)

    #print(" ".join(shlex.quote(c) for c in cmd))

    proc = subprocess.run(cmd, capture_output=True)

    stdout_text = ""
    stderr_text = ""

    if proc.stdout:
        for encoding in ["utf-8", "cp1252", "cp437", "latin1"]:
            try:
                stdout_text = proc.stdout.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            stdout_text = proc.stdout.decode("utf-8", errors="replace")

    if proc.stderr:
        for encoding in ["utf-8", "cp1252", "cp437", "latin1"]:
            try:
                stderr_text = proc.stderr.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            stderr_text = proc.stderr.decode("utf-8", errors="replace")

    output_text = stdout_text + stderr_text

    # Print MEB export output to Blender console
    #print_to_blender_console(f"\n=== MEB EXPORT OUTPUT: {fbx_file.name} ===")
    #if stdout_text.strip():
    #    print_to_blender_console("STDOUT:")
    #    for line in stdout_text.splitlines():
    #        print_to_blender_console(f"  {line}")
    #if stderr_text.strip():
    #    print_to_blender_console("STDERR:")
    #    for line in stderr_text.splitlines():
    #        print_to_blender_console(f"  {line}")
    #print_to_blender_console(f"=== END MEB EXPORT OUTPUT: {fbx_file.name} ===\n")

    if proc.returncode != 0:
        raise RuntimeError(f"Exporter failed for {fbx_file.name}: {output_text}")

    meb_path = output_dir / (fbx_file.stem + ".meb")
    if not meb_path.exists():
        raise RuntimeError(f"Expected MEB file not created: {meb_path}")

    return meb_path, output_text


def parse_bounds(out: str) -> Tuple[np.ndarray, float, np.ndarray, np.ndarray]:
    """Parse bounding info from exporter output."""
    cx = cy = cz = r = 0.0
    minv = np.array([inf, inf, inf])
    maxv = np.array([-inf, -inf, -inf])

    float_re = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")
    # float_re = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")
    for ln in out.splitlines():
        nums = [float(v) for v in float_re.findall(ln)]
        if not nums:
            continue
        if "Mesh bounding sphere" in ln and len(nums) >= 3:
            cx, cy, cz = nums[:3]
        elif ln.startswith("Radius"):
            r = nums[0]
        elif ln.startswith("Min") and len(nums) >= 3:
            minv = np.array(nums[:3])
        elif ln.startswith("Max") and len(nums) >= 3:
            maxv = np.array(nums[:3])

    return np.array([cx, cy, cz]), r, minv, maxv


def rotate_vec(v: np.ndarray) -> np.ndarray:
    """Apply coordinate system rotation to a vector."""
    from ..utils.coordinate_transforms import R_POS
    return R_POS @ v


def rotate_bounds(
    bb_min: np.ndarray, bb_max: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    """Rotate AABB and return new axis-aligned bounds."""
    from ..utils.coordinate_transforms import R_POS
    corners = np.array(
        list(
            itertools.product(
                [bb_min[0], bb_max[0]], [bb_min[1], bb_max[1]], [bb_min[2], bb_max[2]]
            )
        )
    )
    rotated = (R_POS @ corners.T).T
    return rotated.min(axis=0), rotated.max(axis=0)

