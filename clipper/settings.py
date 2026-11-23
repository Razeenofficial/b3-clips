"""User settings stored in settings.json at the project root.

AI providers are saved profiles (name, type, base URL, models, key). One is "active"; switching
loads that profile's own key and models. Keys never leave this PC except to their provider.
"""
import json
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SETTINGS_FILE = ROOT / "settings.json"

# Templates for "Add provider". All speak the OpenAI-compatible /chat/completions API.
TEMPLATES = {
    "gemini":     {"label": "Google Gemini", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
                   "model": "gemini-3.5-flash, gemini-flash-latest, gemini-flash-lite-latest", "needs_key": True},
    "nvidia":     {"label": "NVIDIA (build.nvidia.com)", "base_url": "https://integrate.api.nvidia.com/v1",
                   "model": "", "needs_key": True},
    "groq":       {"label": "Groq", "base_url": "https://api.groq.com/openai/v1", "model": "openai/gpt-oss-120b, llama-3.3-70b-versatile",
                   "needs_key": True},
    "openrouter": {"label": "OpenRouter", "base_url": "https://openrouter.ai/api/v1", "model": "", "needs_key": True},
    "ollama":     {"label": "Ollama (local)", "base_url": "http://localhost:11434/v1", "model": "qwen2.5:7b", "needs_key": False},
    "custom":     {"label": "Custom (OpenAI-compatible)", "base_url": "", "model": "", "needs_key": False},
}

DEFAULTS = {
    "active": "none",          # id of the active provider profile, or "none" (basic picker)
    "fallback": True,          # if the active provider fails, try the other saved ones
    "providers": [],           # [{id, name, type, base_url, model, api_key}]
    "whisper_model": "small.en",
    "max_candidates": 0,       # 0 = auto: keep every moment scoring at least min_score
    "min_score": 55,
    "min_len": 20,
    "max_len": 60,
}
GENERAL = ("fallback", "whisper_model", "max_candidates", "min_score", "min_len", "max_len")


def _write(data: dict):
    SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load() -> dict:
    data = dict(DEFAULTS)
    raw = {}
    if SETTINGS_FILE.exists():
        try:
            raw = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            raw = {}
    data.update({k: v for k, v in raw.items() if k in DEFAULTS})
    data["providers"] = [dict(p) for p in data.get("providers") or []]
    if "provider" in raw and not raw.get("providers"):      # migrate the old single-provider format
        old = raw.get("provider", "none")
        if old != "none":
            pid = "p" + uuid.uuid4().hex[:6]
            name = TEMPLATES.get(old, {}).get("label", old.title())
            data["providers"] = [{"id": pid, "name": name, "type": old, "base_url": raw.get("base_url", ""),
                                  "model": raw.get("model", ""), "api_key": raw.get("api_key", "")}]
            data["active"] = pid
        _write(data)
    if data["active"] != "none" and not any(p["id"] == data["active"] for p in data["providers"]):
        data["active"] = "none"
    return data


def save_general(update: dict) -> dict:
    data = load()
    data.update({k: v for k, v in update.items() if k in GENERAL})
    _write(data)
    return data


def upsert_provider(p: dict) -> dict:
    data = load()
    pid = p.get("id") or ""
    existing = next((x for x in data["providers"] if x["id"] == pid), None)
    if existing is None:
        existing = {"id": "p" + uuid.uuid4().hex[:6], "api_key": ""}
        data["providers"].append(existing)
        if data["active"] == "none":
            data["active"] = existing["id"]
    for k in ("name", "type", "base_url", "model"):
        if k in p and p[k] is not None:
            existing[k] = str(p[k]).strip()
    if p.get("clear_key"):
        existing["api_key"] = ""
    elif p.get("api_key"):                     # empty keeps the saved key
        existing["api_key"] = p["api_key"].strip()
    _write(data)
    return existing


def delete_provider(pid: str) -> dict:
    data = load()
    data["providers"] = [x for x in data["providers"] if x["id"] != pid]
    if data["active"] == pid:
        data["active"] = data["providers"][0]["id"] if data["providers"] else "none"
    _write(data)
    return data


def set_active(pid: str) -> dict:
    data = load()
    if pid != "none" and not any(x["id"] == pid for x in data["providers"]):
        raise KeyError(pid)
    data["active"] = pid
    _write(data)
    return data


def get_provider(data: dict, pid: str) -> dict | None:
    return next((x for x in data["providers"] if x["id"] == pid), None)


def public(data: dict) -> dict:
    """Settings safe to send to the browser: never the keys themselves."""
    out = {k: v for k, v in data.items() if k != "providers"}
    out["providers"] = [{**{k: v for k, v in p.items() if k != "api_key"}, "api_key_set": bool(p.get("api_key"))}
                        for p in data["providers"]]
    return out
