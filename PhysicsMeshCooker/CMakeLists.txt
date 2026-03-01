cmake_minimum_required(VERSION 3.20)
project(PhysicsMeshCooker LANGUAGES CXX)

# ---------------------------------------------------------------------------
#  Compiler enforcement
# ---------------------------------------------------------------------------
if(NOT CMAKE_CXX_COMPILER_ID MATCHES "Clang")
    message(FATAL_ERROR "This project must be built with Clang. "
        "Pass -DCMAKE_CXX_COMPILER=clang++ to CMake, pointing at the "
        "LLVM Windows installer binary (x86_64-pc-windows-msvc target), "
        "NOT the MSYS2 clang64 package (which targets x86_64-w64-windows-gnu "
        "and cannot link MSVC .lib files).\n"
        "Download the LLVM installer from: https://github.com/llvm/llvm-project/releases")
endif()

# Reject MinGW/GNU-ABI clang - it cannot link MSVC .lib files (PhysX 3.3.4)
if(CMAKE_CXX_COMPILER_TARGET MATCHES "windows-gnu")
    message(FATAL_ERROR
        "The detected clang++ targets '${CMAKE_CXX_COMPILER_TARGET}' (MinGW ABI).\n"
        "PhysX 3.3.4 ships MSVC ABI .lib files, which are incompatible with the "
        "MinGW ABI used by the MSYS2 clang64/ucrt64/mingw64 toolchains.\n"
        "Install the standalone LLVM Windows package instead:\n"
        "  https://github.com/llvm/llvm-project/releases\n"
        "Its clang++ defaults to the x86_64-pc-windows-msvc target and can link "
        "against MSVC-built static libraries directly.")
endif()

# ---------------------------------------------------------------------------
#  PhysX SDK path  (override with -DPHYSX_SDK_PATH=... or env var)
# ---------------------------------------------------------------------------
if(DEFINED ENV{PHYSX_SDK_PATH})
    set(PHYSX_SDK_PATH_DEFAULT "$ENV{PHYSX_SDK_PATH}")
else()
    set(PHYSX_SDK_PATH_DEFAULT "C:/PhysX3.3.4")
endif()

set(PHYSX_SDK_PATH "${PHYSX_SDK_PATH_DEFAULT}" CACHE PATH
    "Root directory of the PhysX 3.3.4 SDK")

set(PHYSX_INCLUDE_DIR "${PHYSX_SDK_PATH}/Include")
set(PHYSX_LIB_DIR     "${PHYSX_SDK_PATH}/Lib/vc14win64")

# Validate that the SDK is actually there
if(NOT EXISTS "${PHYSX_INCLUDE_DIR}/PxPhysicsAPI.h")
    message(FATAL_ERROR
        "PxPhysicsAPI.h not found under ${PHYSX_INCLUDE_DIR}\n"
        "Set PHYSX_SDK_PATH to your PhysX 3.3.4 installation root, e.g.:\n"
        "  cmake -DPHYSX_SDK_PATH=C:/PhysX3.3.4 ...")
endif()

# ---------------------------------------------------------------------------
#  Configuration-specific library suffix
#
#  The vc14win64 SDK only ships DEBUG-suffix builds of the PhysX libs.
#  There are no Release/Profile variants in this distribution, so we always
#  link the DEBUG libs regardless of CMAKE_BUILD_TYPE. This is fine for a
#  command-line cooking tool - the PhysX debug DLLs impose no meaningful
#  runtime overhead for offline mesh processing.
# ---------------------------------------------------------------------------
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

set(PX_LIB_SUFFIX "DEBUG")
set(PX_LIB_PROFILE_SUFFIX "DEBUG")

# ---------------------------------------------------------------------------
#  Target
# ---------------------------------------------------------------------------
add_executable(PhysicsMeshCooker
    src/PhysicsMeshCooker.cpp
)

set_target_properties(PhysicsMeshCooker PROPERTIES
    CXX_STANDARD          17
    CXX_STANDARD_REQUIRED ON
    CXX_EXTENSIONS        OFF
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_SOURCE_DIR}/build"
    # Match the runtime library used by the PhysX 3.3.4 vc14win64 static libs:
    #   Debug   -> MTd  (static debug CRT)
    #   Release -> MT   (static release CRT)
    # Using the dynamic CRT (MD/MDd) causes a /failifmismatch linker error.
    MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>"
)

