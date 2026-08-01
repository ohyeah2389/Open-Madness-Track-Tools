param(
    [switch]$Release,
    [string]$PhysxSdkPath = $(if ($env:PHYSX_SDK_PATH) { $env:PHYSX_SDK_PATH } else { "C:/PhysX3.3.4" }),
    [string]$GameDir = "",
    [int]$Jobs = [Environment]::ProcessorCount,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

function Fail([string]$Message) {
    throw "ERROR: $Message"
}

function Assert-LastExit([string]$Step) {
    if ($LASTEXITCODE -ne 0) { Fail "$Step failed with exit code $LASTEXITCODE." }
}

function Test-MsvcAbiClang([string]$ClangPath) {
    if (-not (Test-Path $ClangPath)) { return $false }
    $target = & $ClangPath -dumpmachine 2>$null
    return $target -like "*windows-msvc*"
}

function Get-ClangPath {
    $candidates = @()
    if ($env:LLVM_PATH) { $candidates += (Join-Path $env:LLVM_PATH "bin/clang++.exe") }
    $candidates += @("C:/Program Files/LLVM/bin/clang++.exe", "C:/LLVM/bin/clang++.exe")

    foreach ($candidate in $candidates) {
        if (Test-MsvcAbiClang $candidate) { return $candidate }
    }

    $cmd = Get-Command clang++.exe -ErrorAction SilentlyContinue
    if ($cmd -and (Test-MsvcAbiClang $cmd.Source)) { return $cmd.Source }
    if ($cmd) {
        $target = & $cmd.Source -dumpmachine 2>$null
        Fail "Found clang++ at '$($cmd.Source)' but target '$target' is not MSVC ABI."
    }

    Fail "No MSVC-ABI clang++ found. Install LLVM Windows build and set LLVM_PATH if needed."
}

function Get-CMakePath {
    $cmd = Get-Command cmake.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $fallback = "C:/Program Files/CMake/bin/cmake.exe"
    if (Test-Path $fallback) { return $fallback }
    Fail "cmake not found."
}

function Get-NinjaPath {
    $cmd = Get-Command ninja.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $fallbacks = @(
        "$env:LOCALAPPDATA/Microsoft/WinGet/Links/ninja.exe",
        "C:/ProgramData/chocolatey/bin/ninja.exe",
        "C:/Program Files/Ninja/ninja.exe",
        "C:/Program Files/Microsoft Visual Studio/18/Community/Common7/IDE/CommonExtensions/Microsoft/CMake/Ninja/ninja.exe"
    )
    foreach ($candidate in $fallbacks) {
        if (Test-Path $candidate) { return $candidate }
    }
    Fail "ninja not found. Install with winget: winget install --id Ninja-build.Ninja -e"
}

function Get-RcPath {
    if ($env:RC -and (Test-Path $env:RC)) { return $env:RC }
    $kitsRoot = "C:/Program Files (x86)/Windows Kits/10/bin"
    if (-not (Test-Path $kitsRoot)) { Fail "Windows SDK rc.exe not found." }

    $versions = Get-ChildItem -Path $kitsRoot -Directory |
        Sort-Object { try { [version]$_.Name } catch { [version]"0.0.0.0" } } -Descending

    foreach ($version in $versions) {
        $candidate = Join-Path $version.FullName "x64/rc.exe"
        if (Test-Path $candidate) { return $candidate }
    }

    Fail "Windows SDK rc.exe not found."
}

$buildType = if ($Release) { "Release" } else { "Debug" }
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$buildDir = Join-Path $scriptDir "build"
$exePath = Join-Path $buildDir "PhysicsMeshCooker.exe"
$physxHeader = Join-Path $PhysxSdkPath "Include/PxPhysicsAPI.h"

if (-not (Test-Path $physxHeader)) {
    Fail "PxPhysicsAPI.h not found at '$physxHeader'. Set -PhysxSdkPath or PHYSX_SDK_PATH."
}

$clang = Get-ClangPath
$cmake = Get-CMakePath
$ninja = Get-NinjaPath
$rc = Get-RcPath
$clangCmake = $clang.Replace('\', '/')
$ninjaCmake = $ninja.Replace('\', '/')
$rcCmake = $rc.Replace('\', '/')

Write-Host "Using compiler : $clang"
& $clang --version
Assert-LastExit "clang --version"
Write-Host "Using CMake    : $cmake"
& $cmake --version | Select-Object -First 1
Assert-LastExit "cmake --version"
Write-Host "Using Ninja    : $ninja"
& $ninja --version
Assert-LastExit "ninja --version"
Write-Host "Using rc.exe   : $rc"

if ($Clean -and (Test-Path $buildDir)) {
    Write-Host "Cleaning build directory: $buildDir"
    Remove-Item -Recurse -Force $buildDir
}

New-Item -ItemType Directory -Force -Path $buildDir | Out-Null

Write-Host "`nConfiguring ($buildType)..."
& $cmake `
    -S $scriptDir `
    -B $buildDir `
    -G Ninja `
    -DCMAKE_MAKE_PROGRAM="$ninjaCmake" `
    -DCMAKE_BUILD_TYPE="$buildType" `
    -DCMAKE_CXX_COMPILER="$clangCmake" `
    -DCMAKE_RC_COMPILER="$rcCmake" `
    -DPHYSX_SDK_PATH="$PhysxSdkPath" `
    -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
Assert-LastExit "CMake configure"

Write-Host "`nBuilding with $Jobs parallel job(s)..."
& $cmake --build $buildDir --config $buildType -- -j $Jobs
Assert-LastExit "CMake build"

if (-not (Test-Path $exePath)) {
    Fail "Build appeared to succeed but executable not found at '$exePath'."
}

if ($Release) {
    $dllNames = @(
        "PhysX3_x64.dll",
        "PhysX3Common_x64.dll",
        "PhysX3Cooking_x64.dll",
        "nvToolsExt64_1.dll"
    )
    if ($GameDir) {
        if (-not (Test-Path $GameDir)) { Fail "GameDir not found: $GameDir" }
        Write-Host "`nCopying PhysX DLLs from game install..."
        foreach ($name in $dllNames) {
            $src = Join-Path $GameDir $name
            if (-not (Test-Path $src)) { Fail "Missing game DLL: $src" }
            Copy-Item -Force $src (Join-Path $buildDir $name)
            Write-Host "  Copied $name"
        }
    } else {
        $missing = @($dllNames | Where-Object { -not (Test-Path (Join-Path $buildDir $_)) })
        if ($missing.Count -gt 0) {
            Write-Host "`nRelease build links game PhysX DLL names. Copy these next to the exe:"
            foreach ($name in $missing) { Write-Host "  $name" }
            Write-Host "From your AMS2/PCARS2 install, or re-run with -GameDir <game root>."
        }
    }
}

Write-Host "`nBuild succeeded!"
Write-Host "  Executable : $exePath"
Write-Host "  Run: build\PhysicsMeshCooker.exe <input.obj> <output.csm>"
