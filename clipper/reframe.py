"""9:16 reframing with face tracking, CPU only.

1. Analyse the clip: decode once at 3 fps / 480 px and detect faces with OpenCV YuNet (Haar
   fallback); decode once more as tiny grey frames at full fps to find scene cuts.
2. Split into shots at the cuts and pick a layout per shot:
     face  - a 9:16 crop that follows the subject (one person, or a group that fits)
     split - two people far apart: each in a stacked half (interviews, podcasts)
     fit   - the whole frame over a blurred copy (wide group shots, no faces, slides)
3. Face shots get a smooth camera path: gap fill, median filter, dead zone, critically damped
   spring with a pan-speed cap, hard reset at every cut (the camera never pans across a cut).

Approach and parameters adapted from OpenShorts (MIT) and ideas from SupoClip and Clips Kitty;
own implementation. Face model: YuNet from opencv_zoo (MIT). See THIRD_PARTY_NOTICES.md.
"""
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
YUNET = ROOT / "models" / "face_detection_yunet_2023mar.onnx"

OUT_W, OUT_H = 1080, 1920
ANALYSIS_FPS = 3.0
ANALYSIS_W = 480


# ------------------------------------------------------------------ probing / decoding
def probe(path: Path) -> dict:
    p = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_streams", "-of", "json", str(path)],
                       capture_output=True, text=True)
    st = (json.loads(p.stdout or "{}").get("streams") or [{}])[0]
    w, h = int(st.get("width", 0)), int(st.get("height", 0))
    rot = str(st.get("tags", {}).get("rotate", "0"))
    for sd in st.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = str(sd["rotation"])
    if rot.lstrip("-") in ("90", "270"):   # phone videos: ffmpeg auto-rotates frames, so swap the size
        w, h = h, w
    num, _, den = str(st.get("r_frame_rate", "30/1")).partition("/")
    fps = float(num) / float(den) if den and float(den) else 30.0
    if not w or not h:
        raise RuntimeError(f"Could not read video size of {path}")
    return {"w": w, "h": h, "fps": fps}


def _frames(path: Path, start: float, dur: float, vf: str, w: int, h: int, pix: str = "bgr24"):
    ch = 3 if pix == "bgr24" else 1
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(path),
           "-vf", vf, "-f", "rawvideo", "-pix_fmt", pix, "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10 ** 7)
    size = w * h * ch
    try:
        while True:
            buf = proc.stdout.read(size)
            if len(buf) < size:
                break
            yield np.frombuffer(buf, np.uint8).reshape((h, w, ch) if ch > 1 else (h, w))
    finally:
        proc.stdout.close()
        proc.wait()


# ------------------------------------------------------------------ face detection
class FaceDetector:
    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.yunet = None
        try:
            # 0.72: below this, small "faces" at 480 px are mostly logos, crowd blur or posters
            self.yunet = cv2.FaceDetectorYN.create(str(YUNET), "", (w, h), 0.72, 0.3, 50)
        except Exception:
            self.haar = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    def __call__(self, frame) -> list:
        """Returns faces as (cx, cy, w, h, score) in 0..1 units of the frame."""
        out = []
        if self.yunet is not None:
            _, faces = self.yunet.detect(frame)
            for f in faces if faces is not None else []:
                x, y, fw, fh, score = f[0], f[1], f[2], f[3], f[-1]
                if fw >= 0.025 * self.w:
                    out.append(((x + fw / 2) / self.w, (y + fh / 2) / self.h, fw / self.w, fh / self.h, float(score)))
        else:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            for x, y, fw, fh in self.haar.detectMultiScale(gray, 1.1, 5, minSize=(int(0.03 * self.w),) * 2):
                out.append(((x + fw / 2) / self.w, (y + fh / 2) / self.h, fw / self.w, fh / self.h, 0.7))
        return out


def _main_faces(faces: list) -> list:
    """Drop small background faces: keep faces at least 30% the area of the biggest one."""
    if not faces:
        return []
    big = max(f[2] * f[3] for f in faces)
    return [f for f in faces if f[2] * f[3] >= 0.3 * big]


