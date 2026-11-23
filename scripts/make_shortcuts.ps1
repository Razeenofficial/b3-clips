# Create "B3 Clips" shortcuts on the Desktop and in the Start menu.
# They run the app launcher with the project's own Python (no console window).
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$pythonw = Join-Path $root ".venv\Scripts\pythonw.exe"
$icon = Join-Path $root "assets\clipper.ico"
if (-not (Test-Path $pythonw)) { throw "Missing $pythonw - run install.bat first." }

$shell = New-Object -ComObject WScript.Shell
# remove shortcuts from before the rename to "B3 Clips"
foreach ($old in @((Join-Path ([Environment]::GetFolderPath("Desktop")) "Clipper.lnk"),
                   (Join-Path ([Environment]::GetFolderPath("Programs")) "Clipper.lnk"))) {
    if ((Test-Path $old) -and ($shell.CreateShortcut($old).TargetPath -eq $pythonw)) { Remove-Item $old -Force }
}
$targets = @(
    (Join-Path ([Environment]::GetFolderPath("Desktop")) "B3 Clips.lnk"),
    (Join-Path ([Environment]::GetFolderPath("Programs")) "B3 Clips.lnk")
)
foreach ($path in $targets) {
    $lnk = $shell.CreateShortcut($path)
    $lnk.TargetPath = $pythonw
    $lnk.Arguments = "-m clipper.launch"
    $lnk.WorkingDirectory = $root
    $lnk.IconLocation = "$icon,0"
    $lnk.Description = "B3 Clips - turn long videos into vertical clips"
    $lnk.Save()
    Write-Host "Shortcut: $path"
}
