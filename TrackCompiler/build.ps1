# Build OMTT TrackCompiler Blender extension package
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$sourceDir = Join-Path $scriptDir "trackcompiler"
$outputDir = $scriptDir

if (-not (Test-Path (Join-Path $sourceDir "blender_manifest.toml"))) {
    throw "Missing blender_manifest.toml in: $sourceDir"
}

$blenderRoots = @(
    "${env:ProgramFiles}\Blender Foundation",
    "${env:ProgramFiles(x86)}\Blender Foundation"
)

$blender = Get-ChildItem -Path $blenderRoots -Filter "blender.exe" -Recurse -ErrorAction SilentlyContinue |
    Sort-Object FullName -Descending |
    Select-Object -First 1 -ExpandProperty FullName

if (-not $blender) {
    throw "Could not find blender.exe under Program Files\Blender Foundation"
}

Write-Host "Using Blender: $blender"
Write-Host "Source: $sourceDir"
Write-Host "Output: $outputDir"

& $blender --factory-startup --command extension build --source-dir $sourceDir --output-dir $outputDir --verbose

if ($LASTEXITCODE -ne 0) {
    throw "Extension build failed with exit code $LASTEXITCODE"
}

$zip = Get-ChildItem $outputDir -Filter "trackcompiler-*.zip" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

Write-Host "Created: $($zip.FullName)"
