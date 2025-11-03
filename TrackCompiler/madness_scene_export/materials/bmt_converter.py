"""
BMT (Binary Material) Converter
Converts MTX (XML) material files to BMT (binary) format for Madness Engine

Based on reverse engineering of bmt2xml by Jan-Peter Nilsson
"""

import struct
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple
from pathlib import Path


# BMT Format Constants (FourCC codes stored as little-endian)
BLMY = 0x594D4C42  # File signature
HEAD = 0x44414548  # Header block
ELMT = 0x544D4C45  # Elements block
ATTR = 0x52545441  # Attributes block
COLL = 0x4C4C4F43  # Collections block
NUMB = 0x424D554E  # Numbers (float values) block
BOOL = 0x4C4F4F42  # Boolean values block
STRS = 0x53525453  # Strings block

# Data type constants
TYPE_FLOAT = 0
TYPE_BOOL = 1
TYPE_STRING = 2

# Known string/tag name hashes for common BMT elements
BMT_STRING_HASHES = {
    "e": 0x00000065,
    "f": 0x00000066,
    "t": 0x00000074,
    "v": 0x00000076,
    "w": 0x00000077,
    "name": 0x061B2AC5,
    "type": 0x64A09665,
    "behaviour": 0x1F0F4EA6,
    "technique": 0xA7AB72D0,
    "sb": 0x0001BE02,
    "db": 0x000183E2,
    "bo": 0x00017C2F,
    "shader": 0xB260F2BF,
    "cull": 0x873CF6EC,
    "numparams": 0x25A11D8A,
    "fog": 0x05FD4687,
    "antialias": 0x69753170,
    "deferredID": 0xD345702C,
    "base": 0x4BE14205,
    "data": 0xC04045E1,
    "elements": 0x32DFF53A,
    "enabled": 0xE6F9DDA1,
    "override": 0xED618B4F,
    "shaderparam": 0x26ACEF06,
    "value": 0x69B6F8EB,
    "depthparams": 0xCA6C420B,
    "material": 0xD65A4663,
    "alphablendparams": 0x00E38703,
    "writeenabled": 0x7D3E56F9,
    "sourceblend": 0xED653EEC,
    "destblend": 0xC357F2C1,
    "blendop": 0x1CFD9605,
    "define": 0xCB729509,
    "alphatestparams": 0x2539DE0E,
    "function": 0x15E108AF,
    "VERSION": 0xC5EC1F32,
    "supportsSpecialisedLighting": 0x4E2C0F09,
}


def hashString(s: str) -> int:
    """Calculate the hash for a string using the BMT hashing algorithm."""
    if s in BMT_STRING_HASHES:
        return BMT_STRING_HASHES[s]
    
    # Simple hash for unknown strings
    hashVal = 0
    for char in s:
        hashVal = ((hashVal << 5) + hashVal) + ord(char)
        hashVal = hashVal & 0xFFFFFFFF  # Keep it 32-bit
    return hashVal


