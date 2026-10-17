#!/usr/bin/env python3
"""Write EDIT-PLAN.md from the real numbers in the cut, never typed ones."""
import json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import load
globals().update(load())

def dur(path):
    try:
        return float(subprocess.run(
            ["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",path],
            capture_output=True, text=True).stdout.strip())
    except Exception:
        return 0.0

def ms(t):
    return f"{int(t//60)}:{t%60:05.2f}"

def main():
    import edl
    segs, report = edl.build()
    APP = APP_SPANS
    caps = json.load(open("work/captions.json"))
    M = json.load(open("work/moments.json")) if __import__("os").path.exists("work/moments.json") else {}

    src_a = min(a for _, a, b, *_ in report)
    src_b = max(b for _, a, b, *_ in report)
    content = sum(b - a for _, a, b, *_ in report)
    final = sum(b - a for a, b in segs)
    src_total = SRC_DURATION
    speech = SPEECH_TO - SPEECH_FROM

    out = []
    A = out.append
    A("# Edit plan: Action Items (TRH Reach)\n")
    A(f"Source `videos/action items.mp4` is 1080x1920, 60 fps, {ms(src_total)}. "
      f"Brief `briefs/trh-reach.md`. Target 2 minutes.\n")
    A(f"**Final length {ms(final)}** across {len(segs)} cuts.\n")
    A("| stage | length | removed |")
    A("| --- | --- | --- |")
    A(f"| source | {ms(src_total)} | |")
    A(f"| speech only (head and tail dead air out) | {ms(speech)} | {ms(src_total-speech)} |")
    A(f"| after retakes, repeats and tangents | {ms(content)} | {ms(speech-content)} |")
    A(f"| after squeezing every pause | {ms(final)} | {ms(content-final)} |")
    A("")
    A("## Moments kept, in order\n")
    A("| # | moment | in | out | length | shot | line |")
    A("| --- | --- | --- | --- | --- | --- | --- |")
    acc = 0.0
    for i, (label, a, b, kept, saved, why, n) in enumerate(report, 1):
        mid = (a + b) / 2
        shot = "screen" if any(x <= mid <= y for x, y in APP) else "face"
        line = why.split("  [")[0]
        note = ""
        if "  [" in why:
            note = " " + why.split("  [", 1)[1].rstrip("]")
            note = f"<br>_{note.strip()}_"
        A(f"| {i} | `{label}` | {ms(acc)} | {ms(acc+kept)} | {kept:.2f}s | {shot} | {line}{note} |")
        acc += kept
    A("")
    A("## What was cut and why\n")
    cuts = [(l, w) for l, a, b, k, s, w, n in report if "  [" in w]
    A("| moment | removed |")
    A("| --- | --- |")
    for l, w in cuts:
        A(f"| `{l}` | {w.split('  [',1)[1].rstrip(']')} |")
    A("")
    A(f"Dead air: every pause over 0.25s squeezed to about 0.16s "
      f"({ms(content-final)} recovered in total). Every cut is snapped to the "
      f"quietest point near the word edge and rounded to a whole 60 fps frame.\n")
    A(f"Captions: {len(caps)} words, word by word highlight in the app's own "
      f"green #39FF14. No dashes in on screen text.\n")

    # --- placements, read from the build table so the two cannot drift -----
    import build as b_mod
    b = {"SHOTS": SHOTS, "PUNCH": PUNCH, "EMOJI": EMOJI}
    MM = json.load(open("work/moments.json"))
    def mt(label, off):
        return ms(MM[label][0] + off) if label in MM else "?"

    A("## Screenshots placed\n")
    A("Each one is placed at its cue in `cues.md`, matched against the transcript.\n")
    A("| at | for | file | cue it answers |")
    A("| --- | --- | --- | --- |")
    notes = NOTES if "NOTES" in globals() else {}
    cue = notes.get("shots", {})
    for label, off, dur, asset, w, top, side in b["SHOTS"]:
        A(f"| {mt(label, off)} | {dur:.1f}s | `{asset}` | {cue.get(label, '')} |")
    A("")
    A("## Punch ins\n")
    A("| at | length | zoom | on |")
    A("| --- | --- | --- | --- |")
    pn = notes.get("punch", {})
    for label, off, dur, sc, ox, oy in b["PUNCH"]:
        A(f"| {mt(label, off)} | {dur:.1f}s | {sc:.2f}x | {pn.get(label, label)} |")
    A("")
    A("## Emoji\n")
    A("| at | emoji | on |")
    A("| --- | --- | --- |")
    en = notes.get("emoji", {})
    for label, off, dur, ch, xp, yp in b["EMOJI"]:
        A(f"| {mt(label, off)} | {ch} | {en.get(ch, '')} |")
    A("")
    if notes.get("anim"):
        A("## The one animation\n")
        A(notes["anim"] + "\n")
    if notes.get("guardrail"):
        A("## Guardrail check\n")
        A("SPEC says never capture anything that shows how the product is built. "
          "What this footage carried, and what was done about it:\n")
        for line in notes["guardrail"]:
            A(f"- {line}")
        A("")
    text = "\n".join(out) + "\n"
    open("EDIT-PLAN.md", "w").write(text)                      # handy here
    keep = os.path.join(EDIT_DIR, "EDIT-PLAN.md")
    if os.path.abspath(keep) != os.path.abspath("EDIT-PLAN.md"):
        open(keep, "w").write(text)                            # and kept there
    print(f"EDIT-PLAN.md written ({final:.2f}s, {len(report)} moments) -> {keep}")

if __name__ == "__main__":
    main()