# ------------------------------------------------------------------ analysis
def analyze(source: Path, start: float, end: float) -> dict:
    info = probe(source)
    W, H, fps = info["w"], info["h"], info["fps"] or 30.0
    dur = end - start
    aw = ANALYSIS_W
    ah = int(round(aw * H / W / 2) * 2)
    det = FaceDetector(aw, ah)
    samples = []  # (t, faces)
    for i, fr in enumerate(_frames(source, start, dur, f"fps={ANALYSIS_FPS},scale={aw}:{ah}", aw, ah)):
        samples.append((i / ANALYSIS_FPS, det(fr)))

    # scene cuts: tiny grey frames at full rate
    diffs, prev = [], None
    for fr in _frames(source, start, dur, "fps=30,scale=64:36", 64, 36, pix="gray"):
        f = fr.astype(np.int16)
        diffs.append(0.0 if prev is None else float(np.abs(f - prev).mean()))
        prev = f
    cuts = []
    if len(diffs) > 3:
        d = np.array(diffs)
        thr = max(float(d.mean() + 3.5 * d.std()), 14.0)
        for i in range(1, len(d)):
            t = i / 30.0
            if d[i] > thr and (not cuts or t - cuts[-1] > 0.5) and 0.3 < t < dur - 0.3:
                cuts.append(t)
    return {"W": W, "H": H, "fps": fps, "dur": dur, "samples": samples, "cuts": cuts}


def _clusters(xs: list) -> list:
    """Split face x-centres into groups at gaps wider than 0.12 of the frame."""
    xs = sorted(xs)
    groups = [[xs[0]]]
    for x in xs[1:]:
        if x - groups[-1][-1] > 0.12:
            groups.append([x])
        else:
            groups[-1].append(x)
    return groups


def plan(an: dict, mode: str = "auto") -> list:
    """Per-shot layout plan: list of dicts {t0, t1, layout, path|panels}."""
    W, H, dur = an["W"], an["H"], an["dur"]
    crop_w = min(1.0, (H * 9 / 16) / W)          # crop width as a fraction of the frame width
    if W / H <= 9 / 16 + 0.01:                     # already vertical
        return [{"t0": 0.0, "t1": dur, "layout": "fit"}]
    bounds = [0.0] + an["cuts"] + [dur]
    shots = []
    for t0, t1 in zip(bounds, bounds[1:]):
        smp = [(t, _main_faces(f)) for t, f in an["samples"] if t0 <= t < t1] or \
              [min(an["samples"], key=lambda s: abs(s[0] - (t0 + t1) / 2))] if an["samples"] else []
        shots.append(_shot(t0, t1, smp, crop_w, mode))
    # merge very short shots into the previous one's layout (avoid flicker)
    for i in range(1, len(shots)):
        if shots[i]["t1"] - shots[i]["t0"] < 0.8 and shots[i]["layout"] != shots[i - 1]["layout"] and mode == "auto":
            prev = shots[i - 1]
            shots[i] = {**_shot(shots[i]["t0"], shots[i]["t1"], [], crop_w, prev["layout"]), "layout": prev["layout"]}
            if prev["layout"] == "face":
                shots[i]["path"] = [(0.0, prev["path"][-1][1])]
            if prev["layout"] == "split":
                shots[i]["panels"] = prev["panels"]
    return shots


def _shot(t0, t1, smp, crop_w, mode):
    n = len(smp)
    with_faces = [(t, f) for t, f in smp if f]
    presence = len(with_faces) / n if n else 0.0

    # spread of the main faces in each sample
    spans = [max(x[0] + x[2] / 2 for x in f) - min(x[0] - x[2] / 2 for x in f) for _, f in with_faces]
    span = float(np.median(spans)) if spans else 0.0
    groups_per_sample = [len(_clusters([x[0] for x in f])) for _, f in with_faces]
    two_people = with_faces and sum(1 for g in groups_per_sample if g == 2) / max(n, 1) >= 0.6

    if mode == "fit":
        layout = "fit"
    elif mode == "split":
        layout = "split" if two_people else ("face" if presence >= 0.3 else "fit")
    elif mode == "face":
        layout = "face"
    else:  # auto
        if presence < 0.35:
            layout = "fit"
        elif span <= crop_w * 0.92:
            layout = "face"
        elif two_people and t1 - t0 >= 2.0:
            layout = "split"
        else:
            layout = "fit"

    shot = {"t0": t0, "t1": t1, "layout": layout}
    if layout == "face":
        shot["path"] = _face_targets(with_faces, crop_w)
    elif layout == "split":
        shot["panels"] = _split_panels(with_faces)
    return shot


