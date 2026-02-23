The SGX (Scene Graph XML) format is used to define 3D scenes for tracks, including geometry object references, lighting, particle systems, spatial partitioning, and transformation hierarchies. SGX files are typically found in `tracks/trackname/` directories.

## Format Overview

SGX files are XML documents with a hierarchical structure describing a complete track scenegraph in human-readable form. They are loaded with priority over track SGB64 files. They are usually loaded in pairs for tracks, with a `trackname.sgx` and `trackname_lights.sgx` pair describing the main scenegraph and lights scenegraph of a track. SGX files are only used in the base game for the showroom and its lights; no stock game track from PC2 or AMS2 has been seen to use an SGX instead of an SGB64. 

SGX files have limitations as compared to SGB64 files.
Known limitations are listed below:

- Lack of support for referencing VHF instance hierarchies
- Lack of support for referencing IMB instance meshes

### Header

```xml
<SCENE FileVersion="0.1.0.0" ExporterVersion="Tool Name" NumObjects="50" NumPartitions="25" Merged="0">
```

## Root Element

### SCENE Element

```xml
<SCENE FileVersion="[major.minor.patch.build]" 
       ExporterVersion="[tool_name]" 
       NumObjects="[count]" 
       NumPartitions="[count]" 
       Merged="[0|1]">
    <!-- Scene content -->
</SCENE>
```

**Required Attributes:**
- `FileVersion`: Version string in dotted format
- `ExporterVersion`: Name of the tool that created the file
- `NumObjects`: Total number of objects in the scene
- `NumPartitions`: Number of spatial partitions
- `Merged`: Boolean indicating if scene data is merged (0 or 1)

## Object Types

### OBJ_ID Elements

All scene objects are contained within `OBJ_ID` elements with universal attributes:

```xml
<OBJ_ID no="[unique_id]" Visible="[0|1]" Animated="[0|1]" LodLevel="[integer]" VariationIndex="[integer]" Instances="[count]">
    <!-- Object-specific content -->
</OBJ_ID>
```

**Universal Attributes:**
- `no`: Unique object identifier (integer)
- `Visible`: Object visibility (0=hidden, 1=visible)
- `Animated`: Animation flag (0=static, 1=animated)
- `LodLevel`: Level of detail index
- `VariationIndex`: Material variation index
- `Instances`: Number of instances to render (default: 1)

### NODE Objects

Defines 3D geometry objects with transformation and rendering properties:

```xml
<OBJ_ID no="1">
    <NODE type="OBJECT|LOD|TRANSFORM" Name="[object_name]" MatrixNumber="[id]" instances="[count]" userflags="[flags]" matrices="[count]" subobjects="[count]">
        
        <!-- Resource Reference -->
        <RESOURCE Filename="[path_to_meb_file]" />
        <VariationPaletteFile>[path_to_palette]</VariationPaletteFile>
        
        <!-- Bounding Volumes -->
        <SPHERE Centre="[x] [y] [z] [w]" Radius="[radius]" />
        <AABBOX min="[x] [y] [z]" max="[x] [y] [z]" />
        
        <!-- Transformation (Method 1) -->
        <TRANSFORM>
            <Position>[x] [y] [z]</Position>
            <Orientation>[x] [y] [z] [w]</Orientation>
            <Scale>[scale_factor]</Scale>
        </TRANSFORM>
        
        <!-- Transformation (Method 2) -->
        <MATRIX Offset="[x] [y] [z]" Orientation="[x] [y] [z] [w]" Scale="[scale]" />
        
        <!-- LOD Configuration -->
        <CONTROL Distances="[space_separated_distances]" />
        
        <!-- Hierarchical Children -->
        <NODE type="OBJECT" Name="child_object">
            <!-- Recursive NODE structure -->
        </NODE>
    </NODE>
</OBJ_ID>
```

**NODE Types:**
- `OBJECT`: Standard geometry object
- `LOD`: Level-of-detail container with multiple children
- `TRANSFORM`: Transform-only node (no geometry)

#### `userflags`

Decimal-encoded bitmask determining special visual properties about the node.
Quotes are the inline comments from SMS (or Reiza) developers.

