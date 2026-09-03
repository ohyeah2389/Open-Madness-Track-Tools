This is the source code for PhysicsMeshCooker, a command-line tool that converts OBJ mesh files into the Madness Engine's semi-proprietary CSM format, using the PhysX 3.3.4 SDK to cook triangle meshes.

## For Artists

### Setup

This tool requires compiled NVIDIA PhysX binaries. Release builds of `PhysicsMeshCooker.exe` load the same DLLs as Automobilista 2 / Project CARS 2 use. Copy these DLLs from your game install next to the `PhysicsMeshCooker.exe` executable:

```
PhysX3_x64.dll
PhysX3Common_x64.dll
PhysX3Cooking_x64.dll
nvToolsExt64_1.dll
```

If you do not do this, the program will be unable to run properly.

### Usage

The tool is distributed in compiled binary form in the Releases page of this repository. To use it to convert a prepared OBJ mesh to a CSM mesh, run the following command:

```
PhysicsMeshCooker.exe <path/to/input.obj> <path/to/output.csm>
```

### Material mapping

Material indices are assigned automatically based on the object/group names in the OBJ file using prefix matching (case-insensitive). The full mapping table is provided below (and is also present in `src/PhysicsMeshCooker.cpp`):

| Name prefix | Index |
| --- | --- |
| `ROADS`, `ROAD` | 0 |
| `LOWGRIPROADS`, `LGROAD` | 1 |
| `BUMPYROADS1`, `B1ROAD` | 2 |
| `BUMPYROADS2`, `B2ROAD`, `CONC` | 3 |
| `BUMPYROADS3`, `B3ROAD` | 4 |
| `MARBLES` | 5 |
| `GRASSYBERMS`, `GBRM` | 6 |
| `GRASS`, `GRAS`, `LOGO`, `FLDGRASS`, `RDGRASS` | 7 |
| `GRAVEL`, `GRV`, `GRAV`, `GBER` | 8 |
| `BUMPYGRAVEL`, `BGRV` | 9 |
| `RUMBLESTRIPS`, `BRICK`, `RMBL` | 10 |
| `DRAINS`, `DRAIN` | 11 |
| `TIREWALLS`, `TWALL` | 12 |
| `CEMENTWALLS`, `CEMA`, `CWAL`, `CMWL` | 13 |
| `GUARDRAILS`, `GRDR` | 14 |
| `SAND`, `SBER` | 15 |
| `BUMPYSAND`, `BSAND` | 16 |
| `DIRT` | 17 |
| `BUMPYDIRT`, `BDIRT` | 18 |
| `DIRT_ROAD` | 19 |
| `BUMPYDIRT_ROAD`, `BDIRT_ROAD` | 20 |
| `PAVEMENT` | 21 |
| `DIRT BANK`, `DBANK` | 22 |
| `WOODRAILS`, `WDRL` | 23 |
| `DRY VERGE`, `DVERGE` | 24 |
| `EXITRUMBLES`, `ERUMBLE`, `RMBBL` | 25 |
| `GRASSCRETE`, `GCRETE` | 26 |
| `LONGGRASS`, `LNGGRS` | 27 |
| `SLOPEGRASS`, `SLPGRS` | 28 |
| `COBBLES` | 29 |
| `SAND_ROAD`, `SNDROAD` | 30 |
| `BAKED_CLAY`, `BAKEDCLAY` | 31 |
| `ASTROTURF`, `ASTRO` | 32 |
| `SNOWHALF`, `SNOW` | 33 |
| `SNOWFULL` | 34 |
| `DAMAGEDROAD1`, `DAMROAD1` | 35 |
| `TRAIN_TRACKS`, `TRAINROAD` | 36 |
| `BUMPYCOBBLES`, `RAMP_METAL` | 37 |
| `RMPMTL`, `RAMP` | 38 |
| `ORION_ONLY`, `ORIONONLY` | 39 |
| `B1RUMBLES`, `B1RUMBLE` | 40 |
| `B2RUMBLES`, `B2RUMBLE` | 41 |
| `ROUGHSAND1`, `RSAND1` | 42 |
| `ROUGHSAND2`, `RSAND2` | 43 |
| `SNOWWALLS`, `SWALLS` | 44 |
| `ICEROAD` | 45 |
| `RUNOFFROAD` | 46 |
| `ILLEGAL_STRIP`, `ILLEGALSTRIP` | 47 |
| `PAINTCRETE_LEGAL`, `PCRETE_LEGAL` | 48 |
| `PAINTCRETE_ILLEGAL`, `PCRETE_ILLEGAL`, `RDGREEN` | 49 |
| `RALLYTARMAC` | 50 |
| `RALLY_TARMAC` | 51 |

