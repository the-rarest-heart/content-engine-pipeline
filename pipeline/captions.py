#!/usr/bin/env python3
"""Map word timings into edit time and apply spelling fixes."""
import json, sys
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from config import load as _load
globals().update(_load())

def apply_patch(words):
    repl, drop = {}, set()
    for i, w in enumerate(words):
        low = w['w'].lower()
        for txt, lo, hi, to in PATCH:
            if low == txt and lo <= w['start'] <= hi:
                if to is None: drop.add(i)
                else: repl[i] = to
        for txt, lo, hi, newt in TIME_PATCH:
            if low == txt and lo <= w['start'] <= hi:
                w['start'] = newt
                w['no_lag'] = True
    return repl, drop

def true_times(words):
    """DTW word times run late by a measured amount; correct them with the same
    lag model the cut uses, so captions survive the same cuts the audio does and
    land on the voice instead of 0.4s behind it."""
    import edl
    sr, s = edl.load_audio()
    env = edl.envelope(s, sr)
    anchors = edl.lag_model(env, words)
    for w in words:
        w['true'] = w['start'] if w.get('no_lag') else \
                    max(0.0, w['start'] - edl.lag_at(anchors, w['start']))
    # keep them ordered
    for i in range(1, len(words)):
        if words[i]['true'] < words[i-1]['true']:
            words[i]['true'] = words[i-1]['true']
    return words

def main():
    words = json.load(open('work/words.json'))
    repl, drop = apply_patch(words)
    words = true_times(words)
    segmap = json.load(open('work/segmap.json'))

    total = sum(q - p for m in segmap for p, q in m['parts'])

    out = []
    for m in segmap:
        # Which words this moment keeps is already decided by the cut; the only
        # question here is where each one lands in edit time. A word whose
        # corrected time falls inside a squeezed pause is clamped to the nearest
        # kept part rather than dropped.
        for i in m['words']:
            if i in drop:
                continue
            t = words[i]['true']
            off, placed = m['edit_start'], None
            for p, q in m['parts']:
                if t < p:
                    placed = off; break
                if p <= t < q:
                    placed = off + (t - p); break
                off += q - p
            if placed is None:
                off = m['edit_start'] + sum(q - p for p, q in m['parts'])
                placed = max(m['edit_start'], off - 0.05)
            txt = repl.get(i, words[i]['w'])
            txt = txt.replace('—', ' ').replace('–', ' ').replace('-', ' ')
            out.append({'w': txt, 'start': round(placed, 3), 'end': None,
                        'm': m['label']})

    out.sort(key=lambda x: x['start'])
    for i, w in enumerate(out):
        nxt = out[i+1]['start'] if i+1 < len(out) else total
        w['end'] = round(min(nxt, w['start'] + HOLD), 3)
        if w['end'] <= w['start']:
            w['end'] = round(w['start'] + 0.08, 3)

    json.dump(out, open('work/captions.json', 'w'), indent=1)
    print(f'{len(out)} caption words over {total:.2f}s -> work/captions.json')
    bad = [w['w'] for w in out if '-' in w['w'] or '[' in w['w'] or ']' in w['w']]
    print('dashes/brackets:', bad if bad else 'none')
    print()
    print('--- caption text as it will read on screen ---')
    print(' '.join(w['w'] for w in out))

if __name__ == '__main__':
    main()

