#!/usr/bin/env bash
# build.sh - Configure and build PhysicsMeshCooker with Clang via CMake
# Run from the PhysicsMeshCooker directory inside an MSYS2 shell.

set -euo pipefail

# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------
die() { echo "ERROR: $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
#  Locate clang++
#
#  PhysX 3.3.4 ships MSVC-ABI .lib files (vc14win64). The MSYS2 clang64/ucrt64/
#  mingw64 packages target x86_64-w64-windows-gnu (MinGW ABI) and cannot link
#  against them. We need the standalone LLVM Windows installer whose clang++
#  defaults to x86_64-pc-windows-msvc.
#
#  Search order:
#    1. LLVM_PATH env var (user override)
#    2. Standard LLVM installer location  C:\Program Files\LLVM
#    3. Anything named clang++ already on PATH - accepted only if MSVC ABI
# ---------------------------------------------------------------------------

CLANGPP=""

# Helper: check if a clang++ binary targets the MSVC ABI
is_msvc_abi() {
    local bin="$1"
    local target
    target=$("$bin" -dumpmachine 2>/dev/null || true)
    [[ "$target" == *"windows-msvc"* ]]
}

# 1. User-supplied LLVM_PATH
if [[ -n "${LLVM_PATH:-}" ]]; then
    candidate="${LLVM_PATH}/bin/clang++.exe"
    if [[ -x "$candidate" ]]; then
        if is_msvc_abi "$candidate"; then
            CLANGPP="$candidate"
        else
            die "LLVM_PATH is set to '${LLVM_PATH}' but its clang++ targets $("$candidate" -dumpmachine) (MinGW ABI)." \
                "Set LLVM_PATH to the standalone LLVM Windows installer root instead." \
                "Download: https://github.com/llvm/llvm-project/releases"
        fi
    else
        die "LLVM_PATH is set to '${LLVM_PATH}' but '${candidate}' does not exist."
    fi
fi

# 2. Standard standalone LLVM installer location
if [[ -z "$CLANGPP" ]]; then
    for candidate in \
        "/c/Program Files/LLVM/bin/clang++.exe" \
        "/c/LLVM/bin/clang++.exe"
    do
        if [[ -x "$candidate" ]] && is_msvc_abi "$candidate"; then
            CLANGPP="$candidate"
            break
        fi
    done
fi

# 3. PATH - only accept if it's MSVC ABI
if [[ -z "$CLANGPP" ]] && command -v clang++ &>/dev/null; then
    candidate=$(command -v clang++)
    if is_msvc_abi "$candidate"; then
        CLANGPP="$candidate"
    else
        target=$("$candidate" -dumpmachine 2>/dev/null || echo "unknown")
        cat >&2 <<EOF

ERROR: Found clang++ on PATH at '$candidate'
       but it targets '$target' (MinGW / GNU ABI).

PhysX 3.3.4 ships MSVC-ABI static libraries (vc14win64). The MinGW-ABI clang++
from MSYS2 (clang64 / ucrt64 / mingw64 packages) cannot link against them.

You need the standalone LLVM Windows installer, whose clang++ targets
x86_64-pc-windows-msvc and can link MSVC .lib files directly.

Install it from:
  https://github.com/llvm/llvm-project/releases
  (download the file named  LLVM-<version>-win64.exe)

After installation (default path: C:\Program Files\LLVM), either:
  - Add  C:\Program Files\LLVM\bin  to your Windows PATH, or
  - Set the LLVM_PATH environment variable:
      export LLVM_PATH="C:/Program Files/LLVM"

EOF
        exit 1
    fi
fi

if [[ -z "$CLANGPP" ]]; then
    cat >&2 <<EOF

ERROR: No MSVC-ABI clang++ found.

PhysX 3.3.4 ships MSVC-ABI static libraries (vc14win64). You need a clang++
that targets x86_64-pc-windows-msvc, provided by the standalone LLVM Windows
installer (NOT the MSYS2 clang64/ucrt64/mingw64 packages).

Install it from:
  https://github.com/llvm/llvm-project/releases
  (download the file named  LLVM-<version>-win64.exe)

After installation (default path: C:\Program Files\LLVM), either:
  - Add  C:\Program Files\LLVM\bin  to your Windows PATH, or
  - Set the LLVM_PATH environment variable before running this script:
      export LLVM_PATH="C:/Program Files/LLVM"
      bash build.sh

EOF
    exit 1
fi

echo "Using compiler : $CLANGPP"
"$CLANGPP" --version

# ---------------------------------------------------------------------------
#  Locate cmake
# ---------------------------------------------------------------------------
if command -v cmake &>/dev/null; then
    CMAKE=$(command -v cmake)
elif [[ -x "/c/Program Files/CMake/bin/cmake.exe" ]]; then
    CMAKE="/c/Program Files/CMake/bin/cmake.exe"
else
    die "cmake not found. Install it from https://cmake.org/download/"
fi

echo "Using CMake    : $CMAKE"
"$CMAKE" --version | head -1

# ---------------------------------------------------------------------------
#  Locate rc.exe  (Windows SDK resource compiler, required by CMake's
#  Windows-Clang platform module even though we have no .rc files)
# ---------------------------------------------------------------------------
RC_COMPILER=""

# Check environment variable first
if [[ -n "${RC:-}" && -x "$(cygpath -u "${RC}")" ]]; then
    RC_COMPILER="${RC}"
fi

# Search Windows Kits for x64 rc.exe, prefer newest SDK version
if [[ -z "$RC_COMPILER" ]]; then
    WIN_KITS_POSIX="$(cygpath -u "C:/Program Files (x86)/Windows Kits/10/bin")"
    if [[ -d "$WIN_KITS_POSIX" ]]; then
        # Sort version directories descending, take the first rc.exe found
        RC_FOUND=$(find "$WIN_KITS_POSIX" -name "rc.exe" -path "*/x64/*" 2>/dev/null \
                   | sort -rV | head -1)
        if [[ -n "$RC_FOUND" ]]; then
            RC_COMPILER="$(cygpath -m "$RC_FOUND")"
        fi
    fi
fi

if [[ -z "$RC_COMPILER" ]]; then
    die "rc.exe not found. Ensure the Windows SDK is installed (it ships with Visual Studio " \
        "or the standalone Build Tools). You can also set the RC environment variable to its " \
        "full path."
fi

echo "Using rc.exe   : $RC_COMPILER"

# ---------------------------------------------------------------------------
#  Locate make
# ---------------------------------------------------------------------------
if command -v make &>/dev/null; then
    MAKE=$(command -v make)
elif [[ -x "/c/msys64/usr/bin/make.exe" ]]; then
    MAKE="/c/msys64/usr/bin/make.exe"
else
    die "make not found. Install it via MSYS2: pacman -S make"
fi

# ---------------------------------------------------------------------------
#  Parse arguments
# ---------------------------------------------------------------------------
BUILD_TYPE="Debug"
PHYSX_SDK_PATH="${PHYSX_SDK_PATH:-C:/PhysX3.3.4}"
CLEAN=0
JOBS=$(nproc 2>/dev/null || echo 4)

usage() {
    cat <<EOF
Usage: $(basename "$0") [options]

Options:
  -r, --release            Build in Release mode (default: Debug)
  -p, --physx PATH         Path to PhysX 3.3.4 SDK root
                           (default: \$PHYSX_SDK_PATH or C:/PhysX3.3.4)
  -j, --jobs N             Parallel jobs (default: $JOBS)
  -c, --clean              Delete the build directory before configuring
  -h, --help               Show this help message

Environment variables:
  PHYSX_SDK_PATH           PhysX 3.3.4 SDK root (same as --physx)
  LLVM_PATH                Root of the standalone LLVM installation
                           (e.g. C:/Program Files/LLVM)
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -r|--release)   BUILD_TYPE="Release"; shift ;;
        -p|--physx)     PHYSX_SDK_PATH="$2"; shift 2 ;;
        -j|--jobs)      JOBS="$2"; shift 2 ;;
        -c|--clean)     CLEAN=1; shift ;;
        -h|--help)      usage; exit 0 ;;
        *)              die "Unknown option: $1  (run with --help for usage)" ;;
    esac
