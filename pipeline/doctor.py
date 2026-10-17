#!/usr/bin/env python3
"""Check a video folder's inputs BEFORE any work starts.

Every input problem on video 2 was a naming mismatch that cost real time:
the source was named differently from the prompt, the screens folder had a
trailing space, and two of the three cues pointed at filenames that did not
exist. None of those are interesting problems. This finds them in a second.
"""
import difflib, json, os, re, subprocess, sys

OK, WARN, BAD = "ok  ", "warn", "BAD "
rows = []
def say(level, what, detail=""):
    rows.append((level, what, detail))

ARROW = re.compile(r"\s*(?:-+>|—+>|–+>|=+>|→)\s*")

def read_cues(path):
    """Forgiving: cue sheets get written in a hurry, with curly quotes,
    em dash arrows and stray hashes."""
    out = []
    for raw in open(path, encoding="utf-8").read().splitlines():
        # markdown editors escape the arrow as \-\> or \u2014\>; drop backslashes first
        line = raw.replace("\\", "").strip().lstrip("#").strip()
        if not line or not ARROW.search(line):
            continue
        left, right = ARROW.split(line, 1)
        phrase = left.strip().strip('"“”‘’\'' ).strip()
        target = right.strip().strip('"“”‘’\'' ).strip()
        if phrase and target:
            out.append((phrase, target))
    return out

def probe(src):
    # -select_streams v:0 or the audio stream's r_frame_rate (0/0) wins
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "format=duration:stream=width,height,r_frame_rate",
                        "-of", "default=noprint_wrappers=1", src],
                       capture_output=True, text=True)
    return dict(l.split("=", 1) for l in r.stdout.strip().splitlines() if "=" in l)

def main():
    here = os.getcwd()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import config
    d = config.edit_dir()
    cfg = {}
    if os.path.exists(os.path.join(d, "edit.py")):
        cfg = config.load()
        say(OK, "edit", os.path.relpath(d, here))
    else:
        say(BAD, "edit", f"no edit.py at {d}. "
                         f"python3 ../../pipeline/run.py new <slug> <source.mp4>")
        print(f"\n  [{BAD}] edit  no edit.py at {d}")
        return 1

    # ---- the source video -------------------------------------------------
    src = cfg.get("SRC", "")
    vids = [f for f in os.listdir(here)
            if f.lower().endswith((".mp4", ".mov", ".m4v")) and not f.startswith(".")]
    if src and os.path.exists(src):
        p = probe(src)
        fps = p.get("r_frame_rate", "0/1")
        try:
            n, d = fps.split("/"); fps_v = float(n) / float(d)
        except Exception:
            fps_v = 0.0
        say(OK, "source", f"{src}  {p.get('width')}x{p.get('height')}  "
                          f"{fps_v:.3f} fps  {float(p.get('duration', 0)):.1f}s")
        if cfg.get("FPS") and abs(cfg["FPS"] - fps_v) > 0.01:
            say(BAD, "FPS", f"edit.py says {cfg['FPS']}, the file is {fps_v:.3f}. "
                            "Cuts will drift.")
        if cfg.get("SRC_DURATION") and abs(cfg["SRC_DURATION"] - float(p.get("duration", 0))) > 0.5:
            say(WARN, "SRC_DURATION", f"edit.py says {cfg['SRC_DURATION']}, "
                                      f"the file is {float(p.get('duration',0)):.2f}")
    elif src:
        near = difflib.get_close_matches(src, vids, n=1, cutoff=0.3)
        say(BAD, "source", f"SRC is {src!r}, which is not here." +
            (f" Did you mean {near[0]!r}?" if near else
             f" Videos here: {', '.join(vids) or 'none'}"))
    else:
        say(BAD, "source", "SRC not set in edit.py")

    # ---- screens folder ---------------------------------------------------
    shots_dir = cfg.get("SCREENS_DIR")
    if not (shots_dir and os.path.isdir(shots_dir)):
        shots_dir = None
        say(WARN, "screens/", f"no screens folder at {cfg.get('SCREENS_DIR')} "
                              "(fine if this video has no screenshots)")

    shots = sorted(f for f in os.listdir(shots_dir)
                   if not f.startswith(".")) if shots_dir else []
    if shots_dir:
        say(OK, "screens/", f"{len(shots)} file(s): {', '.join(shots) or 'empty'}")

    # ---- cue sheet --------------------------------------------------------
    cue_path = cfg.get("CUES") if os.path.exists(cfg.get("CUES", "")) else None
    if cue_path is None:
        say(WARN, "cues.md", "no cue sheet (fine if this video has no screenshots)")
    else:
        cues = read_cues(cue_path)
        if not cues:
            say(BAD, "cues.md", "no lines parsed. Each line needs: \"what you say\" -> file.png")
        for phrase, target in cues:
            if target in shots:
                say(OK, "cue", f'"{phrase}" -> {target}')
            else:
                near = difflib.get_close_matches(target, shots, n=1, cutoff=0.4)
                say(BAD, "cue", f'"{phrase}" -> {target!r} is not in screens/.' +
                    (f" Did you mean {near[0]!r}?" if near else ""))
        used = {t for _, t in cues}
        for f in shots:
            if f not in used and f.lower().endswith((".png", ".jpg", ".jpeg")):
                say(WARN, "screens/", f"{f!r} has no cue. It will be suggested, not placed.")

    # ---- brief ------------------------------------------------------------
    briefs = os.path.join(os.path.dirname(config.HERE), "briefs")
    if os.path.isdir(briefs):
        found = [f for f in os.listdir(briefs) if f.endswith(".md")]
        say(OK if found else BAD, "brief", ", ".join(found) or "briefs/ is empty")
    else:
        say(BAD, "brief", "no briefs/ folder at the project root")

    # ---- report -----------------------------------------------------------
    w = max(len(r[1]) for r in rows)
    print()
    for level, what, detail in rows:
        print(f"  [{level}] {what:<{w}}  {detail}")
    bad = sum(1 for r in rows if r[0] == BAD)
    warn = sum(1 for r in rows if r[0] == WARN)
    print(f"\n  {bad} problem(s), {warn} warning(s)")
    if bad:
        print("  Fix the problems before running transcribe: they all cost time later.")
    return bad

if __name__ == "__main__":
    sys.exit(1 if main() else 0)
