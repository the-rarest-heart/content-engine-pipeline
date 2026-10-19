"""Everything specific to ONE video. Copy this to a new video folder as edit.py.

The machinery is in pipeline/ and should not need changing. Fill in the tables
below, then:

    python3 ../../pipeline/run.py transcribe   # once
    python3 ../../pipeline/run.py loop         # repeat until the diff is clean
    python3 ../../pipeline/run.py render compose

Measure, do not guess. Section 7b of SOP.md says which four numbers to take off
the footage before writing anything here.
"""

# ==========================================================================
# THE CUT
# ==========================================================================
SRC        = "<source>.mp4"      # the file inside this folder
FPS        = 60.0                # ffprobe r_frame_rate, exactly
FRAME      = 1.0 / FPS
PAUSE_KEEP = 0.25                # pauses longer than this get squeezed
SQUEEZE_TO = 0.16
MIN_TRIM   = 0.35   # trims shorter than this are not worth a visible jump                # ...down to about this
SNAP       = 0.12                # search window for the quietest edge
FADE       = 0.012               # audio fade at each join

# Moments where the speaker is typing on screen: those pauses are mechanical,
# not breathing room, so they squeeze harder without sounding rushed.
TIGHT      = set()
TIGHT_KEEP = 0.22
TIGHT_TO   = 0.14

# SPEC guardrail: never capture anything showing how the product is built.
# Boxes are painted in the UI's own colour, so sample it rather than using
# black. Gated to APP_SPANS so a face shot is never covered.
HDR_BG    = "0x141418"
MASKS     = []                   # [(x, y, w, h), ...]
APP_SPANS = []                   # [(from, to), ...] source seconds the screen share is up

# Each row is a moment: label, source in, source out, and what it says.
# Put the reason for any internal cut in the text after two spaces and [].
KEEP = [
    # ("hook",  0.00, 5.00, "the line as it should read  [cut: the stumble]"),
]

NUDGE       = {}   # end edge, seconds. Positive keeps more, negative cuts more.
NUDGE_START = {}   # start edge
OVERRIDE    = {}   # {"label": (in, out)} where DTW is measurably wrong
INSIDE_CUTS = []   # [(from, to)] stutters excised from inside a kept moment

# ==========================================================================
# CAPTIONS
# ==========================================================================
HOLD = 0.75        # max time one word stays highlighted

# Whisper's mistakes, anchored by (text, time window) so a fix cannot hit the
# wrong instance. None drops the word; it has been merged into its neighbour.
PATCH      = []    # [("hyper", 14.05, 14.25, "HyperFrames"), ("frames", 14.25, 14.60, None)]
TIME_PATCH = []    # [("love.", 213.90, 214.20, 213.45)] where DTW is measurably wrong

# ==========================================================================
# THE COMPOSITION
# ==========================================================================
W, H, FPS_OUT = 1080, 1920, 60
GREEN = "#39FF14"                      # sample the product's own accent
DIM   = "rgba(255,255,255,.72)"
SPLIT = 1312                           # measured: app above, webcam below

CAP_BOTTOM   = {"screen": 1286, "face": 1800}   # caption bottom edge, per shot
CAP_OVERRIDE = {}                               # {"label": y} where the layout differs

SHOTS = []   # (moment, offset, duration, asset, width, top, slide-from)
PUNCH = []   # (moment, offset, duration, scale, origin-x %, origin-y %)
EMOJI = []   # (moment, offset, duration, emoji, x %, y %)

# The one animation. None for no animation.
ANIM = None   # {"at": ("hook", 0.35), "dur": 10.0, "top": 120, "tick": True,
              #  "title": "Action Items", "rows": [("Send emails", "Rarity")]}

# The brand close. Shown over the last moment; every TRH video ends on it.
CLOSE_CARD = None   # {"text": "Love.", "at": ("close", 0.4), "dur": 2.4, "top": 980}

# ==========================================================================
# VERIFICATION
# ==========================================================================
# Whisper mishearings that are not cut defects. Listing them here keeps the
# diff showing only real problems.
HEARD_OK = []    # [("hyperframes", "hyper frames"), ("claude", "cloud"), ...]

SRC_DURATION = 0.0               # ffprobe, for the plan
SPEECH_FROM, SPEECH_TO = 0.0, 0.0
