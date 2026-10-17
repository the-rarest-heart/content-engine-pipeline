#!/usr/bin/env python3
"""Flatten whisper.cpp DTW token output into word-level timings.

t_dtw is a DTW-aligned timestamp in centiseconds; it is far more accurate at
word edges than whisper's own offsets (SOP errors 6 and 7). Sub-word tokens are
merged: a token beginning with a space starts a new word.
"""
import json, re, sys

# whisper.cpp emits markers like [_BEG_], [_TT_456], [_EOT_]. They can arrive as
# continuation tokens (no leading space), so strip them from any token text
# rather than only skipping whole-token matches.
SPECIAL = re.compile(r'\[_[A-Za-z0-9]+_?[0-9]*\]')

def load(path):
    return json.load(open(path))['transcription']

def tokens(segs):
    for s in segs:
        for t in s.get('tokens', []):
            raw = t.get('text', '')
            txt = SPECIAL.sub('', raw)
            if not txt.strip():
                continue
            dtw = t.get('t_dtw', -1)
            yield txt, (dtw / 100.0 if dtw is not None and dtw >= 0 else None), \
                  t['offsets']['from'] / 1000.0, t['offsets']['to'] / 1000.0

def build(segs):
    words = []
    for txt, dtw, off_a, off_b in tokens(segs):
        new = txt.startswith(' ') or not words
        core = txt.strip()
        if not core:
            continue
        if new:
            words.append({'w': core,
                          'dtw': dtw,
                          'off_a': off_a,
                          'off_b': off_b})
        else:
            words[-1]['w'] += core
            words[-1]['off_b'] = off_b
            if words[-1]['dtw'] is None:
                words[-1]['dtw'] = dtw
    # start time: prefer dtw, fall back to whisper offset
    for w in words:
        w['start'] = w['dtw'] if w['dtw'] is not None else w['off_a']
    # monotonic
    for i in range(1, len(words)):
        if words[i]['start'] < words[i-1]['start']:
            words[i]['start'] = words[i-1]['start']
    # 'end' fills to the next word so captions never gap; 'spoken' is whisper's
    # own measured token end, used to find real pauses.
    for i, w in enumerate(words):
        nxt = words[i+1]['start'] if i+1 < len(words) else None
        w['end'] = nxt if nxt is not None else max(w['off_b'], w['start'] + 0.2)
        if w['end'] <= w['start']:
            w['end'] = w['start'] + 0.08
        w['spoken'] = min(max(w['off_b'], w['start'] + 0.05), w['end'])
    return [{'w': w['w'], 'start': round(w['start'], 3),
             'end': round(w['end'], 3), 'spoken': round(w['spoken'], 3)}
            for w in words]

if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    ws = build(load(src))
    json.dump(ws, open(dst, 'w'), indent=1)
    print(f'{len(ws)} words -> {dst}')
    print(f'span {ws[0]["start"]:.2f}s .. {ws[-1]["end"]:.2f}s')
