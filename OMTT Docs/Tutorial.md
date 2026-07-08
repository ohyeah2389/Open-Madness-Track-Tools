This tutorial, like the entire project, is a work-in-progress and is, by definition and necessity, not complete. Please keep that in mind while following it. If you have any notes or questions, please post them to the Issues tracker of this repository.

# Step 0: Shotgun Introduction to the Madness Engine
The Madness Engine's game data is not designed to be modified by the end-user. That doesn't mean it isn't modifiable under the right configuration. 
It does, however, mean that it is extremely intolerant to error and misconfiguration, and it provides no feedback on what you did wrong.
Be careful, follow the instructions, and be warned that the instructions may be incomplete or unclear.
## Comparison to Assetto Corsa
* Physics/visuals separation
	- Assetto Corsa uses a single set of `KN5` files to define both the graphics and visuals of each track (and track layout). These are authored from source `FBX` files using the proprietary ksEditor software distributed with each copy of the game. Separation between the physical and visual data is not required and needs to be deliberately defined. Each KN5 can be of arbitrary size, with a limit of 65535 triangles per mesh object within each KN5. Arbitrary KN5 files can be defined and arranged using the `models.ini` track layout system, but this system is entirely optional and not always used.
	- The Madness Engine uses a scenegraph and a collection of loose mesh, material definition, and texture files to define the visuals of each track, plus a separate PhysX cooked triangle mesh container to define the physical shape and the surface material index.
- Data spread
	- Assetto Corsa's tracks are entirely contained under their folder at `/content/tracks/trackname`, with no files required to live outside of that folder, and no listing required. This makes distribution of custom tracks very easy.
	- Data for each track in the Madness Engine is spread out between at least six locations:
		- `/tracks/trackname`
		- `/tracks/_data`
		- `/tracks/textures`
		- `/cameras`
		- `/gui`
		- `/pakfiles/tracks`
	- Madness Engine track paths are required to be listed under the file `tracks/_data/tracklist.lst` with the format `Tracks\trackname\@trackname.trd`.
# Step 1: Format Familiarity
Several different file formats are used for track data in the Madness Engine. The game may load tracks without some of the "Required files" present, but key features may not work.
## Required files:
- `/tracks/trackname/trackname.trd`
	- Defines lots of textual and numeric data about the track (UI info, location, AI tuning, and much more)
	- It's human-readable and self-explanatory, openable in a text editor
- `/tracks/trackname/trackname.sgx` (or `sgb64`)
	- Defines the scenegraph of the track (position/rotation/scale of all mesh objects in the scene), as well as LOD info, culling, and occlusion data
	- SGXs are a specialized XML-like format; human readable, but very difficult to manually construct
	- SGB64s are a packed, optimized, binary format that is nowhere near human readable (and not yet operationally documented as of writing)
- `/tracks/trackname/trackname_lights.sgx` (or `sgb64`)
	- Defines the location and attributes of lights in the scene
	- SGXs use a similar format to the main SGX, but with special light-specific nodes only
	- SGB64s are similar to the main SGX (not operationally documented)
- `/tracks/trackname/meshname.meb`
	- Contains a visual mesh object referenceable by the scenegraph
	- Proprietary engine format, optimized packed binary
- `tracks/trackname/materialname.mtx` (or `bmt`)
	- Material definition file, references a shader and lists parameters and defines
	- MTXs are human-readable XML
	- BMTs are packed binary ("Blimey Markup Language") and are not operationally implemented by this toolkit
- `/tracks/trackname/physics/trackname.csm`
	- Contains a series of PhysX cooked triangle meshes with accompanying material indices
- `/tracks/trackname/track_cut/trackname.gcl`
	- Contains two datasets:
		- Track geometry, simplified, defining the edges of the track in triangle mesh format, with a numeric identifier on each triangle defining if it is part of the main track, pit entry, pit lane, or pit exit
		- Three-level dectree grid cells referencing each triangle
- `/tracks/trackname/physics/triggers.xml`
	- Lists all the timing and other trigger zones for the track (start-finish, pit-in, pit-out, DRS, etc.)
