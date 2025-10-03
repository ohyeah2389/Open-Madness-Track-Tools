import numpy as np
from math import sin, cos, radians


# Coordinate system conversion functions
def _quat(ax: float, ay: float, az: float) -> np.ndarray:
    """Create quaternion from Euler degrees (XYZ order)."""
    rx, ry, rz = map(radians, (ax, ay, az))
    cx, sx = cos(rx / 2), sin(rx / 2)
    cy, sy = cos(ry / 2), sin(ry / 2)
    cz, sz = cos(rz / 2), sin(rz / 2)
    # XYZ intrinsic
    w = cx * cy * cz + sx * sy * sz
    x = sx * cy * cz - cx * sy * sz
    y = cx * sy * cz + sx * cy * sz
    z = cx * cy * sz - sx * sy * cz
    return np.array([w, x, y, z])


# Blender to Madness coordinate system conversion
Q_EXTRA = _quat(-90, 0, 0)  # Only rotate around X axis to convert Z-up to Y-up


def q_mult(q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
    """Hamilton product (w,x,y,z)."""
    w1, x1, y1, z1 = q1
    w2, x2, y2, z2 = q2
    return np.array(
        [
            w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
        ]
    )


def q_to_matrix(q: np.ndarray) -> np.ndarray:
    """3×3 rotation matrix from (w,x,y,z)."""
    w, x, y, z = q
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


R_EXTRA = q_to_matrix(Q_EXTRA)


def convert_position(pos: np.ndarray) -> np.ndarray:
    """Convert position from Blender coordinate system to Madness."""
    x, y, z = pos
    return np.array([x, z, y])


def convert_rotation_matrix(rot: np.ndarray) -> np.ndarray:
    """Convert rotation matrix from Blender coordinate system to Madness."""
    converted = R_EXTRA @ rot @ R_EXTRA.T
    return converted


def apply_180_rotation_y(q: np.ndarray) -> np.ndarray:
    """Apply 180° rotation about Y axis to quaternion."""
    q_180_y = np.array([0, 0, 1, 0])
    return q_mult(q_180_y, q)


R_POS = np.diag([1, 1, 1])


def _quat_from_matrix(m: np.ndarray) -> np.ndarray:
    """Convert 3×3 rotation matrix to quaternion (w, x, y, z)."""
    t = np.trace(m)
    if t > 0:
        s = np.sqrt(t + 1.0) * 2
        w = 0.25 * s
        x = (m[2, 1] - m[1, 2]) / s
        y = (m[0, 2] - m[2, 0]) / s
        z = (m[1, 0] - m[0, 1]) / s
    else:
        i = np.argmax(np.diag(m))
        if i == 0:
            s = np.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
            w = (m[2, 1] - m[1, 2]) / s
            x = 0.25 * s
            y = (m[0, 1] + m[1, 0]) / s
            z = (m[0, 2] + m[2, 0]) / s
        elif i == 1:
            s = np.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
            w = (m[0, 2] - m[2, 0]) / s
            x = (m[0, 1] + m[1, 0]) / s
            y = 0.25 * s
            z = (m[1, 2] + m[2, 1]) / s
        else:
            s = np.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
            w = (m[1, 0] - m[0, 1]) / s
            x = (m[0, 2] + m[2, 0]) / s
            y = (m[1, 2] + m[2, 1]) / s
            z = 0.25 * s
    return np.array([w, x, y, z])


def fix_x_axis_rotation_direction(q: np.ndarray) -> np.ndarray:
    """Fix X-axis and Z-axis rotation directions."""
    w, x, y, z = q
    return np.array([-w, x, y, -z])


def decompose_matrix(m: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Returns (translation_vec3, quaternion_wxyz)"""
    translation = m[:3, 3]
    rot_3x3 = m[:3, :3]

    translation_converted = convert_position(translation)
    rot_3x3_converted = convert_rotation_matrix(rot_3x3)
    q = _quat_from_matrix(rot_3x3_converted)
    q_final = fix_x_axis_rotation_direction(q)

    return translation_converted, q_final
