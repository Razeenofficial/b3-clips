"""Burned-in captions as ASS subtitles, with style presets and an optional hook title.

House style: Poppins ExtraBold, white words, the spoken
word highlighted. The active word changes colour only (scaling single words makes lines jitter);
"pop" presets animate the whole line in once instead. Ideas from SupoClip and OpenShorts; own code.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONTS = [ROOT / "assets" / "fonts" / "Poppins-ExtraBold.ttf", ROOT / "assets" / "fonts" / "Poppins-Medium.ttf"]


def _bgr(hex_rgb: str) -> str:
    h = hex_rgb.lstrip("#")
    return f"&H00{h[4:6]}{h[2:4]}{h[0:2]}&".upper()


PRESETS = {
    "classic": {"label": "Classic: white, yellow active word", "font": "Poppins ExtraBold", "size": 84,
                "color": "#FFFFFF", "active": "#FFE600", "outline": 7, "shadow": 3, "box": False,
                "words": 3, "upper": True, "pop": False},
    "pop":     {"label": "Pop: lines bounce in, yellow word", "font": "Poppins ExtraBold", "size": 88,
                "color": "#FFFFFF", "active": "#FFE600", "outline": 7, "shadow": 3, "box": False,
                "words": 3, "upper": True, "pop": True},
    "green":   {"label": "Green: pop with neon-green word", "font": "Poppins ExtraBold", "size": 88,
                "color": "#FFFFFF", "active": "#3DFF6E", "outline": 7, "shadow": 3, "box": False,
                "words": 3, "upper": True, "pop": True},
    "one_word": {"label": "One word: big single words", "font": "Poppins ExtraBold", "size": 120,
                 "color": "#FFFFFF", "active": "#FFE600", "outline": 9, "shadow": 4, "box": False,
                 "words": 1, "upper": True, "pop": True},
    "boxed":   {"label": "Boxed: dark box, yellow word", "font": "Poppins ExtraBold", "size": 76,
                "color": "#FFFFFF", "active": "#FFE600", "outline": 14, "shadow": 0, "box": True,
                "words": 3, "upper": True, "pop": False},
    "minimal": {"label": "Minimal: clean sentence case", "font": "Poppins Medium", "size": 66,
                "color": "#FFFFFF", "active": None, "outline": 4, "shadow": 2, "box": False,
                "words": 6, "upper": False, "pop": False},
}
POSITIONS = {"low": 520, "middle": 860, "high": 1250}   # MarginV from the bottom of a 1920 frame


def _t(x: float) -> str:
    h, r = divmod(max(x, 0), 3600)
    m, s = divmod(r, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _clean(w: str, upper: bool) -> str:
    w = w.strip().replace("{", "(").replace("}", ")").replace("\\", "")
    w = w.strip(".,") if upper else w
    return w.upper() if upper else w


def _groups(words: list, p: dict) -> list:
    max_chars = int(1080 * 0.82 / (p["size"] * (0.66 if p["upper"] else 0.55)))
    groups, cur = [], []
    for i, w in enumerate(words):
        txt = " ".join(x[2] for x in cur + [w])
        if cur and (len(cur) >= p["words"] or len(txt) > max_chars):
            groups.append(cur)
            cur = []
        cur.append(w)
        gap = (words[i + 1][0] - w[1]) if i + 1 < len(words) else 9
        if gap > 0.6 or (p["words"] > 1 and w[2][-1:] in ".?!"):
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    return groups


def build_ass(segs: list, start: float, end: float, preset: str = "classic", position: str = "low",
              hook_title: str = "", seam_ranges: list | None = None) -> str:
    p = PRESETS.get(preset, PRESETS["classic"])
    margin_v = POSITIONS.get(position, 520)
    col, act = _bgr(p["color"]), _bgr(p["active"]) if p["active"] else None
    words = []
    for seg in segs:
        for w in seg["words"]:
            txt = _clean(w["w"], p["upper"])
            if w["s"] >= start - 0.05 and w["e"] <= end + 0.05 and txt.strip(".,?!"):
                words.append((max(0.0, w["s"] - start), min(end - start, w["e"] - start), txt))

    seam = seam_ranges or []
    lines = []
    groups = _groups(words, p)
    for gi, g in enumerate(groups):
        g_start = g[0][0]
        nxt = groups[gi + 1][0][0] if gi + 1 < len(groups) else end - start   # never overlap the next line
        in_seam = any(a <= g_start < b for a, b in seam)
        pos = "{\\an5\\pos(540,960)}" if in_seam else ""
        pop = "{\\fscx88\\fscy88\\t(0,140,\\fscx100\\fscy100)}" if p["pop"] else ""
        if act is None:
            until = min(g[-1][1] + 0.3, nxt)
            text = " ".join(x[2] for x in g)
            lines.append(f"Dialogue: 1,{_t(g_start)},{_t(until)},Cap,,0,0,0,,{pos}{pop}{text}")
            continue
        for k, (s, e, _) in enumerate(g):
            until = g[k + 1][0] if k + 1 < len(g) else min(e + 0.25, nxt)
            text = " ".join(f"{{\\c{act}}}{x[2]}{{\\c{col}}}" if j == k else x[2] for j, x in enumerate(g))
            lines.append(f"Dialogue: 1,{_t(s)},{_t(until)},Cap,,0,0,0,,{pos}{pop if k == 0 else ''}{text}")

    if hook_title.strip():
        ht = hook_title.strip().replace("{", "(").replace("}", ")").replace("\\", "")
        lines.append(f"Dialogue: 2,{_t(0.15)},{_t(min(3.8, end - start))},Hook,,0,0,0,,"
                     f"{{\\fad(150,250)\\fscx90\\fscy90\\t(0,160,\\fscx100\\fscy100)}}{ht}")

    border = 3 if p["box"] else 1
    out_col = "&H99000000&" if p["box"] else "&H00000000&"
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Cap,{p['font']},{p['size']},{col},{col},{out_col},&H80000000&,0,0,0,0,100,100,0,0,{border},{p['outline']},{p['shadow']},2,70,70,{margin_v},1
Style: Hook,Poppins ExtraBold,62,&H00111111&,&H00111111&,&H00FFFFFF&,&H00000000&,0,0,0,0,100,100,0,0,3,18,0,8,90,90,130,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
""" + "\n".join(lines) + "\n"