done

# ---------------------------------------------------------------------------
#  Validate PhysX path
# ---------------------------------------------------------------------------
# Normalise to a POSIX path the shell can test.
# cygpath -u handles all forms: C:\foo, C:/foo, /c/foo, etc.
PX_NORM="$(cygpath -u "${PHYSX_SDK_PATH}")"
PX_HEADER_WIN="${PHYSX_SDK_PATH}/Include/PxPhysicsAPI.h"
PX_HEADER_UNIX="${PX_NORM}/Include/PxPhysicsAPI.h"

[[ -f "$PX_HEADER_UNIX" ]] || die \
    "PxPhysicsAPI.h not found at '${PX_HEADER_WIN}'." \
    "Set PHYSX_SDK_PATH or pass --physx <path> pointing at your PhysX 3.3.4 root."

# ---------------------------------------------------------------------------
#  Configure
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build"

if [[ $CLEAN -eq 1 && -d "$BUILD_DIR" ]]; then
    echo "Cleaning build directory: $BUILD_DIR"
    rm -rf "$BUILD_DIR"
fi

mkdir -p "$BUILD_DIR"

echo ""
echo "Configuring (${BUILD_TYPE})..."
"$CMAKE" \
    -S "$SCRIPT_DIR" \
    -B "$BUILD_DIR" \
    -G "Unix Makefiles" \
    -DCMAKE_BUILD_TYPE="$BUILD_TYPE" \
    -DCMAKE_CXX_COMPILER="$CLANGPP" \
    -DCMAKE_RC_COMPILER="$RC_COMPILER" \
    -DPHYSX_SDK_PATH="$PHYSX_SDK_PATH" \
    -DCMAKE_EXPORT_COMPILE_COMMANDS=ON

