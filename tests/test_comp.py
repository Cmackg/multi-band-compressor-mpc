#!/usr/bin/env python3
"""Offline checks for Multi-Band Compressor: signals in, the output measured and compared with textbook targets (the
Linkwitz-Riley crossover, the compressor's static curve and time constants), plus the screen values, bypass, clicks,
state and CPU.

    python3 tests/test_comp.py path/to/run_engine
"""
import math
import os
import subprocess
import sys
import tempfile

import numpy as np

SR = 44100
HARNESS = sys.argv[1] if len(sys.argv) > 1 else "tests/run_engine"
THRESH, KNEE = -20.0, 6.0                       # the engine's fixed threshold (dBFS after INPUT) and soft knee
ATT = {0: 3.0, 1: 10.0, 2: 30.0}                # SPEED's attack / release (ms) for the middle band
REL = {0: 60.0, 1: 150.0, 2: 400.0}
BAND_TIME = [2.0, 1.5, 1.0, 0.75, 0.5]
failures = []


def check(name, ok, detail=""):
    print("%-64s %s  %s" % (name, "PASS" if ok else "FAIL", detail))
    if not ok:
        failures.append(name)


def hz_pos(hz):
    return round(1000 * math.log(hz / 20) / math.log(1000))


def ratio_pos(r):
    return "%.4f" % (100 * math.log(r) / math.log(20))


def run(sig, *args, stereo=False, **params):
    with tempfile.TemporaryDirectory() as d:
        fi, fo = os.path.join(d, "in.f32"), os.path.join(d, "out.s16")
        sig.astype(np.float32).tofile(fi)
        env = dict(os.environ, STEREO="1" if stereo else "0")
        out = subprocess.run([HARNESS, fi, fo] + ["%s=%s" % kv for kv in params.items()] + list(args),
                             check=True, capture_output=True, text=True, env=env).stdout.split("\n")
        y = np.fromfile(fo, dtype=np.int16).reshape(-1, 2).astype(np.float64) / 32768.0
    n = len(sig) // (2 if stereo else 1)
    info = dict(latency=out[0], curve=[int(v) for v in out[1].split()], bars=[int(v) for v in out[2].split()],
                meters=[int(v) for v in out[3].split()], x=[float(v) for v in out[4].split()],
                xm=[int(v) for v in out[5].split()], state=out[6])
    return y[:n, 0], y[:n, 1], info


def only(*bands, **extra):
    """these bands' compressors on, the rest switched off (a switched-off band passes untouched)"""
    p = {"b%d_on" % i: 1 if i in bands else 0 for i in range(1, 6)}
    p.update(extra)
    return p


def band(i, inp=None, ratio=None, out=None):
    p = {}
    if inp is not None: p["b%d_in" % i] = inp
    if ratio is not None: p["b%d_ratio" % i] = ratio_pos(ratio)
    if out is not None: p["b%d_out" % i] = out
    return p


def gr_of(level, ratio):
    """textbook reduction (dB) for a level (dBFS at the compressor) with the engine's threshold and soft knee"""
    over = level - THRESH
    s = 1 / ratio - 1
    if 2 * over <= -KNEE: return 0.0
    if 2 * over < KNEE: return -s * (over + KNEE / 2) ** 2 / (2 * KNEE)
    return -s * over


def spectrum_db(y, n):
    return 20 * np.log10(np.abs(np.fft.rfft(y[:n])) + 1e-12)


