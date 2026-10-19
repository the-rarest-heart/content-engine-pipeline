#!/usr/bin/env python3
"""Cut dead air, retakes and tangents. Reads edit.py; writes work/edl.json.

No args prints the plan. --render writes assets/edit.mp4.
"""
import json, math, struct, subprocess, sys, wave
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from config import load as _load
globals().update(_load())

# ---------------------------------------------------------------- audio probe
def load_audio(path="work/audio16k.wav"):
    w = wave.open(path, "rb")
    sr = w.getframerate()
    raw = w.readframes(w.getnframes())
    return sr, struct.unpack(f"<{len(raw)//2}h", raw)

def rms_db(s, sr, t, win=0.010):
    a = max(0, int(t * sr)); b = min(len(s), a + max(1, int(win * sr)))
    if b <= a: return 0.0
    acc = 0
    for i in range(a, b): acc += s[i] * s[i]
    return 20 * math.log10(math.sqrt(acc / (b - a)) / 32768 + 1e-9)

# ---------------------------------------------------- speech envelope
HOP    = 0.010
THRESH = -42.0    # dB; below this counts as silence
BRIDGE = 0.05     # ignore silences shorter than this inside a burst

def envelope(s, sr):
    """RMS dB every HOP seconds."""
    n = int(len(s) / sr / HOP)
    w = max(1, int(HOP * sr))
    env = []
    for i in range(n):
        a = i * w
        seg = s[a:a + w]
        if not seg:
            env.append(-120.0); continue
        acc = 0
        for x in seg: acc += x * x
        env.append(20 * math.log10(math.sqrt(acc / len(seg)) / 32768 + 1e-9))
    return env

def is_speech(env, i):
    return 0 <= i < len(env) and env[i] > THRESH

def onset(env, t_hint, back=0.9):
    """Start of the speech burst at t_hint.

    DTW word times in this recording run 0.25-0.6 s late, so t_hint normally
    sits inside the word. Walk back to where the burst began; if t_hint landed
    in silence instead, walk forward to the next burst.
    """
    i = int(t_hint / HOP)
    lim = int(back / HOP)
    bridge = max(1, int(BRIDGE / HOP))
    if not is_speech(env, i):
        j = i
        while j < len(env) and j < i + lim and not is_speech(env, j):
            j += 1
        i = j
    j = i
    while j > 0 and j > i - lim:
        if not is_speech(env, j):
            k, quiet = j, 0
            while k > 0 and not is_speech(env, k) and quiet < bridge:
                k -= 1; quiet += 1
            if quiet >= bridge:
                return (j + 1) * HOP
            j = k
        else:
            j -= 1
    return max(0.0, (i - lim) * HOP)

def offset(env, t_hint, fwd=0.9):
    """End of the speech burst at t_hint."""
    i = int(t_hint / HOP)
    lim = int(fwd / HOP)
    bridge = max(1, int(BRIDGE / HOP))
    j = i
    while j < len(env) and j < i + lim:
        if not is_speech(env, j):
            k, quiet = j, 0
            while k < len(env) and not is_speech(env, k) and quiet < bridge:
                k += 1; quiet += 1
            if quiet >= bridge:
                return j * HOP
            j = k
        else:
            j += 1
    return min(len(env) * HOP, (i + lim) * HOP)

def silence_runs(env):
    """[(start, end)] of every silent stretch in the envelope."""
    runs, i, n = [], 0, len(env)
    while i < n:
        if not is_speech(env, i):
            j = i
            while j < n and not is_speech(env, j):
                j += 1
            runs.append((i * HOP, j * HOP))
            i = j
        else:
            i += 1
    return runs

