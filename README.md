# Open Madness Track Tools
This repository consists of a set of scripts, a Blender plugin, and program source code enabling development of original track models for Slightly Mad Studios' Madness Engine racing games (tested with Project CARS 2 and Reiza Studios' Automobilista 2).

## Disclaimer
This is an unofficial, independent project. It is not affiliated with, authorized by, endorsed by, or sponsored by Reiza Studios, Slightly Mad Studios, or any of their affiliates. "Automobilista 2", "Project CARS", "Madness Engine", and all related names and marks are the property of their respective owners and are used here only to identify the software this toolkit interoperates with.

No game assets or game code are distributed by this project. You must own a legitimate copy of the target game to use this toolkit.

## Limitations:
I want people to be aware of the limitations of the current methodology upfront. Here is the non-exhaustive list of features that are not yet working:

### VHF instance hierarchies and IMB instance models can't be added to a track
This is because the SGX format does not support referencing these files. Certain scene preparation code, which runs if an SGB64 is loaded, doesn't run in the SGX loading pipeline.
The SGB64 format does support VHFs and IMBs, as evidenced by filepath strings containing references to VHF and IMB files inside them, but the SGB64 format is still undocumented.

### LiveGrass isn't implemented
I haven't begun research into the LiveGrass system because I highly suspect it'll only work with SGB64-formatted scenegraphs, not SGXs, for the reasons listed above, because the LiveGrass system likely makes heavy use of instancing.

### LODs are not implemented
This feature is possible to implement and will be implemented at a later date.

## Contents:

### Documentation
In the development of this toolkit, I conducted extensive research into the Madness Engine and the file formats it uses. These are the notes I took on each file format and the file structure of tracks in both games.

### PhysicsMeshCooker
A command-line utility that prepares LiveTrack geometry data (PhysX cooked collision meshes) from FBX files using NVIDIA PhysX 3.3.4.

### TrackCompiler
A Blender addon that handles all Madness-specific track exporting and related authoring. 
It has the following capabilities:
- Export a Blender scene into a collection of MEBs (mesh binaries) and MTXs (material XML files) and a corresponding SGX (scenegraph XML file)
    - Automatically copy all MTX-referenced textures to the correct place in a placeholder game folder structure
- Import, export, and create new loose MTXs linked to a Blender material (defined independently from it, but organized alongside it)
- Export selected Blender objects or the entire active Blender scene to a single MEB file + MTX file(s) for special purposes (such as preparation of custom dynamic physics objects)
- Export an AIW (AI Waypoints) file from a set of scene objects with a specific mesh topology, attributes, and naming convention (see Example Files)
- Export a LiveTrack Weathering-In MRDF (Madness "Machine-Readable Data Format") from an object with a specifically formatted Geometry Nodes setup (see Example Files)
- Export a `triggers.xml` file containing timing gate and other trigger zone information from a set of scene objects with a specific naming convention (see Example Files)
- Export a Cameras XML file from a set of scene objects with a specific naming convention, configured data, placements, and orientation (see Example Files)
- Export a Lights SGX file from a set of scene objects with a specific naming convention, configured data, placements, and orientation (see Example Files)
- Export a paired `dynamic_objects.xml` and `trackname.env.xml` dynamic physics objects layout fileset
- Export a Level Sound Definition LSD file from a set of scene objects with a specific naming convention, configured data, placements, and orientation (see Example Files)
- Export a LiveTrack Point Grid and track cut area GCL file from a set of scene objects representing the drivable surface of the track (see Example Files)

### TrackPacker
A command-line utility that converts and packs files for distribution and installation with [Paolo Ambrosio's AMS2 CM](https://github.com/OpenSimTools/AMS2CM/). This is distributed in each release as `PackTrack.exe`; a PyInstaller-built version of the `pack_track.py` script; which can be used instead if you have Python installed.
Contains the following:
- `bff_creator.py` is a Python script that is capable of creating a new valid BFF from loose files. It does not and will not support BFF encryption; no code that supports BFF encryption is included or will be included.
- `mtx2bmt.py` is a Python script that is capable of converting MTX material definition XML files to BMT binary material files.
- `pack_track.py` is a Python script that performs the actual packing of a template folder structure (such as the one provided in the Example Project) into a `.zip` file ready for installation with the aforementioned Content Manager.
- Seasonal variation BFFs are generated at pack time rather than shipped. Every track needs a pak per season, so each is built from season-suffixed copies of the track's own materials, matching the layout stock tracks use.

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

## License
This project is free software. Different components carry different licenses:

| Component | License |
| --- | --- |
| `TrackCompiler` | [GPL-3.0-or-later](LICENSE) + [output exception](LICENSE-EXCEPTION.txt) |
| `TrackPacker` | [GPL-3.0-or-later](LICENSE) + [output exception](LICENSE-EXCEPTION.txt) |
| `PhysicsMeshCooker` | [MIT](PhysicsMeshCooker/LICENSE) |
| `OMTT Docs` | [CC BY-SA 4.0](OMTT%20Docs/LICENSE) |
| `Example Project` | CC BY 4.0 |

### Tracks you make with this are yours
The copyleft terms apply to this toolkit and to derivatives of it. They do not apply to the tracks you build with it. The [output exception](LICENSE-EXCEPTION.txt) states this explicitly: files produced by these tools belong to you, you may license them however you like, and you may sell them.

### Contributing and naming
See [CONTRIBUTING.md](CONTRIBUTING.md) for the sign-off requirement, and [TRADEMARKS.md](TRADEMARKS.md) for how the project name may be used.