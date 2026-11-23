"""One small client for any OpenAI-compatible chat API (Gemini, Ollama, OpenRouter, Groq, custom).

The model setting may be a comma-separated list, e.g. "gemini-3.5-flash, gemini-flash-lite-latest":
each model is tried in order, with retries on busy/rate-limit errors (free tiers are often overloaded).
"""
import time

import httpx

RETRY_STATUS = {429, 500, 502, 503, 504}


def models_of(settings: dict) -> list:
    return [m.strip() for m in (settings.get("model") or "").split(",") if m.strip()]


def _post(base, headers, body, timeout):
    return httpx.post(f"{base}/chat/completions", json=body, headers=headers,
                      timeout=httpx.Timeout(timeout, connect=10))


def has_ai(s: dict) -> bool:
    return s.get("active", "none") != "none" and any(p["id"] == s["active"] for p in s.get("providers", []))


def profiles_to_try(s: dict) -> list:
    act = [p for p in s.get("providers", []) if p["id"] == s.get("active")]
    if not act:
        return []
    rest = [p for p in s["providers"] if p["id"] != act[0]["id"]] if s.get("fallback", True) else []
    return act + rest


def ask(s: dict, messages: list, json_mode: bool = True, log=lambda m: None) -> str:
    """Ask the active provider; if it fails and fallback is on, try the other saved providers."""
    errors = []
    for p in profiles_to_try(s):
        try:
            return chat(p, messages, json_mode=json_mode, log=log)
        except RuntimeError as e:
            errors.append(f"{p['name']}: {str(e)[:250]}")
            log(f"{p['name']} failed, trying the next provider")
    raise RuntimeError(" || ".join(errors) or "No AI provider is active (Settings).")


_slow: dict[str, float] = {}   # model -> time it last timed out; such models go to the back for 30 min


def chat(settings: dict, messages: list, json_mode: bool = True, timeout: float = 120,
         tries_per_model: int = 2, log=lambda m: None) -> str:
    """Call ONE provider profile (base_url, model list, api_key).

    Busy (429/5xx) -> short wait and one retry. Timeout -> skip to the next model at once (a model that
    does not answer in time usually has a long queue) and remember it as slow for 30 minutes."""
    base = (settings.get("base_url") or "").rstrip("/")
    models = models_of(settings)
    now = time.time()
    models = [m for m in models if now - _slow.get(m, 0) > 1800] + [m for m in models if now - _slow.get(m, 0) <= 1800]
    if not base or not models:
        raise RuntimeError("Provider base URL and model must be set (Settings).")
    headers = {"Content-Type": "application/json"}
    if settings.get("api_key"):
        headers["Authorization"] = f"Bearer {settings['api_key']}"

    errors = []
    for model in models:
        body = {"model": model, "messages": messages, "temperature": 0.3}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        for attempt in range(tries_per_model):
            try:
                r = _post(base, headers, body, timeout)
                if r.status_code == 400 and "response_format" in body:  # server rejects JSON mode: retry without
                    body.pop("response_format")
                    r = _post(base, headers, body, timeout)
            except httpx.TimeoutException:
                errors.append(f"{model}: no reply within {timeout:.0f}s")
                _slow[model] = time.time()
                log(f"AI model {model} did not answer in time, trying the next model")
                break
            except httpx.HTTPError as e:
                errors.append(f"{model}: {e}")
                break
            if r.status_code < 400:
                try:
                    return r.json()["choices"][0]["message"]["content"] or ""
                except Exception:
                    errors.append(f"{model}: unexpected response {r.text[:200]}")
                    break
            errors.append(f"{model}: HTTP {r.status_code} {r.text[:200]}")
            if r.status_code in RETRY_STATUS:
                log(f"AI model {model} busy ({r.status_code}), retrying")
                time.sleep(3 * (attempt + 1))
                continue
            break  # 4xx like 404 (model gone) / 401: try the next model
        log(f"Switching from {model} to the next model")
    raise RuntimeError("All AI models failed: " + " | ".join(errors[-4:]))


def test(settings: dict) -> str:
    return chat(settings, [{"role": "user", "content": "Reply with the single word OK."}],
                json_mode=False, timeout=60, tries_per_model=1)


def list_models(settings: dict) -> list:
    base = (settings.get("base_url") or "").rstrip("/")
    headers = {"Authorization": f"Bearer {settings['api_key']}"} if settings.get("api_key") else {}
    r = httpx.get(f"{base}/models", headers=headers, timeout=30)
    r.raise_for_status()
    return sorted(m["id"].removeprefix("models/") for m in r.json().get("data", []))
