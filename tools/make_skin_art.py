#!/usr/bin/env python3
"""Draws Multi-Band Compressor's skin in its four themes and writes the layout that places the live controls on top.

    python3 tools/make_skin_art.py          # needs: pip install playwright && playwright install chromium

Writes mbc/artwork/bg_<theme>.svg, mbc/images/*.png (knob filmstrips, band switches, the curve column filmstrip,
meters, arrows, bypass) and mbc/layout.conf. All of it is committed, so a normal build does not run this.
Coordinates are the skin's (1280 x 628); layout.conf's are the same plus 86 on y.

The look is Shapey 5-Band EQ's (tools/make_skin_art.py in 3dthc's Shapey EQ, MIT, Copyright (c) 2026 3DTHC): its four
themes, finishes, knobs, header, curve display, analyzer and band columns are carried over here; the compressor's own
parts (band headers with SOLO, gain-reduction meters, crossover lines, the XOVER row) are new.
"""
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
VST = os.path.join(HERE, "..", "mbc")
# Titillium Web from the mpc-vst-plugins toolchain checkout (MV, default ../mpc-vst-plugins next to this repo)
MV = os.environ.get("MV") or os.path.join(HERE, "..", "..", "mpc-vst-plugins")
FONT = os.environ.get("MBC_FONTS") or os.path.join(MV, "tools", "html_art", "fonts")
# ---------------------------------------------------------------- themes
# f0/f1: gradient stops. nat/sharp: (face0, face1, stroke, ink) for a lit and an unlit key. led_*: the lit key's bar.
BASE = dict(amber=("#f2a33a", "#ffc76e", "#1d1407"))
THEMES = [
    ("grey", "Grey", dict(
        bg=("#2c2f34", "#1b1d21"), hdr=("#383c42", "#272a2f"), panel=("#373b41", "#25282c"), line="#4b5159",
        ink="#eef1f4", dim="#9aa3ad", sub="#9d5cff", hint="#7a838d", accent="#9d5cff", accent_hi="#c9a3ff",
        field="#191b1f", field_line="#4b5159", arrow="#9d5cff",
        bezel=("#3a3e44", "#1c1e22"), disc=("#55309a", "#2d1a57", "#150c2b"), ring="#9d5cff", glow=.55,
        tick="#4b5159", tick_major="#727b85", tick_zero="#c9a3ff", tick_label="#9aa3ad",
        note="f7f2ff", cents="c9a3ff", knob_name="eef1f4", knob_value="c9a3ff",
        kface=("#40454c", "#1d2024"), ktrack="#4b5159", karc="#9d5cff", kpointer="#c9a3ff",
        nat_on=("#f6f8fa", "#c8ced5", "#8d959e", "#1b1e22"), nat_off=("#4a4f57", "#3b3f46", "#41464d", "#7f8791"),
        sharp_on=("#2d3137", "#16181b", "#565c64", "#eef1f4"), sharp_off=("#202327", "#17191c", "#2f3338", "#5b626a"),
        led_nat="#9d5cff", led_sharp="#9d5cff", byp_off=("#191b1f", "#4b5159", "#aab3bd"), byp_on=BASE["amber"])),
    ("classic", "Classic", dict(                                                   # MPC-style: grey, black, white and red
        bg=("#4a4d52", "#33363a"), hdr=("#55595e", "#3e4146"), panel=("#1c1d1f", "#101113"), line="#5c6066",
        ink="#ffffff", dim="#b4b8bd", sub="#e3242b", hint="#8e9399", accent="#e3242b", accent_hi="#ff4d52",
        field="#0e0f10", field_line="#26282b", arrow="#e3242b",
        bezel=("#5a5e63", "#2a2c2f"), disc=("#26282b", "#141516", "#09090a"), ring="#e3242b", glow=.45,
        tick="#55595e", tick_major="#c9cdd2", tick_zero="#ff4d52", tick_label="#c9cdd2",
        note="ffffff", cents="ff6a6e", knob_name="ffffff", knob_value="ff6a6e",
        kface=("#2c2e31", "#0b0c0d"), ktrack="#3a3d41", karc="#e3242b", kpointer="#ffffff",
        nat_on=("#ffffff", "#dfe2e5", "#9ba0a6", "#111214"), nat_off=("#55595e", "#45484d", "#4c5055", "#8e9399"),
        sharp_on=("#2a2c2f", "#0b0c0d", "#4a4d52", "#ffffff"), sharp_off=("#1a1b1d", "#111213", "#2a2c2f", "#5f6368"),
        led_nat="#e3242b", led_sharp="#ff4d52", byp_off=("#0e0f10", "#26282b", "#c9cdd2"), byp_on=("#e3242b", "#ff6a6e", "#ffffff"))),
    ("white", "White", dict(                                                       # white, grey and black with orange
        bg=("#eef0f3", "#dde1e5"), hdr=("#fbfcfd", "#e7eaee"), panel=("#f8f9fb", "#e2e6ea"), line="#b9c0c8",
        ink="#121417", dim="#5f6873", sub="#f26b1d", hint="#7f8893", accent="#f26b1d", accent_hi="#ff8a3d",
        field="#15171a", field_line="#15171a", arrow="#ff8a3d",
        bezel=("#d5dae0", "#aab2bb"), disc=("#2b2f34", "#17191c", "#0b0c0e"), ring="#f26b1d", glow=.35,
        tick="#a1a9b2", tick_major="#4a525b", tick_zero="#f26b1d", tick_label="#4a525b",
        note="ffffff", cents="ff8a3d", knob_name="121417", knob_value="d9560f",
        kface=("#2e3237", "#0f1113"), ktrack="#c3c9d0", karc="#f26b1d", kpointer="#ffffff",
        nat_on=("#ffffff", "#e9ecef", "#9aa2ab", "#121417"), nat_off=("#cdd2d8", "#b9bfc6", "#a8afb7", "#7d858f"),
        sharp_on=("#2e3237", "#0f1113", "#0f1113", "#ffffff"), sharp_off=("#90979f", "#7d848c", "#757c84", "#50575f"),
        led_nat="#f26b1d", led_sharp="#ff8a3d", byp_off=("#ffffff", "#b9c0c8", "#121417"), byp_on=("#f26b1d", "#ff8a3d", "#ffffff"))),
    ("silver", "Silver", dict(
        bg=("#cdd2d8", "#9ea6ae"), hdr=("#e3e7eb", "#bcc2c9"), panel=("#dde1e6", "#b5bcc4"), line="#8b939c",
        ink="#14181d", dim="#48505a", sub="#0a6fb0", hint="#5c646e", accent="#0a6fb0", accent_hi="#0a6fb0",
        field="#1b1f24", field_line="#5f6770", arrow="#6fd8ff",
        bezel=("#e4e8ec", "#8e969f"), disc=("#2b5d85", "#173650", "#0c1b29"), ring="#0a6fb0", glow=.35,
        tick="#7a828b", tick_major="#2f363e", tick_zero="#0a6fb0", tick_label="#3a424b",
        note="f2f8ff", cents="9fdcff", knob_name="14181d", knob_value="0a4f80",
        kface=("#3a3e44", "#14171a"), ktrack="#9aa2ab", karc="#0a6fb0", kpointer="#ffffff",
        nat_on=("#ffffff", "#e3e7eb", "#8b939c", "#14181d"), nat_off=("#aeb5bd", "#99a0a8", "#8b939c", "#5f6873"),
        sharp_on=("#2e3237", "#101215", "#101215", "#e9ecef"), sharp_off=("#6f767e", "#5e646b", "#565c63", "#3c4249"),
        led_nat="#0a6fb0", led_sharp="#3fb0ff", byp_off=("#1b1f24", "#5f6770", "#cfd6dd"), byp_on=BASE["amber"])),
]


