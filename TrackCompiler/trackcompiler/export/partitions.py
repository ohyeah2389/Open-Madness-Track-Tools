from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence
import xml.etree.ElementTree as ET

import numpy as np


@dataclass
class PartitionItem:
    obj_id: int
    source_objects: Sequence
    aabb_min: np.ndarray
    aabb_max: np.ndarray


@dataclass
class Partition:
    id: int
    name: str
    children: List["Partition"] = field(default_factory=list)
    object_ids: List[int] = field(default_factory=list)
    aabb_min: np.ndarray = field(default_factory=lambda: np.zeros(3, dtype=np.float64))
    aabb_max: np.ndarray = field(default_factory=lambda: np.zeros(3, dtype=np.float64))


@dataclass
class _Coll:
    collection: object
    name: str
    depth: int
    order: int
    parent: Optional["_Coll"]
    children: List["_Coll"] = field(default_factory=list)
    object_ids: List[int] = field(default_factory=list)


def format_child_ids(ids: Sequence[int]) -> str:
    if not ids:
        return "NONE"
    return " ".join(str(i) for i in ids) + " "


def iter_preorder(node: Partition) -> Iterable[Partition]:
    yield node
    for child in node.children:
        yield from iter_preorder(child)


def _walk_visible(layer_collection, parent: Optional[_Coll], depth: int, order: List[int]) -> Optional[_Coll]:
    if layer_collection.exclude:
        return None
    collection = layer_collection.collection
    node = _Coll(collection, collection.name, depth, order[0], parent)
    order[0] += 1
    for child in layer_collection.children:
        child_node = _walk_visible(child, node, depth + 1, order)
        if child_node:
            node.children.append(child_node)
    return node


def _index_collections(root: _Coll) -> dict:
    by_ptr = {}
    stack = [root]
    while stack:
        node = stack.pop()
        by_ptr[node.collection.as_pointer()] = node
        stack.extend(reversed(node.children))
    return by_ptr


def _home_for_object(obj, by_ptr: dict, label: str, root: _Coll) -> _Coll:
    candidates = []
    for collection in getattr(obj, "users_collection", ()):
        node = by_ptr.get(collection.as_pointer())
        if node:
            candidates.append(node)
    if not candidates:
        return root
    best_depth = max(node.depth for node in candidates)
    deepest = [node for node in candidates if node.depth == best_depth]
    deepest.sort(key=lambda node: node.order)
    if len(deepest) > 1:
        print(
            f"  Warning: {label} is in multiple collections at depth {best_depth}; "
            f"using '{deepest[0].name}'"
        )
    return deepest[0]


def _path(node: _Coll) -> List[_Coll]:
    path = []
    while node:
        path.append(node)
        node = node.parent
    path.reverse()
    return path


def _lca(nodes: Sequence[_Coll], label: str) -> _Coll:
    paths = [_path(node) for node in nodes]
    shared = paths[0][0]
    for level in zip(*paths):
        if all(node is level[0] for node in level):
            shared = level[0]
        else:
            break
    if len({id(node) for node in nodes}) > 1:
        print(f"  Warning: {label} spans collections; placing on '{shared.name}'")
    return shared


def _home_for_item(item: PartitionItem, by_ptr: dict, root: _Coll) -> _Coll:
    homes = []
    for obj in item.source_objects:
        if obj is None:
            continue
        homes.append(_home_for_object(obj, by_ptr, getattr(obj, "name", str(item.obj_id)), root))
    if not homes:
        return root
    if len(homes) == 1:
        return homes[0]
    return _lca(homes, f"object {item.obj_id}")


def _prune(node: _Coll) -> bool:
    node.children = [child for child in node.children if _prune(child)]
    return bool(node.object_ids or node.children or node.parent is None)


def _collapse(node: _Coll) -> None:
    for child in node.children:
        _collapse(child)
    while len(node.children) == 1 and not node.object_ids:
        child = node.children[0]
        node.object_ids = child.object_ids
        node.children = child.children
        node.name = child.name
        for grandchild in node.children:
            grandchild.parent = node


def _to_partition(node: _Coll, items_by_id: dict) -> Partition:
    children = [_to_partition(child, items_by_id) for child in node.children]
    mins = []
    maxs = []
    for obj_id in node.object_ids:
        item = items_by_id[obj_id]
        mins.append(np.asarray(item.aabb_min, dtype=np.float64))
        maxs.append(np.asarray(item.aabb_max, dtype=np.float64))
    for child in children:
        mins.append(child.aabb_min)
        maxs.append(child.aabb_max)
    if mins:
        aabb_min = np.minimum.reduce(mins)
        aabb_max = np.maximum.reduce(maxs)
    else:
        aabb_min = np.zeros(3, dtype=np.float64)
        aabb_max = np.zeros(3, dtype=np.float64)
    return Partition(
        id=-1,
        name=node.name,
        children=children,
        object_ids=list(node.object_ids),
        aabb_min=aabb_min,
        aabb_max=aabb_max,
    )


def _union_aabb(nodes: Sequence[Partition]) -> tuple:
    mins = [node.aabb_min for node in nodes]
    maxs = [node.aabb_max for node in nodes]
    return np.minimum.reduce(mins), np.maximum.reduce(maxs)


def _pad_quadtree(node: Partition) -> Partition:
    """The engine stores exactly 0 or 4 child slots per partition (a quadtree)."""
    node.children = [_pad_quadtree(child) for child in node.children]
    if not node.children:
        return node
    while len(node.children) > 4:
        chunk = node.children[:4]
        aabb_min, aabb_max = _union_aabb(chunk)
        node.children = [
            Partition(id=-1, name="_quad", children=chunk, aabb_min=aabb_min, aabb_max=aabb_max)
        ] + node.children[4:]
    while len(node.children) < 4:
        node.children.append(
            Partition(id=-1, name="_empty", aabb_min=node.aabb_min.copy(), aabb_max=node.aabb_max.copy())
        )
    return node


def _number(node: Partition, next_id: int = 0) -> int:
    node.id = next_id
    next_id += 1
    for child in node.children:
        next_id = _number(child, next_id)
    return next_id


def build_partition_tree(view_layer, items: Sequence[PartitionItem]) -> Partition:
    root = _walk_visible(view_layer.layer_collection, None, 0, [0])
    if root is None:
        root = _Coll(getattr(view_layer, "layer_collection", None), "Scene Collection", 0, 0, None)
    by_ptr = _index_collections(root)
    for item in items:
        _home_for_item(item, by_ptr, root).object_ids.append(item.obj_id)
    _prune(root)
    _collapse(root)
    items_by_id = {item.obj_id: item for item in items}
    tree = _pad_quadtree(_to_partition(root, items_by_id))
    _number(tree)
    return tree


def append_partitions(scene: ET.Element, root: Partition) -> int:
    nodes = list(iter_preorder(root))
    scene.set("NumPartitions", str(len(nodes)))
    for part in nodes:
        elem = ET.SubElement(scene, "PARTITION_ID", no=str(part.id))
        ET.SubElement(
            elem,
            "AABBOX",
            min=f"{part.aabb_min[0]:.6f} {part.aabb_min[1]:.6f} {part.aabb_min[2]:.6f}",
            max=f"{part.aabb_max[0]:.6f} {part.aabb_max[1]:.6f} {part.aabb_max[2]:.6f}",
        )
        ET.SubElement(elem, "CHILD_PARTITIONS", IDs=format_child_ids([child.id for child in part.children]))
        ET.SubElement(elem, "CHILD_OBJS", IDs=format_child_ids(part.object_ids))
    return len(nodes)
