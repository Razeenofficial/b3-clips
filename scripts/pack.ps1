# Make dist\B3Clips.zip to copy B3 Clips to another PC.
# Leaves out the Python environment (.venv, rebuilt by install.bat), your jobs, temp files and logs.
# settings.json (your AI keys) is left out unless you run:  pack.bat keys
param([switch]$IncludeKeys)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $root "dist"
$stage = Join-Path $env:TEMP ("clipper_pack_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force $dist, $stage | Out-Null

$excludeDirs = @(".venv", "jobs", "work", "logs", "dist", "clips", "__pycache__", ".claude", ".git", "memory", "reference")
$excludeFiles = @("*.pyc", "CLAUDE.md")
if (-not $IncludeKeys) { $excludeFiles += "settings.json" }
robocopy $root (Join-Path $stage "b3-clips") /E /NFL /NDL /NJH /NJS /NP /XD $excludeDirs /XF $excludeFiles | Out-Null

$zip = Join-Path $dist "B3Clips.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path (Join-Path $stage "b3-clips") -DestinationPath $zip
Remove-Item -Recurse -Force $stage
$mb = [math]::Round((Get-Item $zip).Length / 1MB, 1)
Write-Host "Created $zip ($mb MB)"
if ($IncludeKeys) { Write-Host "WARNING: this zip contains your API keys (settings.json). Do not share it." -ForegroundColor Red }