def _font_css():
    """Titillium Web as embedded @font-face rules: the SVG is drawn as a separate image, which can't load fonts from
    files, so the background and the pictures carry the font themselves."""
    import base64
    rules = []
    for w, f in ((400, "TitilliumWeb-Regular.ttf"), (600, "TitilliumWeb-SemiBold.ttf"), (700, "TitilliumWeb-Bold.ttf")):
        p = os.path.join(FONT, f)
        if not os.path.exists(p):
            raise SystemExit("make_skin_art: %s not found (set MV to the mpc-vst-plugins checkout, or MBC_FONTS to the Titillium Web folder)" % p)
        rules.append('@font-face{font-family:"Titillium Web";font-weight:%d;src:url(data:font/ttf;base64,%s)}'
                     % (w, base64.b64encode(open(p, "rb").read()).decode()))
    return "".join(rules)


FONT_CSS = _font_css()
TF = "font-family:'Titillium Web',sans-serif"


def grad(id_, stops, vertical=True):
    return '<linearGradient id="%s" x2="%d" y2="%d">%s</linearGradient>' % (
        id_, 0 if vertical else 1, 1 if vertical else 0,
        "".join('<stop offset="%g" stop-color="%s"/>' % (i / max(1, len(stops) - 1), c) for i, c in enumerate(stops)))


# ---------------------------------------------------------------- finish (shared by every theme)
# grain: fine noise over the plate; brushed: horizontal brushed-metal streaks; gloss: strength of the top sheen
FINISH = {"grey": dict(grain=.07, brushed=0, gloss=.09), "classic": dict(grain=.08, brushed=0, gloss=.09),
          "white": dict(grain=.035, brushed=0, gloss=.45), "silver": dict(grain=.02, brushed=.20, gloss=.35)}
def common_defs():
    return ('<filter id="grain" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".85" '
            'numOctaves="2" seed="7"/><feColorMatrix values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 .9 -.35"/></filter>'
            '<filter id="brushed" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".004 .9" '
            'numOctaves="3" seed="3"/><feColorMatrix values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 1.4 -.55"/></filter>'
            '<filter id="drop" x="-10%" y="-10%" width="120%" height="130%"><feDropShadow dx="0" dy="4" stdDeviation="6" flood-opacity=".45"/></filter>'
            '<filter id="soft" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="3.5"/></filter>'
            '<filter id="blur8" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="8"/></filter>'
            '<linearGradient id="bevel" x2="0" y2="1"><stop stop-color="#fff" stop-opacity=".22"/><stop offset=".12" stop-color="#fff" stop-opacity="0"/>'
            '<stop offset=".88" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".35"/></linearGradient>'
            '<linearGradient id="chrome" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#fff" stop-opacity=".55"/>'
            '<stop offset=".45" stop-color="#fff" stop-opacity=".05"/><stop offset=".55" stop-color="#000" stop-opacity=".1"/>'
            '<stop offset="1" stop-color="#000" stop-opacity=".5"/></linearGradient>'
            '<linearGradient id="inset" x2="0" y2="1"><stop stop-color="#000" stop-opacity=".55"/><stop offset=".35" stop-color="#000" stop-opacity="0"/>'
            '<stop offset="1" stop-color="#fff" stop-opacity=".06"/></linearGradient>'
            '<radialGradient id="vignette" cx=".5" cy=".45" r=".75"><stop offset=".55" stop-color="#000" stop-opacity="0"/>'
            '<stop offset="1" stop-color="#000" stop-opacity=".35"/></radialGradient>'
            '<linearGradient id="glass" x2="0" y2="1"><stop stop-color="#fff" stop-opacity=".22"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>')


def gloss_grad(g):
    return ('<linearGradient id="gloss" x2="0" y2="1"><stop stop-color="#fff" stop-opacity="%g"/>'
            '<stop offset=".45" stop-color="#fff" stop-opacity="%g"/><stop offset=".46" stop-color="#fff" stop-opacity="0"/></linearGradient>' % (g, g * .35))


def panel(path, t, fin):
    """A raised panel: soft shadow, fill, top sheen, bevelled edge."""
    return ('<path d="%s" fill="url(#pnl)" filter="url(#drop)"/>'
            '<path d="%s" fill="url(#gloss)" opacity=".6"/>'
            '<path d="%s" fill="none" stroke="url(#bevel)" stroke-width="2"/>'
            '<path d="%s" fill="none" stroke="%s"/>' % (path, path, path, path, t["line"]))


def bypass_svg(slug, t, on):
    _, _, w, h = BYPASS
    fill, stroke, ink = t["byp_on" if on else "byp_off"]
    rr = (h - 4) // 2
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d"><defs>%s<filter id="gl" x="-20%%" y="-50%%" width="140%%" height="200%%">'
            '<feGaussianBlur stdDeviation="3"/></filter></defs>'
            '%s<rect x="2" y="2" width="%d" height="%d" rx="%d" fill="%s"/><rect x="2" y="2" width="%d" height="%d" rx="%d" fill="url(#gloss)"/>'
            '<rect x="2.5" y="2.5" width="%d" height="%d" rx="%d" fill="none" stroke="%s" stroke-width="1.5"/>'
            '<text x="%g" y="%g" text-anchor="middle" dominant-baseline="central" style="%s;font-weight:700;font-size:18px;letter-spacing:3px" fill="%s">BYPASS</text></svg>') % (
        w, h, gloss_grad(.35 if on else .12),
        ('<rect x="4" y="4" width="%d" height="%d" rx="%d" fill="%s" filter="url(#gl)" opacity=".8"/>' % (w - 8, h - 8, rr, fill)) if on else "",
        w - 4, h - 4, rr, fill, w - 4, h - 4, rr, w - 5, h - 5, rr, stroke, w / 2, h / 2 + 1, TF, ink)


def arrow_svg(t, side, pressed):
    """A ◀ or ▶ for an arrows selector, on a transparent square (the field is in the background)."""
    w, h = ARROW_W, SEL_H
    cx, cy = w / 2, h / 2
    d = -1 if side == "prev" else 1
    col = t["arrow"]
    back = ('<rect x="3" y="3" width="%d" height="%d" rx="7" fill="#fff" opacity=".10"/>' % (w - 6, h - 6)) if pressed else ""
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d">%s<path d="M%g %gL%g %gL%g %gZ" fill="%s"/></svg>' % (
        w, h, back, cx + 8 * d, cy, cx - 7 * d, cy - 11, cx - 7 * d, cy + 11, col))


