# MeshCooker

MeshCooker is a command-line tool that converts OBJ (Wavefront) mesh files into the Madness engine's proprietary CSM format.

## System requirements

- **OS**: Windows 10 or later (64-bit)
- **Compiler**: Visual Studio 2022 (v143 toolset) or compatible
- **Dependencies**:
  - NVIDIA PhysX SDK 3.3.4 (specifically the vc14win64 build)
  - Windows SDK 10.0 or later

## Setup instructions

1. Download and install PhysX SDK 3.3.4.

2. Set the `PHYSX_SDK_PATH` environment variable to point to your PhysX installation directory:

```
PHYSX_SDK_PATH=C:\Path\To\PhysX3.3.4
```

For example, if you installed PhysX to `C:\PhysX3.3.4`, set:
```
PHYSX_SDK_PATH=C:\PhysX3.3.4
```

3. Build the project
    1. Open `MeshCooker-Distribution.sln` in Visual Studio 2022
    2. Select your desired configuration (Debug/Release) and platform (x64)
    3. Build the solution (F7 or Build → Build Solution)

The executable will be created in the `build\` directory.

## Usage

```
MeshCooker.exe <input.obj> <output.csm>
```
- `<input.obj>`: Path to the input OBJ file
- `<output.csm>`: Path where the cooked CSM file will be saved

Example:
```
MeshCooker.exe my_track.obj my_track.csm
```

### Material mapping

The tool automatically assigns materials based on object/group names in the OBJ file. The material database includes mappings for:

- Roads and surfaces (ROAD, CONCRETE, ASPHALT)
- Terrain types (GRASS, SAND, DIRT, GRAVEL)
- Track features (RUMBLE_STRIPS, GUARD_RAILS, TIRE_WALLS)
- Special surfaces (SNOW, ICE)

Material indices are assigned based on prefix matching against the object names. See the source code or Open Madness Track Tools' documentation for the complete material mapping table.

## Troubleshooting

### Build Errors

**Error: Cannot find PhysX libraries**
- Verify `PHYSX_SDK_PATH` environment variable is set correctly
- Ensure you have the vc14win64 version of PhysX 3.3.4
- Check that the PhysX installation includes the required libraries:
  - PhysX3DEBUG_x64.lib
  - PhysX3CommonDEBUG_x64.lib
  - PhysX3CookingDEBUG_x64.lib
  - PhysX3ExtensionsDEBUG.lib
  - PhysXProfileSDKDEBUG.lib

**Error: Cannot find PhysX headers**
- Verify the Include directory exists at `%PHYSX_SDK_PATH%\Include`
- Check that `PxPhysicsAPI.h` is present in the Include directory

### Runtime Errors

**Error: Cannot open input file**
- Ensure the OBJ file path is correct and the file exists
- Check file permissions

**PhysX cooking failed**
- Verify the OBJ file contains valid mesh data
- Check that mesh groups have valid geometry (triangles)
