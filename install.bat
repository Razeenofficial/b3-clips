@echo off
rem Install B3 Clips on this PC (Python, FFmpeg, Node.js, packages, models, shortcuts). Safe to run again.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install.ps1"
echo.
pause