# Symlink compile_commands.json to the project root so clangd finds it
COMPILE_COMMANDS_SRC="${BUILD_DIR}/compile_commands.json"
COMPILE_COMMANDS_DST="${SCRIPT_DIR}/compile_commands.json"
if [[ -f "$COMPILE_COMMANDS_SRC" ]]; then
    if ln -sf "${COMPILE_COMMANDS_SRC}" "${COMPILE_COMMANDS_DST}" 2>/dev/null; then
        echo "Linked compile_commands.json -> build/compile_commands.json"
    else
        cp "${COMPILE_COMMANDS_SRC}" "${COMPILE_COMMANDS_DST}"
        echo "Copied compile_commands.json to project root"
    fi
fi

# ---------------------------------------------------------------------------
#  Build
# ---------------------------------------------------------------------------
echo ""
echo "Building with $JOBS parallel job(s)..."
"$CMAKE" --build "$BUILD_DIR" --config "$BUILD_TYPE" -- -j"$JOBS"

# ---------------------------------------------------------------------------
#  Report
# ---------------------------------------------------------------------------
EXE="${SCRIPT_DIR}/build/PhysicsMeshCooker.exe"
if [[ -f "$EXE" ]]; then
    echo ""
    echo "Build succeeded!"
    echo "  Executable : $EXE"
    echo ""
    echo "Usage (from cmd.exe or PowerShell - DLLs are found automatically):"
    echo "  build\\PhysicsMeshCooker.exe <input.obj> <output.csm>"
    echo ""
    echo "Usage (from MSYS2 bash - build/ must be on PATH so Windows finds the DLLs):"
    echo "  PATH=\"\${SCRIPT_DIR}/build:\$PATH\" build/PhysicsMeshCooker.exe <input.obj> <output.csm>"
    echo ""
    echo "Tip: add the following to ~/.bashrc to make this permanent:"
    echo "  export PATH=\"${BUILD_DIR}:\$PATH\""
else
    die "Build appeared to succeed but executable not found at: $EXE"
fi
