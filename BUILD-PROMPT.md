# Build a Content Engine

Paste this whole file into Claude Code, opened in an empty folder on a Mac.
It is the brief for rebuilding what this repository is, from nothing, on
someone else's machine.

It is written as a specification rather than a script, because the order and
the reasons matter more than the exact commands. Every number in it was
measured on a MacBook Pro M1 Pro, 16 GB, and every trap listed was paid for
once already.

---

## What you are building

A pipeline that turns one talking-head recording into a cut, captioned,
animated vertical video, with as little of a human's attention spent as
possible and none of it spent twice.

The shape of it:

```
  a folder you drop a recording into
        |  a watcher fires on the drop, not on a timer
        v
  measured pages: what was said and when, what is on screen
  a catalog card, a brief, a storyboard
        |  one command adopts it into the repo
        v
  an edit file: the cut, the captions, the placements
        |  a verify loop that never encodes video
        v
  render -> compose -> check -> preview -> export
```

**The whole design serves one rule: never look at an expensive thing twice.**
A transcript is computed once. A frame is read once, into a page. A render
happens once, at the end, after everything cheap has been checked.

---

## Before you write any code

Install these. All are free.

```bash
brew install ffmpeg whisper-cpp
```

You also need Node (for the composition renderer), Python 3.11+, and about
2 GB for a whisper model. Download `ggml-small.en.bin` with DTW support; the
larger models are not worth their runtime for a single clear speaker.

