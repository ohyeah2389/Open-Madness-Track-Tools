#!/usr/bin/env pwsh
# Builds standalone PackTrack.exe

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

pyinstaller --onefile --noupx --clean --name PackTrack pack_track.py

Write-Host "`nBuilt: $PSScriptRoot\dist\PackTrack.exe"
