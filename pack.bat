@echo off
rem Make dist\B3Clips.zip for another PC.  "pack.bat keys" also includes your AI keys (settings.json).
cd /d "%~dp0"
if /i "%1"=="keys" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\pack.ps1" -IncludeKeys
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\pack.ps1"
)
echo.
pause
