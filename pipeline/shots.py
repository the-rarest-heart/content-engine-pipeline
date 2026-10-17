#!/usr/bin/env python3
"""Prepare screens/ into assets/shots/, applying the SPEC guardrail.

Screenshots are captured from the same window as the screen recording, so they
carry the same things SPEC forbids: the model badge, the browser chrome, the
dev URL. Doing this by hand once is how it gets forgotten the second time.
"""
import os, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import load
globals().update(load())

def find_screens():
    if os.path.isdir(SCREENS_DIR):
        return SCREENS_DIR
    for cand in os.listdir("."):          # older layout
        if cand.strip().lower() == "screens" and os.path.isdir(cand):
            return cand
    return None

def main():
    src_dir = find_screens()
    if src_dir is None:
        print("no screens/ folder, nothing to prepare")
        return
    os.makedirs("assets/shots", exist_ok=True)
    if not SHOT_PREP:
        print("SHOT_PREP is empty: nothing declared in edit.py")
        return
    for spec in SHOT_PREP:
        src, dst = spec["from"], spec["to"]
        base = src if os.path.isabs(src) else (
            os.path.join("assets/shots", src) if src.startswith("shot-")
            else os.path.join(src_dir, src))
        if not os.path.exists(base):
            sys.exit(f"missing input for {dst}: {base}")
        vf = []
        if spec.get("crop"):
            x, y, w, h = spec["crop"]
            vf.append(f"crop={w}:{h}:{x}:{y}")
        for (x, y, w, h) in spec.get("masks", []):
            vf.append(f"drawbox=x={x}:y={y}:w={w}:h={h}:"
                      f"color={spec.get('mask_color', HDR_BG)}:t=fill")
        out = os.path.join("assets/shots", dst)
        if vf:
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", base,
                            "-vf", ",".join(vf), out], check=True)
        else:
            # nothing to change: copy rather than re-encode, so the file stays
            # byte-for-byte what the user captured
            shutil.copyfile(base, out)
        note = spec.get("why", "")
        print(f"  {dst:24} <- {os.path.basename(base)}" + (f"   {note}" if note else ""))

if __name__ == "__main__":
    main()
