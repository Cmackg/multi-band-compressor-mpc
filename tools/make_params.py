#!/usr/bin/env python3
"""Writes mbc/params.json and mbc/presets.json for Multi-Band Compressor (presets are written in Hz / dB / ratio here and
converted to knob units):

    python3 tools/make_params.py

Every band has: on, solo, INPUT (dB into its compressor), RATIO, OUTPUT (dB after it); bands 1-4 also own the XOVER
(crossover) at their top. Then the globals: MIX, MASTER, SPEED, BYPASS, theme. Then what the engine shows on screen
(curve columns, crossover lines, meters, analyzer), which the host never saves (the engine's own "state" does the saving).

Parameter order is permanent once projects exist: add new parameters at the end.
"""
import json
import math
import os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "mbc")
NB, NX, NCOL, NBAR = 5, 4, 72, 72
XHZ = [100, 400, 1600, 6000]
SPEEDS = ["Fast", "Medium", "Slow"]


def hz_pos(hz):
    return round(1000 * math.log(hz / 20) / math.log(1000))


def ratio_pos(r):
    return round(100 * math.log(r) / math.log(20), 2)


def params():
    P = [{"key": "mix", "name": "MIX", "min": 0, "max": 100, "default": 100, "dynamic_display": True},   # param 0: harmless
         {"key": "master", "name": "MASTER", "min": -24, "max": 24, "default": 0, "dynamic_display": True},
         {"key": "speed", "name": "SPEED", "options": SPEEDS, "default": "Medium"},
         {"key": "bypass", "name": "Bypass", "min": 0, "max": 1, "default": 0, "display": "int"}]
    P += [{"key": "x%d" % k, "name": "XOVER", "min": 0, "max": 1000, "default": hz_pos(XHZ[k - 1]), "dynamic_display": True}
          for k in range(1, NX + 1)]
    for i in range(1, NB + 1):
        P += [{"key": "b%d_on" % i, "name": "Band %d On" % i, "min": 0, "max": 1, "default": 1, "display": "int"},
              {"key": "b%d_solo" % i, "name": "Band %d Solo" % i, "min": 0, "max": 1, "default": 0, "display": "int"},
              {"key": "b%d_in" % i, "name": "INPUT", "min": -24, "max": 24, "default": 0, "dynamic_display": True},
              {"key": "b%d_ratio" % i, "name": "RATIO", "min": 0, "max": 100, "default": ratio_pos(2), "dynamic_display": True},
              {"key": "b%d_out" % i, "name": "OUTPUT", "min": -24, "max": 24, "default": 0, "dynamic_display": True}]
    P += [{"key": "theme", "name": "Theme", "options": ["Grey", "Classic", "White", "Silver"], "default": "Grey", "qlink_ticks": 3},
          {"key": "theme_prev", "name": "Theme <", "momentary": True},
          {"key": "theme_next", "name": "Theme >", "momentary": True},
          {"key": "noop", "name": "-", "momentary": True}]
    # the screen: the engine sets these (display only)
    P += [{"key": "c%d" % c, "name": "Curve %d" % (c + 1), "min": 0, "max": 60, "default": 30} for c in range(NCOL)]
    P += [{"key": "sel", "name": "Selected Band", "options": ["Band %d" % (i + 1) for i in range(NB)], "default": "Band 3"}]
    P += [{"key": "pick_%d" % i, "name": "Pick Band %d" % i, "momentary": True} for i in range(1, NB + 1)]
    P += [{"key": "xm_%d" % k, "name": "XOVER %d Line" % k, "options": ["-"] + [str(c + 1) for c in range(NCOL)], "default": "-"}
          for k in range(1, NX + 1)]
    P += [{"key": "touch", "name": "Touch", "options": ["-"] + [str(c + 1) for c in range(NCOL)], "default": "-"}]
    P += [{"key": "analyzer", "name": "Analyzer", "min": 0, "max": 1, "default": 0, "display": "int"}]
    P += [{"key": "a%d" % k, "name": "Spectrum %d" % (k + 1), "min": 0, "max": 24, "default": 0} for k in range(NBAR)]
    P += [{"key": "g%d" % i, "name": "Band %d GR" % i, "min": 0, "max": 24, "default": 0} for i in range(1, NB + 1)]
    return P


def preset(name, x=XHZ, speed="Medium", mix=100, master=0.0, **bands):
    """bands: b1=(input dB, ratio, output dB) or None for the default (0 dB, 2:1, 0 dB); off=[band numbers]"""
    off = bands.pop("off", [])
    v = {"mix": mix, "master": master, "speed": SPEEDS.index(speed)}
    for k in range(NX):
        v["x%d" % (k + 1)] = hz_pos(x[k])
    for i in range(1, NB + 1):
        inp, ratio, out = bands.get("b%d" % i) or (0.0, 2.0, 0.0)
        v.update({"b%d_on" % i: 0 if i in off else 1, "b%d_solo" % i: 0, "b%d_in" % i: inp,
                  "b%d_ratio" % i: ratio_pos(ratio), "b%d_out" % i: out})
    return {"name": name, "values": v}


def presets():
    return [
        preset("Init"),
        preset("Gentle Glue", speed="Slow", b1=(4, 2, -1), b2=(4, 2, -1), b3=(4, 2, -1), b4=(4, 2, -1), b5=(4, 2, -1)),
        preset("Mix Bus", speed="Medium", b1=(6, 2.5, -1.5), b2=(5, 2, -1), b3=(4, 2, -0.5), b4=(5, 2, -1), b5=(4, 2, 0)),
        preset("Drum Punch", speed="Fast", x=[90, 300, 2000, 7000], b1=(8, 4, 1), b2=(6, 3, 0), b3=(6, 3, 0), b4=(4, 2, 1),
               b5=(2, 2, 1)),
        preset("Tight Low End", speed="Medium", x=[80, 250, 1600, 6000], b1=(10, 6, 0), b2=(8, 4, 0), off=[3, 4, 5]),
        preset("Vocal Control", speed="Fast", x=[150, 500, 3000, 8000], b2=(4, 3, 0), b3=(6, 3, 0), b4=(8, 4, 0), b5=(4, 2, 1),
               off=[1]),
        preset("De-Harsh", speed="Fast", x=[100, 400, 2500, 7000], b4=(10, 4, 0), b5=(8, 3, 0), off=[1, 2, 3]),
        preset("Loud Master", speed="Medium", master=-1.0, b1=(8, 3, -2), b2=(8, 3, -2), b3=(8, 3, -2), b4=(8, 3, -2),
               b5=(8, 3, -2)),
        preset("Parallel Squash", speed="Fast", mix=40, b1=(16, 10, 2), b2=(16, 10, 2), b3=(16, 10, 2), b4=(16, 10, 2),
               b5=(16, 10, 2)),
    ]


def main():
    os.makedirs(OUT, exist_ok=True)
    P, S = params(), presets()
    keys = {p["key"] for p in P}
    for s in S:
        assert set(s["values"]) <= keys, set(s["values"]) - keys
    with open(os.path.join(OUT, "params.json"), "w") as f:
        f.write('{\n  "params": [\n' + ",\n".join("    " + json.dumps(p) for p in P) + "\n  ]\n}\n")
    with open(os.path.join(OUT, "presets.json"), "w") as f:
        f.write('{\n  "presets": [\n' + ",\n".join("    " + json.dumps(p) for p in S) + "\n  ]\n}\n")
    print("mbc: %d params, %d presets" % (len(P), len(S)))


if __name__ == "__main__":
    main()
