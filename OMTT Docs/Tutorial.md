This tutorial, like the entire project, is a work-in-progress and is, by definition and necessity, not complete. Please keep that in mind while following it. If you have any notes or questions, please post them to the Issues tracker of this repository.

Before following this tutorial, you should install the TrackCompiler Blender extension provided in the releases of this repository. It is installable in the same way as any other Blender extension, through Preferences > Extensions > Install from Disk.
# Step 0: Shotgun Introduction to the Madness Engine
The Madness Engine's game data is not designed to be modified by the end-user. That doesn't mean it isn't modifiable under the right configuration. 

It does, however, mean that it is extremely intolerant to error and misconfiguration, and it provides no feedback on what you did wrong.

Be careful, follow the instructions, and be warned that the instructions may be incomplete or unclear.
## Comparison to Assetto Corsa
* Physics/visuals separation
	- Assetto Corsa uses a single set of `KN5` files to define both the graphics and visuals of each track (and track layout). These are authored from source `FBX` files using the proprietary ksEditor software distributed with each copy of the game. Separation between the physical and visual data is not required and needs to be deliberately defined. Each KN5 can be of arbitrary size, with a limit of 65535 triangles per mesh object within each KN5. Arbitrary KN5 files can be defined and arranged using the `models.ini` track layout system, but this system is entirely optional and not always used.
	- The Madness Engine uses a scenegraph and a collection of loose mesh, material definition, and texture files to define the visuals of each track, plus a separate PhysX cooked triangle mesh container to define the physical shape and the surface material index.
- Data spread
	- Assetto Corsa's tracks are entirely contained under their folder at `/content/tracks/TrackName`, with no files required to live outside of that folder, and no listing required. This makes distribution of custom tracks very easy.
	- Data for each track in the Madness Engine is spread out between at least six locations:
		- `/tracks/TrackName`
		- `/tracks/_data`
		- `/tracks/textures`
		- `/cameras`
		- `/gui`
		- `/pakfiles/tracks`
	- Madness Engine track paths are required to be listed under the file `tracks/_data/tracklist.lst` with the format `Tracks\TrackName\@TrackName.trd`.
# Step 1: Format Familiarity
Several different file formats are used for track data in the Madness Engine. The game may load tracks without some of the "Required files" present, but key features may not work.
## Required files:
- `/tracks/TrackName/TrackName.trd`
	- Defines lots of textual and numeric data about the track (UI info, location, AI tuning, and much more)
	- It's human-readable and self-explanatory, openable in a text editor
- `/tracks/TrackName/TrackName.sgx` (or `sgb64`)
	- Defines the scenegraph of the track (position/rotation/scale of all mesh objects in the scene), as well as LOD info, culling, and occlusion data
	- SGXs are a specialized XML-like format; human readable, but very difficult to manually construct
	- SGB64s are a packed, optimized, binary format that is nowhere near human readable (and will not be operationally documented)
- `/tracks/TrackName/TrackName_lights.sgx` (or `sgb64`)
	- Defines the location and attributes of lights in the scene
	- SGXs use a similar format to the main SGX, but with special light-specific nodes only
	- SGB64s are similar to the main SGB64 (not operationally documented)
- `/tracks/TrackName/meshname.meb`
	- Contains a visual mesh object referenceable by the scenegraph
	- Proprietary engine format, optimized packed binary
	- Contains one or more material file references
- `tracks/TrackName/materialname.mtx` (or `bmt`)
	- Material definition file, references a shader and lists parameters and defines
	- MTXs are human-readable XML
	- BMTs are packed binary ("Blimey Markup Language")
- `/tracks/TrackName/physics/TrackName.csm`
	- Contains a series of PhysX cooked triangle meshes with accompanying material indices
- `/tracks/TrackName/track_cut/TrackName.gcl`
	- Contains two datasets:
		- Track geometry, simplified, defining the edges of the track in triangle mesh format, with a numeric identifier on each triangle defining if it is part of the main track, pit entry, pit lane, or pit exit
		- Three-level dectree grid cells referencing each triangle
