#!/usr/bin/env python3
"""Generate index.html from the cut, the captions and the placements."""
import json, subprocess, sys, html
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from config import load as _load
globals().update(_load())

def esc(t): return html.escape(t, quote=True)

def main(mode="full", out_name="index.html"):
    # footage mode keeps the picture and its camera moves and drops every
    # graphic, so Final Cut gets the shot underneath and the overlay on top
    global ANIM, SHOTS, EMOJI, CLOSE_CARD, PAPERCUT
    if mode == "footage":
        ANIM, SHOTS, EMOJI, CLOSE_CARD = None, [], [], None
        PAPERCUT = None
    # The root composition is named after the folder. It used to be hardcoded
    # as "action-items", video 2's slug, on every video since.
    slug = _os.path.basename(_os.getcwd()) or "video"
    import edl
    segs, report = edl.build()
    APP = APP_SPANS

    # moment label -> (edit_in, edit_out, shot)
    #
    # Read from segmap, never recomputed here. report's `kept` is captured
    # inside the per-moment loop, before the micro-cut merge runs, so adding it
    # up put every graphic on a different clock from the captions: shots,
    # punches, emoji and the zoom through all drifted up to 1.3s early by the
    # end of the video while the captions stayed correct. segmap is the one
    # thing that provably tiles the cut, so both clocks come from it.
    smap  = json.load(open("work/segmap.json"))
    spans = {r[0]: (r[1], r[2]) for r in report}
    M, total = {}, 0.0
    for m in smap:
        label = m["label"]
        kept  = sum(q - p for p, q in m["parts"])
        a, b  = spans.get(label, (0.0, 0.0))
        mid   = (a + b) / 2
        shot  = "screen" if any(x <= mid <= y for x, y in APP) else "face"
        st    = m["edit_start"]
        M[label] = (round(st, 3), round(st + kept, 3), shot)
        total = max(total, st + kept)
    total = round(total, 3)

    # The footage has to BE the cut this composition describes.
    #
    # run.py loop rebuilds the EDL and verifies the cut audio, but it does not
    # write assets/edit.mp4; only run.py render does. Change the cut, compose,
    # and render final without that step and the composition plays a short clip
    # across a long timeline: the picture and sound run out partway through
    # while the captions keep going, so the text drifts further from the voice
    # the longer it plays and every effect fires against footage that is not
    # where the timeline thinks it is. That shipped once.
    want = round(sum(b - a for a, b in segs), 2)
    try:
        have = round(float(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nk=1:nw=1", "assets/edit.mp4"],
            capture_output=True, text=True).stdout.strip()), 2)
    except (ValueError, FileNotFoundError):
        have = None
    if have is None:
        sys.exit("assets/edit.mp4 is missing. Run: python3 ../../pipeline/run.py render")
    if abs(have - want) > 0.08:
        sys.exit(f"assets/edit.mp4 is {have:.2f}s but this cut is {want:.2f}s "
                 f"({have - want:+.2f}s). The footage is stale.\n"
                 f"  Run: python3 ../../pipeline/run.py render   (then compose again)")

    # index.html is GENERATED. Anyone editing it in the desktop app loses that
    # work the next time this runs, silently, which is exactly what happened to
    # a set of hand-written pop-up labels. Compare what is on disk against what
    # compose last wrote and say so before overwriting it.
    _stamp = _os.path.join("work", "index.sha")
    if _os.path.exists(out_name) and _os.path.exists(_stamp):
        import hashlib
        _now = hashlib.sha256(open(out_name, "rb").read()).hexdigest()
        if _now != open(_stamp).read().strip():
            print(f"  WARNING {out_name} changed since compose last wrote it.")
            print( "          Those edits are about to be overwritten: this file is")
            print( "          generated from edit.py. Recover them with")
            print(f"            npx hyperframes history show <id>   (history lists them)")
            print( "          then put the change in edit.py so it survives.")

    caps = json.load(open("work/captions.json"))
    # data-fps must be an integer or an ffmpeg rational. FPS is a float here
    # because the cut does frame maths with it, and "60.0" does not parse: the
    # renderer silently falls back to 30 and throws away half the frames.
    fps_attr = int(FPS) if float(FPS).is_integer() else FPS

    def at(label, off):
        return round(M[label][0] + off, 3)

    def clamp(st, dur):
        """No clip may run past the root duration, or it is cut off."""
        return round(max(0.08, min(dur, total - st)), 3)

    def shot_at(t):
        for lb, (a, b, s) in M.items():
            if a <= t < b:
                return s
        return "screen"

    def moment_at(t):
        for lb, (a, b, s) in M.items():
            if a <= t < b:
                return lb
        return ""

    # ------------------------------------------------ caption lines
    # group words into short lines, breaking on punctuation, max 4 words,
    # and never spanning a shot change (the block moves between shots)
    lines, cur = [], []
    for wd in caps:
        if cur and (shot_at(wd["start"]) != shot_at(cur[0]["start"]) or len(cur) >= 4):
            lines.append(cur); cur = []
        cur.append(wd)
        if wd["w"].rstrip().endswith((".", "?", "!", ",")) and len(cur) >= 2:
            lines.append(cur); cur = []
    if cur: lines.append(cur)
    lines = [l for l in lines if l]
    if mode == "footage":
        lines = []

    # ------------------------------------------------------- markup
    out = []
    # an overlay must composite over nothing, so its root stays transparent
    ROOT_BG = "transparent" if mode == "overlay" else "#000"
    out.append(f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width={W}, height={H}">
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
  @font-face {{ font-family: "Apple Color Emoji"; src: local("Apple Color Emoji"); }}
  @font-face {{ font-family: "HelveticaNeue"; src: local("Helvetica Neue"), local("HelveticaNeue"); }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html, body {{ margin:0; width:{W}px; height:{H}px; overflow:hidden; background:#000; }}
  #root {{ width:100%; height:100%; position:relative; overflow:hidden; background:{ROOT_BG}; }}
  .stage {{ position:absolute; inset:0; overflow:hidden; }}
  .punch {{ position:absolute; inset:0; will-change:transform; }}
  .punch video {{ width:100%; height:100%; object-fit:cover; display:block; }}

  .cap {{ position:absolute; left:60px; right:60px; text-align:center; }}
  .cap .plate {{
     display:inline-block; padding:18px 30px 22px; border-radius:22px;
     background:rgba(6,8,10,.80);
     font-family:"HelveticaNeue", system-ui, sans-serif;
     font-weight:800; font-size:70px; line-height:1.14; letter-spacing:-.5px;
     color:{DIM}; text-shadow:0 4px 18px rgba(0,0,0,.65);
  }}
  .cap .w {{ display:inline-block; margin:0 .14em; color:{DIM}; }}

  .poptext {{ position:absolute; font:700 56px/1.12 -apple-system,"SF Pro Text",system-ui,sans-serif;
              color:#fff; background:rgba(8,11,14,.86); padding:16px 34px; border-radius:999px;
              border:3px solid rgba(57,255,20,.65); white-space:nowrap;
              box-shadow:0 10px 34px rgba(0,0,0,.55); }}
  .emo {{ position:absolute; font-family:"Apple Color Emoji"; font-size:132px;
          line-height:1; transform-origin:50% 50%;
          filter:drop-shadow(0 0 10px rgba(0,0,0,.85)) drop-shadow(0 6px 18px rgba(0,0,0,.6)); }}

  .orbit {{ position:absolute; left:0; right:0; }}
  .shot {{ position:absolute; border-radius:20px; overflow:hidden;
           box-shadow:0 26px 70px rgba(0,0,0,.72);
           border:3px solid rgba(57,255,20,.55); background:#0b0b0f; }}
  .shot img {{ display:block; width:100%; height:auto; }}

  .lovecard {{ position:absolute; left:0; right:0; text-align:center; }}
  .lovecard span {{ display:inline-block; padding:22px 58px 26px; border-radius:26px;
       background:rgba(6,8,10,.86); border:3px solid rgba(57,255,20,.5);
       font-family:"HelveticaNeue", system-ui, sans-serif; font-weight:800;
       font-size:96px; line-height:1; letter-spacing:-1px; color:{GREEN}; }}

  .anim {{ position:absolute; left:84px; width:912px; }}
  .anim .ttl {{ display:inline-block; font-family:"HelveticaNeue", system-ui, sans-serif;
                font-weight:800; font-size:52px; color:#fff; letter-spacing:-.5px;
                margin-bottom:26px; padding:12px 26px; border-radius:14px;
                background:rgba(8,10,14,.88); border:2px solid rgba(57,255,20,.45); }}
  .anim .row {{ display:flex; align-items:center; gap:24px; height:96px;
                background:rgba(10,12,16,.86); border:2px solid rgba(255,255,255,.14);
                border-radius:18px; padding:0 26px; margin-bottom:18px; }}
  .anim .box {{ width:46px; height:46px; border-radius:11px; flex:0 0 auto;
                border:3px solid rgba(255,255,255,.5); position:relative; }}
  .anim .tick {{ position:absolute; inset:0; display:flex; align-items:center;
                 justify-content:center; color:{GREEN}; font-size:40px; font-weight:900;
                 font-family:"HelveticaNeue", system-ui, sans-serif; opacity:0; }}
  .anim .lbl {{ font-family:"HelveticaNeue", system-ui, sans-serif; font-weight:700;
                font-size:40px; color:#fff; }}
  .anim .who {{ margin-left:auto; font-family:"HelveticaNeue", system-ui, sans-serif;
                font-weight:800; font-size:30px; color:{GREEN};
                border:2px solid rgba(57,255,20,.5); border-radius:999px; padding:7px 18px; }}
</style>
</head>
<body>
<div id="root" data-composition-id="{slug}"
     data-width="{W}" data-height="{H}" data-fps="{fps_attr}" data-duration="{total}">

''')
    if mode != "overlay":
        out.append(f'''  <div class="stage">
    <div class="punch" id="punch">
      <video id="edit" src="assets/edit.mp4" data-start="0" data-duration="{total}" data-has-audio="true"></video>
    </div>
  </div>
''')

    # --- the one animation ---
    anim_js = []
    if ANIM and ANIM["at"][0] in M:
        a_st = at(ANIM["at"][0], ANIM["at"][1])
        a_du = clamp(a_st, ANIM["dur"])
        rows = ANIM["rows"]
        out.append(f'  <div class="clip anim" id="anim" data-start="{a_st}" '
                   f'data-duration="{a_du}" data-track-index="1" '
                   f'style="top:{ANIM.get("top", 120)}px;">\n')
        out.append(f'    <div class="ttl" id="anim-ttl">{esc(ANIM["title"])}</div>\n')
        for i, (label, pill) in enumerate(rows):
            tick = ('<div class="tick">&#10003;</div>' if ANIM.get("tick", True) else '')
            out.append(f'    <div class="row" id="anim-r{i}"><div class="box">{tick}</div>'
                       f'<div class="lbl">{esc(label)}</div>'
                       f'<div class="who">{esc(pill)}</div></div>\n')
        out.append('  </div>\n')
        anim_js = [a_st, a_du, len(rows), bool(ANIM.get("tick", True))]

    # --- the orbit, as a sub-composition host ---
    if "ORBIT" in globals() and ORBIT and ORBIT["at"][0] in M:
        o_st = at(ORBIT["at"][0], ORBIT["at"][1])
        o_du = clamp(o_st, ORBIT["dur"])
        out.append(f'  <div class="clip orbit" id="orbit" data-composition-id="orbit" '
                   f'data-start="{o_st}" data-duration="{o_du}" data-track-index="2" '
                   f'data-composition-src="compositions/orbit.html" '
                   f'style="top:{ORBIT.get("top", 170)}px; height:{ORBIT.get("height", 1000)}px;">'
                   f'</div>\n')

    # --- the paper rip, as a sub-composition host with two content slots ---
    if "PAPERCUT" in globals() and PAPERCUT and PAPERCUT["at"][0] in M:
        p_st = at(PAPERCUT["at"][0], PAPERCUT["at"][1])
        p_du = clamp(p_st, PAPERCUT["dur"])
        p_w  = PAPERCUT.get("width", 900)
        p_lf = (W - p_w) // 2
        # data-variable-values, NOT data-composition-variables. The second is
        # the schema the component declares; values passed under that name are
        # ignored and the defaults win, silently.
        vals = esc(json.dumps(PAPERCUT.get("vars", {})))
        out.append(f'  <div class="clip papercut" id="papercut" '
                   f'data-composition-id="torn-paper-rip" '
                   f'data-start="{p_st}" data-duration="{p_du}" data-track-index="2" '
                   f'data-composition-src="{PAPERCUT["src"]}" '
                   f"data-variable-values='{vals}' "
                   f'style="left:{p_lf}px; top:{PAPERCUT.get("top", 250)}px; '
                   f'width:{p_w}px; height:{PAPERCUT.get("height", 488)}px;"></div>\n')
        slots = PAPERCUT.get("slots")
        if slots:
            cand = [slots, _os.path.join(EDIT_DIR, slots)]
            hit = next((c for c in cand if _os.path.exists(c)), None)
            if hit:
                out.append(open(hit).read() + "\n")
            else:
                _sys.exit(f"PAPERCUT slots file not found: {slots}")

    # --- screenshots ---
    shot_js = []
    for i, (label, off, dur, asset, w, top, side) in enumerate(SHOTS):
        if label not in M: continue
        st = at(label, off)
        left = (W - w) // 2
        dur = clamp(st, dur)
        out.append(f'  <div class="clip shot" id="shot{i}" data-start="{st}" data-duration="{dur}" '
                   f'data-track-index="2" style="left:{left}px; top:{top}px; width:{w}px;">'
                   f'<img src="assets/shots/{asset}" alt=""></div>\n')
        shot_js.append((f"shot{i}", st, dur, side))

    # --- captions ---
    cap_js = []
    for i, line in enumerate(lines):
        st = line[0]["start"]
        en = line[-1]["end"]
        shot = shot_at(st)
        mo = line[0].get("m", "")
        bottom = H - CAP_OVERRIDE.get(mo, CAP_BOTTOM[shot])
        spans = "".join(
            f'<span class="w" id="c{i}w{j}">{esc(wd["w"])}</span>' for j, wd in enumerate(line))
        out.append(f'  <div class="clip cap" id="cap{i}" data-start="{round(st,3)}" '
                   f'data-duration="{clamp(st, max(en-st,0.12))}" data-track-index="3" '
                   f'style="bottom:{bottom}px;"><span class="plate">{spans}</span></div>\n')
        cap_js.append((i, [(j, round(wd["start"],3), round(wd["end"],3)) for j, wd in enumerate(line)], round(st,3)))

    # --- the closing card ---
    love_js = []
    if CLOSE_CARD:
        lbl, off, dur, top = (CLOSE_CARD["at"][0], CLOSE_CARD["at"][1],
                              CLOSE_CARD["dur"], CLOSE_CARD["top"])
        if lbl in M:
            st = clampstart = at(lbl, off)
            d = clamp(st, dur)
            out.append(f'  <div class="clip lovecard" id="lovecard" data-start="{st}" '
                       f'data-duration="{d}" data-track-index="5" style="top:{top}px;">'
                       f'<span>{esc(CLOSE_CARD["text"])}</span></div>\n')
            love_js.append(("lovecard", st, d))

    # --- pop up text ---
    poptext_js = []
    if "POPTEXT" in globals() and POPTEXT:
        for i, (label, off, dur, txt, xp, yp) in enumerate(POPTEXT):
            if label not in M:
                continue
            st = at(label, off)
            d = clamp(st, dur)
            out.append(f'  <div class="clip poptext" id="pt{i}" data-start="{st}" '
                       f'data-duration="{d}" data-track-index="4" '
                       f'style="left:{xp}%; top:{yp}%;">{esc(txt)}</div>\n')
            poptext_js.append((f"pt{i}", st, d))

    # --- a filter on the picture ---
    # On the punch wrapper, which is the one element proven to render a
    # transform. A filter is a different property from scale, so this does not
    # fight PUNCH. Neutral values are written explicitly at both ends: "none"
    # does not interpolate.
    filter_js = []
    if "FILTERS" in globals() and FILTERS:
        for label, off, dur, css in FILTERS:
            if label not in M:
                continue
            st = at(label, off)
            filter_js.append([st, clamp(st, dur), css])

    # --- emoji ---
    emo_js = []
    for i, row in enumerate(EMOJI):
        # Optional 7th field is the style: "pop" (default) or "beat". Tolerant
        # unpacking so the six-field lists in the earlier videos still load.
        label, off, dur, ch, xp, yp = row[:6]
        style = row[6] if len(row) > 6 else "pop"
        if label not in M: continue
        st = at(label, off)
        dur = clamp(st, dur)
        out.append(f'  <div class="clip emo" id="emo{i}" data-start="{st}" data-duration="{dur}" '
                   f'data-track-index="4" style="left:{xp}%; top:{yp}%;">{ch}</div>\n')
        emo_js.append((f"emo{i}", st, dur, style))

    # --- zoom through cut -------------------------------------------------
    # The registry's zoom-through-transition carries no slots: both its scenes
    # are its own placeholder material, so mounting it would lay a generic
    # graphic over the footage instead of doing anything to it. The real move
    # is on the picture: push in hard so the frame is moving fastest exactly at
    # the cut, then continue out of it on the incoming shot. Scale on the punch
    # wrapper, which already renders; no filter, which does not.
    zoom_js = []
    if "ZOOM_THROUGH" in globals() and ZOOM_THROUGH:
        zs = ZOOM_THROUGH if isinstance(ZOOM_THROUGH, list) else [ZOOM_THROUGH]
        for z in zs:
            lab = z["at"]
            if lab not in M:
                continue
            zoom_js.append([round(M[lab][0], 3), z.get("in", 0.55), z.get("out", 0.60),
                            z.get("scale", 1.5), z.get("ox", 50), z.get("oy", 42)])

    # ------------------------------------------------------- timeline
    punches = [(at(l, o), d, sc, ox, oy) for l, o, d, sc, ox, oy in PUNCH if l in M]
    # PUNCH and ZOOM_THROUGH both animate `punch`'s scale. Where they overlap
    # the punch's return-to-1 overrides the zoom's ramp and the frame zooms OUT
    # through the cut instead of in, which looks like the effect misfiring.
    for zst, zin, zout, *_ in zoom_js:
        for pst, pdur, *_ in punches:
            if pst - 0.05 < zst + zout and pst + pdur + 0.46 > zst - zin:
                print(f"  WARNING punch at {pst:.2f}s overlaps the zoom through "
                      f"ramp {zst - zin:.2f}-{zst + zout:.2f}s; they fight over "
                      f"scale and the punch wins. Shorten or move the punch.")
    out.append(f'''
</div>
<script>
(function () {{
  const tl = gsap.timeline({{ paused: true }});
  const GREEN = "{GREEN}", DIM = "{DIM}";

  // ---- the one animation ----------------------------------------------
  const ANIM = {json.dumps(anim_js)};
  if (ANIM.length) {{
    const aSt = ANIM[0], aDu = ANIM[1], nRows = ANIM[2], tick = ANIM[3];
    tl.fromTo("#anim-ttl", {{ opacity: 0, y: -26 }},
                           {{ opacity: 1, y: 0, duration: .5, ease: "power2.out" }}, aSt + 0.05);
    for (let k = 0; k < nRows; k++) {{
      const row = document.getElementById("anim-r" + k);
      tl.fromTo(row, {{ opacity: 0, y: 34 }},
                     {{ opacity: 1, y: 0, duration: .46, ease: "power3.out" }}, aSt + 0.45 + k * 0.34);
      if (tick) {{
        tl.fromTo(row.querySelector(".tick"), {{ opacity: 0, scale: .4 }},
                  {{ opacity: 1, scale: 1, duration: .32, ease: "back.out(2.2)" }}, aSt + 2.05 + k * 0.30);
      }}
    }}
    tl.to("#anim", {{ opacity: 0, duration: .45, ease: "power1.in" }}, aSt + aDu - 0.55);
  }}

  // ---- punch ins --------------------------------------------------------
  const punch = document.getElementById("punch");
  const POPTEXT = {json.dumps(poptext_js)};
  POPTEXT.forEach(function (p) {{
    const el = document.getElementById(p[0]);
    const st = p[1], dur = p[2];
    tl.fromTo(el, {{ opacity: 0, scale: .72, y: 22 }},
                  {{ opacity: 1, scale: 1.06, y: 0, duration: .24, ease: "back.out(2.4)" }}, st);
    tl.to(el, {{ scale: 1, duration: .16, ease: "power2.out" }}, st + .24);
    tl.to(el, {{ opacity: 0, scale: .94, duration: .22, ease: "power2.in" }}, st + dur - .22);
  }});

  const FILTERS = {json.dumps(filter_js)};
  FILTERS.forEach(function (f) {{
    const st = f[0], dur = f[1], css = f[2];
    tl.fromTo(punch, {{ filter: "saturate(1) contrast(1) brightness(1)" }},
                     {{ filter: css, duration: .34, ease: "power2.out" }}, st);
    tl.to(punch, {{ filter: "saturate(1) contrast(1) brightness(1)",
                   duration: .40, ease: "power2.in" }}, st + dur - .40);
  }});

  const ZOOM = {json.dumps(zoom_js)};
  ZOOM.forEach(function (z) {{
    const cut = z[0], tin = z[1], tout = z[2], sc = z[3], ox = z[4], oy = z[5];
    const from = Math.max(0, cut - tin);
    tl.set(punch, {{ transformOrigin: ox + "% " + oy + "%" }}, Math.max(0, from - 0.001));
    // power3.in so the frame is accelerating into the cut, power3.out so the
    // incoming shot carries the motion out of it. The cut lands at peak speed.
    tl.fromTo(punch, {{ scale: 1 }},  {{ scale: sc, duration: tin,  ease: "power3.in"  }}, from);
    tl.fromTo(punch, {{ scale: sc }}, {{ scale: 1,  duration: tout, ease: "power3.out" }}, cut);
  }});

  const PUNCH = {json.dumps(punches)};
  PUNCH.forEach(function (p) {{
    const st = p[0], dur = p[1], sc = p[2], ox = p[3], oy = p[4];
    tl.set(punch, {{ transformOrigin: ox + "% " + oy + "%" }}, Math.max(0, st - 0.001));
    tl.to(punch, {{ scale: sc, duration: 0.42, ease: "power2.out" }}, st);
    tl.to(punch, {{ scale: 1,  duration: 0.46, ease: "power2.inOut" }}, st + dur);
  }});

  // ---- screenshots ------------------------------------------------------
  const SHOTS = {json.dumps(shot_js)};
  SHOTS.forEach(function (s) {{
    const el = document.getElementById(s[0]);
    const st = s[1], dur = s[2], side = s[3];
    if (side === "pop") {{
      // Near-rest start, one overshoot, clean settle. Reads cleaner than a
      // slide because nothing travels across the frame.
      tl.fromTo(el, {{ opacity: 0, scale: .82 }},
                    {{ opacity: 1, scale: 1.04, duration: .22, ease: "power3.out" }}, st);
      tl.to(el, {{ scale: 1, duration: .20, ease: "power2.out" }}, st + .22);
      tl.to(el, {{ opacity: 0, scale: .96, duration: .24, ease: "power2.in" }}, st + dur - .24);
    }} else if (side === "pop-spin") {{
      tl.fromTo(el, {{ opacity: 0, scale: .70, rotate: -8 }},
                    {{ opacity: 1, scale: 1.06, rotate: 0, duration: .26, ease: "back.out(2.2)" }}, st);
      tl.to(el, {{ scale: 1, duration: .18, ease: "power2.out" }}, st + .26);
      tl.to(el, {{ opacity: 0, scale: .94, duration: .24, ease: "power2.in" }}, st + dur - .24);
    }} else if (side === "pop-drop") {{
      tl.fromTo(el, {{ opacity: 0, scale: .88, y: -46 }},
                    {{ opacity: 1, scale: 1.05, y: 0, duration: .28, ease: "back.out(1.8)" }}, st);
      tl.to(el, {{ scale: 1, duration: .18, ease: "power2.out" }}, st + .28);
      tl.to(el, {{ opacity: 0, scale: .95, duration: .24, ease: "power2.in" }}, st + dur - .24);
    }} else if (side === "up") {{
      tl.fromTo(el, {{ opacity: 0, y: 54, scale: .96 }},
                    {{ opacity: 1, y: 0, scale: 1, duration: .50, ease: "power3.out" }}, st);
      tl.to(el, {{ opacity: 0, duration: .30, ease: "power2.in" }}, st + dur - .30);
    }} else {{
      const dir = side === "right" ? 70 : -70;
      tl.fromTo(el, {{ opacity: 0, x: dir, scale: .94 }},
                    {{ opacity: 1, x: 0, scale: 1, duration: .46, ease: "power3.out" }}, st);
      tl.to(el, {{ opacity: 0, x: dir * .5, duration: .38, ease: "power2.in" }}, st + dur - .38);
    }}
  }});

  // ---- emoji pops -------------------------------------------------------
  const EMO = {json.dumps(emo_js)};
  EMO.forEach(function (e) {{
    const el = document.getElementById(e[0]);
    const st = e[1], dur = e[2], style = e[3] || "pop";
    if (style === "beat") {{
      // A real heartbeat: two quick pulses per cycle, not one even throb.
      // yoyo+repeat is deterministic under seeking, so it renders the same
      // frame in any order.
      tl.fromTo(el, {{ opacity: 0, scale: .34 }},
                    {{ opacity: 1, scale: 1.12, duration: .26, ease: "back.out(3)" }}, st);
      tl.to(el, {{ scale: 1, duration: .14, ease: "power2.out" }}, st + .26);
      tl.to(el, {{ scale: 1.17, duration: .13, yoyo: true, repeat: 5,
                  ease: "power2.inOut" }}, st + .40);
      tl.to(el, {{ opacity: 0, scale: .9, duration: .22, ease: "power2.in" }}, st + dur - .22);
    }} else {{
      tl.fromTo(el, {{ opacity: 0, scale: .3, rotate: -14 }},
                    {{ opacity: 1, scale: 1, rotate: 0, duration: .40, ease: "back.out(2.6)" }}, st);
      tl.to(el, {{ opacity: 0, scale: .82, duration: .30, ease: "power2.in" }}, st + dur - .30);
    }}
  }});

  // ---- the closing card ----------------------------------------------
  const LOVE = {json.dumps(love_js)};
  LOVE.forEach(function (l) {{
    const el = document.getElementById(l[0]);
    const st = l[1], dur = l[2];
    tl.fromTo(el, {{ opacity: 0, scale: .82, y: 26 }},
                  {{ opacity: 1, scale: 1, y: 0, duration: .52, ease: "back.out(1.9)" }}, st);
  }});

  // ---- word by word caption highlight -----------------------------------
  const CAPS = {json.dumps(cap_js)};
  CAPS.forEach(function (c) {{
    const i = c[0], words = c[1], lineStart = c[2];
    const plate = document.getElementById("cap" + i).querySelector(".plate");
    tl.fromTo(plate, {{ opacity: 0, y: 16 }},
                     {{ opacity: 1, y: 0, duration: .18, ease: "power2.out" }}, lineStart);
    words.forEach(function (w) {{
      const el = document.getElementById("c" + i + "w" + w[0]);
      tl.to(el, {{ color: GREEN, duration: .07, ease: "none" }}, w[1]);
      tl.to(el, {{ color: DIM,   duration: .10, ease: "none" }}, w[2]);
    }});
  }});

  window.__timelines["{slug}"] = tl;
}})();
</script>
</body>
</html>
''')

    open(out_name, "w").write("".join(out))
    import hashlib as _hl
    _os.makedirs("work", exist_ok=True)
    open(_os.path.join("work", "index.sha"), "w").write(
        _hl.sha256(open(out_name, "rb").read()).hexdigest())
    print(f"{out_name} written: {total}s, {len(lines)} caption lines, "
          f"{len(shot_js)} screenshots, {len(emo_js)} emoji, {len(punches)} punch ins, "
          f"{len(zoom_js)} zoom through")
    json.dump({k: [round(v[0],3), round(v[1],3), v[2]] for k, v in M.items()},
              open("work/moments.json", "w"), indent=1)

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"
    out = {"full": "index.html", "overlay": "overlay.html",
           "footage": "footage.html"}[mode]
    main(mode, out)

