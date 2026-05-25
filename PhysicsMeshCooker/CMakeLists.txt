cmake_minimum_required(VERSION 3.20)
project(PhysicsMeshCooker LANGUAGES CXX)

set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

if(NOT CMAKE_CXX_COMPILER_ID MATCHES "Clang")
    message(FATAL_ERROR
        "This project must be built with Clang (LLVM Windows installer). "
        "Set -DCMAKE_CXX_COMPILER=clang++.")
endif()

if(CMAKE_CXX_COMPILER_TARGET MATCHES "windows-gnu")
    message(FATAL_ERROR
        "Detected MinGW ABI target '${CMAKE_CXX_COMPILER_TARGET}'. "
        "PhysX 3.3.4 vc14win64 libs require the MSVC ABI clang toolchain.")
endif()

set(PHYSX_SDK_PATH_DEFAULT "C:/PhysX3.3.4")
if(DEFINED ENV{PHYSX_SDK_PATH})
    set(PHYSX_SDK_PATH_DEFAULT "$ENV{PHYSX_SDK_PATH}")
endif()
set(PHYSX_SDK_PATH "${PHYSX_SDK_PATH_DEFAULT}" CACHE PATH "PhysX 3.3.4 root")

set(PHYSX_INCLUDE_DIR "${PHYSX_SDK_PATH}/Include")
set(PHYSX_LIB_DIR "${PHYSX_SDK_PATH}/Lib/vc14win64")
set(PHYSX_BIN_DIR "${PHYSX_SDK_PATH}/Bin/vc14win64")

if(NOT EXISTS "${PHYSX_INCLUDE_DIR}/PxPhysicsAPI.h")
    message(FATAL_ERROR
        "PxPhysicsAPI.h not found under ${PHYSX_INCLUDE_DIR}. "
        "Set PHYSX_SDK_PATH to your PhysX 3.3.4 root.")
endif()

if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

set(PX_SUFFIX "DEBUG")
set(TARGET_NAME PhysicsMeshCooker)

add_executable(${TARGET_NAME} src/PhysicsMeshCooker.cpp)

set_target_properties(${TARGET_NAME} PROPERTIES
    CXX_STANDARD 17
    CXX_STANDARD_REQUIRED ON
    CXX_EXTENSIONS OFF
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_SOURCE_DIR}/build"
    MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>"
)

target_include_directories(${TARGET_NAME} PRIVATE "${PHYSX_INCLUDE_DIR}")

target_compile_definitions(${TARGET_NAME} PRIVATE
    PX_PHYSX_STATIC_LIB
    _WIN64
    _CONSOLE
    _CRT_SECURE_NO_WARNINGS
    UNICODE
    _UNICODE
    $<$<CONFIG:Debug>:_DEBUG>
    $<$<CONFIG:Release>:NDEBUG>
)

target_compile_options(${TARGET_NAME} PRIVATE
    -fms-extensions
    -fms-compatibility
    -Wall
    -Wextra
    -Wno-unused-parameter
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

target_link_directories(${TARGET_NAME} PRIVATE "${PHYSX_LIB_DIR}")
target_link_libraries(${TARGET_NAME} PRIVATE
    "PhysX3${PX_SUFFIX}_x64"
    "PhysX3Common${PX_SUFFIX}_x64"
    "PhysX3Cooking${PX_SUFFIX}_x64"
    "PhysX3Extensions${PX_SUFFIX}"
    "PhysXProfileSDK${PX_SUFFIX}"
)

set(PHYSX_RUNTIME_DLLS
    "${PHYSX_BIN_DIR}/PhysX3${PX_SUFFIX}_x64.dll"
    "${PHYSX_BIN_DIR}/PhysX3Common${PX_SUFFIX}_x64.dll"
    "${PHYSX_BIN_DIR}/PhysX3Cooking${PX_SUFFIX}_x64.dll"
    "${PHYSX_BIN_DIR}/nvToolsExt64_1.dll"
)

foreach(DLL IN LISTS PHYSX_RUNTIME_DLLS)
    add_custom_command(TARGET ${TARGET_NAME} POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different "${DLL}" "$<TARGET_FILE_DIR:${TARGET_NAME}>"
        COMMENT "Copying ${DLL}"
    )
endforeach()