- `/tracks/TrackName/physics/triggers.xml`
	- Lists all the timing and other trigger zones for the track (start-finish, pit-in, pit-out, DRS, etc.)
- `/tracks/_data/aiw/TrackName.aiw`
	- Defines the AI paths and other AI data for the track
	- Human-readable, but difficult to edit or create by hand
- `/gui/tracklogos/TrackName.dds`
	- Logo of the track, appears (tilted to the left) next to the track name in Project CARS 2's track selection screen
- `/gui/trackphotos/TrackName.dds`
	- Image of the track (screenshot, render, real photo, etc.)
	- Used as loading screen background and preview in Automobilista 2
- `/gui/trackmaps3d/TrackName.dds`
	- Track layout image, overlaid on the track photo in Automobilista 2's track selection screen
	- 2D white-red top-down layout for AMS2, 3D render with red-yellow-blue sectors and grey buildings in PC2
- `/tracks/TrackName/trackproperties.bin`
	- Unknown format and unknown content; hopefully it doesn't contain anything important
- `/tracks/TrackName/TrackName.enx`
	- Usually empty, used to be used for background objects (skydomes, etc.) in Shift2/PC1
- `/tracks/TrackName/physics/object_properties.xml`
	- Usually empty, likely a leftover from earlier physics data definition standards in the engine
## Optional files:
- `/tracks/_data/livetrack/TrackName.mrdf`
	- MRDF ("machine-readable data format", packed optimized binary) containing the "Weathering-In" data for the LiveTrack system
	- Optimized grid format containing 4 fields (three floats and an 8-bit flagset)
- `/cameras/TrackName.xml`
	- Defines the camera sets used on the track
	- Human-readable XML-like format, but very difficult to edit or create from scratch
- `/pakfiles/tracks/livegrass/TrackName.bff`
	- Can likely be empty like the previous placeholder BFFs
- `/tracks/_data/dynamicterrain/TrackName.mrdf`
	- MRDF of unknown layout or format
- `/tracks/_data/grassexclusion/TrackName.xcl`
	- Unknown format
- `/tracks/_data/pitgarages/TrackName.mrdf`
	- MRDF of unknown layout or format
- `/tracks/_data/tracklights/TrackName.xml`
	- Human-readable XML containing definitions for starting lights, pit entry/exit stoplights, and their trigger events
- `/tracks/_data/audio/TrackName.lsd`
	- Human-readable XML defining the locations and attributes of ambient sound emitters placed around each track
- `/tracks/_data/crowds/TrackName.lod`
	- Human-readable XML defining LOD distance overrides for various string-matched objects, usually character models
- `/tracks/TrackName/physics/dynamic_collisions.xml`
	- `PhysXCollection` XML-like file containing the mesh data for every dynamic physics object (cone, corner marker) used on the track, referenced to by the next file
- `/tracks/_data/dynamic/physics/TrackName.env.xml`
	- XML file containing listings of every dynamic physics object instance used on the track, referencing the previous file
# Step 2: Project File Setup
The toolkit is designed to operate with a certain template folder structure in mind that you set up when creating each track. The Example Project provided contains that folder structure.

