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
- The Madness engine supports LOD models, but support for LOD systems isn't yet implemented in the Blender toolchain. All objects render at a max distance of 1000m, or ~400m if userflag 0 is false.
- Keep your objects organized with Blender's collection system. Support for separating collections into their own partitions (as well as support for child partitions) may be added later utilizing the Collections system.
	- This could also help when troubleshooting track load crashes, in that you could isolate down to specific similar groups of objects. The Blender scene export option won't export objects inside deactivated (unchecked) collections.
- The Blender scene exporter supports export-time object combining. If you have a significant number of objects that need to be combined, name them using the prefix `KSTREE_GROUP_blabla_`, where `blabla` can be any string without underscores or spaces. This is designed to handle Assetto Corsa's ksEditor Y-tree grouping system. Note, though, that it does NOT apply the vertex normal adjustments that ksEditor does.
	- Additionally, the naming pattern `SMS_GRP_groupname_objectname.123` can be used instead, where all objects with the `SMS_GRP_groupname_` prefix will be combined into an object named `groupname`. Ensure `groupname` is unique and will not overlap with any non-grouped object names.
- The Madness engine, similar to Assetto Corsa, has a limit of 65535 vertices per mesh.