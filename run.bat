@echo off
rem Start B3 Clips on http://127.0.0.1:8790 (close this window to stop it)
cd /d "%~dp0"
start "" http://127.0.0.1:8790
".venv\Scripts\python.exe" -m uvicorn clipper.app:app --host 127.0.0.1 --port 8790