The following files should be located at the project root:
- `Automobilista 2`: a template "unpacked" folder structure that the game will internally load, and that TrackPacker will process into the correct assembly of BFF pakfiles and unpacked files.
- `texture` or `textures`: a folder containing all the textures for this specific track. This is not strictly required, the Blender addon will pull files on export time from anywhere you link to on disk and assemble them to the correct location in the `Automobilista 2` template folder, so this isn't like Assetto Corsa where every texture file must be in the `texture` folder next to the FBX with no folder organization.
- `BakePhysics.bat`: a batch script that runs PhysicsMeshCooker.exe with the exported OBJ physics mesh to create the cooked CSM file. This isn't strictly required as PhysicsMeshCooker.exe can be run manually too. If used, make sure its paths are correctly referencing the relative or absolute location of PhysicsMeshCooker.exe, otherwise you will get a "The system cannot find the path specified" error on run.
- `trackname_project_file.blend`: the Blender project file for your track.
- `trackname.zip`: emitted by TrackPacker.exe upon finishing packing of the template folder structure.
- `trackname_physics.obj`: the physics collision mesh for your track. The name can be different if desired, and if `BakePhysics.bat` is to be used, make sure to update it to point to this file.
# Step 3: Build the Track Model
Instructions on general track modeling are outside the scope of this tutorial, but below are some guidelines for modeling for the Madness engine from what I've seen so far.
- Track physical surface models from Reiza and SMS seem to be lower spatial resolution than those commonly used in other simulators. This may be a limitation of the Madness engine or it may not be; if you run into any performance limitations with high-density physical surface models, please let the community and I know.
- The Madness engine, just like Assetto Corsa, runs on DirectX 11. The Madness engine does support instancing unlike Assetto Corsa, but again, SGX files do not have support for referencing instance meshes. Therefore, try to keep the object count low. The lower the object count, the quicker the track will load, and the better it will perform, to a limit. 
- The Madness engine uses spherical culling. Keep that in mind when combining objects; don't combine large objects that should be culled separately, like buildings.
- The Madness engine supports LOD models, but support for LOD systems isn't yet implemented in the Blender toolkit. All objects render at a max distance of 10,000m, or ~400m if userflag "Far Distant Mesh" is disabled.
- Keep your objects organized with Blender's collection system. The SGX exporter maps the visible (non-excluded) collections tree onto the SGX partition system. Each collection that contains exported objects becomes a `PARTITION_ID`, and nested collections become child partitions. Objects belong to their deepest visible collection, which means grouped `KSTREE_GROUP_*` / `SMS_GRP_*` meshes go into the lowest common ancestor of their members. The engine's partition tree is a quadtree (exactly four children per interior node), so the exporter automatically pads/groups collection children to match that requirement.
	- Uncheck a collection in the Outliner to skip it and its descendants on export. This is useful for isolation when troubleshooting track load crashes/hangs.
- The Blender scene exporter supports export-time object combining. If you have a significant number of objects that need to be combined, name them using the prefix `KSTREE_GROUP_groupname_`, where `groupname` can be any string without underscores or spaces. This is designed to handle Assetto Corsa's ksEditor Y-tree grouping system. Note, though, that it does NOT apply the vertex normal adjustments that ksEditor does.
	- Additionally, the naming pattern `SMS_GRP_groupname_objectname.123` can be used for the same functionality, where all objects with the `SMS_GRP_groupname_` prefix will be combined into an object named `groupname`. Ensure `groupname` is unique and will not overlap with any non-grouped object names.
- The Madness Engine, similar to Assetto Corsa, has a limit of 65535 vertices per mesh.
- The Madness Engine has been seen to support the following texture formats so far:
	- DDS DXT1/3/5 Linear
	- DDS BC7 Linear
	- DDS BC5U
	- DDS A8R8G8B8 Uncompressed
- The Madness Engine has been seen to NOT support the following texture formats so far:
	- DDS R8G8B8 Uncompressed
# Step 4: Author the Materials
In the process of building the track model, you should have given each object a material. What that material looks like in Blender doesn't translate over to the game; the game uses its own method of defining materials to be used on each mesh object. Therefore, the Blender plugin provides an interface for setting up each material to work when exported to the Madness Engine. 
Under the Material Properties page of the Properties panel, you will see a new pane named "Madness MTX Settings". Expanding the pane will show a configuration GUI with four sections:
- Basic Settings
	- Allows selection of the shader and shader technique to use, along with other general options available on all shaders.
- Shader Parameters
	- Allows selection and configuration of each input parameter to the selected shader technique.
- Shader Defines
	- Allows selection of which defines to include for this shader.
- MTX Operations
	- Allows saving and loading of loose MTX files to and from the current Blender material.

