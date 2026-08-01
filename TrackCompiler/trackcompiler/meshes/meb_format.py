"""
MEB file format constants and specifications.

The MEB format is a binary mesh format used by Madness Engine games.
It consists of multiple sections, each identified by a 12-byte header containing section type identifiers.

Section format: [type1(4 bytes), type2(4 bytes), subtype(4 bytes), data...]
"""

# File header (8 bytes)
# Byte 3 = 1, Byte 5 = 1, rest = 0
HEADER = bytes([0, 0, 0, 1, 0, 1, 0, 0])

# Section headers (12 bytes each)
# Format: [type, 0, 0, 0, subtype, 0, 0, 0, index, 0, 0, 0]

# Vertex positions (section 2.0)
SECTION_VERTEX_POSITIONS = bytes([2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])

# Vertex normals (section 2.2)
SECTION_VERTEX_NORMALS = bytes([2, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0])

# Vertex colors (section 4.6)
SECTION_VERTEX_COLORS = bytes([4, 0, 0, 0, 6, 0, 0, 0, 0, 0, 0, 0])

# Tangents (section 2.4)
SECTION_TANGENTS = bytes([2, 0, 0, 0, 4, 0, 0, 0, 0, 0, 0, 0])

# Bitangents (section 2.5)
SECTION_BITANGENTS = bytes([2, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0, 0])

# UV map sections (section 1.3.x)
SECTION_UV_MAP_0 = bytes([1, 0, 0, 0, 3, 0, 0, 0, 0, 0, 0, 0])
SECTION_UV_MAP_1 = bytes([1, 0, 0, 0, 3, 0, 0, 0, 1, 0, 0, 0])
SECTION_UV_MAP_2 = bytes([1, 0, 0, 0, 3, 0, 0, 0, 2, 0, 0, 0])
SECTION_UV_MAP_3 = bytes([1, 0, 0, 0, 3, 0, 0, 0, 3, 0, 0, 0])
SECTION_UV_MAP_4 = bytes([1, 0, 0, 0, 3, 0, 0, 0, 4, 0, 0, 0])
SECTION_UV_MAP_5 = bytes([1, 0, 0, 0, 3, 0, 0, 0, 5, 0, 0, 0])

# W sections (extended UV coordinates with W component)
SECTION_W_UV_1 = bytes([2, 0, 0, 0, 3, 0, 0, 0, 1, 0, 0, 0])  # Section 2.3.1
SECTION_W_UV_2 = bytes([2, 0, 0, 0, 3, 0, 0, 0, 0, 0, 0, 0])  # Section 2.3.0

# Bodywork/special data (section 0.3.3)
SECTION_BODYWORK = bytes([0, 0, 0, 0, 3, 0, 0, 0, 3, 0, 0, 0])


def get_uv_section_header(index: int, include_w: bool = False) -> bytes:
    """Get the appropriate UV section header for a given index.
    
    Args:
        index: UV map index (0-5 for regular UVs, or special indices for W sections)
        include_w: If True, write UVW (3 floats) instead of UV (2 floats)
    
    Returns:
        12-byte section header
    """
    if include_w:
        if index == -1:
            return SECTION_W_UV_2
        elif index == -2:
            return SECTION_W_UV_1
        else:
            raise ValueError(f"Invalid W section index: {index}")
    else:
        headers = [
            SECTION_UV_MAP_0,
            SECTION_UV_MAP_1,
            SECTION_UV_MAP_2,
            SECTION_UV_MAP_3,
            SECTION_UV_MAP_4,
            SECTION_UV_MAP_5,
        ]
        if 0 <= index < len(headers):
            return headers[index]
        else:
            raise ValueError(f"Invalid UV map index: {index}")