def _face_targets(with_faces, crop_w):
    """Target x-centre per sample: centre of the group if it fits, else the biggest face (sticky)."""
    pts, prev = [], None
    for t, f in with_faces:
        left = min(x[0] - x[2] / 2 for x in f)
        right = max(x[0] + x[2] / 2 for x in f)
        if right - left <= crop_w * 0.92:
            x = (left + right) / 2
        else:
            big = max(f, key=lambda x: x[2] * x[3])
            if prev is not None:
                near = min(f, key=lambda x: abs(x[0] - prev))
                if near[2] * near[3] >= 0.7 * big[2] * big[3]:
                    big = near   # keep following the same person unless someone clearly bigger appears
            x = big[0]
        pts.append((t, x))
        prev = x
    return pts or [(0.0, 0.5)]


def _split_panels(with_faces):
    tops, bots = [], []
    for _, f in with_faces:
        g = _clusters([x[0] for x in f])
        if len(g) != 2:
            continue
        a = [x for x in f if x[0] <= g[0][-1]]
        b = [x for x in f if x[0] >= g[1][0]]
        fa, fb = max(a, key=lambda x: x[2] * x[3]), max(b, key=lambda x: x[2] * x[3])
        tops.append(fa)
        bots.append(fb)
    med = lambda L: tuple(float(np.median([x[k] for x in L])) for k in range(4))
    return [med(tops), med(bots)] if tops else [(0.3, 0.4, 0.1, 0.15), (0.7, 0.4, 0.1, 0.15)]


# ------------------------------------------------------------------ camera path
def camera_path(targets: list, t0: float, t1: float, fps: float, crop_w: float) -> np.ndarray:
    """Crop x-centre (0..1) for every output frame of the shot."""
    n = max(1, int(round((t1 - t0) * fps)))
    ts, xs = np.array([t for t, _ in targets]), np.array([x for _, x in targets])
    if len(xs) >= 3:   # 5-tap median (edge-padded) removes one- and two-sample detector jumps
        pad = np.pad(xs, 2, mode="edge")
        xs = np.array([np.median(pad[i:i + 5]) for i in range(len(xs))])
    frame_t = t0 + np.arange(n) / fps
    goal = np.interp(frame_t, ts, xs) if len(ts) > 1 else np.full(n, xs[0])
    lo, hi = crop_w / 2, 1 - crop_w / 2
    dead = 0.045            # hold still while the subject stays within this distance
    smooth_time = 0.45      # seconds; spring time constant
    max_speed = 0.35        # frame-widths per second
    dt = 1.0 / fps
    out = np.empty(n)
    c, v = float(np.clip(np.median(goal[: max(1, int(fps))]), lo, hi)), 0.0   # start on the subject (reset at every cut)
    far_frames = 0
    for i in range(n):
        g = float(np.clip(goal[i], lo, hi))
        d = g - c
        # subject moved far away and stays there: cut to it instead of a long pan (like an editor would)
        far_frames = far_frames + 1 if abs(d) > crop_w * 0.6 else 0
        if far_frames >= int(0.4 * fps):
            c, v, far_frames = g, 0.0, 0
            out[i] = c
            continue
        target = c if abs(d) < dead else g - np.sign(d) * dead * 0.5
        # critically damped spring (Unity-style SmoothDamp)
        omega = 2.0 / smooth_time
        x = omega * dt
        exp = 1.0 / (1.0 + x + 0.48 * x * x + 0.235 * x * x * x)
        change = c - target
        max_change = max_speed * smooth_time
        change = float(np.clip(change, -max_change, max_change))
        temp = (v + omega * change) * dt
        v = (v - omega * temp) * exp
        c_new = (c - change) + (change + temp) * exp
        c = float(np.clip(c_new, lo, hi))
        out[i] = c
    return out


# ------------------------------------------------------------------ frame composition
def _cover(img, w, h):
    ih, iw = img.shape[:2]
    s = max(w / iw, h / ih)
    r = cv2.resize(img, (int(iw * s + 0.5), int(ih * s + 0.5)), interpolation=cv2.INTER_AREA)
    y, x = (r.shape[0] - h) // 2, (r.shape[1] - w) // 2
    return r[y:y + h, x:x + w]