FRAMES = 128


def knob_strip_svg(slug, t, r):
    """128 knob positions stacked top to bottom, each in a (2r+8)-pixel square (the renderer's knob box): value arc with a
    soft glow, a bevelled rim, a domed face lit from above, and a pointer. The light stays put while the pointer turns."""
    s = 2 * r + 8
    sw = max(2.5, r / 11)
    R = r + 4 - sw / 2 - 1.5
    fr = r - sw - 2.5                                   # rim radius
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">' % (s, s * FRAMES, s, s * FRAMES),
         '<defs><radialGradient id="kf" cx=".42" cy=".3" r=".85"><stop stop-color="%s"/><stop offset="1" stop-color="%s"/></radialGradient>' % t["kface"],
         '<linearGradient id="rim" x2="0" y2="1"><stop stop-color="#fff" stop-opacity=".45"/><stop offset=".5" stop-color="#fff" stop-opacity=".05"/>'
         '<stop offset="1" stop-color="#000" stop-opacity=".5"/></linearGradient>',
         '<radialGradient id="spec" cx=".5" cy=".5" r=".5"><stop stop-color="#fff" stop-opacity=".38"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>',
         '<filter id="sh" x="-30%%" y="-30%%" width="160%%" height="170%%"><feDropShadow dx="0" dy="%g" stdDeviation="%g" flood-opacity=".6"/></filter>' % (max(1.5, r / 20), max(1.5, r / 18)),
         '<filter id="ag" x="-30%%" y="-30%%" width="160%%" height="160%%"><feGaussianBlur stdDeviation="%g"/></filter></defs>' % max(1.2, r / 22)]
    pt = lambda cx, cy, a, rad: (cx + rad * math.sin(math.radians(a)), cy - rad * math.cos(math.radians(a)))
    for k in range(FRAMES):
        cx, cy = s / 2, s / 2 + k * s
        a1 = -135 + 270 * k / (FRAMES - 1)
        sx, sy = pt(cx, cy, -135, R)
        ex, ey = pt(cx, cy, 135, R)
        o.append('<path d="M%.2f %.2fA%g %g 0 1 1 %.2f %.2f" fill="none" stroke="%s" stroke-width="%g" stroke-linecap="round"/>' % (
            sx, sy, R, R, ex, ey, t["ktrack"], sw))
        if k:
            vx, vy = pt(cx, cy, a1, R)
            arc = 'd="M%.2f %.2fA%g %g 0 %d 1 %.2f %.2f" fill="none" stroke="%s" stroke-linecap="round"' % (
                sx, sy, R, R, 1 if a1 + 135 > 180 else 0, vx, vy, t["karc"])
            o.append('<path %s stroke-width="%g" opacity=".55" filter="url(#ag)"/>' % (arc, sw * 1.8))
            o.append('<path %s stroke-width="%g"/>' % (arc, sw))
        o.append('<circle cx="%g" cy="%g" r="%g" fill="url(#kf)" filter="url(#sh)"/>' % (cx, cy, fr))
        o.append('<circle cx="%g" cy="%g" r="%g" fill="none" stroke="url(#rim)" stroke-width="%g"/>' % (cx, cy, fr - max(1, r / 40), max(1.2, r / 28)))
        o.append('<circle cx="%g" cy="%g" r="%g" fill="url(#kf)"/>' % (cx, cy, fr * .78))
        o.append('<ellipse cx="%g" cy="%g" rx="%g" ry="%g" fill="url(#spec)"/>' % (cx - fr * .18, cy - fr * .38, fr * .55, fr * .32))
        p0, p1 = pt(cx, cy, a1, fr * .30), pt(cx, cy, a1, fr * .86)
        o.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="%s" stroke-width="%g" stroke-linecap="round"/>' % (
            p0[0], p0[1], p1[0], p1[1], t["kpointer"], max(2, r / 10)))
    o.append("</svg>")
    return "\n".join(o), s, s * FRAMES




def render_pngs(items):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page()
        for path, svg, w, h in items:
            pg.set_viewport_size({"width": w, "height": min(h, 16384)})
            pg.set_content("<html><head><style>%s html,body{margin:0;background:transparent}</style></head><body>%s</body></html>" % (FONT_CSS, svg))
            pg.wait_for_timeout(50)
            pg.screenshot(path=path, omit_background=True, full_page=True)
        b.close()


# ---------------------------------------------------------------- geometry (skin coordinates, 1280 x 628)
HDR_H = 58
SEL_Y, SEL_H = 10, 38                                    # header fields: top, height
ARROW_W = 44
TITLE = ("MULTI-BAND", "COMPRESSOR")
ANALYZER = (262, 29, 140, 38)                            # cx, cy, w, h
SPEED_FIELD = (404, 120)                                 # x, w (label "SPEED" before it)
MIX_KNOB = (640, 29, 140)                                # cx, cy, box width (knob at its left, value after; label before)
MASTER_KNOB = (870, 29, 160)
THEME_SEL = (966, 168)                                   # x, w (arrows at both ends)
BYPASS = (1200, 29, 112, 38)                             # cx, cy, w, h
FIELD_TEXT = 26

GRAPH = (16, 62, 1248, 252)                              # the display panel: x, y, w, h
NCOL, COL_W = 72, 16
PLOT_X, PLOT_Y, PLOT_H = 72, 70, 200                     # the curve: 72 columns of 16 px from x 72, 200 px tall
CURVE_DB, CURVE_STEPS = 18, 60                           # -18 .. +18 dB in 60 steps (frame 30 = 0 dB)
NBAR, BAR_STEPS = 72, 24                                 # analyzer: a haze behind the curve
F_LO, F_HI = 20.0, 20000.0
NX = 4

BANDS = [("LOW", "#ff5a5f"), ("LOW MID", "#ff9f40"), ("MID", "#ffd84a"), ("HIGH MID", "#5b8cff"), ("HIGH", "#ff6fc6")]
COLS_X0, COLS_Y, COL_PITCH, COLS_H = 16, 320, 249, 302   # the band columns under the graph
COL_PAD = 6
HDR_ROW = 38                                             # a column's header row: power, name, solo
POWER_W, PILL_W, SOLO_W = 38, 140, 50
ROW1_R, ROW1_NS = 27, 24                                 # INPUT, RATIO, OUTPUT
ROW2_R, ROW2_NS = 22, 22                                 # XOVER
GR_W, GR_H, GR_STEPS = 148, 22, 24                       # the gain-reduction meter: a bar filling to the right, 1 dB a frame
SCREEN = ("#0b0e13", "#151a22")
CURVE = "#eaf4ff"
TOUCH_W = 64


def knob_box(r, ns, vs):
    """height of a knob's touch box (picture, name, value) as the skin builder lays it out"""
    return 2 * r + 15 + round(1.2 * (ns + vs))


