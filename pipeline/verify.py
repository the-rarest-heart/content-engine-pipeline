#!/usr/bin/env python3
"""Verify the cut by ear, without encoding any video.

Every edge problem this pipeline has had (clipped first words, leaked retakes,
swallowed consonants) is audible in the audio alone. Rendering 2 minutes of
1080x1920 60fps H.264 to check them is wasted work.

--full      transcribe the whole cut audio (what the 7 video renders were for)
--edges     transcribe only a window around each join (much faster still)
"""
import json, subprocess, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import load
globals().update(load())

PAD = 1.3   # seconds either side of a join for --edges

def build_audio(segs, out, fade=0.012):
    af = []
    for i, (a, b) in enumerate(segs):
        af.append(f"[0:a]atrim=start={a:.5f}:end={b:.5f},asetpts=PTS-STARTPTS,"
                  f"afade=t=in:st=0:d={fade},"
                  f"afade=t=out:st={max(0,(b-a)-fade):.5f}:d={fade}[a{i}]")
    n = len(segs)
    graph = ";".join(af + ["".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[a]"])
    open("work/afilter.txt", "w").write(graph)
    subprocess.run(["ffmpeg","-y","-v","error","-i",SRC,
                    "-filter_complex_script","work/afilter.txt","-map","[a]",
                    "-ar","16000","-ac","1","-c:a","pcm_s16le",out], check=True)

def transcribe(wav, out, extra=()):
    subprocess.run(["whisper-cli","-m",
        os.path.expanduser("~/.cache/hyperframes/whisper/models/ggml-small.en.bin"),
        "-f",wav,"-l","en","-otxt","-of",out,*extra],
        check=True, capture_output=True)
    return open(out + ".txt").read()

def main():
    segs = [tuple(s) for s in json.load(open("work/edl.json"))]
    if "--edges" in sys.argv:
        # only the audio around each join, where every defect has ever been
        edges, t = [], 0.0
        for i, (a, b) in enumerate(segs):
            if i:  # a join exists at the start of every segment but the first
                edges.append((max(a - PAD, a - (b - a)), min(b, a + PAD)))
            t += b - a
        edges = [(a, b) for a, b in edges if b > a]
        build_audio(edges, "work/edges16k.wav")
        print(f"{len(edges)} joins, "
              f"{sum(b-a for a,b in edges):.1f}s of audio instead of {t:.1f}s")
        print(transcribe("work/edges16k.wav", "work/edges-heard"))
    else:
        build_audio(segs, "work/cut16k.wav")
        print(transcribe("work/cut16k.wav", "work/cut-heard"))

if __name__ == "__main__":
    main()
