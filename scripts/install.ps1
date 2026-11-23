# B3 Clips installer for a Windows PC. Safe to run again: it skips what is already installed.
# Installs (only if missing): Python, FFmpeg, Node.js (via winget), Python packages (.venv),
# the YuNet face model and the Whisper speech model, then creates Desktop/Start menu shortcuts.
param([switch]$NoShortcuts)   # -NoShortcuts: install only (used for testing a second copy)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Step($text) { Write-Host ""; Write-Host "==> $text" -ForegroundColor Yellow }
function Ok($text) { Write-Host "    OK  $text" -ForegroundColor Green }
function RefreshPath {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}
function HasCmd($name) { return [bool](Get-Command $name -ErrorAction SilentlyContinue) }
function WingetInstall($id, $label) {
    if (-not (HasCmd "winget")) {
        throw "winget is not available. Install $label manually, then run install.bat again."
    }
    Write-Host "    Installing $label with winget (this can take a few minutes)..."
    winget install -e --id $id --accept-package-agreements --accept-source-agreements --silent
    RefreshPath
}

Write-Host "B3 Clips installer - folder: $root" -ForegroundColor Cyan

# ---------------------------------------------------------------- Python
Step "Python 3.11 or newer"
function FindPython {
    $ErrorActionPreference = "Continue"   # "py -3.13" prints an error when that version is absent; that is fine here
    foreach ($v in @("3.14", "3.13", "3.12", "3.11")) {
        if (HasCmd "py") {
            $exe = & py "-$v" -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $exe) { return $exe.Trim() }
        }
    }
    foreach ($p in @("$env:LOCALAPPDATA\Programs\Python\Python312\python.exe", "C:\Python314\python.exe", "C:\Python312\python.exe")) {
        if (Test-Path $p) { return $p }
    }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source -notlike "*WindowsApps*") {
        $ok = & $cmd.Source -c "import sys; print(sys.version_info >= (3, 11))" 2>$null
        if ($ok -eq "True") { return $cmd.Source }
    }
    return $null
}
$venvPy = Join-Path $root ".venv\Scripts\python.exe"
if (Test-Path $venvPy) {
    Ok "using existing .venv"
} else {
    $python = FindPython
    if (-not $python) {
        WingetInstall "Python.Python.3.12" "Python 3.12"
        $python = FindPython
    }
    if (-not $python) { throw "Python was not found after installing. Restart the PC and run install.bat again." }
    Ok $python
    Step "Creating the Python environment (.venv)"
    & $python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Could not create .venv" }
    Ok ".venv created"
}

# ---------------------------------------------------------------- FFmpeg
Step "FFmpeg (video tool)"
if (-not (HasCmd "ffmpeg")) { WingetInstall "Gyan.FFmpeg" "FFmpeg" }
if (HasCmd "ffmpeg") { Ok (Get-Command ffmpeg).Source } else { throw "FFmpeg is still missing. Restart the PC and run install.bat again." }

# ---------------------------------------------------------------- JavaScript runtime for yt-dlp
Step "Node.js (needed by yt-dlp for YouTube)"
if (-not ((HasCmd "node") -or (HasCmd "deno"))) { WingetInstall "OpenJS.NodeJS.LTS" "Node.js" }
if ((HasCmd "node") -or (HasCmd "deno")) { Ok "found" } else { Write-Host "    WARNING: no Node.js/Deno found; some YouTube downloads may fail." -ForegroundColor Red }

# ---------------------------------------------------------------- Python packages
Step "Python packages (yt-dlp, faster-whisper, OpenCV, FastAPI...)"
& $venvPy -m pip install --upgrade pip --quiet
& $venvPy -m pip install -r requirements.txt --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "    Exact versions failed for this Python; installing the newest compatible versions instead..."
    $names = Get-Content requirements.txt | Where-Object { $_ -and -not $_.StartsWith("#") } | ForEach-Object { ($_ -split "==")[0] }
    & $venvPy -m pip install @names --quiet
    if ($LASTEXITCODE -ne 0) { throw "Installing Python packages failed. See the messages above." }
}
& $venvPy -c "import cv2, faster_whisper, fastapi, uvicorn, httpx, yt_dlp; print('    OK  packages import')"
if ($LASTEXITCODE -ne 0) { throw "Packages did not import correctly." }

# ---------------------------------------------------------------- models
Step "Face detection model (YuNet)"
$yunet = Join-Path $root "models\face_detection_yunet_2023mar.onnx"
if (-not (Test-Path $yunet)) {
    New-Item -ItemType Directory -Force (Join-Path $root "models") | Out-Null
    Invoke-WebRequest -UseBasicParsing -OutFile $yunet "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
}
Ok $yunet

Step "Speech-to-text model (Whisper small.en, about 500 MB, downloaded once)"
& $venvPy -c "from faster_whisper import WhisperModel; WhisperModel('small.en', device='cpu', compute_type='int8'); print('    OK  Whisper model ready')"
if ($LASTEXITCODE -ne 0) { Write-Host "    WARNING: could not pre-download the Whisper model; it will download on the first video." -ForegroundColor Red }

# ---------------------------------------------------------------- icon + shortcuts
Step "Desktop and Start menu shortcuts"
if (-not (Test-Path (Join-Path $root "assets\clipper.ico"))) { & $venvPy scripts\make_icon.py }
if ($NoShortcuts) { Write-Host "    skipped (-NoShortcuts)" } else {
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "make_shortcuts.ps1")
}

Write-Host ""
Write-Host "B3 Clips is installed. Double-click the 'B3 Clips' icon on your Desktop to start it." -ForegroundColor Cyan
Write-Host "Add your AI provider keys in B3 Clips > Settings (they are not copied between PCs unless you copy settings.json)."