This UI has been designed to closely mirror the MTX file format and therefore isn't the most visual or intuitive. Designing and configuring shaders may require trial and error until you gain experience with which shader does what and what options are available for each shader. The demo project contains preconfigured shaders for its used materials. If you misconfigure a shader, objects using it will fail to render in game.

Certain shader defines and shader parameters require each other. The actual list of requirements has not been discovered; likely relationships have been noted and baked into the shader database distributed with the toolkit. The material UI will warn about mismatches in enabled shader parameters and defines as compared to the database to help you select an appropriate configuration of parameters and defines. However, the database is likely imperfect, and so the warnings do not block you from setting up any given configuration, even if it is thought to be invalid by the database, as it may still be valid. Again, trial and error will be needed to take full advantage of the material system due to the lack of documentation.
# Step 5: Export the Track Model
As was covered in step 1, there are many files we must create using the toolkit. The following substeps will cover how to create each of the required files, in suggested order, using the tools in the toolkit.
## Step 5.1: Cook the Physics Mesh
In your Blender project (which should be organized into collections), deactivate all collections containing objects that should not contribute to the collision surfaces of the track. Leave only the meshes such as the high-resolution road meshes, grass meshes, and invisible wall meshes. 

The CSM we'll be preparing stores each mesh's material index beside it in the binary content. Creation of the CSM will be through the provided tool `PhysicsMeshCooker.exe`. It takes two arguments as input: a path to an input OBJ file and a path to an output CSM file.

`PhysicsMeshCooker.exe` expects an OBJ mesh with each mesh having a prefixed name corresponding to the material index of that element. While the final material index is numeric, the tool checks for a certain name string from the game's master physics material list. Similar to how Assetto Corsa needs each mesh to be prefixed with `1ROAD_` or `1GRASS_` to index to both the master and custom `surfaces.ini` files, this checks for meshes to be prefixed with names such as `ROADS_` or `GRASS_` to reference to that master material list, embedded as a look-up table.

This is that look-up table, a list of all available material names and their indices. All names on the same line are aliases to the same material index.
```
{"PAINTCRETE_ILLEGAL", 49}, {"PCRETE_ILLEGAL", 49}, {"RDGREEN", 49},
{"PAINTCRETE_LEGAL", 48}, {"PCRETE_LEGAL", 48},
{"BUMPYDIRT_ROAD", 20}, {"BDIRT_ROAD", 20},
{"ILLEGAL_STRIP", 47}, {"ILLEGALSTRIP", 47},
{"TRAIN_TRACKS", 36}, {"TRAINROAD", 36},
{"BUMPYCOBBLES", 37}, {"RAMP_METAL", 37},
{"BUMPYROADS1", 2}, {"B1ROAD", 2},
{"BUMPYROADS2", 3}, {"B2ROAD", 3}, {"CONC", 3},
{"BUMPYROADS3", 4}, {"B3ROAD", 4},
{"BUMPYGRAVEL", 9}, {"BGRV", 9},
{"BUMPYSAND", 16}, {"BSAND", 16},
{"BUMPYDIRT", 18}, {"BDIRT", 18},
{"GRASSYBERMS", 6}, {"GBRM", 6},
{"LOWGRIPROADS", 1}, {"LGROAD", 1},
{"RUMBLESTRIPS", 10}, {"BRICK", 10}, {"RMBL", 10},
{"CEMENTWALLS", 13}, {"CEMA", 13}, {"CWAL", 13}, {"CMWL", 13},
{"TIREWALLS", 12}, {"TWALL", 12},
{"GUARDRAILS", 14}, {"GRDR", 14},
{"DIRT_ROAD", 19},
{"DIRT BANK", 22}, {"DBANK", 22},
{"DRY VERGE", 24}, {"DVERGE", 24},
{"EXITRUMBLES", 25}, {"ERUMBLE", 25}, {"RMBBL", 25},
{"GRASSCRETE", 26}, {"GCRETE", 26},
{"LONGGRASS", 27}, {"LNGGRS", 27},
{"SLOPEGRASS", 28}, {"SLPGRS", 28},
{"SAND_ROAD", 30}, {"SNDROAD", 30},
{"BAKED_CLAY", 31}, {"BAKEDCLAY", 31},
{"ASTROTURF", 32}, {"ASTRO", 32},
{"DAMAGEDROAD1", 35}, {"DAMROAD1", 35},
{"B1RUMBLES", 40}, {"B1RUMBLE", 40},
{"B2RUMBLES", 41}, {"B2RUMBLE", 41},
{"ROUGHSAND1", 42}, {"RSAND1", 42},
{"ROUGHSAND2", 43}, {"RSAND2", 43},
{"SNOWWALLS", 44}, {"SWALLS", 44},
{"ORION_ONLY", 39}, {"ORIONONLY", 39},
{"SNOWHALF", 33}, {"SNOW", 33},
{"RALLY_TARMAC", 51},
{"RALLYTARMAC", 50},
{"RUNOFFROAD", 46},
{"SNOWFULL", 34},
{"WOODRAILS", 23}, {"WDRL", 23},
{"PAVEMENT", 21},
{"ICEROAD", 45},
{"COBBLES", 29},
{"RMPMTL", 38}, {"RAMP", 38},
{"ROADS", 0}, {"ROAD", 0},
{"MARBLES", 5},
{"GRASS", 7}, {"GRAS", 7}, {"LOGO", 7}, {"FLDGRASS", 7}, {"RDGRASS", 7},
{"GRAVEL", 8}, {"GRV", 8}, {"GRAV", 8}, {"GBER", 8},
{"DRAINS", 11}, {"DRAIN", 11},
{"SAND", 15}, {"SBER", 15},
{"DIRT", 17}
```

