#!/usr/bin/env python3
"""The built skin as it looks in use, one image per theme, with a preset loaded and music-like audio playing: the curve
and gain-reduction meters the engine reports drawn from their filmstrips, the crossover lines, the band switches, and
MPC's live text filled in at its size. (Adapted from Shapey EQ's tools/preview_demo.py, MIT, 3DTHC.)

    python3 tools/preview_demo.py <mpc-vst-plugins checkout> <run_engine harness> out_dir [preset name]

Offline approximation: MPC draws its own text (Titillium Web) and knob positions; this stands in for them.
"""
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np

MV, HARNESS, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
PRESET = sys.argv[4] if len(sys.argv) > 4 else "Mix Bus"
sys.path.insert(0, os.path.join(MV, "tools"))
from PIL import Image, ImageDraw, ImageFont   # noqa: E402
import studio                                   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_skin_art as A                       # noqa: E402

VST = A.VST
CFG = json.load(open(os.path.join(VST, "vst.json")))
SKIN = os.path.join(VST, "build", "skin", "%s - VST - %s" % (CFG["vendor"], CFG["name"]), "Plugin Skins")
FONT = os.path.join(MV, "tools", "html_art", "fonts")
EM = 1 / 1.53   # MPC font heights are ascent + descent; Titillium's letters are about 1/1.53 of that
f = lambda size, w="SemiBold": ImageFont.truetype(os.path.join(FONT, "TitilliumWeb-%s.ttf" % w), size)
ImageFont.load_default = lambda size=10: f(max(1, round(size * EM)))
orig_rect = ImageDraw.ImageDraw.rectangle
ImageDraw.ImageDraw.rectangle = lambda self, xy, *a, **k: None if k.get("outline") == (70, 110, 160) else orig_rect(self, xy, *a, **k)

preset = next(p for p in json.load(open(os.path.join(VST, "presets.json")))["presets"] if p["name"] == PRESET)
vals = dict(preset["values"])
img = lambda n: Image.open(os.path.join(VST, "images", n)).convert("RGBA")


def fmt_hz(hz):
    return "%.1f kHz" % (hz / 1000) if hz >= 10000 else "%.2f kHz" % (hz / 1000) if hz >= 1000 else "%d Hz" % round(hz)