ROW1_TOP = COLS_Y + COL_PAD + HDR_ROW + 4
ROW2_TOP = ROW1_TOP + knob_box(ROW1_R, ROW1_NS, ROW1_NS) + 2
ROW2_CY = ROW2_TOP + ROW2_R + 5                          # the XOVER knob's centre (and the meter's row)


def plot_x(hz):
    return PLOT_X + NCOL * COL_W * math.log(hz / F_LO) / math.log(F_HI / F_LO)


def plot_y(db):
    return PLOT_Y + 2.5 + (PLOT_H - 5) * (CURVE_DB - db) / (2 * CURVE_DB)


def band_x(i):
    return COLS_X0 + i * COL_PITCH


def meter_box(i):
    """the gain-reduction meter of band i: x, y, w, h (right of the XOVER knob)"""
    cx = band_x(i) + COL_PITCH // 2
    return cx - 34, ROW2_CY - GR_H // 2 + 4, GR_W, GR_H


def text(x, y, s, size, fill, weight=600, anchor="start", spacing=2):
    return ('<text x="%g" y="%g" text-anchor="%s" dominant-baseline="central" style="%s;font-weight:%d;font-size:%dpx;'
            'letter-spacing:%gpx" fill="%s">%s</text>' % (x, y, anchor, TF, weight, size, spacing, fill, s))


def field(x, y, w, h, t):
    return ('<rect x="%g" y="%g" width="%d" height="%d" rx="8" fill="%s"/>'
            '<rect x="%g" y="%g" width="%d" height="%d" rx="8" fill="url(#inset)"/>'
            '<rect x="%g" y="%g" width="%d" height="%d" rx="8" fill="none" stroke="%s"/>' % (
                x, y, w, h, t["field"], x, y, w, h, x + .5, y + .5, w - 1, h - 1, t["field_line"]))


