# Open Madness Track Tools
This repository consists of a set of scripts, a Blender plugin, and program source code enabling development of original track models for Slightly Mad Studios' Madness Engine racing games (tested with Project CARS 2 and Reiza Studios' Automobilista 2).

## Limitations:
I want people to be aware of the limitations of the current methodology upfront. Here is the list of features that are not yet working:

### VHF instance hierarchies and IMB instance models can't be added to a track
This is because the SGX format does not support referencing these files. Certain scene preparation code, which runs if an SGB64 is loaded, doesn't run in the SGX loading pipeline.
The SGB64 format does support VHFs and IMBs, as evidenced by filepath strings containing references to VHF and IMB files inside them, but the SGB64 format is still undocumented.

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
    - Automatically copy all MTX-referenced textures to a specified folder, including straight into the specified game's folder structure
- Import, export, and create new loose MTXs linked to a Blender material (defined independently from it, but organized alongside it)
- Export selected Blender objects or the entire active Blender scene to a single MEB file + MTX file(s) for special purposes (such as preparation of custom dynamic physics objects)
- Export an AIW (AI Waypoints) file from a set of scene object with a specific mesh topology, attributes, and naming convention (see Example Files)
- Export a LiveTrack Weathering-In MRDF (Madness "Machine-Readable Data Format") from an object with a specifically formatted Geometry Nodes setup (see Example Files)
- Export a `triggers.xml` file containing timing gate and other trigger zone information from a set of scene objects with a specific naming convention (see Example Files)
- Export a Cameras XML file from a set of scene objects with a specific naming convention, configured data, placements, and orientation (see Example Files)
- Export a Lights SGX file from a set of scene objects with a specific naming convention, configured data, placements, and orientation (see Example Files)
- Export a paired `dynamic_objects.xml` and `trackname.env.xml` dynamic physics objects layout fileset from a set of empties with a specific naming convention and configuration
- Export a Level Sound Definition LSD file from a set of scene objects with a specific naming convention, configured data, placements, and orientation (see Example Files)
- Export a LiveTrack Point Grid and track cut area GCL file from a set of scene objects representing the drivable surface of the track (see Example Files)

### Example Project
This contains a Blender project file, textures, and a shell track file structure ready to be exported into.
It is designed as a tutorial project to teach track developers about how the Madness engine works.
To that end, it contains a Tutorial.md that should be followed by anyone interested in using this toolkit.
The Blender project file contains a basic track model and preconfigured setups for the following exporters:
- AI Waypoints `AIW`
- LiveTrack Weathering-In `MRDF`
- Cameras `XML`
- Triggers `XML`
- Lights `SGX`
- Scene `SGX`