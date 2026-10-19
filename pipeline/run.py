#!/usr/bin/env python3
"""One entry point for the whole edit. Run it from a video folder.

    python3 ../../pipeline/run.py loop     # the inner loop: cut, hear it, diff
    python3 ../../pipeline/run.py compose  # captions, index.html, EDIT-PLAN.md
    python3 ../../pipeline/run.py all

The inner loop never encodes video. Every edge defect this pipeline has ever had
is audible, and transcribing ~16s of join audio finds them in a fraction of the
time a 2 minute H.264 encode takes.
"""
import os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.expanduser("~/.cache/hyperframes/whisper/models/ggml-small.en.bin")

def run(*cmd, **kw):
    r = subprocess.run(list(cmd), **kw)
    if r.returncode != 0:
        sys.exit(f"failed: {' '.join(cmd[:3])}...")
    return r

def py(script, *args):
    return run(sys.executable, os.path.join(HERE, script), *args)

def cfg():
    sys.path.insert(0, HERE)
    from config import load
    return load()

def transcribe():
    """Source audio, DTW word times, silence map, words.json. Run once."""
    c = cfg()
    os.makedirs("work", exist_ok=True)
    os.makedirs("assets", exist_ok=True)
    run("ffmpeg", "-y", "-v", "error", "-i", c["SRC"],
        "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", "work/audio16k.wav")
    # DTW needs flash attention off, or it is silently ignored
    run("whisper-cli", "-m", MODEL, "-f", "work/audio16k.wav", "-l", "en",
        "-dtw", "small.en", "-nfa", "-ojf", "-of", "work/transcript-dtw", "-t", "8",
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    sil = subprocess.run(
        ["ffmpeg", "-i", c["SRC"], "-af", "silencedetect=noise=-38dB:d=0.3",
         "-vn", "-f", "null", "-"], capture_output=True, text=True).stderr
    with open("work/silences.txt", "w") as f:
        for line in sil.splitlines():
            if "silence_start:" in line:
                f.write("S " + line.split("silence_start:")[1].strip() + "\n")
            elif "silence_end:" in line:
                f.write("E " + line.split("silence_end:")[1].split("|")[0].strip() + "\n")
    py("words.py", "work/transcript-dtw.json", "work/words.json")

def loop():
    """Cut it, hear it, and report every defect at once. No video is encoded.

    Transcribing the whole cut audio costs about 7s, so there is nothing to be
    saved by only listening to the joins, and the full text is what diff.py can
    actually align against.
    """
    py("edl.py")
    py("captions.py")        # diff compares against these, so rebuild them
    py("verify.py")
    py("diff.py", "work/cut-heard.txt")

def edges():
    """Just the audio either side of every join, for an ear check."""
    py("verify.py", "--edges")

def fcp():
    """Export the two layers a Final Cut finishing pass wants.

    SPEC calls this the best default for a hero piece: the picture with its
    camera moves underneath, and every caption, emoji, screenshot and card as
    one transparent layer on the track above. Drop footage on V1 and overlay
    on V2 and it looks like the delivered render, except the graphics can be
    retimed, restyled or thrown away without touching the shot.
    """
    import shutil
    os.makedirs("fcp", exist_ok=True)
    py("build.py", "footage")
    py("build.py", "overlay")
    run("npx", "hyperframes", "render", "-c", "footage.html",
        "-o", "fcp/footage.mp4", "-q", "delivery")
    # MOV is ProRes 4444, which is what carries the alpha channel
    run("npx", "hyperframes", "render", "-c", "overlay.html",
        "-o", "fcp/overlay.mov", "--format", "mov")
    py("build.py")                     # leave index.html as the full composition
    for f in ("footage.html", "overlay.html"):
        if os.path.exists(f):
            os.remove(f)
    print("\n  fcp/footage.mp4   picture and camera moves, no graphics")
    print(  "  fcp/overlay.mov   every graphic, transparent, ProRes 4444")
    print(  "  assets/edit.mp4   the cut with no camera moves, if you would rather")
    print(  "                    do your own\n")
    py("fcpxml.py")
    print(  "  In Final Cut: footage on V1, overlay on V2, both at 00:00.")

def compose():
    py("shots.py")
    py("captions.py")
    py("build.py")
    py("plan.py")

def new():
    """Start a video, or bring a deleted one back.

        run.py new 03-slug /path/to/source.mp4      (run from videos/)

    The edit itself is created in pipeline/edits/<slug>/ and stays there. The
    video folder holds only the footage and what gets rebuilt from it, so it
    can be deleted or moved off the machine whenever space is needed. Running
    this again with the same slug reuses the existing edit instead of
    overwriting it, which is how a deleted video comes back.
    """
    if len(sys.argv) < 4:
        sys.exit("usage: run.py new <03-slug> <path/to/source.mp4>   (run from videos/)")
    slug, src = sys.argv[2], sys.argv[3]
    if not os.path.exists(src):
        sys.exit(f"no such file: {src}")

    edit_dir = os.path.join(HERE, "edits", slug)
    os.makedirs(os.path.join(edit_dir, "screens"), exist_ok=True)
    edit_py, restored = os.path.join(edit_dir, "edit.py"), False
    if os.path.exists(edit_py):
        restored = True
    else:
        body = open(os.path.join(HERE, "edit-template.py")).read().replace(
            'SRC        = "<source>.mp4"', f'SRC        = "{os.path.basename(src)}"')
        open(edit_py, "w").write(body)
    cues = os.path.join(edit_dir, "cues.md")
    if not os.path.exists(cues):
        open(cues, "w").write(
            "# Cue sheet. One line per screenshot, written the same sitting you film.\n"
            "# Left: the words you say. Right: the file in screens/.\n"
            "# The file name alone should explain what it shows.\n"
            "#\n"
            '# "pull the cable"  -> cable-unplugged.png\n')

    run("npx", "hyperframes", "init", slug, "--non-interactive",
        "--video", os.path.abspath(src), "--skill", "general-video")

    # Anything the edit keeps under compositions/ or assets/ goes back into the
    # video folder at the same relative path. Without this a rebuild came back
    # without its sub-compositions: edit.py was restored but the orbit scene
    # and the paper rip were not, and a fresh "hyperframes add" would reinstall
    # a pristine component over a vendored one that was deliberately changed.
    import shutil as _sh
    for tree in ("compositions", "assets"):
        srcdir = os.path.join(edit_dir, tree)
        if not os.path.isdir(srcdir):
            continue
        for root, _dirs, files in os.walk(srcdir):
            for name in files:
                if name == ".DS_Store":
                    continue
                full = os.path.join(root, name)
                rel = os.path.relpath(full, edit_dir)
                dest = os.path.join(slug, rel)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                _sh.copyfile(full, dest)
                print(f"    restored {rel}")

    # The transcript is the one expensive step in a rebuild and it never
    # changes unless the footage does, so it lives with the edit.
    if restored:
        tdir = os.path.join(edit_dir, "transcript")
        if os.path.isdir(tdir):
            os.makedirs(os.path.join(slug, "work"), exist_ok=True)
            for name in os.listdir(tdir):
                _sh.copyfile(os.path.join(tdir, name),
                             os.path.join(slug, "work", name))
                print(f"    restored work/{name}")

    # edit.py names its source file; the copy that landed here is named after
    # whatever the archive called it. Link the expected name to it so a rebuild
    # does not need the raw footage renamed by hand.
    if restored:
        want = None
        for line in open(edit_py):
            if line.startswith("SRC"):
                want = line.split("=", 1)[1].strip().strip('"\'')
                break
        if want and not os.path.exists(os.path.join(slug, want)):
            here = [f for f in os.listdir(slug)
                    if f.lower().endswith((".mp4", ".mov", ".m4v"))]
            if len(here) == 1:
                try:
                    os.link(os.path.join(slug, here[0]), os.path.join(slug, want))
                except OSError:
                    _sh.copyfile(os.path.join(slug, here[0]), os.path.join(slug, want))
                print(f"    linked {want} -> {here[0]}  (edit.py names the source)")
            elif not here:
                print(f"    NOTE edit.py wants {want}; no video file found here")
            else:
                print(f"    NOTE edit.py wants {want}; several videos here, link it yourself")

    rel = os.path.relpath(edit_dir, os.path.join(os.getcwd(), slug))
    if restored:
        print(f"\n  {slug}/ rebuilt against the existing edit at {rel}")
        print(f"    cd {slug} && python3 ../../pipeline/run.py doctor")
        print( "    python3 ../../pipeline/run.py loop render compose")
    else:
        print(f"\n  {slug}/ ready. The edit lives at {rel} and survives deleting this folder.")
        print(f"    cd {slug}")
        print(f"    # screenshots -> {rel}/screens/ , cues -> {rel}/cues.md")
        print( "    python3 ../../pipeline/run.py doctor")
        print( "    python3 ../../pipeline/run.py transcribe")

def final():
    """Render the composition to out/<slug>.mp4 — the file you actually post.

    Roughly 1.6x realtime at 1080x1920/60, so a 100s video is about 9 minutes.
    `render` above is a different thing: it rebuilds the cut footage that this
    composition plays underneath the graphics.
    """
    slug = os.path.basename(os.getcwd())
    out = os.path.join("out", f"{slug}.mp4")
    os.makedirs("out", exist_ok=True)
    run("npx", "hyperframes", "render", "-o", out)
    if os.path.exists(out):
        print(f"\n  {out}  {os.path.getsize(out) / 1e6:.0f} MB")
        print( "  verify it before posting, against the render and not a snapshot:")
        print( "    python3 ../../pipeline/run.py loop   # re-reads the finished file")


def keep_transcript():
    """Copy this video's transcript into its edit, so a rebuild skips whisper.

    work/words.json and work/transcript-dtw.json are derived purely from the
    footage. Re-deriving them on every rebuild is the only slow part of
    bringing a deleted video back.
    """
    import shutil
    slug = os.path.basename(os.getcwd())
    dest = os.path.join(HERE, "edits", slug, "transcript")
    os.makedirs(dest, exist_ok=True)
    kept = 0
    for name in ("words.json", "transcript-dtw.json", "audio16k.wav", "silences.txt"):
        src = os.path.join("work", name)
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(dest, name))
            print(f"  kept {name}  {os.path.getsize(src)/1e6:.1f} MB")
            kept += 1
    if not kept:
        sys.exit("nothing to keep: run transcribe first")
    print(f"\n  a rebuild of {slug} will now skip transcribing")


