"""Cheap measured signals that help pick moments (no AI).

Used as "hints" in the AI prompt and as scores in the basic picker. Ideas from SupoClip
(signal summary as LLM hints) and Clips Kitty (loudness spikes vs. a rolling median, YouTube's
free "most replayed" heatmap from yt-dlp). Own implementation.
"""
import numpy as np

SR = 16000


def db_per_second(audio: np.ndarray) -> np.ndarray:
    n = len(audio) // SR
    if n == 0:
        return np.zeros(1)
    frames = audio[: n * SR].reshape(n, SR)
    return 20 * np.log10(np.sqrt((frames ** 2).mean(axis=1)) + 1e-6)


def loudness_spikes(db: np.ndarray, top: int = 15, min_gap: float = 8.0) -> list:
    """Seconds that are much louder than the surrounding 30 s (shouts, cheers, laughter, impacts)."""
    if len(db) < 10:
        return []
    k = 15
    padded = np.pad(db, k, mode="edge")
    med = np.array([np.median(padded[i:i + 2 * k + 1]) for i in range(len(db))])
    rise = db - med
    out = []
    for t in np.argsort(-rise):
        if rise[t] < 5.0 or len(out) >= top:
            break
        if all(abs(t - u) >= min_gap for u, _ in out):
            out.append((float(t), float(rise[t])))
    return sorted(out)


def pauses(segs: list, min_gap: float = 1.2) -> list:
    """Silent gaps between lines: often just before a reveal or punchline."""
    out = []
    for a, b in zip(segs, segs[1:]):
        g = b["start"] - a["end"]
        if g >= min_gap:
            out.append((float(b["start"]), float(g)))
    return out


def replayed_peaks(heatmap, top: int = 6) -> list:
    """YouTube 'most replayed' sections (value 0..1), from yt-dlp's info['heatmap']."""
    if not heatmap:
        return []
    pts = [h for h in heatmap if isinstance(h, dict) and "start_time" in h and "value" in h]
    if not pts:
        return []
    vals = np.array([p["value"] for p in pts])
    thr = max(0.5, float(np.percentile(vals, 85)))
    out = []
    for p in sorted(pts, key=lambda p: -p["value"]):
        if p["value"] < thr or len(out) >= top:
            break
        if all(abs(p["start_time"] - q[0]) > 20 for q in out):
            out.append((float(p["start_time"]), float(p["end_time"]), float(p["value"])))
    return sorted(out)


def build_hints(audio: np.ndarray, segs: list, heatmap=None) -> dict:
    db = db_per_second(audio)
    return {
        "loud": loudness_spikes(db),
        "pauses": pauses(segs),
        "replayed": replayed_peaks(heatmap),
        "db": db,
    }


def hints_text(h: dict, t0: float, t1: float) -> str:
    lines = []
    for t, r in h["loud"]:
        if t0 <= t < t1:
            lines.append(f"- {t:.0f}s: loud moment (+{r:.0f} dB over its surroundings)")
    for s, e, v in h["replayed"]:
        if t0 <= s < t1:
            lines.append(f"- {s:.0f}-{e:.0f}s: one of the MOST REPLAYED parts of the video by real YouTube viewers ({v:.0%})")
    for t, g in h["pauses"]:
        if t0 <= t < t1 and g >= 2.0:
            lines.append(f"- {t:.0f}s: {g:.1f}s pause before this line")
    return "\n".join(lines[:25])
