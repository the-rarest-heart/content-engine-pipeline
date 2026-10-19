# Brief — <NN-slug>

Fill this in the **same sitting you film**, while you still remember what you
said and why. Everything below is a decision made once, here, instead of eight
times later over eight renders.

## The post

* **Goal:** Reach (fast hook, short cuts) or Depth (longer explanations)
* **Platforms:** TikTok, Reels, Shorts, YouTube
* **Pacing:** calm, or fast and punchy
* **Caption style:** word-by-word highlight, minimal, or bold
* **Target length:** for example, 30 to 60 seconds
* **Brand rules:** close with "Love." and no dashes in on-screen text

## The cut

* **Must keep:** lines that can't be cut
* **Avoid:** for example, no music over speech
* **End on:** the exact words the video ends on. Write them out. "End on
  'comment Love.'" is a different video from "end on the sign-off", and
  deciding it here saves a full recut.

## The cues

**One row per thing that appears on screen.** The left column is the words you
*say*, quoted closely enough to find in the transcript. The right column is
what appears. This table is the whole edit: if it is filled in before the first
render, there is one render.

| when I say | what appears | how it arrives |
| --- | --- | --- |
|  |  |  |

Screens referenced here go in `pipeline/edits/<slug>/screens/`.

## What the pipeline can actually do

Use these names in the table, so nothing has to be invented mid-edit.

| name | what it does |
| --- | --- |
| `pop` | starts near rest, overshoots once, settles. The default; nothing travels |
| `pop-spin` | same with a slight rotation in |
| `pop-drop` | same, dropping from above |
| `punch-in` | zooms the picture and holds, then releases |
| `zoom pair` | tight on one phrase, all the way out on the next. Good when the words themselves are opposites |
| `pop-up text` | a text chip on a phrase, positioned off the face |
| `filter` | a real grade on the picture, on for a phrase and off again |
| `orbit` | images turning on a ring (Three.js) |
| `emoji` | one glyph; `beat` pulses it |
| `screenshot` | an image from `screens/`, with any of the entrances above |

Two things that are **not** available, because they were tried and did not
work: a filter inside a sub-composition slot (it previews and then renders
blank), and any registry transition that carries no content slots, which puts
a generic graphic over the footage instead of doing something to it.

## Anything on screen that states a number

A card that says "464 words" or "86 clips" is a claim about this cut, and a
recut makes it false. List any here so they get regenerated:

*

