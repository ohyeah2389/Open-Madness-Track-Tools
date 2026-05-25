# PhysicsMeshCooker

A command-line tool that converts OBJ (Wavefront) mesh files into the Madness engine's proprietary CSM (Cooked Static Mesh) format, using the PhysX 3.3.4 SDK to cook triangle meshes.

## System requirements

- **OS**: Windows 10 or later (64-bit)
- **Shell**: PowerShell 7 (`pwsh`)
- **Compiler**: Clang (clang++) targeting `x86_64-pc-windows-msvc` from the standalone LLVM Windows installer
- **Build system**: CMake 3.20+ and Ninja
- **Dependencies**:
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

The standalone LLVM clang++ uses MSVC headers and libraries. Ensure the **Windows SDK** (10.0 or later) and the **MSVC runtime headers** are installed. These are included with any Visual Studio installation, or can be installed via the [Visual Studio Build Tools](https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022) (select the "Desktop development with C++" workload).

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

### VSCode / Cursor

The workspace is configured to use editor features only (no auto-CMake configure) and provides explicit tasks that call `build.ps1`:

- `PhysicsMeshCooker: Build (Debug)` (default build task / `Ctrl+Shift+B`)
- `PhysicsMeshCooker: Clean + Build (Debug)`
- `PhysicsMeshCooker: Build (Release)`

### Build options

| Flag | Description | Default |
|------|-------------|---------|
| `-Release` | Build in Release mode | Debug |
| `-PhysxSdkPath <path>` | Path to PhysX 3.3.4 SDK root | `$env:PHYSX_SDK_PATH` or `C:/PhysX3.3.4` |
| `-Jobs <n>` | Number of parallel compile jobs | CPU count |
| `-Clean` | Delete the `build/` directory before configuring | off |

> Note: `-Release` enables release compile flags for this project, but PhysX 3.3.4 `vc14win64` only provides `DEBUG`-suffixed libraries, so those are linked in all configurations.

| Environment variable | Description |
|----------------------|-------------|
| `PHYSX_SDK_PATH` | PhysX 3.3.4 SDK root (default for `-PhysxSdkPath`) |
| `LLVM_PATH` | Root of the standalone LLVM installation (e.g. `C:/Program Files/LLVM`) |

Examples:

```
# Debug build (default)
pwsh -NoProfile -ExecutionPolicy Bypass -File .\build.ps1

# Release build with a custom PhysX path
pwsh -NoProfile -ExecutionPolicy Bypass -File .\build.ps1 -Release -PhysxSdkPath D:/SDKs/PhysX3.3.4

# Clean release build using 8 parallel jobs
pwsh -NoProfile -ExecutionPolicy Bypass -File .\build.ps1 -Clean -Release -Jobs 8
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

## Usage

```
PhysicsMeshCooker.exe <input.obj> <output.csm>
```

| Argument | Description |
|----------|-------------|
| `<input.obj>` | Path to the input Wavefront OBJ file |
| `<output.csm>` | Path where the cooked CSM file will be written |

Example:

```
build/PhysicsMeshCooker.exe my_track.obj my_track.csm
```

If DLL resolution fails when running from another directory, run from `PhysicsMeshCooker/build` or ensure that directory is on `PATH`.

### Material mapping

Material indices are assigned automatically based on the object/group names in the OBJ file using prefix matching (case-insensitive). The full mapping table is defined in `src/PhysicsMeshCooker.cpp`. A few examples:

| Name prefix | Material | Index |
|-------------|----------|-------|
| `ROAD`, `ROADS` | Road surface | 0 |
| `GRASS`, `GRAS` | Grass | 7 |
| `GRAVEL`, `GRV` | Gravel | 8 |
| `SAND`, `SBER` | Sand | 15 |
| `DIRT`, `BDIRT` | Dirt | 17–18 |
| `RMBL`, `RUMBLESTRIPS` | Rumble strips | 10 |
| `SNOW`, `SNOWFULL` | Snow | 33–34 |

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

**PhysX cooking failed at runtime**
Verify the OBJ file contains valid triangulated geometry. Each OBJ group must have at least one triangle. Degenerate or zero-area triangles will cause the cooker to fail.