0. `FarDistantMesh` "This mesh draws beyond the usual automatic LOD cutoff limits"
1. `GarageNodePlaceHolder` "Object if a node for where cars are to be positioned"
2. `CannotCull` "This object cannot be culled using radius over distance"
3. `UnderPass` "road underpass mesh (removed for reflections)"
4. `CastsShadows` "Casts shadows"
5. `ReceivesShadows` "Receives shadows cast" NOTE: This appears to refer to self-shadowing; disabling this flag does not prevent shadows being cast onto this object from other objects
6. `RenderInDynamicEnvmap` "Render this object in dynamic envmaps"
7. `Damageable` "Can this object receive mesh damage (using MeshDamageManager)"
8. `Distortion` "Render this object as part of Distortion only - note this flag is set by code, not by art"
9. `HighDetail` "Exclude when using Medium and Low Detail settings"
10. `DummyForShadowCasting` "Render this object ONLY when casting shadows"
11. `AnimatedAds` "Meshes flagged with this flag will get registered with AnimatedAds system"
12. `BillboardMesh` "Meshes flagged with this flag contain billboarded polygons"
13. `NeedsHeightOcclusionTests` "Meshes flagged with this flag will do full blown occlusion tests always"
14. `ForceRenderShadows` "Force shadows of this object to render"
15. `MeshHasFlares` "meshes with flares.."
16. `MeshHasVideo` "meshes with videos"
17. `SwappableDecoration` "meshes Swappable Decoration"
18. `PhysicsMesh` "meshes with physics"
19. `GrassyTerrain` "Grassy Terrain"
20. `RenderInReflection` "meshes to render in reflections"
21. `GodRayOcculder` "meshes used to block the god rays"
22. `LowerEmapCull` "Future expansion"
23. `HideInSpring` "Object should not render in spring - use in combination with others to allow easy flag based seasonal controls"
24. `HideInSummer` "Object should not render in summer"
25. `HideInAutumn` "Object should not render in autumn"
26. `HideInWinter` "Object should not render in winter"
27. `HideInSnow` "Object should not render in snow - different to winter in some cases e.g. bare tree vs snow covered tree"
28. `MediumDetail` "Exclude when using Low Detail settings"
29. `GrassBladeRenderable` "Grass BladeMesh"
30. `Trees` "After this we are into the flags which are code generated only"
31. `DontRenderInStaticEnvmap` "Force not to render in static envmap"


### LIGHT Objects

Defines lighting sources with various types and properties:

```xml
<OBJ_ID no="2">
    <LIGHT UID="[unique_id]" Name="[light_name]" 
           Type="AMBIENT|DIRECTIONAL|POINT|SPOTLIGHT|SPOTLIGHTPROJECTED"
           Position="[x] [y] [z]" Direction="[x] [y] [z]" 
           Colour="[r] [g] [b]" Intensity="[value]" Range="[value]"
           InnerAngle="[degrees]" OuterAngle="[degrees]"
           HorizontalAngle="[degrees]" VerticalAngle="[degrees]"
           CastsShadows="TRUE|FALSE" NoSpecular="TRUE|FALSE" 
           NoSmoothDistanceAttenuation="TRUE|FALSE"
           IncludeInLightMaps="TRUE|FALSE" LightIntensityTweakable="TRUE|FALSE"
           LightGroup="[group_id]" GroundPlaneDistance="[value]" 
           GroundPlaneNormal="[x] [y] [z]" GroundPlaneAutoSet="TRUE|FALSE" 
           GroundPlaneShow="TRUE|FALSE" ProjectedTexture="[texture_path]" />
</OBJ_ID>
```

### PARTICLES Objects (WIP)

Defines particle systems with complex emission and behavior controls:

```xml
<OBJ_ID no="3">
    <PARTICLES>
        <PARTICLESYSTEM FileVersion="[version]">
            <!-- Performance Settings -->
            <SYSTEM>
                <PERFLEVEL MinLevel="[0-4|alwayson]" />
                <MAXPARTICLES Max="[count]" Min="[count]" MaxSortable="[count]" />
                <MAXPARTICLESPERTICK Value="[count]" />
                <Offscreen Value="TRUE|FALSE" />
                <KillWhenRewind Value="TRUE|FALSE" />
            </SYSTEM>
            
            <!-- Rendering Configuration -->
            <PARTICLE ParticleType="Billboard|GenericQuad|AxisFacingQuadStrip|OrientedQuad|PhysicsMesh" />
            
            <!-- Emission Parameters -->
            <EMITTERPARAMS>
                <!-- Complex emission configuration -->
            </EMITTERPARAMS>
            
            <!-- Forces and Behaviors -->
            <AFFECTOR type="[affector_type]">
                <!-- Multiple affectors supported -->
            </AFFECTOR>
            
            <!-- Particle Properties -->
            <PARTICLEPARAMS>
                <!-- Type-specific properties -->
            </PARTICLEPARAMS>
            
            <!-- Animation Curves -->
            <ENVELOPE>
                <!-- Parameter animation over time -->
            </ENVELOPE>
            
            <!-- Dynamic Scaling -->
            <PARAMSCALER>
                <!-- Runtime parameter scaling -->
            </PARAMSCALER>
        </PARTICLESYSTEM>
    </PARTICLES>
</OBJ_ID>
```

**Particle Types:**
- `Billboard`: Camera-facing quads (default)
- `GenericQuad`: Fixed-orientation quads
- `AxisFacingQuadStrip`: Strip aligned to axis
- `OrientedQuad`: Velocity-oriented quads
- `PhysicsMesh`: Physics-simulated meshes

### OCCLUDER Objects

Defines occlusion culling volumes with quad corners:

