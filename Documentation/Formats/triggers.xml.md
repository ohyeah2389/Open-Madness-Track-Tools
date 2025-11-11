The `tracks/trackname/physics/triggers.xml` file defines the timing gates and similar checkpoints/triggers for the track.

## Trigger Types

### CRC32 Mapping

The game uses CRC32 hashes (polynomial `0x4c11db7`) to identify trigger types via the "Material CRC" field:

```
TRG_START
TRG_CHECKPOINT1
TRG_CHECKPOINT2
TRG_FINISH
TRG_STOP
TRG_PITIN
TRG_PITOUT
TRG_DRSDET1
TRG_DRSDET2
TRG_DRSDET3
TRG_DRSZONE1START
TRG_DRSZONE2START
TRG_DRSZONE3START
TRG_DRSZONE1END
TRG_DRSZONE2END
TRG_DRSZONE3END
```

### Validation Requirements

The `ProcessTrackTriggers` function uses a validation bitmask that must equal `0x3fff` (14 bits set) for successful processing. Each required field sets a specific bit:

- Bit 0 (0x1): Name field
- Bit 1 (0x2): Format field  
- Bit 2 (0x4): Type field
- Bit 3 (0x8): Width field
- Bit 4 (0x10): Height field
- Bit 5 (0x20): Length field
- Bit 6 (0x40): Mass field
- Bit 7 (0x80): Material CRC field
- Bit 8 (0x100): Relative Position field
- Bit 9 (0x200): Relative Orientation field
- Bit 10 (0x400): Mesh Data Size field
- Bit 11 (0x800): Vertex Count field
- Bit 12 (0x1000): Vertices field
- Bit 13 (0x2000): Mesh Data field

## ShapeDesc Field Requirements

### Required Fields - Constant Values

These fields must always have the specified values:

```xml
<prop name="Format" data="0" />
<prop name="Type" data="0" />
<prop name="Mass" data="0" />
<prop name="Mesh Data Size" data="0" />
<prop name="Vertex Count" data="0" />
<prop name="Trigger" data="false" />
```

### Required Fields - Variable Values

#### Name Field

The Name field contains 8-character hexadecimal strings (in lowercase) that are unique for each trigger. 
They don't seem to serve any purpose in the code (as of current understanding) other than they must be unique per trigger.
Examples: `"b6695790"`, `"b6695e60"`, `"b6696530"`

#### Material CRC

As described in the previous section, the Material CRC is a CRC32 hash corresponding to a trigger type string.

#### Dimensional Properties
- **Width**: Trigger box width in meters
- **Height**: Trigger box height in meters
- **Length**: Trigger box depth in meters

#### Spatial Properties
- **Relative Position**: `"x;y;z"` coordinates in 3D space
  - Format: Three semicolon-separated float values
  - Example: `"-232.191;2.84887;-505.046"`
  
- **Relative Orientation**: 3x3 rotation matrix
  - Format: Nine semicolon-separated float values (row-major order)
  - Identity matrix: `"1;0;0;0;1;0;0;0;1"`
  - Example: `"0.0921467;0;0.995745;0;-1;0;0.995745;0;-0.0921565"`

#### Required Empty Collections
```xml
<prop name="Vertices" elements="0">
    <funcpropdata />
</prop>
<prop name="Mesh Data" elements="0">
    <funcpropdata />
</prop>
```

## Creating New Triggers

### Template

```xml
<data class="ShapeDesc" id="0xF3284DD0">
    <prop name="Name" data="c0000001" />
    <prop name="Format" data="0" />
    <prop name="Type" data="0" />
    <prop name="Width" data="1.0" />
    <prop name="Height" data="120" />
    <prop name="Length" data="25" />
    <prop name="Mass" data="0" />
    <prop name="Material CRC" data="747266536" />
    <prop name="Relative Position" data="0.0;0.0;0.0" />
    <prop name="Relative Orientation" data="1;0;0;0;1;0;0;0;1" />
    <prop name="Mesh Data Size" data="0" />
    <prop name="Vertex Count" data="0" />
    <prop name="Trigger" data="false" />
    <prop name="Vertices" elements="0">
        <funcpropdata />
    </prop>
    <prop name="Mesh Data" elements="0">
        <funcpropdata />
    </prop>
</data>
```

## XML Structure

### Container Structure

```xml
<data class="TriggerObjectManager" id="0x65994AB0">
    <prop name="Name" data="" />
    <prop name="Shapes" elements="N">
        <funcpropdata>
            <!-- ShapeDesc elements go here -->
        </funcpropdata>
    </prop>
</data>
```