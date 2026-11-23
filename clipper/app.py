"""B3 Clips local web server.

Run as an app: the "B3 Clips" desktop shortcut (clipper/launch.py), which stops itself when the window is closed.
Run for development: run.bat  (or  .venv\\Scripts\\python -m uvicorn clipper.app:app --port 8790), which never auto-stops.
"""
import os
import threading
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import captions, jobs, providers, render as render_mod, settings as cfg

app = FastAPI(title="B3 Clips")
STATIC = Path(__file__).parent / "static"
jobs.load_all()

# ---------- app lifecycle (auto-stop when the window is closed) ----------
# browsers slow timers in minimized windows to ~1/min, so allow a few missed beats
IDLE_STOP_SECONDS = int(os.environ.get("CLIPPER_IDLE_STOP", "180"))
_last_seen = time.time()


def _watchdog():
    while True:
        time.sleep(min(15, max(2, IDLE_STOP_SECONDS // 4)))
        if time.time() - _last_seen > IDLE_STOP_SECONDS and not jobs.is_busy():
            print(f"{time.strftime('%H:%M:%S')} B3 Clips window closed and nothing is processing: stopping.", flush=True)
            os._exit(0)


if os.environ.get("CLIPPER_AUTOSTOP") == "1":
    threading.Thread(target=_watchdog, daemon=True).start()


@app.get("/api/ping")
def ping():
    return {"app": "clipper", "busy": jobs.is_busy()}


@app.post("/api/heartbeat")
def heartbeat():
    global _last_seen
    _last_seen = time.time()
    return {"ok": True, "busy": jobs.is_busy(), "autostop": os.environ.get("CLIPPER_AUTOSTOP") == "1"}


class QuitIn(BaseModel):
    force: bool = False


@app.post("/api/quit")
def quit_app(q: QuitIn):
    if jobs.is_busy() and not q.force:
        return {"ok": False, "busy": True}
    threading.Timer(0.5, lambda: os._exit(0)).start()
    return {"ok": True}


def _job(job_id: str) -> dict:
    j = jobs.get(job_id)
    if not j:
        raise HTTPException(404, "Job not found")
    return j


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/favicon.ico")
def favicon():
    return FileResponse(Path(__file__).resolve().parent.parent / "assets" / "clipper.ico", media_type="image/x-icon")


# ---------- settings ----------
class GeneralIn(BaseModel):
    fallback: bool = True
    whisper_model: str = "small.en"
    max_candidates: int = 0
    min_score: float = 55
    min_len: int = 20
    max_len: int = 60


class ProviderIn(BaseModel):
    id: str | None = None
    name: str
    type: str = "custom"
    base_url: str = ""
    model: str = ""
    api_key: str | None = None
    clear_key: bool = False


def _settings_out():
    return {"settings": cfg.public(cfg.load()), "templates": cfg.TEMPLATES}


def _provider(pid: str) -> dict:
    p = cfg.get_provider(cfg.load(), pid)
    if not p:
        raise HTTPException(404, "No such provider")
    return p


@app.get("/api/settings")
def get_settings():
    return _settings_out()


@app.post("/api/settings")
def set_settings(s: GeneralIn):
    if not (5 <= s.min_len < s.max_len <= 180):
        raise HTTPException(400, "Clip lengths must satisfy 5 <= min < max <= 180")
    cfg.save_general(s.model_dump())
    return _settings_out()


@app.post("/api/providers")
def save_provider(p: ProviderIn):
    if p.type not in cfg.TEMPLATES:
        raise HTTPException(400, "Unknown provider type")
    if not p.name.strip() or not p.base_url.strip() or not p.model.strip():
        raise HTTPException(400, "Name, base URL and at least one model are required")
    saved = cfg.upsert_provider(p.model_dump())
    return {**_settings_out(), "saved_id": saved["id"]}


@app.delete("/api/providers/{pid}")
def delete_provider(pid: str):
    _provider(pid)
    cfg.delete_provider(pid)
    return _settings_out()


@app.post("/api/providers/{pid}/activate")
def activate_provider(pid: str):
    try:
        cfg.set_active(pid)
    except KeyError:
        raise HTTPException(404, "No such provider")
    return _settings_out()


@app.post("/api/providers/{pid}/test")
def test_provider(pid: str):
    try:
        return {"ok": True, "reply": providers.test(_provider(pid))[:200]}
    except HTTPException:
        raise
    except Exception as e:
        return {"ok": False, "error": str(e)[:600]}


class ModelsIn(BaseModel):
    base_url: str
    api_key: str | None = None
    id: str | None = None


@app.post("/api/providers/models")
def list_models(m: ModelsIn):
    """List models for the form: uses the typed key, or the saved key of an existing provider."""
    key = m.api_key or ((cfg.get_provider(cfg.load(), m.id) or {}).get("api_key") if m.id else "")
    try:
        return {"ok": True, "models": providers.list_models({"base_url": m.base_url, "api_key": key})}
    except Exception as e:
        return {"ok": False, "error": str(e)[:400]}


# ---------- jobs ----------
class JobIn(BaseModel):
    input: str
    rights_confirmed: bool = False


@app.post("/api/jobs")
def create_job(j: JobIn):
    if not j.input.strip():
        raise HTTPException(400, "Paste a link or a local file path")
    if not j.rights_confirmed:
        raise HTTPException(400, "Confirm you have the right to use this footage")
    return jobs.create(j.input)


@app.get("/api/jobs")
def list_jobs():
    return [{k: j.get(k) for k in ("id", "status", "stage", "meta", "created")} for j in jobs.all_jobs()]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    return _job(job_id)


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str):
    _job(job_id)
    try:
        jobs.delete(job_id)
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {"ok": True}


@app.post("/api/jobs/{job_id}/repick")
def repick(job_id: str):
    j = _job(job_id)
    if j["status"] == "running" or not (jobs.JOBS_DIR / job_id / "transcript.json").exists():
        raise HTTPException(400, "Job has no finished transcript yet")
    jobs.repick(j)
    return {"ok": True}


class RenderIn(BaseModel):
    start: float
    end: float
    label: str = ""
    layout: str = "auto"
    preset: str = "classic"
    position: str = "low"
    hook_title: str = ""
    captions: bool = True
    post_text: str = ""


@app.get("/api/options")
def options():
    return {"layouts": render_mod.LAYOUTS,
            "presets": {k: v["label"] for k, v in captions.PRESETS.items()},
            "positions": {"low": "Lower third", "middle": "Middle", "high": "Upper"}}


@app.post("/api/jobs/{job_id}/render")
def render(job_id: str, r: RenderIn):
    j = _job(job_id)
    if not j.get("source"):
        raise HTTPException(400, "Source video not ready")
    if not (0 <= r.start < r.end) or r.end - r.start > 180:
        raise HTTPException(400, "Bad start/end (max 180 s)")
    if r.layout not in render_mod.LAYOUTS or r.preset not in captions.PRESETS or r.position not in captions.POSITIONS:
        raise HTTPException(400, "Unknown layout, caption style or position")
    return jobs.render_clip(j, r.start, r.end, r.model_dump(exclude={"start", "end"}))


class CampaignIn(BaseModel):
    name: str = ""
    min_sec: float | None = None
    max_sec: float | None = None
    deadline: str = ""
    platforms: str = ""
    hashtags: str = ""
    mentions: str = ""
    phrase: str = ""
    credit: str = ""


@app.post("/api/jobs/{job_id}/campaign")
def campaign(job_id: str, c: CampaignIn):
    j = _job(job_id)
    jobs.set_campaign(j, c.model_dump())
    return j["campaign"]


class PostIn(BaseModel):
    text: str


@app.post("/api/jobs/{job_id}/clips/{n}/post")
def post_text(job_id: str, n: int, p: PostIn):
    c = jobs.set_post_text(_job(job_id), n, p.text)
    if not c:
        raise HTTPException(404, "No such clip")
    return c


@app.get("/api/jobs/{job_id}/source")
def source(job_id: str):
    j = _job(job_id)
    if not j.get("source") or not Path(j["source"]).exists():
        raise HTTPException(404, "No source video")
    return FileResponse(j["source"], media_type="video/mp4")


@app.get("/api/jobs/{job_id}/clips/{name}")
def clip_file(job_id: str, name: str):
    _job(job_id)
    folder = (jobs.JOBS_DIR / job_id / "clips").resolve()
    f = (folder / name).resolve()
    if f.parent != folder or not f.exists():
        raise HTTPException(404, "No such clip")
    return FileResponse(f, media_type="video/mp4", filename=name)


@app.post("/api/jobs/{job_id}/open-folder")
def open_folder(job_id: str):
    _job(job_id)
    folder = jobs.JOBS_DIR / job_id / "clips"
    folder.mkdir(exist_ok=True)
    os.startfile(folder)  # Windows: open in Explorer
    return {"ok": True}