```xml
<OBJ_ID no="4">
    <OCCLUDER Shape="[shape_type]" Resource="[resource_path]"
              PositionTL="[x] [y] [z]" PositionTR="[x] [y] [z]"
              PositionBL="[x] [y] [z]" PositionBR="[x] [y] [z]" />
</OBJ_ID>
```

### TERRAIN Objects (WIP)

Defines terrain geometry with specialized handling:

```xml
<OBJ_ID no="5">
    <TERRAIN>
        <!-- Terrain-specific configuration -->
        <!-- Processed by specialized terrain system -->
    </TERRAIN>
</OBJ_ID>
```

## Spatial Partitioning

### PARTITION_ID Elements

Defines spatial partitions for performance optimization using octree-like structures:

```xml
<PARTITION_ID no="[partition_id]">
    <AABBOX min="[x] [y] [z]" max="[x] [y] [z]" />
    <CHILD_PARTITIONS IDs="[space_separated_ids]|NONE" />
    <CHILD_OBJS IDs="[space_separated_object_ids]" />
</PARTITION_ID>
```

**Structure:**
- `AABBOX`: Axis-aligned bounding box defining partition volume
- `CHILD_PARTITIONS`: Space-separated list of child partition IDs or "NONE"
- `CHILD_OBJS`: Space-separated list of object IDs contained in this partition

## Data Format Specifications

### Vector3 Format

Used for positions, directions, colors, etc.:
```
Format: "x y z"
Example: "-232.191 2.84887 -505.046"
```

### Quaternion Format

Used for rotations/orientations:
```
Format: "x y z w"
Example: "0.0 0.0 0.0 1.0"
Note: Order is (x,y,z,w) where w is the scalar component
```

### Matrix Format

4x4 transformation matrices constructed from:
1. Scale transformation
2. Rotation (from quaternion)
3. Translation (from position)

Applied in order: **Scale → Rotation → Translation**

### Child ID Lists

Space-separated integer lists:
```
Format: "id1 id2 id3 ..."
Example: "1 2 3 4 5 6"
Special: "NONE" for empty lists
```

## Advanced Features

### Hierarchical Objects

- NODE elements support unlimited nesting depth
- Child objects inherit parent transformations
- Supports complex hierarchical assemblies

### Level of Detail (LOD)

```xml
<NODE type="LOD" Name="lod_object">
    <CONTROL Distances="10.0 50.0 100.0" />
    <NODE type="OBJECT" Name="high_detail"><!-- High LOD --></NODE>
    <NODE type="OBJECT" Name="medium_detail"><!-- Medium LOD --></NODE>
    <NODE type="OBJECT" Name="low_detail"><!-- Low LOD --></NODE>
</NODE>
```

- `type="LOD"` creates LOD container
- `CONTROL Distances` specifies transition distances
- Child objects represent different detail levels

### Object Instancing

- `instances` attribute creates multiple copies
- `MatrixNumber` references transformation matrices
- Efficient rendering of repeated geometry

### Material Variations

- `VariationIndex` selects material variant
- `VariationPaletteFile` defines available variations
- Runtime material swapping support

## Parser Validation

The SGX parser performs comprehensive validation:

1. **Version Checking**: FileVersion attribute parsing and compatibility
2. **XML Structure**: Proper element hierarchy and nesting
3. **Data Types**: Automatic string-to-numeric conversion
4. **Bounding Volumes**: Sphere and AABB validation
5. **Reference Integrity**: Resource file and ID reference checking

## Examples

### Basic Geometry Object

```xml
<OBJ_ID no="1" Visible="1" Animated="0" LodLevel="0" VariationIndex="0" Instances="1">
    <NODE type="OBJECT" Name="track_object" MatrixNumber="1" instances="1" userflags="0">
        <RESOURCE Filename="objects/barrier.meb" />
        <SPHERE Centre="0.0 0.0 0.0 1.0" Radius="5.0" />
        <TRANSFORM>
            <Position>100.0 0.0 50.0</Position>
            <Orientation>0.0 0.0 0.0 1.0</Orientation>
            <Scale>1.0</Scale>
        </TRANSFORM>
    </NODE>
</OBJ_ID>
```

### Directional Light

```xml
<OBJ_ID no="2">
    <LIGHT UID="sun_light" Name="main_sun" Type="DIRECTIONAL"
           Position="0.0 1000.0 0.0" Direction="0.2 -0.8 0.3" 
           Colour="1.0 0.95 0.8" Intensity="2.0" 
           CastsShadows="TRUE" LightGroup="0" />
</OBJ_ID>
```

### Spatial Partition

```xml
<PARTITION_ID no="1">
    <AABBOX min="-500.0 -10.0 -500.0" max="500.0 50.0 500.0" />
    <CHILD_PARTITIONS IDs="2 3 4 5" />
    <CHILD_OBJS IDs="1 6 7 8 15 22" />
</PARTITION_ID>
```
