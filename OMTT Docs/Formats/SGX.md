The SGX (Scene Graph XML) format is used to define 3D scenes for tracks, including geometry object references, lighting, particle systems, spatial partitioning, and transformation hierarchies. 

SGX files are XML documents with a hierarchical structure describing a complete track scenegraph in human-readable form. They are loaded with priority over track SGB64 files. They are usually loaded in pairs for tracks, with a `trackname.sgx` and `trackname_lights.sgx` pair describing the main scenegraph and lights scenegraph of a track. SGX files are only used in the base game for the showroom and its lights; no stock game track from PC2 or AMS2 has been seen to use an SGX instead of an SGB64. 

SGX files have limitations as compared to SGB64 files. Known limitations are listed below:

- Lack of support for referencing VHF instance hierarchies
- Lack of support for referencing IMB instance meshes

### SCENE Element

```xml
<SCENE FileVersion="[major.minor.patch.build]" ExporterVersion="[tool_name]" NumObjects="[count]" NumPartitions="[count]" Merged="[0|1]">
    <!-- OBJ_ID, PARTITION_ID, etc. placed here -->
</SCENE>
```

Required attributes:
- `FileVersion`: Version string in dotted format
- `ExporterVersion`: Name of the tool that created the file
- `NumObjects`: Object count NOTE: Lights files match the `OBJ_ID` count; stock main-track scenegraph files are seen to list `0` here regardless of the number of referenced meshes
- `NumPartitions`: Number of spatial partitions

Optional attributes:
- `Merged`: Present on lights files as `1`; omitted on geometry files

### OBJ_ID Elements

All scene objects are contained within `OBJ_ID` elements:

```xml
<OBJ_ID no="[unique_id]">
    <!-- Object-specific content -->
</OBJ_ID>
```

Attributes:
- `no`: Unique object identifier (integer, 1-based)

#### NODE Objects

Defines 3D geometry objects with transformation and rendering properties:

```xml
<OBJ_ID no="1">
    <NODE type="OBJECT|LOD" Name="[object_name]" MatrixNumber="[id]" instances="[count]" userflags="[flags]" matrices="[count]" subobjects="[count]">
        <!-- Resource reference (OBJECT nodes) -->
        <RESOURCE Filename="[path_to_meb_file]" />
        
        <!-- Culling sphere -->
        <SPHERE Centre="[x] [y] [z] [w]" Radius="[radius]" />
        
        <!-- Transformation (present on top-level OBJECT and on LOD; omitted on LOD children) -->
        <MATRIX Offset="[x] [y] [z]" Orientation="[x] [y] [z] [w]" Scale="[scale]" />
        
        <!-- Hierarchical children (LOD nodes), then distances -->
        <NODE type="OBJECT" Name="child_object">
            <!-- Child OBJECT: RESOURCE + SPHERE only -->
        </NODE>
        <CONTROL Distances="[space_separated_distances]" />
    </NODE>
</OBJ_ID>
```

`OBJECT` nodes list attributes `type`, `Name`, `MatrixNumber`, `instances`, and `userflags`.

`LOD` nodes list attributes `type`, `Name`, `MatrixNumber`, `matrices`, and `subobjects`, with `MatrixNumber` being `-1` when the node has its own `MATRIX`, or `0` for a child that uses the parent LOD matrix.

**NODE Types:**
- `OBJECT`: Standard single geometry object
- `LOD`: Level-of-detail container listing two or more child `OBJECT` nodes for the detail levels and using `CONTROL Distances` to list the transition distances between them

```xml
<NODE type="LOD" Name="lod_object">
    <NODE type="OBJECT" Name="high_detail"><!-- High LOD --></NODE>
    <NODE type="OBJECT" Name="medium_detail"><!-- Medium LOD --></NODE>
    <NODE type="OBJECT" Name="low_detail"><!-- Low LOD --></NODE>
    <CONTROL Distances="10.0 50.0 100.0" />
</NODE>
```

Userflags:

Userflags are a decimal-encoded bitmask determining special visual properties about the node. Quotes shown here are the inline comments from SMS (or Reiza) developers.

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

#### LIGHT Objects

Defines lighting sources with various types and properties. Used in the `*_lights.sgx` files.