with tempfile.TemporaryDirectory() as tmp:
    # stand-in music: pink-ish noise with a kick-like low thump every half second, loud enough to compress
    n = 3 * 44100
    w = np.random.default_rng(3).normal(0, 1, n)
    pink = np.real(np.fft.irfft(np.fft.rfft(w) / np.sqrt(np.maximum(np.arange(n // 2 + 1), 1)), n))
    t = np.arange(n) / 44100
    kick = np.sin(2 * math.pi * 55 * t) * np.exp(-((t % 0.5) * 12))
    music = 0.3 * pink / np.max(np.abs(pink)) + 0.45 * kick
    fin = os.path.join(tmp, "in.f32")
    music.astype(np.float32).tofile(fin)
    out = subprocess.run([HARNESS, fin, os.path.join(tmp, "o.s16"), "analyzer=1"] + ["%s=%s" % kv for kv in vals.items()],
                         check=True, capture_output=True, text=True, env=dict(os.environ, STEREO="0")).stdout.split("\n")
    cols = [int(v) for v in out[1].split()]
    bars = [int(v) for v in out[2].split()]
    meters = [int(v) for v in out[3].split()]
    xm = [int(v) for v in out[5].split()]
    skin = os.path.join(tmp, "skin")
    shutil.copytree(SKIN, skin)
    # studio draws every when= part at its parameter's first option: blank the live ones (the curve, the meters, band 1
    # shown as selected) -- they are drawn below from the engine's values instead
    first_sel = [np.asarray(img(n)) for n in ("ring_1.png", "pill_1_sel.png")]
    for m in os.listdir(skin):
        path = os.path.join(skin, m)
        if m.startswith("sh_meter_"):
            Image.new("RGBA", Image.open(path).size).save(path)
        elif m.startswith("sh_btn_") and m.endswith(".png"):
            a = np.asarray(Image.open(path).convert("RGBA"))
            if any(a.shape == b.shape and np.abs(a.astype(int) - b).max() < 8 for b in first_sel):
                Image.new("RGBA", Image.open(path).size).save(path)
    names = [p["key"] for p in json.load(open(os.path.join(VST, "params.json")))["params"]]
    tag = "_mode%d-" % names.index("theme")
    import inspect
    src = inspect.getsource(studio.preview).replace(
        "    for out, tab, state, note in pages:",
        "    pages = [pg for pg in pages if '_mode' not in pg[0] or %r in pg[0]]\n    pages = [pg for pg in pages if '_open' not in pg[0]]\n"
        "    for out, tab, state, note in pages:" % tag, 1)
    assert "_open' not in" in src
    exec(compile(src, studio.__file__, "exec"), studio.__dict__)
    pages = [p for p, _ in studio.preview(skin, os.path.join(tmp, "p_%d.png")) if "_open" not in p]
    pages = [pages[0]] + sorted(p for p in pages[1:] if tag in p)
    strip = img("curve_col.png")
    os.makedirs(OUT, exist_ok=True)
    sel = 2
    for (slug, name, t), page in zip(A.THEMES, pages):
        im = Image.open(page).convert("RGBA")
        d = ImageDraw.Draw(im)

        def text(cx, cy, s, size, colour, weight="SemiBold", anchor="mm"):
            d.text((cx, cy), s, font=f(size, weight), fill="#" + colour.lstrip("#"), anchor=anchor)

        im.alpha_composite(img("ring_%d.png" % (sel + 1)), (A.band_x(sel) + 1, A.COLS_Y - 2))
        bar = img("bar.png")
        bw = A.NCOL * A.COL_W // A.NBAR
        for k, v in enumerate(bars):
            im.alpha_composite(bar.crop((0, v * A.PLOT_H, bw, (v + 1) * A.PLOT_H)), (A.PLOT_X + k * bw, A.PLOT_Y))
        ax, ay, aw, ah = A.ANALYZER
        im.alpha_composite(img("analyzer_on.png"), (ax - aw // 2, ay - ah // 2))
        for k, c in enumerate(xm):
            im.alpha_composite(img("xline_%d.png" % (k + 1)), (A.PLOT_X + (c - 1) * A.COL_W + A.COL_W // 2 - 14, A.PLOT_Y))
        for c, v in enumerate(cols):
            im.alpha_composite(strip.crop((0, v * A.PLOT_H, A.COL_W, (v + 1) * A.PLOT_H)), (A.PLOT_X + c * A.COL_W, A.PLOT_Y))
        for i, (bname, col) in enumerate(A.BANDS):
            k = i + 1
            x0 = A.band_x(i) + (A.COL_PITCH - (A.POWER_W + A.PILL_W + A.SOLO_W + 8)) // 2
            hy = A.COLS_Y + A.COL_PAD
            if vals.get("b%d_on" % k):
                im.alpha_composite(img("power_%d_on.png" % k), (x0, hy))
            if i == sel:
                im.alpha_composite(img("pill_%d_sel.png" % k), (x0 + A.POWER_W + 4, hy))
            mx, my, mw, mh = A.meter_box(i)
            g = img("gr_%d.png" % k)
            v = meters[i]
            im.alpha_composite(g.crop((0, v * mh, mw, (v + 1) * mh)), (mx, my))
            cx = A.band_x(i) + A.COL_PITCH // 2
            vy = A.ROW1_TOP + A.knob_box(A.ROW1_R, A.ROW1_NS, A.ROW1_NS) - round(A.ROW1_NS * 1.2) // 2 - 4
            r = 20 ** (vals["b%d_ratio" % k] / 100)
            for s, dx in (("%+.1f dB" % vals["b%d_in" % k], -78), (("%.1f:1" if r < 9.95 else "%.0f:1") % r, 0),
                          ("%+.1f dB" % vals["b%d_out" % k], 78)):
                text(cx + dx, vy, s, round(A.ROW1_NS * EM), t["knob_value"])
            if i < A.NX:
                hz = 20 * 1000 ** (vals["x%d" % k] / 1000)
                vy2 = A.ROW2_TOP + A.knob_box(A.ROW2_R, A.ROW2_NS, A.ROW2_NS) - round(A.ROW2_NS * 1.2) // 2 - 4
                text(cx - 78, vy2, fmt_hz(hz), round(A.ROW2_NS * EM), t["knob_value"])
        x, w = A.THEME_SEL
        text(x + w // 2, A.SEL_Y + A.SEL_H // 2, name, round(A.FIELD_TEXT * EM), "eef1f4")
        sx, sw = A.SPEED_FIELD
        text(sx + sw // 2, A.SEL_Y + A.SEL_H // 2, ["Fast", "Medium", "Slow"][vals["speed"]], round(24 * EM), "eef1f4")
        for (kx, ky, kw), s in ((A.MIX_KNOB, "%d%%" % vals["mix"]), (A.MASTER_KNOB, "%+.1f dB" % vals["master"])):
            text(kx - kw // 2 + 52, ky, s, round(26 * EM), t["ink"], anchor="lm")
        path = os.path.join(OUT, "mbc_%s.png" % slug)
        im.convert("RGB").save(path)
        print(path)
