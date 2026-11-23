"""Video info, download, audio decode and transcription."""
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

import shutil

# yt-dlp needs a JavaScript runtime for YouTube; it enables deno by default, so add node when that is what's installed
YTDLP = [sys.executable, "-m", "yt_dlp", "--no-playlist"] + (["--js-runtimes", "node"] if shutil.which("node") and not shutil.which("deno") else [])
SR = 16000


def fetch_meta(url: str) -> dict:
    p = subprocess.run(YTDLP + ["--skip-download", "--dump-single-json", url],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode:
        raise RuntimeError("Could not read video info: " + p.stderr[-600:])
    m = json.loads(p.stdout)
    return {k: m.get(k) for k in ("title", "channel", "license", "duration", "webpage_url", "heatmap")}


def download(url: str, job_dir: Path) -> Path:
    out = job_dir / "source.mp4"
    p = subprocess.run(YTDLP + [
        "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080]/b",
        "--merge-output-format", "mp4", "--remux-video", "mp4",
        "-o", str(job_dir / "source.%(ext)s"), url],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode or not out.exists():
        raise RuntimeError("Download failed: " + (p.stderr or p.stdout)[-600:])
    return out


def probe_duration(path: Path) -> float:
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True)
    try:
        return float(p.stdout.strip())
    except ValueError:
        return 0.0


def decode_audio(path: Path) -> np.ndarray:
    # ffmpeg decode instead of PyAV: PyAV 19 breaks faster-whisper on Python 3.14
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


_models = {}


def _model(name: str):
    if name not in _models:
        from faster_whisper import WhisperModel
        _models[name] = WhisperModel(name, device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 4)
    return _models[name]


def transcribe(audio: np.ndarray, model_name: str, on_progress=None) -> list:
    lang = "en" if model_name.endswith(".en") else None
    segs, _ = _model(model_name).transcribe(audio, word_timestamps=True, vad_filter=True, language=lang)
    total = max(len(audio) / SR, 1)
    out = []
    for s in segs:
        out.append({"start": s.start, "end": s.end, "text": s.text.strip(),
                    "words": [{"w": w.word.strip(), "s": w.start, "e": w.end} for w in (s.words or [])]})
        if on_progress:
            on_progress(min(s.end / total, 1.0))
    return out
