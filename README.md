# Open Madness Track Tools
This repository consists of a set of scripts, a Blender plugin, and program source code enabling development of original track models for Slightly Mad Studios' Madness Engine racing games (tested with Project CARS 2 and Reiza Studios' Automobilista 2).

## Limitations:
I want people to be aware of the limitations of the current methodology upfront. Here is the list of features that are not yet working:

### LiveTrack visuals don't show on track surfaces
MTX material definition files' structure isn't saved to memory correctly by the game, leading to the DEFINE parameters not taking effect in the main view. They do take effect in the rear view, which uses a different memory address check in its separated pipeline.
This can be crudely patched by setting bytes `84 C0 74 0E 83 CB 03` in AMS2.exe and AMS2AVX.exe to `84 C0 90 90 83 CB 03` to skip LiveTrack's check for those defines, but this may have unintended consequences, as LiveTrack will then render on all shaders capable of showing it, regardless of their configuration, even on stock game tracks. That also doesn't fix the core issue, leaving all the other DEFINE-based functionality still broken. To fix this, a tool must be created to convert from the XML-like human-readable MTX material definition format back to the machine-readable BMT material definition format.

### Wrong way/track cut/illegal pass detection doesn't work in AMS2
This results in no warning or penalty when driving backwards or when skipping sections of the track, and warnings when overtaking drivers.
Driving backwards through the pit exit trigger does still disqualify the player.
This does not apply in PC2; it is suspected that AMS2 added some extra form of cut identification that hasn't yet been located in the filesystem.
Tracks stolen from PC2 also have this issue due to missing that data.

### VHF instance hierarchies and IMB instance models can't be added to a track
This is because the SGX format does not support referencing these files. Certain scene preparation code, which runs if an SGB64 is loaded, doesn't run in the SGX loading pipeline.
The SGB64 format does support VHFs and IMBs, as evidenced by filepath strings containing references to VHF and IMB files inside them, but the SGB64 format is still undocumented.
This is unfortunate as there are many pre-made assets, such as trees, trackside vehicles, and similar that are ready to be used, but can't currently be referenced. Development time would be saved if these assets could be referenced, especially for the trees and foliage.

### Dynamic physics objects don't load
This may be related to the SGX format not supporting VHFs, which seem to be what dynamic physics objects are paired with.
Since the VHF/IMB preparation code isn't run when an SGX is loaded, it may not load the visuals for the objects. However, it doesn't seem to load the physics for them either, though I have not conclusively tested this.

### LiveGrass isn't implemented
I haven't begun research into the LiveGrass system because I highly suspect it'll only work with SGB64-formatted scenegraphs, not SGXs, for the reasons listed above, because the LiveGrass system likely makes heavy use of instancing.

## Contents:

### Documentation
In the development of this toolkit, I conducted extensive research into the Madness Engine and the file formats it uses. These are the notes I took on each file format and the file structure of tracks in both games.

### PhysicsMeshCooker
A command-line utility that prepares LiveTrack geometry data (PhysX cooked collision meshes) from FBX files using NVIDIA PhysX 3.3.4.

### TrackCompiler
A Blender addon that handles all Madness-specific track exporting and related authoring. 
It has the following capabilities:
- Export a Blender scene into a collection of MEBs (mesh binaries) and MTXs (material XML files) and a corresponding SGX (scenegraph XML file)
- Import, export, and create new loose MTXs linked to a Blender material (defined independently from it, but organized alongside it)
- Automatically copy all MTX-referenced textures to a specified folder, including straight into the specified game's folder structure
- Export a LiveTrack Weathering-In MRDF (Madness "Machine-Readable Data Format") from an object with a specifically formatted Geometry Nodes setup (see Example Files)
- Export a `triggers.xml` file containing timing gate and other trigger zone information from a set of scene objects with a specific naming convention (see Example Files)
- Export an AIW (AI Waypoints) file from a set of scene object with a specific mesh topology, attributes, and naming convention (see Example Files)
- Export a Cameras XML file from a set of scene objects with a specific naming convention, configured data, placements, and orientation (see Example Files)
- (WIP, see Limitations above) Export a paired `dynamic_objects.xml` and `trackname.env.xml` dynamic physics objects layout fileset from a set of empties with a specific naming convention and configuration

### Example Project
This contains a Blender project file, textures, and a shell track file structure ready to be exported into.
It is designed as a tutorial project to teach track developers about how the Madness engine works.
To that end, it contains a Tutorial.md that should be followed by anyone interested in using this toolkit.
The Blender project file contains a basic track model and preconfigured setups for the following exporters:
- AIW
- LiveTrack Weathering-In
- Cameras
- Triggers
- Lights
- Scene