# ---------------------------------------------------------------- background
def background(slug, t):
    fin = FINISH[slug]
    gx, gy, gw, gh = GRAPH
    cy = HDR_H // 2 + 1
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="628" viewBox="0 0 1280 628">', "<defs>",
         grad("bg", t["bg"]), grad("hdr", t["hdr"]), grad("pnl", t["panel"]), grad("scr", SCREEN), gloss_grad(fin["gloss"]),
         common_defs(), "<style>%s</style>" % FONT_CSS, "</defs>",
         '<rect width="1280" height="628" fill="url(#bg)"/>']
    if fin["brushed"]:
        o.append('<rect width="1280" height="628" filter="url(#brushed)" opacity="%g"/>' % fin["brushed"])
    if fin["grain"]:
        o.append('<rect width="1280" height="628" filter="url(#grain)" opacity="%g"/>' % fin["grain"])
    o.append('<rect width="1280" height="628" fill="url(#vignette)"/>')

    # header: title, then each control's label before it
    o.append('<rect width="1280" height="%d" fill="url(#hdr)" filter="url(#drop)"/>' % HDR_H)
    o.append('<rect width="1280" height="%d" fill="url(#gloss)" opacity=".7"/>' % (HDR_H * 34 // 80))
    o.append('<path d="M0 .5H1280" stroke="#fff" stroke-opacity=".18"/><path d="M0 %gH1280" stroke="#000" stroke-opacity=".45"/>' % (HDR_H - .5))
    o.append(text(24, 22, TITLE[0], 25, t["ink"], 700, spacing=1))
    o.append(text(25, 44, TITLE[1], 12, t["sub"], 600, spacing=3.2))
    sx, sw = SPEED_FIELD
    o.append(text(sx - 54, cy, "SPEED", 14, t["dim"]))
    o.append(field(sx, SEL_Y, sw, SEL_H, t))
    for label, (kx, _, kw) in (("MIX", MIX_KNOB), ("MASTER", MASTER_KNOB)):
        o.append(text(kx - kw // 2 - 8, cy, label, 14, t["dim"], anchor="end"))
    x, w = THEME_SEL
    o.append(field(x, SEL_Y, w, SEL_H, t))
    for dx in (x + ARROW_W, x + w - ARROW_W):
        o.append('<path d="M%g %gV%g" stroke="#fff" stroke-opacity=".08"/>' % (dx, SEL_Y + 7, SEL_Y + SEL_H - 7))

    # the display: a dark screen in every theme, with a frame from the theme
    o.append('<rect x="%d" y="%d" width="%d" height="%d" rx="12" fill="url(#pnl)" filter="url(#drop)"/>' % (gx, gy, gw, gh))
    o.append('<rect x="%d" y="%d" width="%d" height="%d" rx="12" fill="none" stroke="url(#bevel)" stroke-width="2"/>' % (gx, gy, gw, gh))
    o.append('<rect x="%d" y="%d" width="%d" height="%d" rx="8" fill="url(#scr)"/>' % (gx + 6, gy + 6, gw - 12, gh - 12))
    o.append('<rect x="%d" y="%d" width="%d" height="%d" rx="8" fill="url(#inset)"/>' % (gx + 6, gy + 6, gw - 12, gh - 12))
    x0, x1 = PLOT_X, PLOT_X + NCOL * COL_W
    for db in range(-18, 19, 6):
        y = plot_y(db)
        o.append('<path d="M%d %.1fH%d" stroke="#fff" stroke-opacity="%g"/>' % (x0, y, x1, .28 if db == 0 else .08))
        o.append(text(x0 - 8, y, ("%+d" % db) if db else "0", 14, "#8793a3", anchor="end", spacing=0))
    for hz, lab in ((20, "20"), (50, "50"), (100, "100"), (200, "200"), (500, "500"), (1000, "1k"), (2000, "2k"),
                    (5000, "5k"), (10000, "10k"), (20000, "20k")):
        x = plot_x(hz)
        o.append('<path d="M%.1f %dV%d" stroke="#fff" stroke-opacity="%g"/>' % (x, PLOT_Y, PLOT_Y + PLOT_H, .12 if lab in ("100", "1k", "10k") else .06))
        o.append(text(x, PLOT_Y + PLOT_H + 18, lab, 14, "#8793a3", anchor="middle", spacing=0))
    for hz in (30, 40, 60, 70, 80, 90, 300, 400, 600, 700, 800, 900, 3000, 4000, 6000, 7000, 8000, 9000):
        x = plot_x(hz)
        o.append('<path d="M%.1f %dV%d" stroke="#fff" stroke-opacity=".03"/>' % (x, PLOT_Y, PLOT_Y + PLOT_H))
    o.append(text(x1, PLOT_Y + PLOT_H + 29, "DRAG A DASHED LINE SIDEWAYS TO MOVE A CROSSOVER", 11, "#5d6876", anchor="end", spacing=1.5))
    o.append('<rect x="%d" y="%d" width="%d" height="%d" rx="8" fill="url(#glass)" opacity=".35"/>' % (gx + 6, gy + 6, gw - 12, (gh - 12) // 2))

    # band columns: a panel each, its colour along the top; the meter's slot, label and scale
    for i, (name, col) in enumerate(BANDS):
        x = band_x(i)
        p = "M%g %dH%gA8 8 0 0 1 %g %dV%dA8 8 0 0 1 %g %dH%gA8 8 0 0 1 %g %dV%dA8 8 0 0 1 %g %dZ" % (
            x + 10, COLS_Y, x + COL_PITCH - 12, x + COL_PITCH - 4, COLS_Y + 8, COLS_Y + COLS_H - 8, x + COL_PITCH - 12, COLS_Y + COLS_H,
            x + 10, x + 2, COLS_Y + COLS_H - 8, COLS_Y + 8, x + 10, COLS_Y)
        o.append(panel(p, t, fin))
        o.append('<path d="M%g %dH%g" stroke="%s" stroke-width="3" stroke-linecap="round" opacity=".9"/>' % (x + 16, COLS_Y + 1.5, x + COL_PITCH - 18, col))
        mx, my, mw, mh = meter_box(i)
        o.append(text(mx, my - 12, "GAIN REDUCTION", 11, t["dim"], spacing=1.5))
        o.append('<rect x="%g" y="%g" width="%d" height="%d" rx="5" fill="%s"/>' % (mx - 2, my - 2, mw + 4, mh + 4, SCREEN[0]))
        o.append('<rect x="%g" y="%g" width="%d" height="%d" rx="5" fill="url(#inset)"/>' % (mx - 2, my - 2, mw + 4, mh + 4))
        for db in (0, 6, 12, 18, 24):
            tx = mx + mw * db / GR_STEPS
            o.append('<path d="M%.1f %gV%g" stroke="%s" stroke-opacity=".5"/>' % (tx, my + mh + 3, my + mh + 7, t["dim"]))
            o.append(text(tx, my + mh + 16, str(db), 11, t["dim"], anchor="middle", spacing=0))
        if i == len(BANDS) - 1:   # the top band has no crossover above it
            o.append(text(band_x(i) + COL_PITCH // 2 - 78, ROW2_CY, "TOP", 13, t["dim"], anchor="middle", spacing=2))
    o.append("</svg>")
    return "\n".join(o)


# ---------------------------------------------------------------- pictures
def power_svg(colour, on):
    """a band's on/off switch: a round button with a power symbol, glowing in the band's colour when on (Shapey's)"""
    w = h = POWER_W
    c = w / 2
    ink = colour if on else "#5d6570"
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d"><defs>'
            '<filter id="g" x="-50%%" y="-50%%" width="200%%" height="200%%"><feGaussianBlur stdDeviation="2.2"/></filter>'
            '<linearGradient id="f" x2="0" y2="1"><stop stop-color="#262b33"/><stop offset="1" stop-color="#11141a"/></linearGradient></defs>'
            '<circle cx="%g" cy="%g" r="%g" fill="url(#f)" stroke="%s" stroke-opacity="%g" stroke-width="1.5"/>'
            '<g fill="none" stroke="%s" stroke-width="2.4" stroke-linecap="round" %s>'
            '<path d="M%g %g A7 7 0 1 0 %g %g"/><path d="M%g %gV%g"/></g>'
            '<g fill="none" stroke="%s" stroke-width="2.4" stroke-linecap="round">'
            '<path d="M%g %g A7 7 0 1 0 %g %g"/><path d="M%g %gV%g"/></g></svg>') % (
        w, h, c, c, c - 1.5, ink, .9 if on else .25,
        colour, 'filter="url(#g)" opacity="%g"' % (.9 if on else 0),
        c - 4.6, c - 4.4, c + 4.6, c - 4.4, c, c - 9, c - 1,
        ink, c - 4.6, c - 4.4, c + 4.6, c - 4.4, c, c - 9, c - 1)


def pill_svg(name, colour, selected):
    """a band's name plate: outlined in the band's colour, lit when the band is selected (Shapey's TYPE field look)"""
    w, h = PILL_W, HDR_ROW
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d"><defs>'
            '<filter id="g" x="-20%%" y="-50%%" width="140%%" height="200%%"><feGaussianBlur stdDeviation="2.5"/></filter>'
            '<linearGradient id="f" x2="0" y2="1"><stop stop-color="%s"/><stop offset="1" stop-color="#11141a"/></linearGradient></defs>'
            '%s<rect x="1.5" y="1.5" width="%d" height="%d" rx="9" fill="url(#f)" stroke="%s" stroke-opacity="%g" stroke-width="%g"/>'
            '<text x="%g" y="%g" text-anchor="middle" dominant-baseline="central" style="%s;font-weight:700;font-size:17px;letter-spacing:1.5px" fill="%s">%s</text></svg>') % (
        w, h, "#2a2f38" if selected else "#20252d",
        ('<rect x="2" y="2" width="%d" height="%d" rx="9" fill="none" stroke="%s" stroke-width="3" filter="url(#g)"/>' % (w - 4, h - 4, colour)) if selected else "",
        w - 3, h - 3, colour, 1 if selected else .35, 2 if selected else 1,
        w / 2, h / 2 + 1, TF, "#ffffff" if selected else "#c3cad3", name)


def solo_svg(colour, on):
    """a band's SOLO switch: an S, lit in the band's colour when on"""
    w, h = SOLO_W, HDR_ROW
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d"><defs>'
            '<filter id="g" x="-30%%" y="-50%%" width="160%%" height="200%%"><feGaussianBlur stdDeviation="2.5"/></filter>'
            '<linearGradient id="f" x2="0" y2="1"><stop stop-color="%s"/><stop offset="1" stop-color="%s"/></linearGradient></defs>'
            '%s<rect x="1.5" y="1.5" width="%d" height="%d" rx="9" fill="url(#f)" stroke="%s" stroke-opacity="%g" stroke-width="1.5"/>'
            '<text x="%g" y="%g" text-anchor="middle" dominant-baseline="central" style="%s;font-weight:700;font-size:13px;letter-spacing:1px" fill="%s">SOLO</text></svg>') % (
        w, h, colour if on else "#20252d", "#6a5a20" if on else "#11141a",
        ('<rect x="3" y="3" width="%d" height="%d" rx="9" fill="%s" filter="url(#g)" opacity=".7"/>' % (w - 6, h - 6, colour)) if on else "",
        w - 3, h - 3, colour if on else "#ffffff", 1 if on else .14, w / 2, h / 2 + 1, TF, "#0b0e13" if on else "#8b949e")


def column_ring_svg(colour):
    """around the selected band's column"""
    w, h = COL_PITCH - 2, COLS_H + 4
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d"><defs><filter id="g" x="-10%%" y="-10%%" width="120%%" height="120%%">'
            '<feGaussianBlur stdDeviation="2.5"/></filter></defs>'
            '<rect x="3" y="3" width="%d" height="%d" rx="10" fill="none" stroke="%s" stroke-width="3" opacity=".75" filter="url(#g)"/>'
            '<rect x="2.5" y="2.5" width="%d" height="%d" rx="10" fill="none" stroke="%s" stroke-width="1.5"/></svg>') % (
        w, h, w - 6, h - 6, colour, w - 5, h - 5, colour)


def gr_strip_svg(colour):
    """a gain-reduction meter: GR_STEPS + 1 frames, frame k = k dB, a bar filling to the right with a bright tip"""
    w, h = GR_W, GR_H
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d"><defs>'
         '<linearGradient id="b"><stop stop-color="%s" stop-opacity=".55"/><stop offset="1" stop-color="%s"/></linearGradient>'
         '<filter id="g" x="-20%%" y="-50%%" width="140%%" height="200%%"><feGaussianBlur stdDeviation="2"/></filter></defs>' % (
             w, h * (GR_STEPS + 1), colour, colour)]
    for k in range(1, GR_STEPS + 1):
        y = k * h
        bw = w * k / GR_STEPS
        o.append('<rect x="0" y="%d" width="%.1f" height="%d" rx="3" fill="url(#b)" opacity=".9"/>' % (y + 3, bw, h - 6))
        o.append('<rect x="%.1f" y="%d" width="3" height="%d" rx="1" fill="#ffffff" filter="url(#g)"/>' % (max(0, bw - 3), y + 2, h - 4))
        o.append('<rect x="%.1f" y="%d" width="2" height="%d" fill="#ffffff"/>' % (max(0, bw - 2), y + 3, h - 6))
    o.append("</svg>")
    return "".join(o), w, h * (GR_STEPS + 1)


def bar_strip_svg():
    """an analyzer column (Shapey's): BAR_STEPS + 1 frames of soft haze"""
    w, h = NCOL * COL_W // NBAR, PLOT_H
    n = BAR_STEPS + 1
    c = "#8fb8ff"
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d">' % (w, h * n)]
    for k in range(1, n):
        top = k * h + 3 + (h - 6) * (1 - k / BAR_STEPS)
        bottom = (k + 1) * h - 2
        y0 = max(k * h, top - 14)
        span = bottom - y0
        edge = min(.5, max(.02, (top - y0) / span))
        o.append('<defs><linearGradient id="g%d" x2="0" y2="1"><stop stop-color="%s" stop-opacity="0"/>'
                 '<stop offset="%.3f" stop-color="%s" stop-opacity=".30"/><stop offset="1" stop-color="%s" stop-opacity=".05"/></linearGradient></defs>'
                 % (k, c, edge, c, c))
        o.append('<rect x="0" y="%.1f" width="%d" height="%.1f" fill="url(#g%d)"/>' % (y0, w, span, k))
    o.append("</svg>")
    return "".join(o), w, h * n


def analyzer_svg(on):
    """the analyzer switch (Shapey's): a dark pill with a little spectrum, lit when on"""
    _, _, w, h = ANALYZER
    ink = "#bcd6ff" if on else "#6d7682"
    bars = "".join('<rect x="%g" y="%g" width="4" height="%g" rx="1" fill="%s"/>' % (12 + 6 * i, h / 2 + 9 - v, v, ink)
                   for i, v in enumerate((6, 12, 17, 10, 14, 7)))
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d"><defs>'
            '<filter id="g" x="-20%%" y="-50%%" width="140%%" height="200%%"><feGaussianBlur stdDeviation="2.5"/></filter>'
            '<linearGradient id="f" x2="0" y2="1"><stop stop-color="%s"/><stop offset="1" stop-color="#0f1217"/></linearGradient></defs>'
            '%s<rect x="1.5" y="1.5" width="%d" height="%d" rx="9" fill="url(#f)" stroke="%s" stroke-opacity="%g" stroke-width="1.5"/>%s'
            '<text x="%g" y="%g" text-anchor="middle" dominant-baseline="central" style="%s;font-weight:700;font-size:14px;letter-spacing:1.5px" fill="%s">ANALYZER</text></svg>') % (
        w, h, "#262c35" if on else "#1b1f26",
        ('<rect x="3" y="3" width="%d" height="%d" rx="9" fill="none" stroke="#9fc4ff" stroke-width="3" filter="url(#g)" opacity=".7"/>' % (w - 6, h - 6)) if on else "",
        w - 3, h - 3, "#9fc4ff" if on else "#ffffff", .8 if on else .14, bars, w / 2 + 20, h / 2 + 1, TF, "#eef4ff" if on else "#8b949e")


def touch_glow_svg():
    """the graph column under the finger (Shapey's)"""
    w, h = TOUCH_W, PLOT_H
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d"><defs>'
            '<linearGradient id="hz"><stop stop-color="#ffffff" stop-opacity="0"/><stop offset=".5" stop-color="#ffffff" stop-opacity=".26"/>'
            '<stop offset="1" stop-color="#ffffff" stop-opacity="0"/></linearGradient>'
            '<linearGradient id="v" x2="0" y2="1"><stop stop-color="#000" stop-opacity=".55"/><stop offset=".5" stop-color="#000" stop-opacity="0"/>'
            '<stop offset="1" stop-color="#000" stop-opacity=".55"/></linearGradient>'
            '<mask id="m"><rect width="%d" height="%d" fill="#fff"/><rect width="%d" height="%d" fill="url(#v)"/></mask></defs>'
            '<g mask="url(#m)"><rect width="%d" height="%d" fill="url(#hz)"/><rect x="%g" width="2" height="%d" fill="#ffffff" opacity=".7"/></g></svg>') % (
        w, h, w, h, w, h, w, h, w / 2 - 1, h)


def xline_svg(k):
    """crossover k's line on the graph: dashed, with its number in a little tag at the top"""
    w, h = 28, PLOT_H
    c = w / 2
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d"><path d="M%g 16V%d" stroke="#ffffff" stroke-width="1.6" '
            'stroke-dasharray="6 4" opacity=".7"/><rect x="%g" y="1" width="18" height="15" rx="4" fill="#ffffff" opacity=".85"/>'
            '<text x="%g" y="9" text-anchor="middle" dominant-baseline="central" style="%s;font-weight:700;font-size:12px" fill="#0b0e13">%d</text></svg>') % (
        w, h, c, h, c - 9, c, TF, k)


