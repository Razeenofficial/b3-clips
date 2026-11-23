"""Start B3 Clips like a desktop app.

Used by the "B3 Clips" desktop shortcut:  .venv\\Scripts\\pythonw.exe -m clipper.launch
- If B3 Clips is already running, just open its window.
- Otherwise start the server hidden (no console; output goes to logs/clipper.log) and open the
  UI in its own Edge/Chrome "app" window. The server stops itself a few minutes after the window
  is closed, once nothing is transcribing or rendering (see app.py watchdog).
"""
import ctypes
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = int(os.environ.get("CLIPPER_PORT", "8790"))
URL = f"http://127.0.0.1:{PORT}"

if os.name == "nt":
    # pythonw has no console, so every ffmpeg / yt-dlp child would flash its own console window:
    # start all child processes without a window.
    _orig_init = subprocess.Popen.__init__

    def _no_window_init(self, *args, **kwargs):
        kwargs["creationflags"] = kwargs.get("creationflags", 0) | 0x08000000  # CREATE_NO_WINDOW
        _orig_init(self, *args, **kwargs)

    subprocess.Popen.__init__ = _no_window_init


def _is_clipper() -> bool:
    import httpx
    try:
        return httpx.get(URL + "/api/ping", timeout=1.5).json().get("app") == "clipper"
    except Exception:
        return False


def _port_taken() -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", PORT)) == 0


def _message(text: str):
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(0, text, "B3 Clips", 0x40)
    else:
        print(text)


def open_window():
    candidates = [shutil.which("msedge"), shutil.which("chrome")]
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")):
        if base:
            candidates += [Path(base) / "Microsoft/Edge/Application/msedge.exe", Path(base) / "Google/Chrome/Application/chrome.exe"]
    for exe in candidates:
        if exe and Path(exe).exists():
            subprocess.Popen([str(exe), f"--app={URL}", "--window-size=1400,920"])
            return
    webbrowser.open(URL)


def main():
    os.chdir(ROOT)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    if _is_clipper():
        open_window()
        return
    if _port_taken():
        _message(f"Port {PORT} is used by another program, so B3 Clips cannot start.\n"
                 f"Close that program, or set the CLIPPER_PORT environment variable to another port.")
        return

    logs = ROOT / "logs"
    logs.mkdir(exist_ok=True)
    log = open(logs / "clipper.log", "a", buffering=1, encoding="utf-8", errors="replace")
    sys.stdout = sys.stderr = log
    print(f"\n===== B3 Clips started {time.strftime('%Y-%m-%d %H:%M:%S')} =====", flush=True)
    os.environ["CLIPPER_AUTOSTOP"] = "1"

    def open_when_ready():
        for _ in range(120):
            if _is_clipper():
                open_window()
                return
            time.sleep(0.5)
        _message("B3 Clips did not start. See logs\\clipper.log in the B3 Clips folder.")

    threading.Thread(target=open_when_ready, daemon=True).start()
    import logging
    logging.basicConfig(stream=log, level=logging.WARNING, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    import uvicorn
    uvicorn.run("clipper.app:app", host="127.0.0.1", port=PORT, log_level="warning", log_config=None)


if __name__ == "__main__":
    main()