class BmtBuilder:
    """Builds a BMT binary file from XML material data"""
    
    def __init__(self):
        self.elements: List[Dict] = []
        self.attributes: List[Dict] = []
        self.numbers: List[float] = []
        self.booleans: List[bool] = []
        self.strings: bytearray = bytearray()
        self.stringOffsets: Dict[str, int] = {}
        
    def addString(self, s: str) -> int:
        """Add a string to the string pool and return its offset"""
        if s in self.stringOffsets:
            return self.stringOffsets[s]
        
        offset = len(self.strings)
        self.stringOffsets[s] = offset
        self.strings.extend(s.encode('utf-8'))
        self.strings.append(0)  # Null terminator
        return offset
    
    def addNumber(self, value: float) -> int:
        """Add a float to the numbers array and return its index"""
        index = len(self.numbers)
        self.numbers.append(value)
        return index
    
    def addBoolean(self, value: bool) -> int:
        """Add a boolean to the boolean array and return its bit index"""
        index = len(self.booleans)
        self.booleans.append(value)
        return index
    
    def processElement(self, xmlElem: ET.Element, parentIdx: int = -1) -> int:
        """Process an XML element and convert it to BMT element/attribute structures."""
        elementIdx = len(self.elements)
        
        # Get the element name hash
        tagName = xmlElem.tag
        nameHash = hashString(tagName)
        
        # Start building the element
        attrStart = len(self.attributes)
        attrCount = 0
        
        # Process XML attributes (these become BMT attributes)
        for attrName, attrValue in xmlElem.attrib.items():
            attrNameHash = hashString(attrName)
            
            # Determine value type and add to appropriate storage
            if attrValue.lower() in ('true', 'false'):
                valueType = TYPE_BOOL
                valueIdx = self.addBoolean(attrValue.lower() == 'true')
                numValues = 1
            else:
                try:
                    # Try to parse as float(s)
                    floatVals = [float(x) for x in attrValue.split()]
                    valueType = TYPE_FLOAT
                    valueIdx = len(self.numbers)
                    for fv in floatVals:
                        self.addNumber(fv)
                    numValues = len(floatVals)
                except ValueError:
                    # It's a string
                    valueType = TYPE_STRING
                    valueIdx = self.addString(attrValue)
                    numValues = 1
            
            # Create attribute
            attribute = {
                'name': attrNameHash,
                'type': valueType,
                'value': valueIdx,
                'num_values': numValues,
                'next_same': -1
            }
            self.attributes.append(attribute)
            attrCount += 1
        
        # All child XML elements become BMT child elements
        childElements = list(xmlElem)
        
        # Create element structure
        childFirst = -1
        childCount = len(childElements)
        
        if childCount > 0:
            childFirst = len(self.elements) + 1  # Next element to be added
        
        element = {
            'name': nameHash,
            'attr_start': attrStart,
            'attr_num': attrCount,
            'child_num': childCount,
            'child_first': childFirst,
            'next_sibling': -1,
            'next_same_tag': -1
        }
        
        self.elements.append(element)
        
        # Process children
        prevChildIdx = -1
        for child in childElements:
            childIdx = self.processElement(child, elementIdx)
            
            # Link siblings
            if prevChildIdx != -1:
                self.elements[prevChildIdx]['next_sibling'] = childIdx
            
            prevChildIdx = childIdx
        
        return elementIdx
    
    def reorderElements(self):
        """Reorder elements so that the root element is last."""
        if not self.elements:
            return
        
        # The root is currently at index 0, move it to the end
        root = self.elements[0]
        children = self.elements[1:]
        self.elements = children + [root]
        
        # Update all indices in elements
        oldToNew = {0: len(self.elements) - 1}
        for i in range(1, len(self.elements)):
            oldToNew[i] = i - 1
        
        # Update element references
        for elem in self.elements:
            if elem['child_first'] != -1:
                elem['child_first'] = oldToNew[elem['child_first']]
            if elem['next_sibling'] != -1:
                elem['next_sibling'] = oldToNew[elem['next_sibling']]
    
    def buildColl(self) -> List[Tuple[int, int, int, int]]:
        """Build the COLL (collection) index."""
        collEntries = []
        nameToElements = {}
        nameToAttributes = {}
        
        # Build indices of element names
        for idx, elem in enumerate(self.elements):
            name = elem['name']
            if name not in nameToElements:
                nameToElements[name] = []
            nameToElements[name].append(idx)
        
        # Build indices of attribute names
        for idx, attr in enumerate(self.attributes):
            name = attr['name']
            if name not in nameToAttributes:
                nameToAttributes[name] = []
            nameToAttributes[name].append(idx)
        
        # Create COLL entries for elements
        for name, indices in sorted(nameToElements.items()):
            collEntries.append((name, indices[0] if indices else 0, len(indices), -1))
        
        # Create COLL entries for attributes  
        for name, indices in sorted(nameToAttributes.items()):
            collEntries.append((name, indices[0] if indices else 0, len(indices), -1))
        
        return collEntries
    
    def buildBmt(self, xmlRoot: ET.Element) -> bytes:
        """Build the complete BMT binary from XML root element"""
        # Process the XML tree
        self.processElement(xmlRoot)
        
        # Reorder elements so root is last (required by BMT format)
        self.reorderElements()
        
        # Build the collection index
        collEntries = self.buildColl()
        
        # Helper function to convert signed to unsigned
        def toUnsigned(val):
            if val < 0:
                return (val + 2**32) & 0xFFFFFFFF
            return val & 0xFFFFFFFF
        
        # HEAD block - contains counts of elements
        headData = struct.pack('<7I',
            len(self.elements),
            len(self.attributes),
            len(collEntries),
            len(self.numbers),
            len(self.strings),
            len(self.booleans),
            0
        )
        
        # ELMT block - element structures
        elmtData = bytearray()
        for elem in self.elements:
            elmtData.extend(struct.pack('<7I',
                toUnsigned(elem['name']),
                toUnsigned(elem['attr_start']),
                toUnsigned(elem['attr_num']),
                toUnsigned(elem['child_num']),
                toUnsigned(elem['child_first']),
                toUnsigned(elem['next_sibling']),
                toUnsigned(elem['next_same_tag'])
            ))
        
        # ATTR block - attribute structures
        attrData = bytearray()
        for attr in self.attributes:
            attrData.extend(struct.pack('<5I',
                toUnsigned(attr['name']),
                toUnsigned(attr['type']),
                toUnsigned(attr['value']),
                toUnsigned(attr['num_values']),
                toUnsigned(attr['next_same'])
            ))
        
        # COLL block - collection index
        collData = bytearray()
        for name, u1, u2, u3 in collEntries:
            collData.extend(struct.pack('<4I',
                toUnsigned(name),
                toUnsigned(u1),
                toUnsigned(u2),
                toUnsigned(u3)
            ))
        
        # NUMB block - float values
        numbData = bytearray()
        for num in self.numbers:
            numbData.extend(struct.pack('<f', num))
        
        # BOOL block - boolean bits packed into bytes
        boolData = bytearray()
        if self.booleans:
            byteCount = (len(self.booleans) + 7) // 8
            boolBytes = [0] * byteCount
            for i, b in enumerate(self.booleans):
                if b:
                    byteIdx = i // 8
                    bitIdx = i % 8
                    boolBytes[byteIdx] |= (1 << bitIdx)
            boolData.extend(boolBytes)
        
        # STRS block - null-terminated strings
        strsData = bytes(self.strings)
        
        # Build block table
        numBlocks = 7
        fileHeaderSize = 16
        blockTableSize = 16 * numBlocks
        currentOffset = fileHeaderSize + blockTableSize
        
        blocksInfo = [
            (HEAD, headData),
            (ELMT, elmtData),
            (ATTR, attrData),
            (COLL, collData),
            (NUMB, numbData),
            (BOOL, boolData),
            (STRS, strsData),
        ]
        
        blockTable = []
        for blockId, data in blocksInfo:
            blockTable.append((blockId, len(data), currentOffset, 0))
            currentOffset += len(data)
        
        fileSize = currentOffset
        
        # Build the file
        output = bytearray()
        
        # File header
        output.extend(struct.pack('<4I',
            BLMY,
            numBlocks,
            fileSize,
            0
        ))
        
        # Block table
        for blockId, length, start, unknown in blockTable:
            output.extend(struct.pack('<4I', blockId, length, start, unknown))
        
        # Block data
        for _, data in blocksInfo:
            output.extend(data)
        
        return bytes(output)


def convertMtxToBmt(mtxPath: Path, bmtPath: Path = None) -> None:
    """Convert an MTX file to BMT format"""
    if bmtPath is None:
        bmtPath = mtxPath.with_suffix('.bmt')
    
    # Parse XML
    tree = ET.parse(mtxPath)
    root = tree.getroot()
    
    # Build BMT
    builder = BmtBuilder()
    bmtData = builder.buildBmt(root)
    
    # Write output
    with open(bmtPath, 'wb') as f:
        f.write(bmtData)
    
    return bmtPath

