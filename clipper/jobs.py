"""Background jobs: info -> download -> transcribe -> pick moments; then render on request.

Each job lives in jobs/<id>/ with job.json, source.mp4 (if downloaded), transcript.json and clips/.
Heavy steps (transcribe, render) run one at a time so the CPU-only PC stays usable.
"""
import json
import shutil
import threading
import time
import traceback
import uuid
from pathlib import Path

from . import pipeline, picker, render, settings as cfg

ROOT = Path(__file__).resolve().parent.parent
JOBS_DIR = ROOT / "jobs"
JOBS_DIR.mkdir(exist_ok=True)

_heavy = threading.Lock()
_save_lock = threading.Lock()
_jobs: dict[str, dict] = {}

CAMPAIGN_DEFAULT = {"name": "", "min_sec": None, "max_sec": None, "deadline": "", "platforms": "",
                    "hashtags": "", "mentions": "", "phrase": "", "credit": ""}


def _dir(job) -> Path:
    return JOBS_DIR / job["id"]


def _save(job):
    with _save_lock:
        (_dir(job) / "job.json").write_text(json.dumps(job, indent=1), encoding="utf-8")


def _update(job, **kw):
    job.update(kw)
    _save(job)


def load_all():
    for f in sorted(JOBS_DIR.glob("*/job.json")):
        try:
            job = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if job.get("status") in ("queued", "running"):
            job.update(status="error", error="Interrupted (server was stopped). Start a new job or re-run picking.")
        for c in job.get("clips", []):
            if c.get("status") == "rendering":
                c.update(status="error", error="Interrupted")
        job.setdefault("campaign", dict(CAMPAIGN_DEFAULT))
        _jobs[job["id"]] = job


def get(job_id: str) -> dict | None:
    return _jobs.get(job_id)


def _job_busy(j: dict) -> bool:
    return j.get("status") in ("queued", "running") or any(c.get("status") == "rendering" for c in j.get("clips", []))


def is_busy() -> bool:
    """True while anything is downloading, transcribing, picking or rendering."""
    return any(_job_busy(j) for j in _jobs.values())


def delete(job_id: str):
    """Delete a job and its folder (download, transcript, clips). A user's own local source video
    lives outside the job folder and is never touched."""
    job = _jobs.get(job_id)
    if job is None:
        raise KeyError(job_id)
    if _job_busy(job):
        raise RuntimeError("This job is still processing. Wait until it finishes, then delete it.")
    folder = (JOBS_DIR / job_id).resolve()
    if folder.parent != JOBS_DIR.resolve():
        raise RuntimeError("Refusing to delete a folder outside jobs/")
    last = None
    for _ in range(10):   # Windows: a video may still be open for a moment (preview stream) - retry briefly
        try:
            if folder.exists():
                shutil.rmtree(folder)
            break
        except PermissionError as e:
            last = e
            time.sleep(0.5)
    else:
        raise RuntimeError(f"Some files are still in use, close any open clip and try again ({last}).")
    _jobs.pop(job_id, None)


def all_jobs() -> list:
    return sorted(_jobs.values(), key=lambda j: j["created"], reverse=True)


def _segs(job) -> list:
    return json.loads((_dir(job) / "transcript.json").read_text(encoding="utf-8"))


def create(source: str) -> dict:
    job_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
    job = {"id": job_id, "input": source.strip(), "created": time.time(), "status": "queued",
           "stage": "Waiting", "progress": 0.0, "meta": None, "source": None, "duration": None,
           "candidates": [], "pick_method": None, "warning": None, "clips": [], "error": None,
           "campaign": dict(CAMPAIGN_DEFAULT)}
    _dir(job).mkdir(parents=True)
    _jobs[job_id] = job
    _save(job)
    threading.Thread(target=_run, args=(job,), daemon=True).start()
    return job


