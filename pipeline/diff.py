#!/usr/bin/env python3
"""Compare what the cut SHOULD say against what it actually says.

captions.json is the intention; the transcription of the cut audio is the
reality. Aligning them turns "read the prose and spot the problems" into a list
of defects, each attributed to the moment whose edge caused it.
"""
import difflib, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import load
globals().update(load())

def expected(w, h):
    w, h = w.strip(), h.strip()
    return any(w == a and h == b for a, b in HEARD_OK)

def norm(t):
    t = t.lower().replace("’", "'")
    t = re.sub(r"[^a-z0-9' ]+", " ", t)
    return [w for w in t.split() if w]

def main():
    want = norm(" ".join(w["w"] for w in json.load(open("work/captions.json"))))
    heard = norm(open(sys.argv[1] if len(sys.argv) > 1 else "work/cut-heard.txt").read())
    order = [m["label"] for m in json.load(open("work/segmap.json")) for _ in m["words"]]

    sm = difflib.SequenceMatcher(None, want, heard, autojunk=False)
    rows, same = [], 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            same += i2 - i1
            continue
        a, b = " ".join(want[i1:i2]), " ".join(heard[j1:j2])
        if expected(a, b):
            continue
        rows.append((tag, order[min(i1, len(order) - 1)] if order else "?",
                     a or "-", b or "-"))

    pct = 100 * same / max(len(want), 1)
    print(f"intended {len(want)} words, heard {len(heard)}, {same} matched ({pct:.1f}%)")
    print(f"{len(rows)} mismatch(es)\n")
    if not rows:
        print("the cut says exactly what the captions say")
        return 0
    print(f"{'moment':12} {'kind':9} {'intended':36} heard")
    print("-" * 96)
    for tag, where, w, h in rows:
        kind = {"delete": "MISSING", "insert": "EXTRA", "replace": "DIFFERS"}[tag]
        print(f"{where:12} {kind:9} {w[:34]:36} {h[:38]}")
    print()
    print("MISSING near a start -> cut too late  (NUDGE_START negative)")
    print("EXTRA   near a start -> cut too early (NUDGE_START positive)")
    print("MISSING at an end -> NUDGE positive;  EXTRA at an end -> NUDGE negative")
    return len(rows)

if __name__ == "__main__":
    sys.exit(0 if main() == 0 else 0)