In Blender, once all objects have been renamed according to their desired physical material (for example: `ROADS_MainTrack.001`, `GRASS_CloseGrass.001`, `GUARDRAILS_ArmcoCollision.001`, `BRICK_CurbT1`, `SAND_Turn5RunoffPit`, etc.), export the scene as an OBJ file without materials. Then, open a terminal in the folder containing `PhysicsMeshCooker.exe` and run the following command: `./PhysicsMeshCooker.exe path_to_exported.obj path_to_target.csm`

A Batch file is provided in the example project folder that contains a setup for the example track. You will have to adjust the path to `PhysicsMeshCooker.exe` if you move the project file.
The exported CSM's path should be in the track's physics folder, named the same as the track (for the Meadowdale example: `\Automobilista 2\Tracks\meadowdale\physics\meadowdale.csm`).
## Step 5.2: Create and Export the GCL
The GCL file contains two datasets, the first of which has to be set up manually, and the second of which is set up automatically by the toolkit on export time. The first dataset is assembled from four meshes that form the legal racing area of the track: the main racing surface, the pitlane, the pitlane exit area (within the white pit exit lines, usually), and the pitlane entry area. The first three are required; the last one is optional. To create these, it is usually sufficient to take the physical surface of the track and dissolve all interior geometry (all vertices not part of the non-manifold edge of the track), triangulate it, and split off the triangles that form the pitlane-related areas (some application of the knife tool may be necessary). Then, of the three to four resultant meshes, name them as follows:
- `SMS_GCL_ROAD` (main racing surface)
- `SMS_GCL_PIT` (pit area)
- `SMS_GCL_EXIT` (pit exit area)
- `SMS_GCL_ENTRY` (pit entry area)

The role that these surfaces seem to play, as noted through experimentation, are as follows:
- If the vehicle crosses from the pit area directly to the road area without first crossing through the pit exit area, a pit exit line cross penalty/warning is issued
- As the vehicle drives on the pit entry area, the pit lane speed limit HUD element is displayed in preparation for crossing the pit entry trigger

