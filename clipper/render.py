"""Render one clip: face-tracked 9:16 reframe + burned captions + optional hook title."""
import shutil
from pathlib import Path

from . import captions, reframe

LAYOUTS = {"auto": "Auto (face crop, split or blurred per shot)", "face": "Face crop (always follow a face)",
           "fit": "Blurred fill (whole frame, no crop)", "split": "Split (two people stacked)"}


def render_clip(source: Path, segs: list, start: float, end: float, out: Path, workdir: Path, name: str,
                layout: str = "auto", preset: str = "classic", position: str = "low", hook_title: str = "",
                with_captions: bool = True, log=lambda m: None) -> dict:
    workdir.mkdir(parents=True, exist_ok=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    log("Finding faces and scene cuts")
    an = reframe.analyze(source, start, end)
    shots = reframe.plan(an, layout)
    ass_name = None
    if with_captions or hook_title.strip():
        for f in captions.FONTS:
            if not (workdir / f.name).exists():
                shutil.copy(f, workdir / f.name)
        ass_name = f"{name}.ass"
        segs_used = segs if with_captions else []
        (workdir / ass_name).write_text(
            captions.build_ass(segs_used, start, end, preset, position, hook_title, reframe.split_seam_times(shots)),
            encoding="utf-8")
    log("Rendering")
    share = reframe.render(source, start, end, shots, out, workdir, ass_name, log=log)
    return {"layout_share": share, "shots": len(shots), "cuts": len(an["cuts"]),
            "faces_seen": round(sum(1 for _, f in an["samples"] if f) / max(1, len(an["samples"])), 2)}
