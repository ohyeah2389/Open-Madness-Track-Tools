# PhysicsMeshCooker

A command-line tool that converts OBJ (Wavefront) mesh files into the Madness engine's proprietary CSM (Cooked Static Mesh) format, using the PhysX 3.3.4 SDK to cook triangle meshes.

## System requirements

- **OS**: Windows 10 or later (64-bit)
- **Shell**: MSYS2 (for `build.sh`)
- **Compiler**: Clang (clang++) targeting `x86_64-pc-windows-msvc` — **must be the standalone LLVM Windows installer**, not the MSYS2 clang64/ucrt64/mingw64 packages (those target the MinGW ABI and cannot link MSVC `.lib` files)
- **Build system**: CMake 3.20 or later
- **Dependencies**:
  - NVIDIA PhysX SDK 3.3.4 (vc14win64 build)

## Setup

### 1. Install MSYS2

Download and install MSYS2 from https://www.msys2.org/. The `build.sh` script must be run from an MSYS2 terminal. You also need `make` from MSYS2:

```
pacman -S make
```

### 2. Install the standalone LLVM Windows toolchain

> **Important:** Do *not* use the MSYS2 `clang64`, `ucrt64`, or `mingw64` clang packages. Those target the MinGW ABI (`x86_64-w64-windows-gnu`) and cannot link against PhysX 3.3.4's MSVC-ABI `.lib` files.

Download and install the standalone LLVM Windows installer from:

```
https://github.com/llvm/llvm-project/releases
```

Look for the file named `LLVM-<version>-win64.exe`. The default install path is `C:\Program Files\LLVM`. Its `clang++` targets `x86_64-pc-windows-msvc` and can link MSVC-built static libraries directly.

After installing, either add `C:\Program Files\LLVM\bin` to your Windows `PATH`, or set the `LLVM_PATH` environment variable before running `build.sh`:

```
export LLVM_PATH="C:/Program Files/LLVM"
```

### 3. Install CMake

CMake can be installed via the official installer (https://cmake.org/download/). The system-wide installer is recommended as it adds `cmake` to your PATH automatically.

### 4. Install the Windows SDK

The standalone LLVM clang++ uses MSVC headers and libraries. Ensure the **Windows SDK** (10.0 or later) and the **MSVC runtime headers** are installed. These are included with any Visual Studio installation, or can be installed via the [Visual Studio Build Tools](https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022) (select the "Desktop development with C++" workload).

### 5. Install PhysX SDK 3.3.4

Download the PhysX 3.3.4 SDK and install or extract it so that the following paths exist:

```
<SDK root>\Include\PxPhysicsAPI.h
<SDK root>\Lib\vc14win64\PhysX3DEBUG_x64.lib
```

Set the `PHYSX_SDK_PATH` environment variable to the SDK root, for example (in your MSYS2 `~/.bashrc`):

```
export PHYSX_SDK_PATH="C:/PhysX3.3.4"
```



## Building

Navigate to the `PhysicsMeshCooker` directory and run `build.sh`:

```
cd PhysicsMeshCooker
bash build.sh
```

The script will locate `clang++` and `cmake` automatically, configure the project, and produce the executable at:

```
build/PhysicsMeshCooker.exe
```

### Build options

| Flag | Description | Default |
|------|-------------|---------|
| `-r` / `--release` | Build in Release mode | Debug |
| `-p` / `--physx PATH` | Path to PhysX 3.3.4 SDK root | `$PHYSX_SDK_PATH` or `C:/PhysX3.3.4` |
| `-j` / `--jobs N` | Number of parallel compile jobs | CPU count |
| `-c` / `--clean` | Delete the `build/` directory before configuring | off |
| `-h` / `--help` | Show usage information | — |

| Environment variable | Description |
|----------------------|-------------|
| `PHYSX_SDK_PATH` | PhysX 3.3.4 SDK root (equivalent to `--physx`) |
| `LLVM_PATH` | Root of the standalone LLVM installation (e.g. `C:/Program Files/LLVM`) |

Examples:

```
# Debug build (default)
bash build.sh

# Release build with a custom PhysX path
bash build.sh --release --physx D:/SDKs/PhysX3.3.4

# Clean release build using 8 parallel jobs
bash build.sh --clean --release --jobs 8
```

### Manual CMake invocation

If you prefer to drive CMake directly:

```
cmake -S . -B build \
      -G "Unix Makefiles" \
      -DCMAKE_BUILD_TYPE=Debug \
      -DCMAKE_CXX_COMPILER=clang++ \
      -DPHYSX_SDK_PATH="C:/PhysX3.3.4" \
      -DCMAKE_EXPORT_COMPILE_COMMANDS=ON

cmake --build build -- -j4
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
./build/PhysicsMeshCooker.exe my_track.obj my_track.csm
```

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

After the first build, a `compile_commands.json` is generated in the `build/` directory. The `.clangd` file at the project root is configured to read from that directory, so clangd will pick up the correct include paths and flags automatically.

If you haven't built yet, `.clangd` includes a `CompileFlags` fallback that points at `C:/PhysX3.3.4/Include` directly, so IntelliSense will still work before the first build.

## Troubleshooting

**`clang++ not found` / `No MSVC-ABI clang++ found`**
Install the standalone LLVM Windows toolchain from https://github.com/llvm/llvm-project/releases (the file named `LLVM-<version>-win64.exe`). Do *not* use the MSYS2 clang64 package — it targets the MinGW ABI and cannot link PhysX `.lib` files.

**`clang++ targets windows-gnu (MinGW ABI)`**
The MSYS2 clang64/ucrt64/mingw64 `clang++` was found instead of the standalone LLVM installer. Either add `C:\Program Files\LLVM\bin` to the front of your PATH, or set `LLVM_PATH` before running the script: `export LLVM_PATH="C:/Program Files/LLVM"`.

**`PxPhysicsAPI.h not found`**
Verify `PHYSX_SDK_PATH` points to the root of the PhysX 3.3.4 installation and that `$PHYSX_SDK_PATH/Include/PxPhysicsAPI.h` exists.

**`cannot open input file 'PhysX3DEBUG_x64.lib'`**
The PhysX SDK ships pre-built against the MSVC runtime. Ensure you have the `vc14win64` library set at `$PHYSX_SDK_PATH/Lib/vc14win64/`. Clang on Windows can link MSVC-built static libraries directly.

**PhysX cooking failed at runtime**
Verify the OBJ file contains valid triangulated geometry. Each OBJ group must have at least one triangle. Degenerate or zero-area triangles will cause the cooker to fail.