If no prefix matches, the surface defaults to `ROAD` (index 0).

## Output format

The CSM file has the following binary layout:

```
[version : uint32]                         // always 330
  [mesh_size : uint32]                     // byte length of the cooked PhysX data
  [cooked_mesh : mesh_size bytes]          // PhysX triangle mesh (PxTriangleMesh)
  [material_index : uint32]                // terrain material index
  ... repeated once per OBJ group
```

### Troubleshooting

**`The code execution cannot proceed because PhysX3_x64.dll was not found`**
Copy the four PhysX/nvTools DLLs from your game install next to `PhysicsMeshCooker.exe`, or rebuild with `-GameDir`.

**PhysX cooking failed at runtime**
Verify the OBJ file contains valid triangulated geometry. Each OBJ group must have at least one triangle. Degenerate or zero-area triangles will cause the cooker to fail.

## For Developers

## System requirements

- OS: Windows 10 or later (64-bit)
- Shell: PowerShell 7 (`pwsh`)
- Compiler: Clang (clang++) targeting `x86_64-pc-windows-msvc` from the standalone LLVM Windows installer
- Build system: CMake 3.20+ and Ninja
- Dependencies:
  - NVIDIA PhysX SDK 3.3.4 (vc14win64 build)

## Setup

### 1. Install the standalone LLVM Windows toolchain

> **Important:** Do not use MinGW-ABI clang toolchains (`x86_64-w64-windows-gnu`). PhysX 3.3.4 `vc14win64` libraries require MSVC ABI (`x86_64-pc-windows-msvc`).

Download and install the standalone LLVM Windows installer from:

```
https://github.com/llvm/llvm-project/releases
```

Look for the file named `LLVM-<version>-win64.exe`. The default install path is `C:\Program Files\LLVM`. Its `clang++` targets `x86_64-pc-windows-msvc` and can link MSVC-built static libraries directly.

After installing, add `C:\Program Files\LLVM\bin` to PATH or set `LLVM_PATH`.

### 2. Install CMake