def compose_fit(fr):
    small = _cover(fr, OUT_W // 10, OUT_H // 10)
    bg = cv2.GaussianBlur(small, (0, 0), 6)
    bg = cv2.resize(bg, (OUT_W, OUT_H), interpolation=cv2.INTER_LINEAR)
    bg = (bg.astype(np.float32) * 0.75).astype(np.uint8)
    ih, iw = fr.shape[:2]
    fh = int(round(OUT_W * ih / iw / 2) * 2)
    fg = cv2.resize(fr, (OUT_W, fh), interpolation=cv2.INTER_AREA if iw > OUT_W else cv2.INTER_LINEAR)
    y = max(0, (OUT_H - fh) // 2 - 120)
    bg[y:y + fh] = fg[: OUT_H - y]
    return bg


def compose_face(fr, cx: float):
    ih, iw = fr.shape[:2]
    cw = min(iw, int(round(ih * 9 / 16)))
    x0 = int(round(cx * iw - cw / 2))
    x0 = max(0, min(iw - cw, x0))
    return cv2.resize(fr[:, x0:x0 + cw], (OUT_W, OUT_H), interpolation=cv2.INTER_LINEAR)


def compose_split(fr, panels):
    ih, iw = fr.shape[:2]
    out = np.empty((OUT_H, OUT_W, 3), np.uint8)
    ph = OUT_H // 2
    for k, (cx, cy, fw, fh) in enumerate(panels):
        h = min(ih, max(int(fh * ih * 3.4), int(ih * 0.45)))     # face + shoulders
        w = min(iw, int(h * OUT_W / ph))
        h = int(w * ph / OUT_W)
        x0 = max(0, min(iw - w, int(cx * iw - w / 2)))
        y0 = max(0, min(ih - h, int(cy * ih - h * 0.42)))
        out[k * ph:(k + 1) * ph] = cv2.resize(fr[y0:y0 + h, x0:x0 + w], (OUT_W, ph), interpolation=cv2.INTER_LINEAR)
    out[ph - 3:ph + 3] = 0   # thin divider
    return out


# ------------------------------------------------------------------ render
def render(source: Path, start: float, end: float, shots: list, out: Path, workdir: Path, ass_name: str | None,
           fps: float = 30.0, log=lambda m: None) -> dict:
    info = probe(source)
    W, H = info["w"], info["h"]
    crop_w = min(1.0, (H * 9 / 16) / W)
    dur = end - start
    n_total = int(round(dur * fps))
    # per-frame instructions
    per_frame = []
    for sh in shots:
        f0, f1 = int(round(sh["t0"] * fps)), int(round(sh["t1"] * fps))
        if f1 <= f0:
            continue
        if sh["layout"] == "face":
            xs = camera_path(sh["path"], sh["t0"], sh["t1"], fps, crop_w)
            per_frame += [("face", float(xs[min(i, len(xs) - 1)])) for i in range(f1 - f0)]
        else:
            per_frame += [(sh["layout"], sh.get("panels"))] * (f1 - f0)
    while len(per_frame) < n_total:
        per_frame.append(per_frame[-1] if per_frame else ("fit", None))

    vf = f"ass={ass_name}:fontsdir=." if ass_name else "null"
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y",
         "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{OUT_W}x{OUT_H}", "-r", f"{fps}", "-i", "-",
         "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(Path(source).resolve()),
         "-map", "0:v", "-map", "1:a?", "-vf", vf,
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(Path(out).resolve())],
        stdin=subprocess.PIPE, stderr=subprocess.PIPE, cwd=workdir)
    counts = {"face": 0, "fit": 0, "split": 0}
    i = 0
    try:
        for fr in _frames(source, start, dur, f"fps={fps}", W, H):
            if i >= len(per_frame):
                break
            kind, arg = per_frame[i]
            img = compose_face(fr, arg) if kind == "face" else compose_split(fr, arg) if kind == "split" else compose_fit(fr)
            enc.stdin.write(img.tobytes())
            counts[kind] += 1
            i += 1
            if i % 150 == 0:
                log(f"Rendering {i}/{n_total} frames")
        enc.stdin.close()
    except BrokenPipeError:
        pass
    err = enc.stderr.read().decode(errors="replace")
    enc.wait()
    if enc.returncode:
        raise RuntimeError("ffmpeg encode failed: " + err[-800:])
    total = max(1, sum(counts.values()))
    return {k: round(v / total, 2) for k, v in counts.items() if v}


def split_seam_times(shots: list) -> list:
    """Time ranges where the split layout is used (captions move to the seam there)."""
    return [(s["t0"], s["t1"]) for s in shots if s["layout"] == "split"]