def column_strip_svg():
    """the curve, one column (Shapey's): CURVE_STEPS + 1 frames, the column's net gain as a bright cap over a soft fill"""
    w, h = COL_W, PLOT_H
    n = CURVE_STEPS + 1
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d"><defs>'
         '<linearGradient id="up" x2="0" y2="1"><stop stop-color="%s" stop-opacity=".34"/><stop offset="1" stop-color="%s" stop-opacity=".06"/></linearGradient>'
         '<linearGradient id="dn" x2="0" y2="1"><stop stop-color="%s" stop-opacity=".06"/><stop offset="1" stop-color="%s" stop-opacity=".34"/></linearGradient>'
         '<filter id="g" x="-50%%" y="-200%%" width="200%%" height="500%%"><feGaussianBlur stdDeviation="2"/></filter></defs>' % (
             w, h * n, CURVE, CURVE, CURVE, CURVE)]
    y0 = h / 2
    for k in range(n):
        top = k * h
        y = top + 2.5 + (h - 5) * (1 - k / CURVE_STEPS)
        a, b = sorted((top + y0, y))
        if b - a > .5:
            o.append('<rect x="0" y="%.2f" width="%d" height="%.2f" fill="url(#%s)"/>' % (a, w, b - a, "up" if y < top + y0 else "dn"))
        o.append('<rect x="-1" y="%.2f" width="%d" height="4" fill="%s" opacity=".55" filter="url(#g)"/>' % (y - 2, w + 2, CURVE))
        o.append('<rect x="-.5" y="%.2f" width="%g" height="2.6" rx="1" fill="%s"/>' % (y - 1.3, w + 1, CURVE))
    o.append("</svg>")
    return "".join(o), w, h * n


