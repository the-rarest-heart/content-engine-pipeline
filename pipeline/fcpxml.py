#!/usr/bin/env python3
"""Write a Final Cut timeline with the two layers already stacked.

footage.mp4 goes on the primary storyline; overlay.mov rides above it as a
connected clip in lane 1, which is what Final Cut calls V2. Both start at
00:00, so the timeline looks like the delivered render until you start
changing it.

Run after `run.py fcp`. Open the result with:  open fcp/<name>.fcpxml
"""
import json, os, subprocess, sys
from fractions import Fraction
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import load
globals().update(load())

def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "format=duration:stream=width,height,r_frame_rate", "-of", "json", path],
        capture_output=True, text=True).stdout
    d = json.loads(out)
    st = d["streams"][0]
    has_audio = bool(json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=index", "-of", "json", path],
        capture_output=True, text=True).stdout).get("streams"))
    return {"dur": float(d["format"]["duration"]),
            "w": st["width"], "h": st["height"],
            "fps": Fraction(st["r_frame_rate"]), "audio": has_audio}

def main():
    name = os.path.basename(os.getcwd())
    footage, overlay = "fcp/footage.mp4", "fcp/overlay.mov"
    for f in (footage, overlay):
        if not os.path.exists(f):
            sys.exit(f"missing {f}. Run: python3 ../../pipeline/run.py fcp")
    fv, ov = probe(footage), probe(overlay)
    if fv["fps"] != ov["fps"]:
        print(f"  warning: footage is {float(fv['fps']):.3f} fps and overlay is "
              f"{float(ov['fps']):.3f} fps. They will drift.")

    fps = fv["fps"]
    fd = Fraction(1, 1) / fps                       # frame duration
    def tc(sec):
        n = round(Fraction(sec).limit_denominator(1000000) / fd)
        return "0s" if n == 0 else f"{n * fd.numerator}/{fd.denominator}s"
    # the timeline is as long as the shorter layer, so nothing dangles
    dur = tc(min(fv["dur"], ov["dur"]))

    def url(p):
        return "file://" + quote(os.path.abspath(p))

    fmt_name = f"FFVideoFormat{fv['w']}x{fv['h']}p{int(round(float(fps)))}"
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE fcpxml>
<fcpxml version="1.10">
  <resources>
    <format id="r1" name="{fmt_name}" frameDuration="{fd.numerator}/{fd.denominator}s"
            width="{fv['w']}" height="{fv['h']}" colorSpace="1-1-1 (Rec. 709)"/>
    <asset id="a1" name="{name} footage" start="0s" duration="{tc(fv['dur'])}"
           hasVideo="1" videoSources="1" hasAudio="{1 if fv['audio'] else 0}"
           audioSources="{1 if fv['audio'] else 0}" audioChannels="2" format="r1">
      <media-rep kind="original-media" src="{url(footage)}"/>
    </asset>
    <asset id="a2" name="{name} overlay" start="0s" duration="{tc(ov['dur'])}"
           hasVideo="1" videoSources="1" hasAudio="0" format="r1">
      <media-rep kind="original-media" src="{url(overlay)}"/>
    </asset>
  </resources>
  <library>
    <event name="Content Engine">
      <project name="{name}">
        <sequence format="r1" duration="{dur}" tcStart="0s" tcFormat="NDF"
                  audioLayout="stereo" audioRate="48k">
          <spine>
            <asset-clip ref="a1" offset="0s" name="footage" start="0s"
                        duration="{dur}" format="r1" tcFormat="NDF">
              <asset-clip ref="a2" lane="1" offset="0s" name="overlay"
                          start="0s" duration="{dur}" format="r1"/>
            </asset-clip>
          </spine>
        </sequence>
      </project>
    </event>
  </library>
</fcpxml>
'''
    out = f"fcp/{name}.fcpxml"
    open(out, "w").write(xml)
    print(f"  {out}")
    print(f"    footage  {fv['w']}x{fv['h']}  {float(fv['fps']):.3f} fps  {fv['dur']:.2f}s"
          f"  audio: {'yes' if fv['audio'] else 'no'}")
    print(f"    overlay  {ov['w']}x{ov['h']}  {float(ov['fps']):.3f} fps  {ov['dur']:.2f}s"
          f"  lane 1 (V2)")
    print(f"\n  Open it:  open {out}")

if __name__ == "__main__":
    main()