# ---------------------------------------------------------------------------
#  Include paths
# ---------------------------------------------------------------------------
target_include_directories(PhysicsMeshCooker PRIVATE
    "${PHYSX_INCLUDE_DIR}"
)

# ---------------------------------------------------------------------------
#  Preprocessor definitions
#
#  When targeting x86_64-pc-windows-msvc, clang++ defines _MSC_VER, so
#  PxPreprocessor.h sets PX_WINDOWS and PX_X64 automatically via the PX_VC
#  branch. No need to define them manually (doing so causes -Wmacro-redefined).
# ---------------------------------------------------------------------------
target_compile_definitions(PhysicsMeshCooker PRIVATE
    # PhysX static lib mode - must match how the .lib files were built
    PX_PHYSX_STATIC_LIB
    # Standard Windows / CRT defines
    _WIN64
    _CONSOLE
    _CRT_SECURE_NO_WARNINGS
    UNICODE
    _UNICODE
    $<$<CONFIG:Debug>:_DEBUG>
    $<$<CONFIG:Release>:NDEBUG>
)

# ---------------------------------------------------------------------------
#  Compiler flags
# ---------------------------------------------------------------------------
target_compile_options(PhysicsMeshCooker PRIVATE
    # MSVC compatibility - required because PhysX 3.3.4 headers use MSVC
    # extensions: __declspec(align/dllimport/noinline/noalias/deprecated),
    # __forceinline, __cdecl, __pragma(pack(...)), and __int64.
    # -fms-extensions and -fms-compatibility are implied by the
    # x86_64-pc-windows-msvc target, but listed explicitly for clarity.
    -fms-extensions
    -fms-compatibility

    # Warnings
    -Wall
    -Wextra
    -Wno-unused-parameter
    # Warnings that fire in PhysX 3.3.4 headers - not our code
    -Wno-ignored-pragma-intrinsic
    -Wno-pragma-pack
    -Wno-unknown-pragmas
    -Wno-ignored-attributes
    -Wno-microsoft-anon-tag
    -Wno-microsoft-enum-forward-reference
    -Wno-return-type-c-linkage

    $<$<CONFIG:Debug>:-g -O0>
    $<$<CONFIG:Release>:-O2>
)

# ---------------------------------------------------------------------------
#  Linker: PhysX import libs  (vc14win64 / MSVC ABI build)
#
#  PhysX3, PhysX3Common, and PhysX3Cooking ship as DLLs with import libs.
#  PhysX3Extensions and PhysXProfileSDK are fully static.
# ---------------------------------------------------------------------------
set(PHYSX_BIN_DIR "${PHYSX_SDK_PATH}/Bin/vc14win64")

target_link_directories(PhysicsMeshCooker PRIVATE
    "${PHYSX_LIB_DIR}"
)

target_link_libraries(PhysicsMeshCooker PRIVATE
    "PhysX3${PX_LIB_SUFFIX}_x64"
    "PhysX3Common${PX_LIB_SUFFIX}_x64"
    "PhysX3Cooking${PX_LIB_SUFFIX}_x64"
    "PhysX3Extensions${PX_LIB_SUFFIX}"
    "PhysXProfileSDK${PX_LIB_PROFILE_SUFFIX}"
)

# ---------------------------------------------------------------------------
#  Post-build: copy PhysX DLLs next to the executable
#
#  PhysX3, PhysX3Common, and PhysX3Cooking are the core DLLs.
#  nvToolsExt64_1.dll is an NVIDIA profiling library that PhysX3DEBUG depends on.
# ---------------------------------------------------------------------------
set(PHYSX_RUNTIME_DLLS
    "${PHYSX_BIN_DIR}/PhysX3${PX_LIB_SUFFIX}_x64.dll"
    "${PHYSX_BIN_DIR}/PhysX3Common${PX_LIB_SUFFIX}_x64.dll"
    "${PHYSX_BIN_DIR}/PhysX3Cooking${PX_LIB_SUFFIX}_x64.dll"
    "${PHYSX_BIN_DIR}/nvToolsExt64_1.dll"
)

foreach(DLL ${PHYSX_RUNTIME_DLLS})
    add_custom_command(TARGET PhysicsMeshCooker POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${DLL}"
            "$<TARGET_FILE_DIR:PhysicsMeshCooker>"
        COMMENT "Copying ${DLL} to output directory"
    )
endforeach()

# ---------------------------------------------------------------------------
#  Export compile_commands.json for clangd / IDEs
# ---------------------------------------------------------------------------
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