def _run(job):
    try:
        inp = job["input"].strip('"')
        local = Path(inp)
        if local.exists() and local.is_file():
            source = local.resolve()
            _update(job, status="running", meta={"title": local.name, "channel": "Local file", "license": "local file"})
        else:
            _update(job, status="running", stage="Reading video info")
            meta = pipeline.fetch_meta(inp)
            _update(job, meta=meta, stage="Downloading video")
            source = pipeline.download(inp, _dir(job))
        _update(job, source=str(source), duration=pipeline.probe_duration(source))

        with _heavy:
            s = cfg.load()
            _update(job, stage=f"Transcribing ({s['whisper_model']}, CPU - this is the slow part)", progress=0.0)
            audio = pipeline.decode_audio(source)
            last = [0.0]

            def prog(p):
                if p - last[0] >= 0.01:
                    last[0] = p
                    _update(job, progress=round(p, 3))

            segs = pipeline.transcribe(audio, s["whisper_model"], prog)
            (_dir(job) / "transcript.json").write_text(json.dumps(segs, ensure_ascii=False), encoding="utf-8")
            _pick(job, s, segs, audio)
    except Exception as e:
        traceback.print_exc()
        _update(job, status="error", error=str(e))


def _pick(job, s, segs, audio):
    _update(job, stage="Finding moments", progress=1.0)
    heatmap = (job.get("meta") or {}).get("heatmap")
    cands, method, warning, note = picker.pick(s, segs, audio, heatmap, log=lambda m: _update(job, stage=m))
    _update(job, status="ready", stage="Ready for review", candidates=cands, pick_method=method, warning=warning,
            pick_note=note)


def repick(job):
    """Re-run moment finding on the saved transcript (e.g. after adding an AI key)."""
    def run():
        try:
            with _heavy:
                _update(job, status="running", error=None, warning=None)
                audio = pipeline.decode_audio(Path(job["source"]))
                _pick(job, cfg.load(), _segs(job), audio)
        except Exception as e:
            traceback.print_exc()
            _update(job, status="error", error=str(e))
    threading.Thread(target=run, daemon=True).start()


def set_campaign(job, campaign: dict):
    job["campaign"] = {**CAMPAIGN_DEFAULT, **{k: v for k, v in campaign.items() if k in CAMPAIGN_DEFAULT}}
    _save(job)


def set_post_text(job, n: int, text: str):
    for c in job["clips"]:
        if c["n"] == n:
            c["post_text"] = text
            if c.get("file"):
                (_dir(job) / "clips" / (Path(c["file"]).stem + ".txt")).write_text(text, encoding="utf-8")
            _save(job)
            return c
    return None


def render_clip(job, start: float, end: float, opts: dict) -> dict:
    n = max([c["n"] for c in job["clips"]] or [0]) + 1
    clip = {"n": n, "start": start, "end": end, "label": opts.get("label", ""), "status": "rendering",
            "stage": "Waiting for the CPU", "file": None, "error": None, "created": time.time(),
            "layout": opts.get("layout", "auto"), "preset": opts.get("preset", "classic"),
            "position": opts.get("position", "low"), "hook_title": opts.get("hook_title", ""),
            "captions": opts.get("captions", True), "post_text": opts.get("post_text", ""), "info": None}
    job["clips"].append(clip)
    _save(job)

    def log(m):
        clip["stage"] = m
        _save(job)

    def run():
        try:
            with _heavy:
                name = f"short_{n:02d}"
                out = _dir(job) / "clips" / f"{name}.mp4"
                info = render.render_clip(Path(job["source"]), _segs(job), start, end, out, _dir(job), name,
                                          clip["layout"], clip["preset"], clip["position"], clip["hook_title"],
                                          clip["captions"], log=log)
                clip.update(status="done", file=out.name, info=info, stage="")
                if clip["post_text"]:
                    (out.parent / f"{name}.txt").write_text(clip["post_text"], encoding="utf-8")
        except Exception as e:
            traceback.print_exc()
            clip.update(status="error", error=str(e))
        _save(job)
    threading.Thread(target=run, daemon=True).start()
    return clip
