"""Writer for Blimey Markup Language, the engine's compiled form of its Reflection XML.

Tag and attribute names are stored only as hashes and values live in per-type pools,
so a document is built by flattening a tree of nodes into element and attribute tables.
The collection chunk indexes every element path, and every attribute as "path/@name",
which is how the engine looks nodes up.
"""

import struct
from typing import Any, Dict, List, Tuple

NUMBER, BOOLEAN, STRING = 0, 1, 2
END = -1


def name_hash(text: str) -> int:
    """The engine's name hash, used for tags, attributes and collection paths."""
    result = 0
    for char in text:
        result = (31 * ((result >> 27) + 32 * result) + ord(char)) & 0xFFFFFFFF
    return result


def chunk_id(name: str) -> int:
    return int.from_bytes(name[:4].encode().ljust(4, b"\0"), "little")


class Node:
    """One element: a tag, its attributes in order, and its children."""

    __slots__ = ("tag", "attrs", "children")

    def __init__(self, tag: str, attrs=None, children=None):
        self.tag = tag
        self.attrs: List[Tuple[str, Any]] = list(attrs or [])
        self.children: List["Node"] = list(children or [])


class BmlWriter:
    def __init__(self):
        self.elements: List[List[int]] = []
        self.attributes: List[List[int]] = []
        self.numbers: List[float] = []
        self.bools: List[int] = []
        self.strings = bytearray()
        self._offsets: Dict[str, int] = {}
        self._collections: Dict[int, Tuple[int, bool]] = {}

    def _string(self, text: str) -> int:
        if text not in self._offsets:
            self._offsets[text] = len(self.strings)
            self.strings += text.encode("utf-8") + b"\0"
        return self._offsets[text]

    def _value(self, value) -> Tuple[int, int, int]:
        """Return the type, pool index and vector length for an attribute value."""
        if isinstance(value, bool):
            self.bools.append(1 if value else 0)
            return BOOLEAN, len(self.bools) - 1, 1
        if isinstance(value, str):
            return STRING, self._string(value), 1
        values = [float(v) for v in (value if isinstance(value, (list, tuple)) else [value])]
        index = len(self.numbers)
        self.numbers.extend(values)
        return NUMBER, index, len(values)

    def _collect(self, path: str, index: int, is_attr: bool) -> None:
        """Record a path's first occurrence, chaining any later ones onto it."""
        key = name_hash(path)
        if key not in self._collections:
            self._collections[key] = (index, is_attr)
            return
        table, link = (self.attributes, 4) if is_attr else (self.elements, 6)
        cursor = self._collections[key][0]
        while table[cursor][link] != END:
            cursor = table[cursor][link]
        table[cursor][link] = index

    def add(self, node: Node, path: str = "") -> int:
        """Append an element and its subtree, returning the element's index."""
        path = f"{path}/{node.tag}" if path else node.tag
        index = len(self.elements)
        record = [name_hash(node.tag), len(self.attributes), len(node.attrs), 0, END, END, END]
        self.elements.append(record)
        self._collect(path, index, False)

        for name, value in node.attrs:
            value_type, pool_index, count = self._value(value)
            self._collect(f"{path}/@{name}", len(self.attributes), True)
            self.attributes.append([name_hash(name), value_type, pool_index, count, END])

        previous = None
        for child in node.children:
            child_index = self.add(child, path)
            if previous is None:
                record[4] = child_index
            else:
                self.elements[previous][5] = child_index
            previous = child_index
        record[3] = len(node.children)
        return index

    def build(self, root: Node) -> bytes:
        self.add(root)
        # Collections are searched by halving the array, and stock files order them by
        # signed comparison of the hash.
        def signed(key: int) -> int:
            return struct.unpack("<i", struct.pack("<I", key))[0]

        chunks = [
            ("HEAD", struct.pack("<6Ii", len(self.elements), len(self.attributes), len(self._collections), len(self.numbers), len(self._offsets), len(self.bools), 0)),
            ("COLL", b"".join(struct.pack("<IiIi", key, index, 1 if is_attr else 0, 0) for key, (index, is_attr) in sorted(self._collections.items(), key=lambda item: signed(item[0])))),
            ("ELMT", b"".join(struct.pack("<IiIIiii", *e) for e in self.elements)),
            ("ATTR", b"".join(struct.pack("<IIiIi", *a) for a in self.attributes)),
            ("NUMB", struct.pack(f"<{len(self.numbers)}f", *self.numbers)),
            ("STRS", bytes(self.strings)),
            ("BOOL", bytes(self.bools)),
        ]

        table_size = 0x10 + 0x10 * len(chunks)
        offset, table, body = table_size, b"", b""
        for name, payload in chunks:
            payload += b"\0" * (-len(payload) % 4)
            table += struct.pack("<IIIi", chunk_id(name), len(payload), offset, 0)
            body += payload
            offset += len(payload)
        return struct.pack("<4sIIi", b"BLMY", len(chunks), table_size + len(body), 0) + table + body
