# The process

Cut a talking-head video from its own transcript, then compose it with
HyperFrames. One raw recording and one data file per video.

This is the order that works. It is written down because the first few videos
were made in a different order and cost nine renders each.

## The idea

The cut is named in words, not timecodes. You write down the sentences worth
keeping; word-level timings from `whisper.cpp` supply the numbers. A moment is
a label, a start, an end and the line as spoken:

```python
("hook", 3.12, 8.64, "So I don't edit my videos. My last two videos were edited by AI."),
```

Everything after that is derived: the cut, the captions, where graphics land.
Change the words and the numbers follow.

## Before you record

Nothing here is optional, and all of it takes ten minutes.

**Write the brief, including the cue table.** One row per thing that appears on
screen: the words you say on the left, the graphic and how it arrives on the
right. This single table is the difference between one render and nine. Every
graphic decided afterwards, as a note on a finished render, costs a full
re-encode of the whole video.

**Decide the last line.** "End on 'comment Love.'" is a different video from
"end on the sign-off", and changing it later is a recut, not a tweak.

## The order

```bash
python3 ../../pipeline/run.py new <NN-slug> <path/to/raw.mp4>
cd <NN-slug>
python3 ../../pipeline/run.py doctor        # inputs, cues, screens
python3 ../../pipeline/run.py transcribe    # once per recording
python3 ../../pipeline/run.py keep          # cache it with the edit
# write KEEP in edit.py from the transcript
python3 ../../pipeline/run.py loop          # ~5s. Repeat until 0 mismatches
python3 ../../pipeline/run.py render        # the cut footage, ~35s
python3 ../../pipeline/run.py compose       # captions, graphics, index.html
python3 ../../pipeline/run.py check         # must pass
npx hyperframes snapshot --at <cue times> --no-end -o work/look
npx hyperframes preview --background        # review HERE
python3 ../../pipeline/run.py final         # the MP4 you post, ~6 min
```

`render` before `compose`, always: compose describes the footage, so the
footage has to match first. It refuses to run against a stale cut.

## Verification, and what each check cannot see

The loop transcribes the cut audio and aligns it against the captions. Ten
seconds a pass, and it is the fastest way to find a clipped word:

```
intended 314 words, heard 311, 306 matched (97.5%)
0 mismatch(es)
```

Where it is blind, and what to use instead:

| question | the loop | what answers it |
| --- | --- | --- |
| does the cut say what the captions say | yes | |
| does it jump | no | read the cut list; a cut every four seconds on a static shot hitches |
| does a sentence still make sense | no | read the kept lines; a moment opening on "and then" needs its antecedent |
| is a graphic in the right place | no | `snapshot --at` |
| is text covering the speaker's face | no | `snapshot --at`, and look |
| does a number on a card still hold | no | regenerate the cards after any recut |
| is the footage the current cut | no | `compose` compares durations and refuses |

Every defect these videos have shipped was visible before rendering, in a
snapshot, a cut list, a pixel sample or a duration comparison. The renders
were not diagnostic. They were the cost of not looking.

## Review in the preview, not in renders

`npx hyperframes preview --background` is live and instant and shows everything
a render shows except the final encode. Collect every note from one viewing,
apply them together, render once. Watching a six-minute render to decide
whether a label sits too high is the single most expensive habit available.

## What survives, and what is disposable

```
pipeline/            the machinery
pipeline/edits/<slug>/
    edit.py          the whole edit: cut, captions, placements, effects
    cues.md          one line per captured screenshot
    screens/         the screenshots themselves
    compositions/    any sub-composition this video adds
    assets/          images the compositions need
    transcript/      cached, so a rebuild skips whisper
    cards/           generators for anything drawn rather than captured
videos/<slug>/       footage, renders, work files. DELETE FREELY
```

`videos/` is gitignored and reproducible. `run.py new` with an existing edit
restores the compositions, assets and transcript, links the source under the
name `edit.py` expects, and the video rebuilds. Keep the raw recording
somewhere outside the project.

`index.html` is **generated**. Anything hand-edited there dies at the next
compose. Compose warns before overwriting a changed file, and
`npx hyperframes history` can recover the edit, but the durable place for a
change is `edit.py`.

## Things that look like fixes and are not

- `whisper-cli -ml 1 -sow` for better word times. Its times are a partition,
  not onsets, and carry the same lag.
- `--video-frame-format png` for UI recordings. Stalls frame extraction.
- A CSS filter inside a sub-composition slot. Previews correctly, renders
  blank. On the composition's own wrapper it works.
- A registry transition with no content slots. It renders its own placeholder
  material over your footage instead of doing anything to it.
- Cutting on the word grid without checking the envelope. DTW word times run
  late, by 0.6s in places.