- `/tracks/_data/aiw/trackname.aiw`
	- Defines the AI paths and other AI data for the track
	- Human-readable, but difficult to edit or create by hand
- `/gui/tracklogos/trackname.dds`
	- Logo of the track, appears (tilted to the left) next to the track name in Project CARS 2's track selection screen
- `/gui/trackphotos/trackname.dds`
	- Image of the track (screenshot, render, real photo, etc.)
	- Used as loading screen background and preview in Automobilista 2
- `/gui/trackmaps/trackname.dds`
	- Used in-session for the track background
	- Not yet known how to map it properly to the 3D model
- `/gui/trackmaps3d/trackname.dds`
	- Track layout image, overlaid on the track photo in Automobilista 2's track selection screen
	- 2D white-red top-down layout for AMS2, 3D render with red-yellow-blue sectors and grey buildings in PC2
- `/tracks/trackname/trackproperties.bin`
	- Unknown format; hopefully it doesn't contain anything important
- `/tracks/trackname/trackname.enx`
	- Usually empty, used to be used for background objects (skydomes, etc.) in Shift2/PC1
- `/tracks/trackname/physics/object_properties.xml`
	- Usually empty, likely a leftover from earlier physics data definition standards in the engine
## Required placeholder files:
These can all be small, identical, empty BFF containers.
- `/pakfiles/tracks/trackname.bff`
- `/pakfiles/tracks/trackname_physics.bff`
- `/pakfiles/tracks/sno_trackname.bff`
- `/pakfiles/tracks/spr_trackname.bff`
- `/pakfiles/tracks/sum_trackname.bff`
- `/pakfiles/tracks/win_trackname.bff`
## Optional files:
- `/tracks/_data/livetrack/trackname.mrdf`
	- MRDF ("machine-readable data format", packed optimized binary) containing the "Weathering-In" data for the LiveTrack system
	- Optimized grid format containing 4 fields (three floats and an 8-bit flagset)
- `/cameras/trackname.xml`
	- Defines the camera sets used on the track
	- Human-readable XML-like format, but very difficult to edit or create from scratch
- `/pakfiles/tracks/livegrass/trackname.bff`
	- Can likely be empty like the previous placeholder BFFs
- `/tracks/_data/dynamicterrain/trackname.mrdf`
	- MRDF of unknown layout or format
- `/tracks/_data/grassexclusion/trackname.xcl`
	- Unknown format
- `/tracks/_data/pitgarages/trackname.mrdf`
	- MRDF of unknown layout or format
- `/tracks/_data/tracklights/trackname.xml`
	- Human-readable XML containing definitions for starting lights, pit entry/exit stoplights, and their trigger events
- `/tracks/_data/audio/trackname.lsd`
	- Human-readable XML defining the locations and attributes of ambient sound emitters placed around each track
- `/tracks/_data/crowds/trackname.lod`
	- Human-readable XML defining LOD distance overrides for various string-matched objects, usually character models
- `/tracks/trackname/physics/dynamic_collisions.xml`
	- `PhysXCollection` XML-like file containing the mesh data for every dynamic physics object (cone, corner marker) used on the track, referenced to by the next file
- `/tracks/_data/dynamic/physics/trackname.env.xml`
	- XML file containing listings of every dynamic physics object instance used on the track, referencing the previous file
# Step 2: Build the Track Model
Instructions on general track modeling are outside the scope of this tutorial, but below are some guidelines for modeling for the Madness engine from what I've seen so far.
- Track physical surface models from Reiza and SMS seem to be lower spatial resolution than those commonly used in other simulators. This may be a limitation of the Madness engine or it may not be; if you run into any performance limitations with high-density physical surface models, please let the community and I know.
- The Madness engine, just like Assetto Corsa, runs on DirectX 11. The Madness engine does support instancing unlike Assetto Corsa, but again, SGX files do not have support for referencing instance meshes. Therefore, try to keep the object count low. The lower the object count, the quicker the track will load, and the better it will perform, to a limit. 
	- The Madness engine uses spherical culling. Keep that in mind when combining objects; don't combine large objects that should be culled separately, like buildings.
