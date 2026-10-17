#!/usr/bin/env python3
"""Find and load the edit for the video folder we are standing in.

Everything that is expensive to recreate lives in pipeline/edits/<slug>/ and
is committed:

    pipeline/edits/03-name/
        edit.py          the whole edit
        cues.md          "what you say" -> file in screens/
        screens/         the screenshots
        EDIT-PLAN.md     what was approved

The video folder itself holds only the footage and what the pipeline rebuilds
from it, so it can be deleted or moved off the machine at any time. Getting a
video back means putting the footage in a folder of the same name and running
the pipeline again.
"""
import importlib.util, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EDITS = os.path.join(HERE, "edits")

def edit_dir(slug=None):
    """Where this video's edit lives. Falls back to the video folder itself."""
    slug = slug or os.path.basename(os.getcwd())
    shared = os.path.join(EDITS, slug)
    if os.path.exists(os.path.join(shared, "edit.py")):
        return shared
    if os.path.exists(os.path.join(os.getcwd(), "edit.py")):
        return os.getcwd()
    return shared          # the place it should be, so callers can name it

def load(slug=None):
    d = edit_dir(slug)
    path = os.path.join(d, "edit.py")
    if not os.path.exists(path):
        sys.exit(
            f"no edit found for {os.path.basename(os.getcwd())!r}.\n"
            f"  expected: {path}\n"
            f"  create it with:  python3 {HERE}/run.py new <slug> <source.mp4>")
    spec = importlib.util.spec_from_file_location("edit", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    g = {k: v for k, v in vars(mod).items() if not k.startswith("_")}
    g["EDIT_DIR"] = d
    g["SCREENS_DIR"] = os.path.join(d, "screens")
    g["CUES"] = os.path.join(d, "cues.md")
    return g