Optional but recommended: [ollama](https://ollama.com) with any small local
instruct model, around 8B. It is used only for labelling, and **nothing it
says is trusted** — see Phase 4, so the particular model barely matters.

For the composition and render layer this project uses HyperFrames, which
renders HTML compositions to MP4 through a headless browser. Any renderer
that can seek deterministically to a frame will do; what matters is that the
composition is data, generated from one file, and never hand-edited.

---

## The principles, which are the actual product

Build these in, or you will rebuild the project later.

**1. The cut is named in words, not timecodes.**
Write the sentences worth keeping; word-level timings supply the numbers.
A moment is a label, a start, an end and the line as spoken:

```python
("hook", 3.12, 8.64, "So I don't edit my videos."),
```

Everything downstream is derived. Change the words and the numbers follow.

**2. Verification never needs a video encode.**
Every edge defect in a cut is audible. Cut the audio, transcribe *that*, and
diff it against the captions. This takes about ten seconds. Rendering the
video first and transcribing that took eighty-nine. Build this loop before
you build anything pretty.

**3. Read pages, not sources.**
Write the expensive things down once, in a form small enough to re-read:
what was said and when (about 1,000 tokens), what is on screen and whether it
covers the speaker's face (about 300). Never read the raw transcript JSON
(35,000) or a contact sheet (1,843 per image, and an image rides along in
context on every later turn). One session on this project carried a 463,000
token context for 1,993 turns before this rule existed.

**4. Decide every on-screen graphic before you film.**
One row per thing that appears: the words on the left, the graphic and its
entrance on the right. The first video built without this table cost nine
renders and fifty-nine minutes of rendering for ninety seconds of video.
Eight of the nine were superseded within minutes. Every one was a single
decision arriving as a note on a finished render.

**5. Nothing gets built from a page nobody agreed to.**
Put a literal line in a file — `STORYBOARD AGREED: no` — and have the build
steps read it and stop. Only the human flips it. This is the cheapest quality
gate there is.

---

## Phase 1 — the cut

Write one module that turns a moments table into an edit decision list.

- Extract 16 kHz mono audio with ffmpeg.
- Transcribe with whisper.cpp using DTW for word-level times:
  `whisper-cli -m <model> -f audio.wav -l en -dtw small.en -nfa -ojf`
  **`-nfa` matters: DTW is silently ignored with flash attention on.**
- Measure silence separately with ffmpeg `silencedetect=noise=-38dB:d=0.3 -vn`.
  You need real silences, not inferred gaps.

**The trap that will cost you a day:** DTW word times run *late*, by 0.25 to
0.60 seconds on real footage. Cutting at the word time eats the first word of
every clip and clips the consonant off a sentence-initial "So". Build a lag
model: compare word onsets against the measured silence boundaries and
correct every edge by the measured offset. Do not hand-tune it per clip.

Squeeze pauses rather than cutting them: a pause over ~0.25s becomes ~0.16s.
A cut that removes a pause entirely reads as a jump.

**A second trap, which you will hit at the end of your first video:** if you
squeeze every silence, you destroy anything that happens *during* one — a
gesture, a smile, a sign-off. Make the squeeze skip a silence that does not
start strictly inside its moment, so a clip that begins mid-silence is passed
through whole.

## Phase 2 — the local prep

Two small programs that run for free and write a page each.

- **Moments:** word times in, a table out — the lines as spoken with in/out
  times, measured dead air, retakes, filler counts.
- **Look:** sample frames, run the OS vision API on each (on macOS, Apple
  Vision via a small Swift binary, ~0.2s a frame), and write what is on
  screen, where it sits, and whether it overlaps the speaker's face.

Two things Vision cannot tell you, and the page should say so: stylised type
comes back misspelt, so trust positions and not spelling; and a logo on a hat
or a shirt is indistinguishable from an overlay. Report, let a human judge.

## Phase 3 — intake

A watcher on a drop folder. On macOS use `launchd` with `WatchPaths`, which
fires on the drop rather than on a timer. A 15-minute cron poll was the
longest wait in the old flow.

**macOS will not let a launchd job read `~/Desktop` or `~/Documents`.** Tested,
not assumed. Do not grant your shell Full Disk Access to work around it: stage
everything in an unprotected folder under `$HOME`, and have a second command,
run from inside a session that already has access, move it into the repo.

Settle the file before touching it (compare size a second apart), dedupe by
sha256 so a re-drop does not make a second project, and move the master out of
the drop folder so no cleanup can take it.

Use a second folder for photos and screenshots. They must not go in the video
inbox, and a junk-drawer folder like `~/Downloads` must never be globbed into
a project — the first version of this did exactly that and would have swept
twenty-five unrelated PNGs into an edit.

## Phase 4 — the brief, the card and the storyboard

A local model can label a video for free. **Check every claim it makes
against something you measured:**

- a best-moment timecode that is not a real line start is dropped, not fixed
- a person's name never reaches the card unless that name is spoken
- a line that breaks a brand rule is dropped rather than rewritten, because
  rewriting it means the machine wrote the words instead of the person
- if the model is not running, write nothing. A card with an invented summary
  is worse than no card.

The storyboard is the page both sides sign: beat by beat, in, out, what is
said, what is on screen, which effect, what text. Propose treatments, then
hold them to the rules — an effect name that is not in the allowed list
becomes `ASK`, and `ASK` means nobody has chosen, which is different from
`none`, meaning someone chose nothing.

Keep the allowed effects as one file each in a folder, and read the list from
that folder. Adding an effect is then adding a page, and the page can carry a
real example from a video that shipped.

A refresh must never overwrite a decision: carry filled rows over by their in
and out, park beats that left the cut at the bottom, keep the human's notes.

## Phase 5 — compose, check, look, export

**Render the cut footage before you compose, always.** Compose describes the
footage, so the footage has to match. Have compose compare the footage's real
duration against the edit list and refuse when they differ. One video shipped
76 seconds of footage across a 90.5 second timeline because a cut changed and
only the composition was rebuilt; every check passed and every snapshot looked
right, because each of them reads the plan rather than the picture.

Separate the two frame rates and name them differently. The **source** rate is
what the cut does frame maths with. The **output** rate is what the renderer
produces. They are usually both 60 and the difference never shows — until
footage arrives from a phone at 120, the output silently renders at 120, and a
twenty minute render takes thirty-six.

Review in a live preview, never in a rendered file. Collect every note from
one viewing, apply them together, render once.

**Export something that plays.** A renderer that defaults to HEVC produces a
file many phones and galleries refuse to open. Always write an H.264 copy
beside the master: `-c:v libx264 -profile:v high -pix_fmt yuv420p -c:a aac`.

## Phase 6 — a window on it

Once it works, the remaining friction is that everything happens in a terminal
or a chat. A local page on `127.0.0.1`, serving from the standard library with
no dependencies, removes most of it: what is waiting, what is running and
roughly how long is left, the storyboard as a table, a button per step, and a
download link for the file that plays.

Have it shell out to the same commands a human would run, so it can do nothing
the pipeline cannot — the agreement gate included.

**`BUILD-APP.md` is this phase in full**: the state model, the five surfaces,
honest progress from a measured rate, and the traps. Build the engine first;
an app on a pipeline that does not exist yet is a shell.

---

## How to know each phase works

| phase | the test |
|---|---|
| cut | the loop reports 0 mismatches between captions and cut audio |
| prep | the two pages are under ~1,500 tokens together and answer "what was said" and "is anything over the face" |
| intake | a dropped file becomes finished pages, unattended, in about a minute |
| labelling | unplug the model: the card is not written, rather than written wrong |
| gate | a build attempted against an unagreed storyboard stops and builds nothing |
| export | the output plays on an Android phone with no conversion |

---

## What to steal, and what to leave

Steal the loop, the pages, the gate and the two folders. Those are the ideas.

Leave the specifics: the library layout, the brand rules, the effect names,
the pillar list. Those are one person's, and copying them gives you their
workflow rather than your own.
