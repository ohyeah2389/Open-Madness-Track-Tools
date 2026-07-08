#!/usr/bin/env pwsh
# Builds standalone PackTrack.exe

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

pyinstaller --onefile --noupx --clean --name PackTrack --add-data "placeholder_seasonal.bff;." pack_track.py

Write-Host "`nBuilt: $PSScriptRoot\dist\PackTrack.exe"