- The Madness engine supports LOD models, but support for LOD systems isn't yet implemented in the Blender toolkit. All objects render at a max distance of 1000m, or ~400m if userflag "Far Distant Mesh" is disabled.
- Keep your objects organized with Blender's collection system. Support for separating collections into their own partitions (as well as support for child partitions) may be added later utilizing the Collections system.
	- This could also help when troubleshooting track load crashes, in that you could isolate down to specific similar groups of objects. The Blender scene export option won't export objects inside deactivated (unchecked) collections.
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
# Step 3: Author the Materials
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
# Step 4: Design the AIW Data
placeholder...
Required AIW objects in Blender:
- `SMS_AIW_CENTERLINE`: Defines the location of the individual waypoints forming the main path. Pay attention to the vertex indices; they should be ordered correctly counting up along the path, with no errors. To easily fix a disordered vertex series, convert the line mesh to a curve and back to a mesh. Make sure to set the "Waypoint Span" distance to roughly the average distance between each waypoint vertex. Remember that a spacing of less than 3 meters between each waypoint can cause very strange AI driving behaviors, such as being overly cautious.
- `SMS_AIW_PITLINE`: Defines the location of the individual waypoints forming the pit path. Same vertex index restrictions apply.
- `SMS_AIW_GARAGE_0A`: Spawn location of each car, uses A/B/C/etc. for additional garages paired with each `PITBOX` spot. Z up, Y forward, X right. Make sure to set the "Garage Spots Per Pitbox" in the Madness AIW Params pane under the Scene Properties tab correctly: if only A is used, set it to 1, set to 2 if B is used, set to 3 if C is used, etc.
- `SMS_AIW_PITBOX_0`: Pitstop location for each car. If `GARAGE_...B/C/etc` are used, multiple cars may stop in the same pitbox. Z up, Y forward, X right. Make sure to set the "Pitboxes" count correctly corresponding to the number of these objects (final index +1 since it is 0-indexed).
- `SMS_AIW_START_0`: Standing start spawn location for each car. Z up, Y forward, X right. Make sure to set the "Starting Grid" count correctly corresponding to the number of these objects (final index +1 since it is 0-indexed).
- `SMS_AIW_TELEPORT_0`: Rolling start spawn location for each car. Z up, Y forward, X right.
Optional AIW objects in Blender:
- `SMS_AIW_RACINGLINE`: If present, is used to calculate the lateral racing line offset for the main path waypoints. Density and vertex index order does not matter for this line mesh.
- `SMS_AIW_CUTLINE_LEFT/RIGHT` If present, is used to calculate the lateral track edge offset for the main path waypoints. Density and vertex index order does not matter for this line mesh. If not present, a default value of 5 meters of offset is used.
- `SMS_AIW_WALLLINE_LEFT/RIGHT` If present, is used to calculate the lateral maximum offtrack position offset for the main path waypoints. Density and vertex index order does not matter for this line mesh. If not present, a default value of 10 meters of offset is used.
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
A Batch file is provided in the example project folder that contains a setup for the example track.
The exported CSM's path should be in the track's physics folder, named the same as the track (for the Meadowdale example: `\Automobilista 2\Tracks\meadowdale\physics\meadowdale.csm`).
## Step 5.2: Export the GCL
## Step 5.3: Assemble the Visuals
Reactivate all collections containing all visible objects. Deactivate all collections consisting of physics-only objects (wall collision, etc.) as well as all marker object collections ("Madness Objects" in the demo project). Ensure that every visible object has a material assigned and that every visible material has been configured (step 3). Then, export the scene using the "Madness Scene" option, and export to the SGX file named the same as the track under the track's folder (`Automobilista 2/tracks/trackname/trackname.sgx`). This will take a long time; it needs to export every object in the scene as its own MEB, each material as its own MTX, and then write the assembled SGX scenegraph file. No caching is currently performed, so the entire operation is redone every time. No status updates are currently provided; the Blender UI will lock up and will unlock with a message in the bottom bar upon a successful export. To see progress reports, show the Blender Console window using the Window > Toggle System Console button in the top bar. 