Note that unlike Assetto Corsa which uses a physical mesh material to determine when the pit speed limiter is applied, the Madness Engine uses triggers instead, which are waypoint/gate-like objects you have to pass through in a certain direction to trigger. This means if the vehicle manages to make its way from the racing surface to the pit area without passing through the trigger, the game won't register it as being on pit road, and the speed limit won't apply. This is probably similar to the behavior in gMotor games; I don't have any experience authoring content for gMotor games, so I don't know for sure.

Once all objects have been properly created and named, use the "Madness LiveTrack Cells" export function in Blender to export this data to the `\Automobilista 2\Tracks\TrackName\track_cut\TrackName.gcl` file for your track. In this process, the cell dectree will be calculated and saved into the GCL alongside the triangle data you just authored.
## Step 5.3: Create and Export the Triggers
Triggers are special zones that trigger certain events when the car passes them. To create a trigger, create a cube mesh and do the following with it:
- Place it at the center point you want the trigger to be located at
- Rotate it so its Z axis is upwards, its Y axis is forwards (along the direction the cars traveling through it are moving), and its X axis is right (compared to the direction the cars traveling through it are moving)
- Scale it so that its Y size is ~3m, its Z size is 50m, and its X size fills the potential area a car could cross it from (barrier to barrier, typically)
The possible and valid names for trigger cubes are as follows:
- `TRG_START` (start-finish line for circuits or the start line for point-to-point tracks)
- `TRG_CHECKPOINT1` (start of sector 2)
- `TRG_CHECKPOINT2` (start of sector 3)
- `TRG_FINISH` (finish line for point to point tracks, not required for circuits)
- `TRG_STOP` (unknown purpose)
- `TRG_PITIN` (pit entry line, where speed limit begins)
- `TRG_PITOUT` (pit exit line, where speed limit ends)
- `TRG_DRSDET1` (DRS detection line for zone 1)
- `TRG_DRSDET2` (DRS detection line for zone 2)
- `TRG_DRSDET3` (DRS detection line for zone 3)
- `TRG_DRSZONE1START` (start of DRS zone 1)
- `TRG_DRSZONE2START` (start of DRS zone 2)
- `TRG_DRSZONE3START` (start of DRS zone 3)
- `TRG_DRSZONE1END` (end of DRS zone 1)
- `TRG_DRSZONE2END` (end of DRS zone 2)
- `TRG_DRSZONE3END` (end of DRS zone 3)
After all required triggers have been set up, use the "Madness Triggers" export function to export them to `\Automobilista 2\Tracks\TrackName\physics\triggers.xml`.
## Step 5.4: Create and Export the AIW Data
The AIW data serves the same purpose in Madness Engine games as it does in gMotor-based games (AMS1, rF2, rF1, GTR2, etc.): to define the waypoint graph used by the computer opponents. As the AIW system is internally point-based, the toolkit expects you to author a few meshes with ascending vertex indices along the path the computer opponents are to follow:
- `SMS_AIW_CENTERLINE`: Defines the location of the individual waypoints forming the main path. Pay attention to the vertex indices; they should be ordered correctly counting up along the path, with no errors. To easily fix a disordered vertex series, convert the line mesh to a curve and back to a mesh. 
- `SMS_AIW_PITLINE`: Defines the location of the individual waypoints forming the pit path. Same vertex index restrictions apply.

In the added Madness AIW Params section of the Scene Properties panel, make sure to set the "Waypoint Span" distance to roughly the average distance between each waypoint vertex. Remember that a spacing of less than 3 meters between each waypoint can cause very strange AI driving behaviors, such as being overly cautious.

The centerline also needs certain data set up for each waypoint regarding the cornering behavior of the computer opponents in that area. If no corner data is assigned, it is likely that the computer opponents will fling themselves off the side of the track once they reach a corner as they won't be aware that there is a corner. To set this up, create two attribute fields `corner_type` and `corner_state`. 

`corner_type` determines the "style" of corner at that waypoint:
0. Straight
1. Unknown
2. Unknown
3. Left turn
4. Right turn
5. Loose chicane
6. Tight chicane

`corner_state` determines the "phase" of corner at that waypoint:
0. Straight
1. Entry
2. Apex
3. Exit