# ---------------------------------------------------------------- layout.conf
def layout():
    Y = 86
    L = ["# Multi-Band Compressor -- Cmackg. Written by tools/make_skin_art.py: edit the design there and rerun it, not this file.",
         "# One page: globals on top, the gain curve display, then one column per band (power, name, solo; INPUT, RATIO,",
         "# OUTPUT; XOVER and the gain-reduction meter). Themed parts: one line per theme (when=theme:<n>). Layout y = skin y + 86.", "",
         "theme_ink=e6eef6", "theme_ink_dim=7d8b9a", "theme_accent=d7dce2", "theme_accent_hi=ffffff", "theme_line=2b3746",
         "theme_box=10151b", "theme_lcd=0a0e13", "theme_seg_active=d7dce2", "theme_seg_inactive=121820", "theme_seg_active_tx=06121c",
         "art_css=popup.css", "", "[tab COMPRESSOR]"]
    for n, (slug, name, _) in enumerate(THEMES):
        L.append('art file="artwork/bg_%s.svg" when=theme:%d' % (slug, n))
    x, w = THEME_SEL
    L += ["", "# theme: its name between the arrows",
          'readout cx=%d cy=%d w=%d h=%d box=0 tsize=%d tcolor=eef1f4 label="THEME" key=theme' % (
              x + w // 2, SEL_Y + SEL_H // 2 + Y, w - 2 * ARROW_W - 8, SEL_H, FIELD_TEXT)]
    sx, sw = SPEED_FIELD
    L += ["", "# SPEED: attack and release for every band (a tap opens the list)",
          'popup cx=%d cy=%d w=%d h=%d label="SPEED" key=speed field=none accent=eef1f4 cols=1 cw=%d options="Fast,Medium,Slow"' % (
              sx + sw // 2, SEL_Y + SEL_H // 2 + Y, sw, SEL_H, sw)]
    ax, ay, aw, ah = ANALYZER
    L += ["", "# the analyzer: a switch in the header, and a 72-column haze behind the curve (display only)",
          'toggle cx=%d cy=%d key=analyzer label="ANALYZER" img=images/analyzer_off.png img_on=images/analyzer_on.png w=%d h=%d ns=0' % (
              ax, ay + Y, aw, ah)]
    bw_ = NCOL * COL_W // NBAR
    for k in range(NBAR):
        L.append('meter cx=%d cy=%d w=%d h=%d key=a%d strip=images/bar.png frames=%d' % (
            PLOT_X + k * bw_ + bw_ // 2, PLOT_Y + PLOT_H // 2 + Y, bw_, PLOT_H, k, BAR_STEPS + 1))
    L += ["", "# touch feedback: the column under the finger glows while it's down (the engine's touch picks it)"]
    for c in range(NCOL):
        L.append('button cx=%d cy=%d w=%d h=%d key=noop label="" img=images/touch_glow.png img_on=images/touch_glow.png when=touch:%d' % (
            PLOT_X + c * COL_W + COL_W // 2, PLOT_Y + PLOT_H // 2 + Y, TOUCH_W, PLOT_H, c + 1))
    L += ["", "# each crossover's dashed line, at its frequency (the engine's xm_<k> picks the column)"]
    for k in range(NX):
        for c in range(NCOL):
            L.append('button cx=%d cy=%d w=28 h=%d key=noop label="" img=images/xline_%d.png img_on=images/xline_%d.png when=xm_%d:%d' % (
                PLOT_X + c * COL_W + COL_W // 2, PLOT_Y + PLOT_H // 2 + Y, PLOT_H, k + 1, k + 1, k + 1, c + 1))
    L += ["", "# the curve: 72 columns, each a filmstrip following the engine's c<n> (net gain right now). A touch moves the",
          "# nearest crossover line to that column; drag sideways to keep moving it"]
    for c in range(NCOL):
        L.append('meter cx=%d cy=%d w=%d h=%d key=c%d strip=images/curve_col.png frames=%d' % (
            PLOT_X + c * COL_W + COL_W // 2, PLOT_Y + PLOT_H // 2 + Y, COL_W, PLOT_H, c, CURVE_STEPS + 1))
    L += ["", "# a tap on a band's column (between its controls) selects it"]
    for i in range(len(BANDS)):
        top = COLS_Y + COL_PAD + HDR_ROW
        h = COLS_H - COL_PAD - HDR_ROW
        L.append('button cx=%d cy=%d w=%d h=%d key=pick_%d label="" img=images/blank.png img_on=images/blank.png' % (
            band_x(i) + COL_PITCH // 2, top + h // 2 + Y, COL_PITCH - 8, h, i + 1))
    L += ["", "# the selected band's column glows (the controls sit on top of it)"]
    for i in range(len(BANDS)):
        L.append('button cx=%d cy=%d w=%d h=%d key=noop label="" img=images/ring_%d.png img_on=images/ring_%d.png when=sel:%d' % (
            band_x(i) + COL_PITCH // 2, COLS_Y + COLS_H // 2 + Y, COL_PITCH - 2, COLS_H + 4, i + 1, i + 1, i))
    L += ["", "# each band's header (power, name: a tap selects it, solo) and its gain-reduction meter"]
    for i in range(len(BANDS)):
        x0 = band_x(i) + (COL_PITCH - (POWER_W + PILL_W + SOLO_W + 8)) // 2
        cy = COLS_Y + COL_PAD + HDR_ROW // 2 + Y
        L.append('toggle cx=%d cy=%d key=b%d_on label="ON" img=images/power_%d_off.png img_on=images/power_%d_on.png w=%d h=%d ns=0' % (
            x0 + POWER_W // 2, cy, i + 1, i + 1, i + 1, POWER_W, HDR_ROW))
        px = x0 + POWER_W + 4 + PILL_W // 2
        L.append('button cx=%d cy=%d w=%d h=%d key=pick_%d label="" img=images/pill_%d.png img_on=images/pill_%d.png' % (
            px, cy, PILL_W, HDR_ROW, i + 1, i + 1, i + 1))
        L.append('button cx=%d cy=%d w=%d h=%d key=noop label="" img=images/pill_%d_sel.png img_on=images/pill_%d_sel.png when=sel:%d' % (
            px, cy, PILL_W, HDR_ROW, i + 1, i + 1, i))
        L.append('toggle cx=%d cy=%d key=b%d_solo label="SOLO" img=images/solo_%d_off.png img_on=images/solo_%d_on.png w=%d h=%d ns=0' % (
            x0 + POWER_W + 4 + PILL_W + 4 + SOLO_W // 2, cy, i + 1, i + 1, i + 1, SOLO_W, HDR_ROW))
        mx, my, mw, mh = meter_box(i)
        L.append('meter cx=%d cy=%d w=%d h=%d key=g%d strip=images/gr_%d.png frames=%d' % (
            mx + mw // 2, my + mh // 2 + Y, mw, mh, i + 1, i + 1, GR_STEPS + 1))
    bx, by, bw, bh = BYPASS
    for n, (slug, _, t) in enumerate(THEMES):
        L += ["", "# ---- theme %d: %s" % (n, slug)]
        L.append('toggle cx=%d cy=%d key=bypass label="BYPASS" img=images/%s_bypass_off.png img_on=images/%s_bypass_on.png w=%d h=%d ns=0 when=theme:%d' % (
            bx, by + Y, slug, slug, bw, bh, n))
        for (kx, ky, kw), label, key in ((MIX_KNOB, "MIX", "mix"), (MASTER_KNOB, "MASTER", "master")):
            L.append('knob cx=%d cy=%d r=20 lay=side bw=%d bh=%d vs=26 ink=%s ink_dim=%s strip=images/%s_knob_r20.png frames=%d label="%s" key=%s when=theme:%d' % (
                kx, ky + Y, kw, SEL_H + 8, t["knob_name"], t["ink"].lstrip("#"), slug, FRAMES, label, key, n))
        x, w = THEME_SEL
        for side, ax in (("prev", x + ARROW_W // 2), ("next", x + w - ARROW_W // 2)):
            L.append('button cx=%d cy=%d w=%d h=%d key=theme_%s label="" img=images/%s_arrow_%s.png img_on=images/%s_arrow_%s_on.png when=theme:%d' % (
                ax, SEL_Y + SEL_H // 2 + Y, ARROW_W, SEL_H, side, slug, side, slug, side, n))
        for i in range(len(BANDS)):
            cx = band_x(i) + COL_PITCH // 2
            for (lab, key), dx in ((("INPUT", "b%d_in" % (i + 1)), -78), (("RATIO", "b%d_ratio" % (i + 1)), 0),
                                   (("OUTPUT", "b%d_out" % (i + 1)), 78)):
                L.append('knob cx=%d cy=%d r=%d bw=78 ns=%d vs=%d ink=%s ink_dim=%s strip=images/%s_knob_r%d.png frames=%d label="%s" key=%s when=theme:%d' % (
                    cx + dx, ROW1_TOP + ROW1_R + 5 + Y, ROW1_R, ROW1_NS, ROW1_NS, t["knob_name"], t["knob_value"], slug, ROW1_R, FRAMES, lab, key, n))
            if i < NX:
                L.append('knob cx=%d cy=%d r=%d bw=78 ns=%d vs=%d ink=%s ink_dim=%s strip=images/%s_knob_r%d.png frames=%d label="XOVER" key=x%d when=theme:%d' % (
                    cx - 78, ROW2_CY + Y, ROW2_R, ROW2_NS, ROW2_NS, t["knob_name"], t["knob_value"], slug, ROW2_R, FRAMES, i + 1, n))
    L += ["", "# Q-Links: one column of four per band (XOVER, INPUT, RATIO, OUTPUT), then band 5 and the globals"]
    ql = []
    for i in range(NX):
        ql += ["x%d" % (i + 1), "b%d_in" % (i + 1), "b%d_ratio" % (i + 1), "b%d_out" % (i + 1)]
    L.append('qlinks "BANDS 1-4" = %s' % ",".join(ql))
    L.append('qlinks "BAND 5, MASTER" = b5_in,b5_ratio,b5_out,mix,master,speed')
    L.append("")
    return "\n".join(L)


def main():
    os.makedirs(os.path.join(VST, "artwork"), exist_ok=True)
    img = os.path.join(VST, "images")
    os.makedirs(img, exist_ok=True)
    items = []
    for slug, _, t in THEMES:
        with open(os.path.join(VST, "artwork", "bg_%s.svg" % slug), "w") as f:
            f.write(background(slug, t) + "\n")
        for on in (0, 1):
            items.append((os.path.join(img, "%s_bypass_%s.png" % (slug, "on" if on else "off")), bypass_svg(slug, t, on), BYPASS[2], BYPASS[3]))
        for r in (ROW1_R, ROW2_R, 20):
            svg, w, h = knob_strip_svg(slug, t, r)
            items.append((os.path.join(img, "%s_knob_r%d.png" % (slug, r)), svg, w, h))
        for side in ("prev", "next"):
            for pressed in (0, 1):
                items.append((os.path.join(img, "%s_arrow_%s%s.png" % (slug, side, "_on" if pressed else "")),
                              arrow_svg(t, side, pressed), ARROW_W, SEL_H))
    for i, (name, col) in enumerate(BANDS):
        for on in (0, 1):
            items.append((os.path.join(img, "power_%d_%s.png" % (i + 1, "on" if on else "off")), power_svg(col, on), POWER_W, HDR_ROW))
            items.append((os.path.join(img, "solo_%d_%s.png" % (i + 1, "on" if on else "off")), solo_svg(col, on), SOLO_W, HDR_ROW))
        items.append((os.path.join(img, "pill_%d.png" % (i + 1)), pill_svg(name, col, False), PILL_W, HDR_ROW))
        items.append((os.path.join(img, "pill_%d_sel.png" % (i + 1)), pill_svg(name, col, True), PILL_W, HDR_ROW))
        items.append((os.path.join(img, "ring_%d.png" % (i + 1)), column_ring_svg(col), COL_PITCH - 2, COLS_H + 4))
        svg, w, h = gr_strip_svg(col)
        items.append((os.path.join(img, "gr_%d.png" % (i + 1)), svg, w, h))
    for k in range(NX):
        items.append((os.path.join(img, "xline_%d.png" % (k + 1)), xline_svg(k + 1), 28, PLOT_H))
    bw_, bh_ = COL_PITCH - 8, COLS_H - COL_PAD - HDR_ROW
    items.append((os.path.join(img, "blank.png"), '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d"/>' % (bw_, bh_), bw_, bh_))
    items.append((os.path.join(img, "touch_glow.png"), touch_glow_svg(), TOUCH_W, PLOT_H))
    svg, w, h = bar_strip_svg()
    items.append((os.path.join(img, "bar.png"), svg, w, h))
    for on in (0, 1):
        items.append((os.path.join(img, "analyzer_%s.png" % ("on" if on else "off")), analyzer_svg(on), ANALYZER[2], ANALYZER[3]))
    svg, w, h = column_strip_svg()
    items.append((os.path.join(img, "curve_col.png"), svg, w, h))
    render_pngs(items)
    with open(os.path.join(VST, "layout.conf"), "w") as f:
        f.write(layout())
    print("wrote %d themes: backgrounds, %d images, layout.conf" % (len(THEMES), len(items)))


if __name__ == "__main__":
    main()
