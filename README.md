# Open Madness Track Tools
This repository consists of a set of scripts, a Blender plugin, and program source code enabling development of original track models for Slightly Mad Studios' Madness engine racing games (only tested with Automobilista 2 so far).

## Contents:
### Documentation
A docs suite on everything I know so far about tracks and their file formats in the Madness engine. **Start by reading this!**
### MEB Exporter Extended
A modification of the .NET program `Project CARS MEB Exporter` by `Shiimis`, `Autoprophet-ZR` and `LamboMantisMan23` that adds command-line support for batch-conversion of FBX/DAE files to the MEB format used by the Madness engine.
### MeshCooker
A command-line utility that prepares LiveTrack geometry data (PhysX cooked collision meshes) from FBX files using NVIDIA PhysX 3.3.4.
### TrackCompiler
A Blender plugin featuring full scene MEB+MTX+SGX export (using MEB Exporter Extended) and an MTX definition/configuration UI.