To assign values to an attribute field, select the desired attribute field in the Object Data Properties panel, and in edit mode on the object with the desired vertices selected, on the top bar in the Mesh dropdown, click Set Attribute and type in the value to assign to those vertices for that attribute field. Note that these attribute fields need to be set as vertex-domain integers, not floats or any other data type or any other domain type. As a hint to assign the `corner_state` values: with all corner areas selected (after performing the `corner_type` assignments), assign them as Exit, then deselect the exits, then assign as Apex, then deselect the apexes, then assign the remaining as Entry.

A few objects are required to be created and placed correctly. These can be meshes or empties; all that matters is their object names. They should be placed with their origin on the physical surface below them (unlike AC where a raycast is automatically done to resolve this, if you place the pitboxes high up, the cars will slide upwards when "magnetically" dragged into the pitbox, which can look weird, among other issues).
- `SMS_AIW_GARAGE_0A`: Spawn location of each car, uses A/B/C/etc. for additional garages paired with each `PITBOX` spot. Z up, Y forward, X right. Garage spots per pitbox are derived automatically from these objects (1 if only A is used, 2 if B is used, etc.).
- `SMS_AIW_PITBOX_0`: Pitstop location for each car. If `GARAGE_...B/C/etc` are used, multiple cars may stop in the same pitbox. Z up, Y forward, X right. Pitbox count is derived automatically from these objects.
- `SMS_AIW_START_0`: Standing start spawn location for each car. Z up, Y forward, X right. Starting grid count is derived automatically from these objects.
- `SMS_AIW_TELEPORT_0`: Rolling start spawn location for each car. Z up, Y forward, X right.

Optional AIW objects in Blender:
- `SMS_AIW_RACINGLINE`: If present, is used to calculate the lateral racing line offset for the main path waypoints. Density and vertex index order does not matter for this line mesh.
- `SMS_AIW_CUTLINE_LEFT/RIGHT` If present, is used to calculate the lateral track edge offset for the main path waypoints. Density and vertex index order does not matter for this line mesh. If not present, a default value of 5 meters of offset is used.
- `SMS_AIW_WALLLINE_LEFT/RIGHT` If present, is used to calculate the lateral maximum offtrack position offset for the main path waypoints. Density and vertex index order does not matter for this line mesh. If not present, a default value of 10 meters of offset is used.