STAGES = {
    "new":        new,
    "doctor":     lambda: py("doctor.py"),
    "shots":      lambda: py("shots.py"),
    "transcribe": transcribe,
    "keep":       keep_transcript,
    "cut":        lambda: py("edl.py"),
    "loop":       loop,
    "edges":      edges,
    "render":     lambda: py("edl.py", "--render"),
    "compose":    compose,
    "fcp":        fcp,
    "fcpxml":     lambda: py("fcpxml.py"),
    "check":      lambda: run("npx", "hyperframes", "check"),
    "final":      final,
    # render BEFORE compose, always: compose describes the footage, so the
    # footage has to exist and match first. compose now refuses stale footage
    # rather than quietly composing against it.
    "all":        lambda: (loop(), py("edl.py", "--render"), compose(),
                           run("npx", "hyperframes", "check"), final()),
}

if __name__ == "__main__":
    want = sys.argv[1:] or ["loop"]
    # "new" takes its own arguments; everything else is a list of stages
    if want and want[0] == "new":
        want = ["new"]
    for stage in want:
        if stage not in STAGES:
            sys.exit(f"unknown stage {stage!r}. one of: {', '.join(STAGES)}")
        t = time.time()
        print(f"\n=== {stage} ===")
        STAGES[stage]()
        print(f"--- {stage} took {time.time()-t:.1f}s")
