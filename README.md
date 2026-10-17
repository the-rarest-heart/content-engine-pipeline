# Content Engine pipeline

Scripts that cut a talking-head video from its own transcript, then hand the
result to [HyperFrames](https://github.com/heygen-com/hyperframes) to compose
and render. One raw video and a table of decisions in, a cut and captioned
vertical clip out.

This is the machinery only. Each video is one data file, `edit.py`, that the
scripts read.

## Why it exists

Cutting dead air by hand means scrubbing a timeline. Cutting it from the
transcript means saying which sentences to keep and letting word timings place
every blade. That part is scriptable, so it is scripted. The design is taken
from the parts of a real build that kept going wrong.

## What it does

```
transcribe   whisper.cpp with DTW alignment, plus a measured silence map
cut          keep-list -> edges snapped to the quietest 10ms -> whole frames
verify       transcribe the cut AUDIO and diff it against the intended captions
compose      HyperFrames HTML: captions, emoji, punch-ins, screenshots
fcp          two layers for a finishing pass: picture, and graphics with alpha
```

## The loop

```bash
cd videos/03-my-video
python3 ../../pipeline/run.py doctor      # inputs sane? names match?
python3 ../../pipeline/run.py transcribe  # once
python3 ../../pipeline/run.py loop        # ~10s, encodes no video
```

`loop` cuts, transcribes the cut audio, and prints every mismatch between what
the captions say and what the cut actually says, attributed to the moment whose
edge caused it:

```
moment       kind      intended                heard
additem-a    EXTRA     -                       have
note3pm      MISSING   feed                    -

MISSING near a start -> cut too late  (NUDGE_START negative)
EXTRA   near a start -> cut too early (NUDGE_START positive)
```

Nudge in `edit.py`, run again. Two or three passes is normal.

## Three things this learned the hard way

**Whisper's word times run late.** 0.25 to 0.60s on the footage this was built
against. Cutting at the word time eats the first word of the clip and the
consonant off a sentence-initial "So", which comes back as "Oh". `edl.py`
measures that lag where it can be measured — a word after a real silence has a
true onset — and interpolates it across mid-phrase boundaries.

**Verification does not need a video encode.** Every edge defect is audible.
Transcribing the cut audio takes about 10 seconds. Rendering the video first
and reading the transcript took 89.

**Round every cut to a whole frame.** Otherwise 76 cuts drifted the captions
0.6s by the end.

## Needs

Python 3, FFmpeg, [whisper.cpp](https://github.com/ggerganov/whisper.cpp),
Node 22+ for HyperFrames. A `small.en` model.

## Starting a video

```bash
cp pipeline/edit-template.py videos/03-my-video/edit.py
```

Fill in the tables. `doctor` tells you what is missing.

## Licence

MIT. Built on a MacBook Pro for [The Rarest Heart](https://therarestheart.io).