Once created, the AIW data can be exported using the "Madness AIW" export option to `Automobilista 2\Tracks\_data\aiw\TrackName.aiw`. Ensure the collection the AIW objects are part of is enabled (and that all its parents are enabled) before export.
## Step 5.5: Configure LiveTrack Weathering-In Data
The Weathering-In Data consists of a sparse grid of cells with specific float and flag data determining how to initialize the LiveTrack system for the preset track states (puddles, rubber, etc.). Officially, this is done with a tool present in debug builds of the game (see https://www.youtube.com/watch?v=3yjgO0yylhc for an example of its usage), but since debug builds are not provided to the public, we must find an alternate way of synthesizing that data. 

The approach this toolkit takes is to use a Blender Geometry Nodes node tree to generate the data from some input parameters. A premade node tree, LiveTrackRasterGenerator, that achieves this goal is available in the example project. To use it for your track, do the following:
- Use Blender's Append functionality to copy the LiveTrackRasterGenerator node tree into your project
- Create any mesh (the content doesn't matter as it's discarded)
- Add the following attribute fields to the mesh:
	- `height`
	- `friction`
	- `grip`
	- `mask`
	- `flag_0`
	- `flag_1`
- Add a Geometry Nodes modifier to the mesh and switch it to use the appended node tree
- In the Output Attributes section of the new Geometry Nodes modifier, wire the output attributes of the node tree to those you added earlier
- Organize your track physical ground mesh objects into two collections: one containing only the objects forming the off-track surfaces ("Grass", but can also contain dirt, sand, etc.) and one containing the on-track surfaces ("Track", but also contains concrete runoff, side roads, etc.)
- Configure the options in the node tree as below:
	- `Target Cell Count` determines the resultant number of cells to generate. The amount used in the base game datasets is ~1,500,000; I would not go any higher than this except for very large tracks (Nordschleife, Targa Florio, etc.), and while you're adjusting the other parameters, I would turn it down to reduce the amount of recomputation performed each time a value is changed, only turning it back to 1.5M cells for export time.
	- `Roads` is a collection reference to the aforementioned road physical surfaces meshes.
	- `Grass` is a collection reference to the aforementioned non-road physical surface meshes.
	- `Racing Line Mesh` is a reference to your AIW racing line mesh, used to determine how to place the rubbered areas.
	- `Height Range` and `Height Offset` determine the parameters used to perform the raycasts to evaluate the slope of the surfaces as used for puddle generation. Defaults are 50m and 100m, but these may need to be increased for tracks with more elevation change.
	- `Water Blur Iterations` determines the amount of blurring steps performed to derive the low and high regions to place and avoid placing water. This will need to be adjusted for each track size and for changes in `Target Cell Count` as it is not spatially normalized.
	- The remaining `Water` parameters are used to tune the resultant water map after the derivation of the low and high regions. 
To preview the outputs at any step of the nodetree, you can use the Viewer system. To create a useful preview output node, start by holding Control and Shift and then left-clicking on the final `Transform Geometry` node in the `Rasterization` section of the LiveTrackRasterGenerator node tree to preview the raster grid, then Ctrl-Shift-left-clicking on the final node in the section you want to preview, such as the final `Multiply` node from the `Water` section to preview the water heightmap. 

Those who are adept with Geometry Nodes, feel free to make modifications and improvements to the node tree for your own use; there are certainly things that can be improved in it, such as the rubber generator not fully considering braking zones.

To export the data to an MRDF, ensure the object with the LiveTrackRasterGenerator node tree is inside an enabled collection (and all of its parent collections are enabled as well), select it, then use the "Madness LiveTrack Data" exporter to render the data to `Automobilista 2\Tracks\_data\livetrack\TrackName.mrdf`.
## Step 5.6: Assemble the Visuals
Reactivate all collections containing all objects intended to be visible. Deactivate all collections consisting of physics-only objects (wall collision, triggers, AIW data, LiveTrack generator, etc.) as well as all marker object collections ("Madness Objects" in the demo project). Ensure that every visible object has a material assigned and that every visible material has been configured (step 3). Then, export the scene using the "Madness Scene" option, and export to the SGX file named the same as the track under the track's folder (`Automobilista 2/tracks/TrackName/TrackName.sgx`). This will take a long time; it needs to export every object in the scene as its own MEB, each material as its own MTX, copy the referenced textures into the template game folder structure, and then write the assembled SGX scenegraph file. No caching is currently performed, so the entire operation is redone every time. No status updates are currently provided; the Blender UI will lock up and will unlock with a message in the bottom bar upon a successful export. To see progress reports, show the Blender Console window using the Window > Toggle System Console button in the top bar. 
## Step 5.7: Author and Export Remaining Optional Data
This section is WIP.

The following datasets can also be authored with the tool, and the example project is set up with data for each:
- Cameras
- Lights
- Sounds
- Dynamic Physics Objects
# Step 6: Package the Track
As provided for each release of this toolkit, there is included an EXE file PackTrack.exe. This is a PyInstaller-packaged version of the Python scripts available under the TrackPacker source folder in this repository. When run with no command line flags (such as by double-clicking on it in Explorer), it will open a file picker prompting you to pick the track folder to package. This supports track projects prepared in the same way the Example Project is packaged; to package it, select the `Automobilista 2` template folder inside the project folder. Packing will then start; after it is complete, a `.zip` file with the name of the track will be emitted next to the selected template folder. This file is then ready to be tested in-game by installing it with [Paolo Ambrosio's AMS2 CM](https://github.com/OpenSimTools/AMS2CM/).