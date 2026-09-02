#!/usr/bin/env python3
"""
MTX to BMT converter utility:
Converts Madness Engine material XML files (.mtx) to binary material files (.bmt)
"""

import logging
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Block FourCC codes (little-endian)
BLMY, HEAD, ELMT, ATTR, COLL, NUMB, BOOL, STRS = (0x594D4C42, 0x44414548, 0x544D4C45, 0x52545441, 0x4C4C4F43, 0x424D554E, 0x4C4F4F42, 0x53525453,)

TYPE_FLOAT, TYPE_BOOL, TYPE_STRING = 0, 1, 2


def hash_string(s: str) -> int:
    h = 0
    for ch in s.encode("utf-8"):
        h = ((((h >> 27) + ((h << 5) & 0xFFFFFFFF)) * 31) + ch) & 0xFFFFFFFF
    return h


def _u32(v: int) -> int:
    return v & 0xFFFFFFFF


class BmtBuilder:
    """Builds a BMT binary from XML material data"""

    def __init__(self):
        self.elements: list[dict] = []
        self.attributes: list[dict] = []
        self.numbers: list[float] = []
        self.booleans: list[bool] = []
        self.strings = bytearray()
        self.string_offsets: dict[str, int] = {}

    def add_string(self, s: str) -> int:
        if s in self.string_offsets:
            return self.string_offsets[s]
        offset = len(self.strings)
        self.string_offsets[s] = offset
        encoded = s.encode("utf-8") + b"\0"
        self.strings.extend(encoded)
        self.strings.extend(b"\0" * ((4 - len(encoded) % 4) % 4))
        return offset

    def _add_value(self, raw: str) -> tuple[int, int, int]:
        """Store a raw attribute value (type, value_index, count)"""
        if raw.lower() in ("true", "false"):
            self.booleans.append(raw.lower() == "true")
            return TYPE_BOOL, len(self.booleans) - 1, 1
        try:
            floats = [float(x) for x in raw.split()]
        except ValueError:
            return TYPE_STRING, self.add_string(raw), 1
        start = len(self.numbers)
        self.numbers.extend(floats)
        return TYPE_FLOAT, start, len(floats)

    def process_element(self, xml_elem: ET.Element) -> int:
        """Post-order traversal, so parent strings are added after their children"""
        element_idx = len(self.elements)
        children = list(xml_elem)
        element = {
            "name": hash_string(xml_elem.tag),
            "attr_start": len(self.attributes),
            "attr_num": 0,
            "child_num": len(children),
            "child_first": element_idx + 1 if children else -1,
            "next_sibling": -1,
            "next_same_tag": -1,
        }
        self.elements.append(element)

        prev_child = -1
        for child in children:
            child_idx = self.process_element(child)
            if prev_child != -1:
                self.elements[prev_child]["next_sibling"] = child_idx
            prev_child = child_idx

        attr_count = 0
        for name, value in xml_elem.attrib.items():
            vtype, vidx, vnum = self._add_value(value)
            self.attributes.append({
                "name": hash_string(name),
                "type": vtype,
                "value": vidx,
                "num_values": vnum,
                "next_same": -1,
            })
            attr_count += 1
        self.elements[element_idx]["attr_num"] = attr_count
        return element_idx

    def build_coll(self) -> list[tuple[int, int, int, int]]:
        """Index of element/attribute name hashes (name, first_index, count, -1)"""
        entries = []
        for items in (self.elements, self.attributes):
            by_name: dict[int, list[int]] = {}
            for idx, item in enumerate(items):
                by_name.setdefault(item["name"], []).append(idx)
            for name, indices in sorted(by_name.items()):
                entries.append((name, indices[0], len(indices), -1))
        return entries

    def reorder_elements(self):
        """BMT stores elements depth-first, but with the root element last"""
        if not self.elements:
            return
        self.elements = self.elements[1:] + [self.elements[0]]
        last = len(self.elements) - 1
        remap = lambda i: last if i == 0 else i - 1
        for elem in self.elements:
            for key in ("child_first", "next_sibling"):
                if elem[key] != -1:
                    elem[key] = remap(elem[key])

    def build(self, xml_root: ET.Element) -> bytes:
        self.process_element(xml_root)
        self.reorder_elements()
        coll = self.build_coll()

        head = struct.pack("<7I", len(self.elements), len(self.attributes),
                           len(coll), len(self.numbers), len(self.strings),
                           len(self.booleans), 0)
        elmt = b"".join(struct.pack("<7I", *(_u32(e[k]) for k in (
            "name", "attr_start", "attr_num", "child_num",
            "child_first", "next_sibling", "next_same_tag"))) for e in self.elements)
        attr = b"".join(struct.pack("<5I", *(_u32(a[k]) for k in (
            "name", "type", "value", "num_values", "next_same"))) for a in self.attributes)
        coll_data = b"".join(struct.pack("<4I", *(_u32(v) for v in row)) for row in coll)
        numb = b"".join(struct.pack("<f", n) for n in self.numbers)

        bool_bytes = bytearray((len(self.booleans) + 7) // 8)
        for i, b in enumerate(self.booleans):
            if b:
                bool_bytes[i // 8] |= 1 << (i % 8)

        blocks = [(HEAD, head), (ELMT, elmt), (ATTR, attr), (COLL, coll_data),
                  (NUMB, numb), (BOOL, bytes(bool_bytes)), (STRS, bytes(self.strings))]

        offset = 16 + 16 * len(blocks)
        table = []
        for block_id, data in blocks:
            table.append((block_id, len(data), offset, 0))
            offset += (len(data) + 3) & ~3

        out = bytearray(struct.pack("<4I", BLMY, len(blocks), offset, 0))
        for row in table:
            out.extend(struct.pack("<4I", *row))
        for i, (_, data) in enumerate(blocks):
            out.extend(data)
            if i < len(blocks) - 1:
                out.extend(b"\0" * ((4 - len(out) % 4) % 4))
        return bytes(out)


def convert(mtx_path, bmt_path: Optional[str] = None, name_suffix: str = "") -> None:
    """Convert an MTX to a BMT, optionally appending a suffix to the material's name"""
    mtx_file = Path(mtx_path)
    if not mtx_file.exists():
        raise FileNotFoundError(f"MTX file not found: {mtx_path}")
    bmt_path = Path(bmt_path) if bmt_path else mtx_file.with_suffix(".bmt")

    root = ET.parse(mtx_file).getroot()
    if name_suffix:
        root.set("name", root.get("name", mtx_file.stem) + name_suffix)

    builder = BmtBuilder()
    data = builder.build(root)
    Path(bmt_path).write_bytes(data)

    logger.debug("Converted %s -> %s (elements=%d, attributes=%d, numbers=%d, booleans=%d, strings=%dB)",
                 mtx_path, bmt_path, len(builder.elements), len(builder.attributes), len(builder.numbers), len(builder.booleans), len(builder.strings))


def main() -> int:
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")

    if len(sys.argv) < 2:
        logger.error("Usage: mtx2bmt.py <input.mtx> [output.bmt]")
        return 1

    try:
        convert(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    except Exception as e:
        logger.error("%s", e)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