def lag_model(env, words, min_sil=0.32):
    """How far behind the audio each DTW word time runs.

    Measured only where it can be measured: a word that follows a real silence
    has a true onset (the end of that silence), so lag = dtw_start - onset.
    Those anchors are then interpolated to cover mid-phrase boundaries, where
    no onset exists to measure against.
    """
    runs = [r for r in silence_runs(env) if r[1] - r[0] >= min_sil]
    anchors = []
    for w in words:
        t = w["start"]
        prev = [r for r in runs if r[1] <= t and t - r[1] <= 0.80]
        if prev:
            lag = t - prev[-1][1]
            if 0.0 <= lag <= 0.80:
                anchors.append((t, lag))
    anchors.sort()
    return anchors

def lag_at(anchors, t, window=20.0):
    """Local median lag. Individual anchors are noisy (a stop consonant can
    look like a pause), so the median of the neighbourhood is used rather than
    interpolation between two of them."""
    if not anchors:
        return 0.35
    near = [l for ts, l in anchors if abs(ts - t) <= window]
    if not near:
        near = [l for _, l in anchors]
    near.sort()
    n = len(near)
    return near[n // 2] if n % 2 else (near[n // 2 - 1] + near[n // 2]) / 2

def after_pause(env, t, min_sil=0.18):
    """True when t begins a phrase rather than sitting mid phrase."""
    i = int(t / HOP)
    need = int(min_sil / HOP)
    back = int(0.70 / HOP)
    quiet = 0
    for j in range(i, max(0, i - back), -1):
        if not is_speech(env, j):
            quiet += 1
            if quiet >= need:
                return True
        elif quiet > 0:
            return False
    return False

def snap(s, sr, t, lo=None, hi=None):
    """Move t to the quietest 10 ms within +/- SNAP seconds."""
    lo = max(0.0, t - SNAP) if lo is None else max(lo, t - SNAP)
    hi = (t + SNAP) if hi is None else min(hi, t + SNAP)
    best, best_db = t, 1e9
    x = lo
    while x <= hi:
        d = rms_db(s, sr, x)
        if d < best_db: best_db, best = d, x
        x += 0.005
    return best

def frames(t):
    return round(t * FPS) / FPS

# ------------------------------------------------------------------ silences
def load_silences(path="work/silences.txt"):
    out, cur = [], None
    for line in open(path):
        p = line.split()
        if not p: continue
        if p[0] == "S": cur = float(p[1])
        elif p[0] == "E" and cur is not None:
            out.append((cur, float(p[1]))); cur = None
    return out

# ---------------------------------------------------------------------- plan
def build():
    sr, s = load_audio()
    sils = load_silences()
    words = json.load(open("work/words.json"))
    env = envelope(s, sr)
    anchors = lag_model(env, words)
    segs, report, segmap = [], [], []
    for label, a0, b0, why in KEEP:
        # Anchor both edges to the word grid. The declared time says which
        # moment is wanted; the word timings decide where the blade may land,
        # so a cut can never fall inside a word it is meant to keep or drop.
        kept_ix = [i for i, w in enumerate(words) if a0 - 0.02 <= w["start"] < b0 - 0.02]
        kept = [words[i] for i in kept_ix]
        if label in OVERRIDE:
            oa, ob = OVERRIDE[label]
            a, b = frames(oa), frames(ob)
        elif kept:
            w_first = kept[0]
            nxt = next((w for w in words if w["start"] >= kept[-1]["start"] + 1e-6), None)
            # Start: a phrase start has a real onset to measure; a mid-phrase
            # start has none, so it uses the DTW time pulled back by the lag
            # model and must NOT walk back to the burst start, or it drags in
            # the words this cut exists to remove.
            fs = w_first["start"]
            ns = NUDGE_START.get(label, 0.0)
            if after_pause(env, fs):
                a = frames(max(0.0, onset(env, fs) - 0.06 + ns))
            else:
                est = fs - lag_at(anchors, fs) + ns
                a = frames(max(0.0, snap(s, sr, est, lo=est - 0.07, hi=est + 0.05)))
            # End: the first dropped word's DTW time, pulled back the same way,
            # then nudged to the quietest point just before it.
            if nxt:
                hint = nxt["start"] - lag_at(anchors, nxt["start"]) + NUDGE.get(label, 0.0)
                # symmetric: the estimate can land either side of the true
                # boundary, so let the search find the trough in both directions
                lo_b = max(a + 0.08, hint - 0.07)
                hi_b = max(lo_b + 0.01, hint + 0.07)
                b = frames(snap(s, sr, hint, lo=lo_b, hi=hi_b))
            else:
                b = frames(offset(env, kept[-1]["start"]) + 0.08)
        else:
            a = frames(snap(s, sr, a0, lo=a0 - SNAP, hi=a0 + SNAP))
            b = frames(snap(s, sr, b0, lo=b0 - SNAP, hi=b0 + SNAP))
        if b <= a:
            a, b = frames(a0), frames(b0)
        # split on internal pauses, squeezing each down
        keep_thr = TIGHT_KEEP if label in TIGHT else PAUSE_KEEP
        squeeze  = TIGHT_TO   if label in TIGHT else SQUEEZE_TO
        parts, cut, saved = [], a, 0.0
        for sa, sb in sils:
            if sa > a + 0.02 and sb < b - 0.02 and (sb - sa) > keep_thr:
                mid_a = frames(sa + squeeze / 2)
                mid_b = frames(sb - squeeze / 2)
                if mid_a > cut and mid_b > mid_a:
                    parts.append((cut, mid_a))
                    saved += mid_b - mid_a
                    cut = mid_b
        parts.append((cut, b))
        parts = [(p, q) for p, q in parts if q - p > FRAME]
        for ca, cb in INSIDE_CUTS:
            nxt_parts = []
            for p, q in parts:
                if cb <= p or ca >= q:
                    nxt_parts.append((p, q)); continue
                if p < ca: nxt_parts.append((p, frames(ca)))
                if q > cb: nxt_parts.append((frames(cb), q))
            parts = [(p, q) for p, q in nxt_parts if q - p > FRAME]
        segs.extend(parts)
        segmap.append({"label": label, "words": kept_ix,
                       "parts": [[round(p, 5), round(q, 5)] for p, q in parts]})
        report.append((label, a, b, sum(q - p for p, q in parts), saved, why, len(parts)))
    # Merge away trims too small to be worth a visible cut.
    #
    # A cut on a static talking head costs something even when it removes
    # nothing of value: the head jumps. Independent edge snapping on two
    # CONTIGUOUS moments pulls one boundary earlier and the next later, which
    # opens a hole of a tenth of a second where the take was continuous, and
    # the viewer sees a hitch that buys no time at all. Anything under
    # MIN_TRIM is not removed: the footage stays joined.
    min_trim = MIN_TRIM if "MIN_TRIM" in globals() else 0.0
    if min_trim > 0:
        merged, dropped = [segs[0]], 0.0
        for a, b in segs[1:]:
            pa, pb = merged[-1]
            if 0 < a - pb < min_trim:
                merged[-1] = (pa, b)      # one continuous piece, nothing cut
                dropped += a - pb
            else:
                merged.append((a, b))
        if len(merged) != len(segs):
            print(f"merged {len(segs) - len(merged)} micro cuts "
                  f"(kept {dropped:.2f}s that was not worth a jump)")
        # The moments have to TILE the merged segments: every instant of
        # kept footage must belong to exactly one moment, with no holes and no
        # overlaps. Intersecting each moment with its own original span left
        # the merged gap belonging to nobody, so the durations summed short,
        # every edit_start after the first merge was early, the captions ran
        # ahead of the voice, and anything positioned from a moment start (the
        # zoom through) fired in the wrong place.
        #
        # Each moment therefore owns [its own start, the next moment's start),
        # and the last one owns everything to the end.
        bounds = [min(p for p, _ in m["parts"]) for m in segmap]
        for n, m in enumerate(segmap):
            a = bounds[n]
            b = bounds[n + 1] if n + 1 < len(bounds) else float("inf")
            fixed = []
            for sa, sb in merged:
                p, q = max(sa, a), min(sb, b)
                # Partitioning, not segmenting: a sub-frame sliver still
                # carries its duration and dropping it is exactly the one
                # frame of drift this assertion catches.
                if q - p > 1e-9:
                    fixed.append([round(p, 5), round(q, 5)])
            if fixed:
                m["parts"] = fixed

        # The sum has to match the cut exactly, or caption timing is built on a
        # different video than the one being rendered.
        _seg = sum(b - a for a, b in merged)
        _map = sum(q - p for m in segmap for p, q in m["parts"])
        if abs(_seg - _map) > 0.002:
            sys.exit(f"segmap does not tile the cut: {_map:.3f}s mapped against "
                     f"{_seg:.3f}s of segments ({_seg - _map:+.3f}s). "
                     f"Caption timing would drift by that much.")
        segs = merged

    # edit-time offset of each moment, in order
    acc = 0.0
    for m in segmap:
        m["edit_start"] = round(acc, 5)
        acc += sum(q - p for p, q in m["parts"])
    json.dump(segmap, open("work/segmap.json", "w"), indent=1)
    return segs, report

def main():
    segs, report = build()
    total = sum(b - a for a, b in segs)
    print(f"{'moment':11} {'source in':>9} {'source out':>10} {'raw':>6} {'kept':>6} {'pause-':>7}")
    print(f"{'':11} {'':>9} {'':>10} {'':>6} {'':>6} {'saved':>7}")
    print("-" * 78)
    t = 0.0
    for label, a, b, kept, saved, why, n in report:
        print(f"{label:11} {a:9.2f} {b:10.2f} {b-a:6.2f} {kept:6.2f} {saved:7.2f}")
        t += kept
    print("-" * 78)
    src_speech = 214.35 - 4.52
    print(f"source speech      {src_speech:7.2f}s")
    print(f"after content cuts {sum(b-a for _,a,b,_,_,_,_ in report):7.2f}s")
    print(f"after pause squeeze{total:7.2f}s   ({int(total//60)}m {total%60:04.1f}s)")
    print(f"segments           {len(segs)}")
    json.dump([[round(a,5), round(b,5)] for a, b in segs], open("work/edl.json", "w"), indent=1)
    print("wrote work/edl.json")
    if "--render" in sys.argv:
        render(segs)

def in_app(t):
    return any(a <= t <= b for a, b in APP_SPANS)

def render(segs):
    vf, af = [], []
    for i, (a, b) in enumerate(segs):
        chain = f"[0:v]trim=start={a:.5f}:end={b:.5f},setpts=PTS-STARTPTS"
        if in_app((a + b) / 2):
            for x, y, w, h in MASKS:
                chain += f",drawbox=x={x}:y={y}:w={w}:h={h}:color={HDR_BG}:t=fill"
        vf.append(chain + f"[v{i}]")
        af.append(f"[0:a]atrim=start={a:.5f}:end={b:.5f},asetpts=PTS-STARTPTS,"
                  f"afade=t=in:st=0:d={FADE},afade=t=out:st={max(0,(b-a)-FADE):.5f}:d={FADE}[a{i}]")
    n = len(segs)
    cat = "".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a]"
    graph = ";".join(vf + af + [cat])
    open("work/filtergraph.txt", "w").write(graph)
    cmd = ["ffmpeg", "-y", "-v", "error", "-stats", "-i", SRC,
           "-filter_complex_script", "work/filtergraph.txt",
           "-map", "[v]", "-map", "[a]",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
           "-pix_fmt", "yuv420p", "-r", "60",
           "-c:a", "aac", "-b:a", "192k", "assets/edit.mp4"]
    print("rendering assets/edit.mp4 ...")
    subprocess.run(cmd, check=True)
    print("done")

if __name__ == "__main__":
    main()