```xml
<OBJ_ID no="2">
    <LIGHT 
        UID="[unique_id]"
        Name="[light_name]"
        Type="AMBIENT|DIRECTIONAL|POINT|SPOTLIGHT|SPOTLIGHTPROJECTED"
        Position="[x] [y] [z]"
        Direction="[x] [y] [z]"
        Colour="[r] [g] [b]"
        Intensity="[value]"
        Range="[value]"
        InnerAngle="[degrees]"
        OuterAngle="[degrees]"
        HorizontalAngle="[degrees]"
        VerticalAngle="[degrees]"
        CastsShadows="TRUE|FALSE"
        NoSpecular="TRUE|FALSE"
        NoSmoothDistAtten="TRUE|FALSE"
        IncludeInLightMaps="TRUE|FALSE"
        LightIntensityTweakable="TRUE|FALSE"
        LightGroup="[group_id]"
        GroundPlaneDistance="[value]"
        GroundPlaneNormal="[x] [y] [z]"
        GroundPlaneAutoSet="TRUE|FALSE"
        GroundPlaneShow="TRUE|FALSE"
        ProjectedTexture="[texture_path]"
    />
</OBJ_ID>
```

#### PARTICLES Objects (WIP)

Defines particle systems with complex emission and behavior controls.

> This is speculative and may not be accurate. No stock SGX uses this object type.

```xml
<OBJ_ID no="3">
    <PARTICLES>
        <PARTICLESYSTEM FileVersion="[version]">
            <SYSTEM>
                <PERFLEVEL MinLevel="[0-4|alwayson]" />
                <MAXPARTICLES Max="[count]" Min="[count]" MaxSortable="[count]" />
                <MAXPARTICLESPERTICK Value="[count]" />
                <Offscreen Value="TRUE|FALSE" />
                <KillWhenRewind Value="TRUE|FALSE" />
            </SYSTEM>
            
            <PARTICLE ParticleType="Billboard|GenericQuad|AxisFacingQuadStrip|OrientedQuad|PhysicsMesh" />
            
            <EMITTERPARAMS>
            </EMITTERPARAMS>
            
            <AFFECTOR type="[affector_type]">
            </AFFECTOR>
            
            <PARTICLEPARAMS>
            </PARTICLEPARAMS>
            
            <ENVELOPE>
            </ENVELOPE>
            
            <PARAMSCALER>
            </PARAMSCALER>
        </PARTICLESYSTEM>
    </PARTICLES>
</OBJ_ID>
```

Particle types:
- `Billboard`: Camera-facing quads (default)
- `GenericQuad`: Fixed-orientation quads
- `AxisFacingQuadStrip`: Strip aligned to axis
- `OrientedQuad`: Velocity-oriented quads
- `PhysicsMesh`: Physics-simulated meshes

#### OCCLUDER Objects (WIP)

Defines occlusion culling volumes with quad corners.

> This is speculative and may not be accurate. No stock SGX uses this object type.

```xml
<OBJ_ID no="4">
    <OCCLUDER Shape="[shape_type]" Resource="[resource_path]" PositionTL="[x] [y] [z]" PositionTR="[x] [y] [z]" PositionBL="[x] [y] [z]" PositionBR="[x] [y] [z]" />
</OBJ_ID>
```

#### TERRAIN Objects (WIP)

Defines some node type, presumably related to terrain.

> This is speculative and may not be accurate. No stock SGX uses this object type.

```xml
<OBJ_ID no="5">
    <TERRAIN>
        <!-- ??? -->
    </TERRAIN>
</OBJ_ID>
```

### PARTITION_ID Elements

Defines an authored tree of axis-aligned volumes used for culling. Every interior `PARTITION_ID` has exactly four `CHILD_PARTITIONS` (or `NONE` if it is a leaf), suggesting this is a quadtree-like format internally.

```xml
<PARTITION_ID no="[partition_id]">
    <AABBOX min="[x] [y] [z]" max="[x] [y] [z]" />
    <CHILD_PARTITIONS IDs="[space_separated_ids]|NONE" />
    <CHILD_OBJS IDs="[space_separated_object_ids]|NONE" />
</PARTITION_ID>
```

**Structure:**
- `AABBOX`: Axis-aligned bounding box of this partition. Parent boxes contain their children; sibling boxes may overlap.
- `CHILD_PARTITIONS`: Four child partition IDs, or `NONE` for a leaf. The loader matches these IDs against later `PARTITION_ID/@no` values.
- `CHILD_OBJS`: Space-separated list of object IDs contained in this partition, or `NONE`. Each object ID appears in exactly one partition. A parent may list both child partitions and its own objects.