def impulse_response(amp=0.9, **params):
    """the exact response of the linear parts: an impulse in, its spectrum out (n = 2^16: 1.5 s of tail)"""
    n = 1 << 16
    x = np.zeros(n + SR // 10)
    x[SR // 20] = amp
    l, r, info = run(x, **params)
    f = np.fft.rfftfreq(n, 1 / SR)
    xi = np.zeros(n); xi[0] = math.trunc(amp * 32767) / 32768
    return f, spectrum_db(l[SR // 20:SR // 20 + n], n) - spectrum_db(xi, n), info


def at(f, db, hz):
    return float(np.interp(math.log(hz), np.log(f[1:]), db[1:]))


def tone(hz, dbfs, secs):
    t = np.arange(int(secs * SR)) / SR
    return 10 ** (dbfs / 20) * np.sin(2 * math.pi * hz * t)


def peak_db(y, a, b):
    return 20 * math.log10(np.max(np.abs(y[int(a * SR):int(b * SR)])) + 1e-12)


AUDIO = (lambda f: (f > 20) & (f < 20000))

# ------------------------------------------------------------------ crossover
f, db, info = impulse_response(**only())
dev = np.max(np.abs(db[AUDIO(f)]))
check("crossover alone sums flat (20 Hz - 20 kHz)", dev < 0.05, "max deviation %.4f dB" % dev)
check("latency is 0", info["latency"] == "0")

# defaults (every band on, 2:1, INPUT 0 dB): quiet material is untouched (= the crossover alone, sample for sample)
quiet = np.random.default_rng(7).normal(0, 0.01, 2 * SR)    # -40 dBFS RMS: peaks far under -20 dBFS
a, _, _ = run(quiet)
b, _, _ = run(quiet, **only())
check("defaults, quiet material: same as the bare crossover", np.max(np.abs(a - b)) < 2.0 / 32768,
      "max difference %.1f LSB" % (np.max(np.abs(a - b)) * 32768))

# solo band 3 (400 Hz .. 1.6 kHz): LR4 band pass, -6 dB at both crossovers, 24 dB/oct skirts
f, db, _ = impulse_response(**only(b3_solo=1))
c, want = at(f, db, 800), 2 * 20 * math.log10(16 / 17)   # each skirt an octave away: |LR4| = 16/17
check("solo band 3: its middle (800 Hz) at the LR4 value", abs(c - want) < 0.05, "%.3f dB (textbook %.3f)" % (c, want))
for hz in (400, 1600):
    v = at(f, db, hz)
    check("solo band 3: -6 dB at the %d Hz crossover" % hz, abs(v + 6.02) < 0.15, "%.2f dB" % v)
for hz in (6400, 100):
    v = at(f, db, hz)
    check("solo band 3: steep skirts (2 octaves out, %d Hz)" % hz, v < -45, "%.1f dB" % v)
f, db, _ = impulse_response(**only(b2_solo=1, b3_solo=1))
v = at(f, db, 400)   # band 3's top skirt (LR4 at 1.6 kHz, 2 octaves up) where band 2 has an allpass: -0.04 dB
check("solo bands 2 + 3: flat across their shared crossover", abs(v) < 0.1, "400 Hz %.3f dB" % v)

f, db, _ = impulse_response(**only(x1=hz_pos(60), x2=hz_pos(250), x3=hz_pos(3000), x4=hz_pos(9000)))
dev = np.max(np.abs(db[AUDIO(f)]))
check("moved crossovers still sum flat", dev < 0.05, "max deviation %.4f dB" % dev)

# a crossover turned past its neighbour stops there (the neighbour stays), and its knob follows after a pause
f, db, info = impulse_response(**only(x1=hz_pos(5000)))
dev = np.max(np.abs(db[AUDIO(f)]))
check("XOVER 1 turned past XOVER 2: still flat", dev < 0.05, "max deviation %.4f dB" % dev)
check("XOVER 1 stops 1/3 octave under XOVER 2, XOVER 2 stays", abs(info["x"][1] - info["x"][0] - 33) < 0.6 and
      info["x"][1] == hz_pos(400), "x = %s" % info["x"])

# ------------------------------------------------------------------ static compression (band 3 alone, widened)
# band 3 widened to 100 Hz .. 8 kHz, so a 1 kHz tone is all in it
WIDE = dict(x1=hz_pos(40), x2=hz_pos(100), x3=hz_pos(8000), x4=hz_pos(11000))
ISO3 = only(3, **WIDE)

for level, inp, ratio in ((-12, 0, 4), (-6, 6, 2), (-6, 12, 4), (-20, 20, 10), (-26, 6, 4)):
    l, r, info = run(tone(1000, level, 2.0), **ISO3, **band(3, inp=inp, ratio=ratio))
    got = peak_db(l, 1.5, 2.0)
    gr = gr_of(level + inp, ratio)
    want = level + inp - gr
    check("1 kHz at %d dBFS, INPUT %+d, %g:1: output level" % (level, inp, ratio), abs(got - want) < 0.3,
          "%.2f dBFS (textbook %.2f)" % (got, want))
    check("  its meter shows the reduction (%.1f dB)" % gr, abs(info["meters"][2] - gr) <= 1.0, "meter %d" % info["meters"][2])

l, r, info = run(tone(1000, -6, 2.0), **ISO3, **band(3, inp=12, ratio=4))
check("  the other bands' meters stay at 0", info["meters"][:2] + info["meters"][3:] == [0, 0, 0, 0], str(info["meters"]))

l, r, _ = run(tone(1000, -10, 2.0), **ISO3, **band(3, inp=10, ratio=4, out=-6))
got, want = peak_db(l, 1.5, 2.0), -10 + 10 - gr_of(0, 4) - 6
check("OUTPUT -6 dB after compression", abs(got - want) < 0.3, "%.2f dBFS (textbook %.2f)" % (got, want))

l, r, _ = run(tone(1000, -30, 2.0), **ISO3, **band(3, inp=24, ratio=1))
check("ratio 1:1: no compression, only INPUT's gain", abs(peak_db(l, 1.5, 2.0) + 6) < 0.2, "%.2f dBFS" % peak_db(l, 1.5, 2.0))

l, r, _ = run(tone(5000, -6, 2.0), **only(3), **band(3, inp=24, ratio=20, out=-24))   # (INPUT +24 alone would lift its skirt)
check("band 3 squashing: a 5 kHz tone (band 4) untouched", abs(peak_db(l, 1.5, 2.0) + 6) < 0.2, "%.2f dBFS" % peak_db(l, 1.5, 2.0))

t = tone(1000, -6, 2.0)
st = np.stack([t, 0.1 * t], axis=1).reshape(-1)
l, r, _ = run(st, stereo=True, **ISO3, **band(3, inp=6, ratio=4))
want = -26 + 6 - gr_of(0, 4)
check("stereo link: the quiet side gets the loud side's reduction", abs(peak_db(r, 1.5, 2.0) - want) < 0.3,
      "R %.2f dBFS (want %.2f)" % (peak_db(r, 1.5, 2.0), want))

# ------------------------------------------------------------------ SPEED: attack and release per band
def gain_track(y, x, a, b, per):
    """the gain (dB) over successive windows of `per` samples between a and b seconds"""
    g = []
    for s in range(int(a * SR), int(b * SR) - per, per):
        g.append(20 * math.log10((np.max(np.abs(y[s:s + per])) + 1e-12) / (np.max(np.abs(x[s:s + per])) + 1e-12)))
    return np.array(g), per / SR


for speed in (0, 1, 2):
    att, rel = ATT[speed] * BAND_TIME[2], REL[speed] * BAND_TIME[2]
    x = np.concatenate([tone(1000, -40, 1.0), tone(1000, -6, 1.5), tone(1000, -40, 2.5)])
    l, r, _ = run(x, **ISO3, **band(3, inp=6, ratio=4), speed=speed)
    full = gr_of(0, 4)
    g, dt = gain_track(l, x, 1.0, 2.5, 88)                      # 2 ms windows from the step up
    red = 6 - g
    k = int(np.argmax(red >= 0.632 * full)) if np.any(red >= 0.632 * full) else -1
    tau = k * dt * 1000 if k >= 0 else float("nan")
    check("SPEED %s: attack ~%g ms" % (("Fast", "Medium", "Slow")[speed], att), 0.5 * att <= tau <= 1.5 * att + 2.5,
          "63%% after %.1f ms" % tau)
    g, dt = gain_track(l, x, 2.52, 5.0, 176)                    # 4 ms windows, from 20 ms after the step down
    red = 6 - g
    k = int(np.argmax(red <= 0.368 * full)) if np.any(red <= 0.368 * full) else -1
    tau = 20 + k * dt * 1000 if k >= 0 else float("nan")
    check("SPEED %s: release ~%g ms" % (("Fast", "Medium", "Slow")[speed], rel), 0.6 * rel <= tau <= 1.5 * rel + 20,
          "down to 37%% after %.0f ms" % tau)

# lower bands are slower: band 1 releases 2x band 3's time
x = np.concatenate([tone(60, -6, 1.5), tone(60, -40, 2.0)])
l, r, _ = run(x, **only(1, x1=hz_pos(300), x2=hz_pos(600), x3=hz_pos(3000), x4=hz_pos(9000)), **band(1, inp=6, ratio=4))
g, dt = gain_track(l, x, 1.55, 3.5, 1470)
red = 6 - g
k = int(np.argmax(red <= 0.368 * gr_of(0, 4)))
tau = 50 + k * dt * 1000
check("band 1 (bass) releases about twice as slowly as band 3", 200 <= tau <= 450, "%.0f ms (band 3: 150 ms)" % tau)

# ------------------------------------------------------------------ mix, solo, bypass, master
loud = np.random.default_rng(3).normal(0, 0.08, 4 * SR)
heavy = dict({k: v for i in range(1, 6) for k, v in band(i, inp=24, ratio=20).items()})
a, _, _ = run(loud, mix=0, **heavy)
b, _, _ = run(loud, **only())
check("MIX 0%: the bands unprocessed (= the bare crossover), no comb", np.max(np.abs(a - b)[SR // 10:]) < 2.0 / 32768,
      "max difference %.1f LSB" % (np.max(np.abs(a - b)[SR // 10:]) * 32768))
lw, _, _ = run(loud, mix=100, **heavy)
lm, _, _ = run(loud, mix=50, **heavy)
check("MIX 50%: between fully processed and dry", min(np.std(lw), np.std(b)) < np.std(lm) < max(np.std(lw), np.std(b)),
      "rms processed %.3f mix %.3f dry %.3f" % (np.std(lw), np.std(lm), np.std(b)))

l, r, _ = run(tone(1000, -6, 2.0), **only(b1_solo=1))
check("solo band 1: a 1 kHz tone is gone", peak_db(l, 1.0, 2.0) < -50, "%.1f dBFS" % peak_db(l, 1.0, 2.0))

x = np.random.default_rng(5).normal(0, 0.1, SR)
l, r, _ = run(x, bypass=1, **heavy)
xi = np.trunc(x.astype(np.float32) * np.float32(32767)).astype(np.float64) / 32768.0   # as the harness converts it
check("BYPASS is bit-exact (from the first sample)", np.max(np.abs(l - xi)) < 1e-9 and np.max(np.abs(r - xi)) < 1e-9)

l, r, _ = run(tone(1000, -26, 2.0), master=-6)
check("MASTER -6 dB", abs(peak_db(l, 1.5, 2.0) + 32) < 0.2, "%.2f dBFS" % peak_db(l, 1.5, 2.0))

l, r, _ = run(tone(1000, -26, 2.0), **only(), **band(3, inp=6))
check("a switched-off band ignores its INPUT (passes untouched)", abs(peak_db(l, 1.5, 2.0) + 26) < 0.2, "%.2f dBFS" % peak_db(l, 1.5, 2.0))

# ------------------------------------------------------------------ the screen
l, r, info = run(tone(1000, -6, 2.0), **ISO3, **band(3, inp=6, ratio=4))
curve_db = [v / 60 * 36 - 18 for v in info["curve"]]
col = lambda hz: int(72 * math.log(hz / 20) / math.log(1000))
want = 6 - gr_of(0, 4)
check("curve: the 1 kHz column shows band 3's net gain", abs(curve_db[col(1000)] - want) < 0.8,
      "%.1f dB (INPUT +6 minus %.1f dB = %.1f)" % (curve_db[col(1000)], gr_of(0, 4), want))
check("curve: a 25 Hz column (band 1, off) stays at 0 dB", abs(curve_db[col(25)]) < 0.7, "%.1f dB" % curve_db[col(25)])
b3 = [curve_db[c] for c in range(72) if 100 * 1.02 < 20 * 1000 ** ((c + 0.5) / 72) < 8000 / 1.02]
check("curve: flat across band 3's whole range (100 Hz - 8 kHz), as in Multipressor", max(b3) - min(b3) < 0.01,
      "%d columns, %.1f .. %.1f dB" % (len(b3), min(b3), max(b3)))
c_lo, c_hi = curve_db[col(90)], curve_db[col(110)]
check("curve: steps at the crossover (100 Hz): band 2 at 0 dB, band 3 compressed", abs(c_lo) < 0.7 and c_hi < -5,
      "90 Hz %.1f dB, 110 Hz %.1f dB" % (c_lo, c_hi))
_, _, info = run(tone(1000, -40, 1.0), **band(2, out=6))
c = [v / 60 * 36 - 18 for v in info["curve"]][col(200)]
check("curve: band 2's OUTPUT +6 dB lifts its columns", abs(c - 6) < 1.0, "%.1f dB" % c)
_, _, info = run(tone(1000, -40, 0.5), x1=hz_pos(100), x2=hz_pos(400), x3=hz_pos(1600), x4=hz_pos(6000))
cols = [col(hz) + 1 for hz in (100, 400, 1600, 6000)]
check("crossover lines sit on their frequencies", all(abs(a - b) <= 1 for a, b in zip(info["xm"], cols)),
      "%s vs %s" % (info["xm"], cols))
_, _, info = run(tone(1000, -12, 1.0), analyzer=1, **only())
lvl = info["bars"][col(1000)] * 1.25 - 60
check("analyzer: a 1 kHz tone at -12 dBFS reads about -12 dB at 1 kHz", abs(lvl + 12) <= 3.5, "%.1f dB" % lvl)

# a touch on the graph moves the nearest crossover line there
_, _, info = run(tone(1000, -40, 0.5), "@10:c%d=30" % col(2500))
check("graph touch at 2.5 kHz moves the nearest line (XOVER 3, 1.6 kHz) there",
      abs(info["x"][2] - 1000 * (col(2500) + 0.5) / 72) < 0.6 and info["x"][3] == hz_pos(6000), "x = %s" % info["x"])

# ------------------------------------------------------------------ state
_, _, info = run(tone(1000, -20, 0.2), speed=2, mix=63, master=-3.5, x2=hz_pos(300), b4_solo=1, b5_on=0,
                 **band(1, inp=4.5, ratio=6, out=-2))
check("state: saved, loaded into a new instance, saved again: identical", info["state"] == "state ok", info["state"])

# ------------------------------------------------------------------ clicks: everything jumps while tones play
EVENTS = [("band on/off", ["@120:b2_on=0", "@180:b2_on=1"]), ("solo", ["@120:b3_solo=1", "@180:b3_solo=0"]),
          ("crossover jump", ["@120:x2=%d" % hz_pos(1200), "@180:x2=%d" % hz_pos(300)]),
          ("MIX jump", ["@120:mix=0", "@180:mix=100"]), ("BYPASS", ["@120:bypass=1", "@180:bypass=0"]),
          ("INPUT jump", ["@120:b4_in=18", "@180:b4_in=0"]), ("OUTPUT jump", ["@120:b4_out=12", "@180:b4_out=0"]),
          ("RATIO jump", ["@120:b2_ratio=100", "@180:b2_ratio=0"]), ("SPEED", ["@120:speed=0", "@180:speed=2"]),
          ("MASTER jump", ["@120:master=-12", "@180:master=0"])]
x = tone(220, -12, 1.5) + tone(3000, -18, 1.5)


def hf(y):
    """what a click leaves: energy above 6 kHz (the tones and the compressors' smooth gain moves stay well under it)"""
    Y = np.fft.rfft(y)
    Y[np.fft.rfftfreq(len(y), 1 / SR) < 6000] = 0
    return np.abs(np.fft.irfft(Y, len(y)))[SR // 4:-SR // 10]


# a click from a jump in this -12 dBFS material lands around -30..-40 dBFS above 6 kHz; a 10 ms fade's sidebands stay
# near the 16-bit floor. Ceiling: -60 dBFS (48 dB under the music). First, prove the detector sees a real click
CEIL = -60.0
dropped = x.copy(); dropped[SR // 2:SR // 2 + 8] = 0.0
check("click detector: catches an 8-sample dropout", 20 * np.log10(hf(dropped).max()) > CEIL,
      "%.1f dBFS" % (20 * np.log10(hf(dropped).max())))
for name, ev in EVENTS:
    l, r, _ = run(x, *ev, **band(2, inp=10, ratio=4), **band(4, inp=10, ratio=4))
    lvl = 20 * np.log10(max(hf(l).max(), 1e-9))
    check("no click: %s" % name, lvl < CEIL, "worst above 6 kHz %.1f dBFS" % lvl)

# ------------------------------------------------------------------ silence and denormals, CPU
l, r, _ = run(np.zeros(5 * SR), **heavy)
check("silence in: silence out", np.max(np.abs(l)) == 0 and np.max(np.abs(r)) == 0)

with tempfile.TemporaryDirectory() as d:
    sig = np.random.default_rng(1).normal(0, 0.2, 60 * SR).astype(np.float32)
    fi = os.path.join(d, "in.f32"); sig.tofile(fi)
    t0 = os.times()
    subprocess.run([HARNESS, fi, os.path.join(d, "o.s16"), "analyzer=1"] + ["%s=%s" % kv for kv in heavy.items()],
                   check=True, capture_output=True, env=dict(os.environ, STEREO="0"))
    t1 = os.times()
    cpu = (t1.children_user - t0.children_user) + (t1.children_system - t0.children_system)
print("CPU: %.2f %% of one x86 core (60 s of audio, every band compressing, analyzer on, harness I/O included)" % (100 * cpu / 60))

print("\n%d failure(s)" % len(failures))
sys.exit(1 if failures else 0)