CMake can be installed via the official installer (https://cmake.org/download/). The system-wide installer is recommended as it adds `cmake` to your PATH automatically.

### 3. Install Ninja

Install Ninja (recommended):

```
winget install --id Ninja-build.Ninja -e
```

### 4. Install the Windows SDK

The standalone LLVM clang++ uses MSVC headers and libraries. Ensure the Windows SDK (10.0 or later) and the MSVC runtime headers are installed. These are included with any Visual Studio installation, or can be installed via the [Visual Studio Build Tools](https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022) (select the "Desktop development with C++" workload).

### 5. Install PhysX SDK 3.3.4

Download the PhysX 3.3.4 SDK and install or extract it so that the following paths exist:

```
<SDK root>\Include\PxPhysicsAPI.h
<SDK root>\Lib\vc14win64\PhysX3DEBUG_x64.lib
```

Set the `PHYSX_SDK_PATH` environment variable to the SDK root, for example:

```
$env:PHYSX_SDK_PATH = "C:/PhysX3.3.4"
```

### 6. Prepare release PhysX libs (for `-Release` / distribution builds)

Debug cooker builds link the SDK's `*DEBUG*` libraries. Release builds link the unsuffixed names that match the game DLLs (`PhysX3_x64.dll`, etc.). The stock `vc14win64` package often only ships DEBUG libs, so prepare release link inputs once:

1. **Import libs** from the game DLLs (names must match the EXE imports):

```
dumpbin /EXPORTS PhysX3_x64.dll
# then lib /DEF:... /MACHINE:X64 /OUT:PhysX3_x64.lib
# repeat for PhysX3Common_x64.dll and PhysX3Cooking_x64.dll into Lib\vc14win64\
```

2. **Static libs** `PhysX3Extensions.lib` and `PhysXProfileSDK.lib`; build the `release|x64` configs of those projects from `Source\compiler\vc14win64\`, and retarget the toolset/SDK if needed.

You should end up with:

```
<SDK root>\Lib\vc14win64\PhysX3_x64.lib
<SDK root>\Lib\vc14win64\PhysX3Common_x64.lib
<SDK root>\Lib\vc14win64\PhysX3Cooking_x64.lib
<SDK root>\Lib\vc14win64\PhysX3Extensions.lib
<SDK root>\Lib\vc14win64\PhysXProfileSDK.lib
```

## Building

Navigate to the `PhysicsMeshCooker` directory and run `build.ps1`:

```
cd PhysicsMeshCooker
pwsh -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

The script will locate `clang++` and `cmake` automatically, configure the project, and produce the executable at:

```
build/PhysicsMeshCooker.exe
```

### Build options

| Flag | Description | Default |
| --- | --- | --- |
| `-Release` | Build in Release mode (links game PhysX DLL names) | Debug |
| `-PhysxSdkPath <path>` | Path to PhysX 3.3.4 SDK root | `$env:PHYSX_SDK_PATH` or `C:/PhysX3.3.4` |
| `-GameDir <path>` | After a Release build, copy PhysX DLLs from this game install next to the exe | (none) |
| `-Jobs <n>` | Number of parallel compile jobs | CPU count |
| `-Clean` | Delete the `build/` directory before configuring | off |

| Build type | Linked PhysX runtime names | DLLs next to exe |
| --- | --- | --- |
| Debug | `PhysX3DEBUG_x64.dll`, ... | Copied from SDK `Bin\vc14win64` |
| Release | `PhysX3_x64.dll`, ... | Not bundled; copied from the game (or use `-GameDir`) |

| Environment variable | Description |
| --- | --- |
| `PHYSX_SDK_PATH` | PhysX 3.3.4 SDK root (default for `-PhysxSdkPath`) |
| `LLVM_PATH` | Root of the standalone LLVM installation (e.g. `C:/Program Files/LLVM`) |

Examples:

```
# Debug build (default)
pwsh -NoProfile -ExecutionPolicy Bypass -File .\build.ps1

# Release build with a custom PhysX path
pwsh -NoProfile -ExecutionPolicy Bypass -File .\build.ps1 -Release -PhysxSdkPath D:/SDKs/PhysX3.3.4

# Clean release build + copy PhysX DLLs from AMS2 for local testing
pwsh -NoProfile -ExecutionPolicy Bypass -File .\build.ps1 -Clean -Release -Jobs 8 -GameDir "G:/SteamLibrary/steamapps/common/Automobilista 2"
```

### Manual CMake invocation

If you prefer to drive CMake directly:

```
cmake -S . -B build `
      -G Ninja `
      -DCMAKE_BUILD_TYPE=Debug `
      -DCMAKE_CXX_COMPILER="C:/Program Files/LLVM/bin/clang++.exe" `
      -DCMAKE_MAKE_PROGRAM="ninja" `
      -DCMAKE_RC_COMPILER="C:/Program Files (x86)/Windows Kits/10/bin/10.0.26100.0/x64/rc.exe" `
      -DPHYSX_SDK_PATH="C:/PhysX3.3.4" `
      -DCMAKE_EXPORT_COMPILE_COMMANDS=ON

cmake --build build --config Debug -- -j4
```

## IntelliSense / clangd

After the first configure/build, `compile_commands.json` is generated in `build/`. The `.clangd` file points clangd at that compile database (`CompileDatabase: build`), so include paths and flags come from the real CMake build.

If you have not configured yet, run one build first so clangd has a compile database to read.

## Troubleshooting

**`clang++ not found` / wrong target ABI**
Install the standalone LLVM Windows toolchain from https://github.com/llvm/llvm-project/releases (`LLVM-<version>-win64.exe`), then put `C:\Program Files\LLVM\bin` on PATH or set `LLVM_PATH`.

**`PxPhysicsAPI.h not found`**
Verify `PHYSX_SDK_PATH` points to the root of the PhysX 3.3.4 installation and that `$PHYSX_SDK_PATH/Include/PxPhysicsAPI.h` exists.

**`cannot open input file 'PhysX3DEBUG_x64.lib'`**
The PhysX SDK ships pre-built against the MSVC runtime. Ensure you have the `vc14win64` library set at `$PHYSX_SDK_PATH/Lib/vc14win64/`. Clang on Windows can link MSVC-built static libraries directly.

**`Missing .../PhysX3_x64.lib for Release build`**
Release builds need unsuffixed PhysX libs. See [Prepare release PhysX libs](#6-prepare-release-physx-libs-for--release--distribution-builds).
