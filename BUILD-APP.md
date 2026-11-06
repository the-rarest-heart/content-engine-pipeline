# Build the app

Paste this whole file into Claude Code, or hand it to a developer. It is the
brief for building the surface people actually use: a local app that takes a
recording and gives back a video, with the pipeline underneath doing the work.

Read `BUILD-PROMPT.md` first. It specifies the engine — the cut, the verify
loop, the pages, the intake, the gate. **This file does not repeat any of it.**
An app on top of a pipeline you have not built yet is a shell.

Everything below was measured on one working implementation: about 700 lines of
Python using only the standard library, and one HTML file. No framework, no
build step, no dependencies. That is not minimalism for its own sake — it is
what makes it still run in a year.

---

## The one rule

**The app shells out to the same commands a human would run.** It can do
nothing the pipeline cannot, including refusing to build against a storyboard
nobody agreed to.

Every button is a subprocess:

```python
cmd = ["python3", "pipeline/run.py", "render", "compose", "check"]
subprocess.Popen(cmd, cwd=video_dir, stdout=logfile, stderr=subprocess.STDOUT)
```

This is the whole architecture, and it is worth defending. It means the app
cannot drift from the pipeline, cannot acquire its own half-correct copy of the
cut logic, and can be deleted without losing anything. It also means anyone who
prefers a terminal still has one.

---

## State

One global job. One lock. Clients poll.

```python
JOB = {"slug": None, "stage": None, "started": 0,
       "done": None, "ok": None, "frames": 0}
```

**Refuse to start a second job while one is running.** A render and a compose
on the same folder will corrupt each other, and the honest answer to a second
click is "something is already running", not a queue. A queue is a feature for
a machine with more than one of you on it.

One `GET /api/state` returns everything a client needs to draw itself: what is
staged and waiting, every project and its status, the running job with elapsed
and estimated time, and how many files sit in each drop folder. The page polls
it. There is no websocket, and at this scale there should not be.

Logs go to one file per project and stage, served raw. When something fails,
the fix is reading what the command printed, not a prettier error.

---

## Honest progress

A progress bar that lies is worse than none. Do not estimate a render from a
guess; **measure your own machine and remember.**

After each successful export, record frames and seconds. Keep a running
seconds-per-frame. The next render's estimate is that rate times this video's
frame count, and it is right within a few percent after two or three videos.

Cap the displayed percentage at 99 until the process actually exits. A bar that
sits at 100% while work continues reads as a hang.

---

## Speak in human terms

The pipeline's stages are named for what they do to files. The app is read by
someone waiting for a video. Translate:

| stage | what the app says |
|---|---|
| `doctor` | Checking everything is there |
| `loop` | Listening to the cut |
| `render` | Cutting the footage |
| `compose` | Laying out the page |
| `final` | Making your video |

This costs one dictionary and changes how the thing feels to use.

---

## The surfaces

Five, one per question someone actually has:

**Words** — the transcript as measured, editable. Whisper mishears names and
brand words every time; fixing them here writes the correction back into the
edit rather than into a file that gets regenerated.

**Plan** — the storyboard as a table: in, out, what is said, what is on screen,
which effect, what text. This is the page both sides sign, and it carries the
agreement line.

**Pictures** — the stills, converted and sized on drop. Dropping a photo should
not require knowing what format the renderer wants.

**Style** — the look as data: accent colour, caption colour, font, border,
corner. Named starting points in a folder, one file each. Picking one copies
its values into that video, so a later change to the starting point never
reaches a video that already chose it.

**Video** — the output, and a link that plays.

---

## The gate, in the app

The build buttons call the same check the command line does, and stop while the
storyboard says `no`. **The app must not offer a way around it.** A button that
flips the agreement is the same as no gate at all; show the line, link to the
page, and let the person edit the file.

The one exception worth building: a project made before the gate existed has no
storyboard page at all, and refusing to build is then unhelpful. Offer to write
the page, not to skip the check.

---

## Always leave something that plays

A renderer that defaults to HEVC produces a file many phones and galleries
refuse to open, with no error — the file simply does not appear. After every
successful export, write an H.264 copy beside the master, automatically:

```
-c:v libx264 -profile:v high -pix_fmt yuv420p -c:a aac
```

Do not make this a button. Nobody remembers to press it, and the failure is
silent and happens on someone else's phone.

---

## Drop targets

Two folders, and the app accepts drops onto itself as a convenience that routes
to the same places:

- a recording goes to the video inbox and starts intake
- photos and screenshots go to the stills folder

**A still dropped in the video inbox is logged and ignored, not guessed at.**
Guessing produces a project made from a screenshot, which is worse than
nothing. See `BUILD-PROMPT.md` Phase 3 for why the folders are outside the
repository and why a junk-drawer folder must never be globbed.

---

## Traps, each paid for once

**Serving files by path from a web handler is an open door.** Resolve every
requested path and confirm it is inside the folder you meant to serve. A slug
arrives from the client and a slug can contain `..`.

**A subprocess whose output nobody reads will block** when the pipe fills. Give
every job a real file handle, not a pipe you plan to read later.

**Reap the process on a thread and record the result.** A job whose exit code
nobody collects shows as running forever, and the next click is refused because
the app still thinks it is busy.

**The browser caches your HTML.** During development this presents as a fix
that did not work. Send `Cache-Control: no-store` for the page.

---

## How to know it works

| the test | what passing means |
|---|---|
| drop a recording on the page | it appears as a project, unattended, in about a minute |
| click build twice | the second click is refused, clearly, and nothing is corrupted |
| build against an unagreed storyboard | it stops, says why, and links to the page |
| watch an export | the estimate is within a few percent, and reaches 100% only on exit |
| open the output on an Android phone | it plays with no conversion |
| kill the app mid-render | the render survives or dies cleanly; the next start is not blocked by a ghost job |
| delete the app | the pipeline still does everything, from a terminal |

That last row is the real test. If removing the app costs you a capability, the
app has grown logic that belonged in the pipeline, and the next person to
change the cut will change it in one place and not the other.

---

## What to steal, and what to leave

Steal the one-job lock, the learned rate, the shell-out architecture, the
automatic playable copy, and the gate the app cannot bypass.

Leave the five tabs, the stage wording and the style fields. Those follow from
one person's way of working, and copying them gives you their habits instead of
your own.
