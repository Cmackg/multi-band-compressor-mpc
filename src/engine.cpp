/*
 * Multi-Band Compressor -- a 5-band compressor for MPC (Cmackg), built on Shapey 5-Band EQ (3DTHC, MIT): the same touch
 * screen, themes, analyzer, glides and RBJ filter maths, with the EQ bands replaced by a crossover and a compressor per band.
 *
 * Each band has four things to set: where it ends (XOVER, its crossover to the next band: bands 1-4), how hard it is driven
 * into its compressor (INPUT), how much it compresses (RATIO), and its level afterwards (OUTPUT). Plus on/off and solo.
 * The threshold is fixed (THRESH_DB, soft knee): turn a band's INPUT up to compress it more. One SPEED switch sets the
 * attack and release of every band; lower bands get longer times, so bass is not distorted by the gain riding its waves.
 *
 * Signal flow (both channels, zero latency):
 *
 *   in --+--> 4 Linkwitz-Riley crossovers (24 dB/oct) -> 5 bands -> INPUT -> compressor -> OUTPUT -> sum -> MIX -> MASTER
 *        |    (a tree of splits; the lower bands get matching allpasses,                       ^ dry = the same bands,
 *        |     so the bands add back to a flat, allpass response)                              | unprocessed (in phase)
 *        +------------------------------------------------- BYPASS (fades) ------------------------------------------->
 *
 * Crossovers: each split is a 4th-order Linkwitz-Riley low pass / high pass (two RBJ Butterworth biquads each). The bands
 * sum to LP^2 + HP^2 = a 2nd-order allpass at each crossover, so with every band at 0 dB and nothing over the threshold
 * the output is the input with only a phase change: flat (tests/test_comp.py). MIX blends with those same bands, not the
 * raw input, so parallel compression doesn't comb.
 *
 * Compressor (per band): stereo-linked peak detector (the louder channel), a gain computer in dB with a 6 dB soft knee,
 * and the gain reduction smoothed in the log domain by the "smooth decoupled" peak detector (release, then attack;
 * Giannoulis, Massberg & Reiss, JAES 2012). log2 / exp2 are fast polynomial approximations (under 0.01 dB).
 *
 * Screen (as Shapey, drawn like Logic's Multipressor): each band is a flat line across its own range at its gain right now
 * (INPUT + OUTPUT minus the gain reduction), stepping at the crossovers, filled from 0 dB: red where the band is pulled
 * down (compressed), green where it is raised. Behind it, the analyzer haze of the sound after the plugin. A line marks each crossover: touch the graph and drag sideways to move the nearest one. Each
 * band's column has a gain-reduction meter. All of it reaches the screen through the wrapper's display_rev poll, run on
 * the wrapper's own reporter thread (DISPLAY_REV_THREAD), not the audio thread.
 *
 * Parameters are in knob units and mapped here: crossovers 0..1000 (log 20 Hz .. 20 kHz, as Shapey's FREQ), ratio 0..100
 * (log 1:1 .. 20:1); gains are plain dB.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <time.h>
#include <new>

extern "C" {
#include "engine.h"
}

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

static const float SR = 44100.0f;
static const int NB = 5;                       /* bands */
static const int NX = NB - 1;                  /* crossovers */
static const int NCOL = 72;                    /* curve columns on screen */
static const float CURVE_DB = 18.0f;           /* the graph shows -18 .. +18 dB */
static const int CURVE_STEPS = 60;             /* frames per column: 0 = -18 dB .. 60 = +18 dB */
static const float F_LO = 20.0f, F_HI = 20000.0f;
static const int DEF_SEL = 2;                  /* selected at first: the middle band */
static const int TOUCH_HOLD = 86;              /* blocks (~250 ms) a touch glow stays after the finger's last move */
static const int SNAP_HOLD = 86;               /* blocks a crossover pushed against its neighbour waits before its knob follows */
static const int NBAR = 72;                    /* analyzer columns */
static const int FFT_N = 4096;                 /* 10.8 Hz bins: the low columns get bins of their own */
static const int BAR_STEPS = 48;               /* analyzer frames: 0 = nothing .. 48 = the top, 1.25 dB a step */
/* The analyzer's scale (it has no numbers of its own: the graph's dB labels are the gain bars'). A column shows the
 * energy in its range, which for a loud, finished mix is around -10 to -25 dB, so the chart spans BAR_FLOOR .. BAR_TOP
 * to put that mid-chart with room above for peaks. A sine at -12 dBFS reads -12 (two thirds up) */
static const float BAR_FLOOR = -48.0f, BAR_TOP = 12.0f;
static const float BAR_RISE = 0.6f;            /* a rising column goes this share of the way up per picture (no flicker
                                                * to every peak: about 90% in three pictures) */
static const float BAR_FALL = 1.5f;            /* dB an analyzer column falls per picture (~15 dB a second) */
static const float AN_TILT = 1.5f;             /* dB per octave, pivoting at 1 kHz. Each column shows the energy in its
                                                * own frequency range (as a real-time analyzer does), so pink noise reads
                                                * level; a typical mix falls ~1.5 dB/oct faster than pink, and this tilt
                                                * levels it (the same look as FabFilter's 4.5 dB/oct on single bins) */
static const int AN_BLOCKS = 34;               /* screen pictures (analyzer, meters, live curve) every 34 blocks (~99 ms) */
/* The screen budget. Every value that moves costs MPC's screen thread a repaint (the toolchain measured a 48-column
 * display at 10 a second, one report per column, at more than a whole core on its screen thread), and a screen that
 * falls behind looks frozen. So per picture (~10 a second) the analyzer moves at most AN_BUDGET of its columns (the
 * ones furthest from where they should be), and the live gain bars at most LIVE_COL_BUDGET columns, a band moving only
 * when its gain changed by GAIN_JUMP steps or more, or by less for GAIN_HOLD pictures in a row (no flicker). Edits
 * (a knob, a crossover) redraw the bars at once, exactly. Before this, a busy mix sent ~960 reports a second. */
static const int AN_BUDGET = 24;
static const int LIVE_COL_BUDGET = 40;
static const int GAIN_JUMP = 2;                /* curve steps (0.6 dB each) */
static const int GAIN_HOLD = 3;
static const int GR_STEPS = 24;                /* a gain-reduction meter's frames: 0 .. 24 dB, 1 dB a frame */
static const float XGAP = 33.0f;               /* crossovers stay at least 1/3 octave apart (knob units: 100 = 1 octave) */
static const float X_MIN = 59.0f, X_MAX = 917.0f;   /* crossovers 30 Hz .. 11 kHz */
static const float THRESH_DB = -20.0f;         /* every band's threshold (dBFS, at the compressor: after INPUT) */
static const float KNEE_DB = 6.0f;             /* soft knee width */

static const float DEF_XHZ[NX] = {100, 400, 1600, 6000};
static const char *SPEED_NAMES[3] = {"Fast", "Medium", "Slow"};
static const float SPEED_ATT[3] = {3.0f, 10.0f, 30.0f};      /* attack (ms) of the middle band */
static const float SPEED_REL[3] = {60.0f, 150.0f, 400.0f};   /* release (ms) of the middle band */
static const float BAND_TIME[NB] = {2.0f, 1.5f, 1.0f, 0.75f, 0.5f};   /* lower bands slower, higher faster */

static float clampf(float x, float lo, float hi) { return x < lo ? lo : (x > hi ? hi : x); }
static float pos_to_hz(float p) { return F_LO * powf(F_HI / F_LO, clampf(p, 0, 1000) / 1000.0f); }
static float hz_to_pos(float hz) { return 1000.0f * logf(hz / F_LO) / logf(F_HI / F_LO); }
static float ratio_of(float p) { return powf(20.0f, clampf(p, 0, 100) / 100.0f); }            /* 1 .. 20 */
static float ratio_pos(float r) { return 100.0f * logf(r) / logf(20.0f); }

/* ---------- fast log2 / exp2 (dB conversions within 0.01 dB) ---------- */
static inline float fast_log2(float x)
{
    union { float f; uint32_t i; } u = {x};
    float e = (float)(int)((u.i >> 23) & 255) - 127.0f;
    u.i = (u.i & 0x7FFFFFu) | 0x3F800000u;   /* mantissa in [1, 2) */
    float m = u.f;
    /* the polynomial is ln(m) on [1, 2) (max error ~1e-4); times 1 / ln 2 for log2 */
    return e + 1.44269504f * (-1.7417939f + (2.8212026f + (-1.4699568f + (0.44717955f - 0.056570851f * m) * m) * m) * m);
}
static inline float fast_exp2(float x)
{
    x = clampf(x, -126.0f, 126.0f);
    float fl = floorf(x), f = x - fl;
    float p = 1.0f + f * (0.69583355f + f * (0.22606716f + f * 0.078024521f));
    union { float f; uint32_t i; } u;
    u.i = (uint32_t)((int)fl + 127) << 23;
    return u.f * p;
}
static inline float lin_to_db(float x) { return 6.0205999f * fast_log2(x + 1e-9f); }
static inline float db_to_lin(float db) { return fast_exp2(db * 0.16609640f); }

/* ---------- filters (RBJ cookbook, transposed direct form II, as Shapey) ---------- */
struct Biquad {
    float b0 = 1, b1 = 0, b2 = 0, a1 = 0, a2 = 0;
    float zl1 = 0, zl2 = 0, zr1 = 0, zr2 = 0;
    inline void run(float &l, float &r)
    {
        float yl = b0 * l + zl1;
        zl1 = b1 * l - a1 * yl + zl2;
        zl2 = b2 * l - a2 * yl;
        float yr = b0 * r + zr1;
        zr1 = b1 * r - a1 * yr + zr2;
        zr2 = b2 * r - a2 * yr;
        l = yl; r = yr;
    }
};

enum { LP, HP, AP };
static void design(Biquad &f, int kind, float hz)
{
    const float q = 0.70710678f;                  /* Butterworth: two of them make a Linkwitz-Riley 4th order */
    float w = 2.0f * (float)M_PI * clampf(hz, 10.0f, 0.49f * SR) / SR;
    float cw = cosf(w), al = sinf(w) / (2.0f * q);
    float b0, b1, b2, a0 = 1 + al, a1 = -2 * cw, a2 = 1 - al;
    switch (kind) {
    case LP: b0 = (1 - cw) / 2; b1 = 1 - cw; b2 = b0; break;
    case HP: b0 = (1 + cw) / 2; b1 = -(1 + cw); b2 = b0; break;
    default: b0 = 1 - al; b1 = -2 * cw; b2 = 1 + al; break;   /* allpass: what LP^2 + HP^2 of the same corner add up to */
    }
    f.b0 = b0 / a0; f.b1 = b1 / a0; f.b2 = b2 / a0; f.a1 = a1 / a0; f.a2 = a2 / a0;
}

/* ---------- state ---------- */
struct Xover {
    float pos = 500;                           /* target (knob units, as set: may sit past a neighbour while dragged) */
    float lf = 0;                              /* gliding log2 Hz */
    bool settled = false;
    Biquad lp[2], hp[2];                       /* the split: LR4 low / high */
    Biquad ap[NX];                             /* this crossover's allpass, run on each band below it (ap[b] for band b) */
};

struct Band {
    /* targets */
    int on = 1, solo = 0;
    float in = 0.0f, rpos = 23, out = 0.0f;    /* INPUT dB, RATIO (knob units), OUTPUT dB */
    /* running */
    float in_g = 1, out_g = 1;                 /* gliding linear INPUT, OUTPUT gains */
    float y1 = 0, gr = 0;                      /* detector state (dB of gain reduction) */
    float mix = 1;                             /* 0 = band passes untouched (switched off), 1 = processed; fades */
    float audible = 1;                         /* 0 = muted by another band's solo; fades */
    float gr_peak = 0;                         /* the most reduction since the meter last looked */
    float gain_now = 1;                        /* the band's linear gain at the end of the last block (the live curve) */
};

struct Comp {
    Xover x[NX];
    Band b[NB];
    int speed = 1;
    float mixpct = 100.0f, mix_s = 1.0f;       /* target %, gliding 0..1 */
    float master = 0.0f, master_g = 1.0f;      /* target dB, gliding linear gain */
    int bypass = 0, theme = 0;
    float byp = 0;                             /* 0 = processed, 1 = dry */
    bool started = false;                      /* the first block takes fades at their targets (no fade-in on load) */
    /* the screen */
    int col[NCOL];
    float wcol[NCOL][NB];                      /* which band each column shows (1 for that band, 0 for the rest) */
    unsigned display_rev = 0;
    int curve_dirty = 1, curve_wait = 0;
    double last_step = -1.0;
    int theme_changed = 0;
    int sel = DEF_SEL, sel_changed = 0, pend_sel = -1;
    int xmark[NX];                             /* each crossover's line on the graph: its column + 1 */
    int grm[NB];                               /* each band's gain-reduction meter frame */
    int touch = 0, touch_hold = 0;
    int drag_x = -1;                           /* the crossover a finger on the graph is moving (-1: none) */
    int last_x = -1;                           /* the crossover last moved (it stops at its neighbours; they don't move) */
    int snap_wait[NX];                         /* blocks until a crossover's knob goes to where it plays */
    int x_changed[NX];                         /* crossovers the engine moved itself: report to the host */
    unsigned char col_touched[NCOL];
    unsigned noise = 1;
    /* analyzer */
    int analyzer = 0;
    float an_buf[FFT_N];
    float fre[FFT_N], fim[FFT_N];
    float win[FFT_N];                          /* the Hann window, made once */
    int an_pos = 0, an_wait = 0;
    float bar_db[NBAR];
    int bar[NBAR];
    int bar_age[NBAR];                         /* pictures a column has waited to move (fair turns under the budget) */
    int bshown[NB], bwait[NB];                 /* each band's gain bar as shown (curve step, -1 = not yet), and how long
                                                * a small change has waited */
};

/* where each crossover really sits: in order and at least XGAP apart, whatever order the knobs were set in. The one moved
 * last stops at its neighbours instead of pushing them */
static void x_effective(const Comp *p, float *e)
{
    for (int k = 0; k < NX; ++k) e[k] = clampf(p->x[k].pos, X_MIN + k * XGAP, X_MAX - (NX - 1 - k) * XGAP);
    int m = p->last_x;
    if (m >= 0) e[m] = clampf(e[m], m > 0 ? e[m - 1] + XGAP : X_MIN, m < NX - 1 ? e[m + 1] - XGAP : X_MAX);
    for (int k = 1; k < NX; ++k) if (e[k] < e[k - 1] + XGAP) e[k] = e[k - 1] + XGAP;
    for (int k = NX - 2; k >= 0; --k) if (e[k] > e[k + 1] - XGAP) e[k] = e[k + 1] - XGAP;
}

static void xover_design(Comp *p, int k)
{
    float hz = exp2f(p->x[k].lf);
    for (int s = 0; s < 2; ++s) { design(p->x[k].lp[s], LP, hz); design(p->x[k].hp[s], HP, hz); }
    for (int b = 0; b < NX; ++b) design(p->x[k].ap[b], AP, hz);
}

/* glide every crossover toward where it should be; redesign while moving, nothing once settled */
static void xover_glide(Comp *p, float k)
{
    float e[NX];
    bool any = false;
    for (int i = 0; i < NX; ++i) any |= !p->x[i].settled;
    if (!any) return;
    x_effective(p, e);
    for (int i = 0; i < NX; ++i) {
        Xover &x = p->x[i];
        float t = log2f(pos_to_hz(e[i]));
        if (x.settled && fabsf(t - x.lf) < 1e-5f) continue;
        x.lf += (t - x.lf) * k;
        x.settled = fabsf(t - x.lf) < 1e-4f;
        if (x.settled) x.lf = t;
        xover_design(p, i);
    }
}

/* which band each curve column shows: the one whose range (between its crossovers) holds the column's frequency. The
 * display is drawn per band, as a multiband compressor's usually is (Logic's Multipressor): one flat level across each
 * band, stepping at the crossovers, rather than the crossovers' smooth blend */
static void update_weights(Comp *p)
{
    float e[NX];
    x_effective(p, e);
    for (int c = 0; c < NCOL; ++c) {
        float pos = 1000.0f * (c + 0.5f) / NCOL;
        int band = 0;
        while (band < NX && pos >= e[band]) ++band;
        for (int b = 0; b < NB; ++b) p->wcol[c][b] = b == band ? 1.0f : 0.0f;
    }
}

/* the gain bars (each band's gain right now, flat across its columns) and the crossover lines; display_rev moves when
 * any of it changed. live: the ~10-a-second refresh while audio plays, under the screen budget; otherwise (an edit)
 * every column is redrawn exactly */
static int band_of_column(const Comp *p, int c)
{
    for (int b = 0; b < NB; ++b) if (p->wcol[c][b] > 0.5f) return b;
    return 0;
}

static void update_curve(Comp *p, bool live)
{
    bool moved = false;
    float mx = p->mixpct / 100.0f;
    bool any_solo = false;
    for (int b = 0; b < NB; ++b) any_solo |= p->b[b].solo != 0;
    int target[NB], ncols[NB] = {0};
    for (int b = 0; b < NB; ++b) {
        float au = !any_solo || p->b[b].solo ? 1.0f : 0.0f;
        float g = mx * p->b[b].gain_now + (1.0f - mx) * au;
        float db = p->bypass ? 0.0f : 20.0f * log10f(fmaxf(g, 1e-6f)) + p->master;
        target[b] = (int)lrintf((clampf(db, -CURVE_DB, CURVE_DB) + CURVE_DB) / (2 * CURVE_DB) * CURVE_STEPS);
    }
    for (int c = 0; c < NCOL; ++c) ++ncols[band_of_column(p, c)];
    bool redraw[NB];
    if (!live) {
        for (int b = 0; b < NB; ++b) { redraw[b] = true; p->bwait[b] = 0; }
    } else {
        /* the bands that need moving, biggest change first, while the column budget lasts (one band always may) */
        int want[NB], n = 0, used = 0;
        for (int b = 0; b < NB; ++b) {
            redraw[b] = false;
            int d = abs(target[b] - p->bshown[b]);
            if (d == 0) { p->bwait[b] = 0; continue; }
            if (p->bshown[b] < 0 || d >= GAIN_JUMP || ++p->bwait[b] >= GAIN_HOLD) want[n++] = b;
        }
        for (int i = 0; i < n; ++i)
            for (int j = i + 1; j < n; ++j)
                if (abs(target[want[j]] - p->bshown[want[j]]) > abs(target[want[i]] - p->bshown[want[i]])) {
                    int t = want[i]; want[i] = want[j]; want[j] = t;
                }
        for (int i = 0; i < n; ++i) {
            int b = want[i];
            if (used > 0 && used + ncols[b] > LIVE_COL_BUDGET) continue;   /* next picture */
            redraw[b] = true; used += ncols[b]; p->bwait[b] = 0;
        }
    }
    for (int b = 0; b < NB; ++b) if (redraw[b]) p->bshown[b] = target[b];
    for (int c = 0; c < NCOL; ++c) {
        int b = band_of_column(p, c);
        int v = p->bshown[b] < 0 ? target[b] : p->bshown[b];
        if (v != p->col[c]) { p->col[c] = v; moved = true; }
    }
    float e[NX];
    x_effective(p, e);
    for (int k = 0; k < NX; ++k) {
        int m = (int)(NCOL * clampf(e[k], 0, 999.9f) / 1000.0f) + 1;
        if (m != p->xmark[k]) { p->xmark[k] = m; moved = true; }
    }
    if (moved) ++p->display_rev;
}

/* gain-reduction meters: the most reduction since the last look, 1 dB a frame */
static void update_meters(Comp *p)
{
    bool moved = false;
    for (int b = 0; b < NB; ++b) {
        int v = p->bypass || !p->b[b].on ? 0 : (int)lrintf(clampf(p->b[b].gr_peak, 0, (float)GR_STEPS));
        p->b[b].gr_peak = 0.0f;
        if (v != p->grm[b]) { p->grm[b] = v; moved = true; }
    }
    if (moved) ++p->display_rev;
}

/* ---------- engine ---------- */

static void *create(const char *)
{
    Comp *p = new (std::nothrow) Comp();
    if (!p) return NULL;
    for (int k = 0; k < NX; ++k) {
        p->x[k].pos = lrintf(hz_to_pos(DEF_XHZ[k]));
        p->x[k].lf = log2f(pos_to_hz(p->x[k].pos));
        xover_design(p, k);
        p->x[k].settled = true;
        p->xmark[k] = -1;
        p->snap_wait[k] = p->x_changed[k] = 0;
    }
    for (int b = 0; b < NB; ++b) { p->b[b].rpos = lrintf(ratio_pos(2.0f)); p->grm[b] = -1; }
    for (int c = 0; c < NCOL; ++c) { p->col[c] = -1; p->col_touched[c] = 0; }
    for (int k = 0; k < NBAR; ++k) { p->bar_db[k] = BAR_FLOOR - 20; p->bar[k] = 0; p->bar_age[k] = 0; }
    for (int b = 0; b < NB; ++b) { p->bshown[b] = -1; p->bwait[b] = 0; }
    for (int i = 0; i < FFT_N; ++i) p->win[i] = 0.5f - 0.5f * cosf(2.0f * (float)M_PI * i / FFT_N);
    memset(p->an_buf, 0, sizeof p->an_buf);
    update_weights(p);
    update_curve(p, false);
    update_meters(p);
    return p;
}

static void destroy(void *inst) { delete static_cast<Comp *>(inst); }

static int band_key(const char *key, const char **field)
{
    if (key[0] != 'b' || key[1] < '1' || key[1] > '0' + NB || key[2] != '_') return -1;
    *field = key + 3;
    return key[1] - '1';
}

static int xover_key(const char *key)   /* "x1".."x4" */
{
    if (key[0] != 'x' || key[1] < '1' || key[1] > '0' + NX || key[2]) return -1;
    return key[1] - '1';
}

static void set_xover(Comp *p, int k, float pos)
{
    p->x[k].pos = clampf(pos, 0, 1000);
    p->x[k].settled = false;
    p->last_x = k;
    p->snap_wait[k] = SNAP_HOLD;
    p->curve_dirty = 1; p->curve_wait = 0;
}

/* the settings a project saves (the "state" text): a version line, then name=value lines. Display-only values (curve,
 * meters) are left out, so loading a project never replays them as touches. Unknown names are ignored and missing ones
 * keep their defaults, so later versions can add settings. */
static const char *STATE_HDR = "mbc2\n";
static const char *STATE_KEYS[] = {"bypass", "theme", "mix", "master", "speed", "analyzer", "sel", "x1", "x2", "x3", "x4",
    "b1_on", "b1_solo", "b1_in", "b1_ratio", "b1_out", "b2_on", "b2_solo", "b2_in", "b2_ratio", "b2_out",
    "b3_on", "b3_solo", "b3_in", "b3_ratio", "b3_out", "b4_on", "b4_solo", "b4_in", "b4_ratio", "b4_out",
    "b5_on", "b5_solo", "b5_in", "b5_ratio", "b5_out"};
static const int NSTATE = (int)(sizeof STATE_KEYS / sizeof STATE_KEYS[0]);

static void set_param(void *inst, const char *key, const char *val);
static int get_param(void *inst, const char *key, char *buf, int len);
static void load_state(Comp *p, const char *val)
{
    if (strncmp(val, STATE_HDR, strlen(STATE_HDR))) return;
    const char *s = val + strlen(STATE_HDR);
    while (*s) {
        const char *nl = strchr(s, '\n'), *eq = strchr(s, '=');
        size_t n = nl ? (size_t)(nl - s) : strlen(s);
        if (eq && eq < s + n && eq - s < 24 && n < 64) {
            char k[24], v[48];
            snprintf(k, sizeof k, "%.*s", (int)(eq - s), s);
            snprintf(v, sizeof v, "%.*s", (int)(s + n - eq - 1), eq + 1);
            for (int i = 0; i < NSTATE; ++i) if (!strcmp(k, STATE_KEYS[i])) { set_param(p, k, v); break; }
        }
        s += n;
        if (*s) ++s;
    }
    for (int k = 0; k < NX; ++k) p->snap_wait[k] = 1;      /* a saved order is used as it is */
    p->last_x = -1;
    p->pend_sel = -1;
    p->started = false;                                     /* no fades from the old settings */
    p->curve_dirty = 1;
}

static void set_param(void *inst, const char *key, const char *val)
{
    Comp *p = static_cast<Comp *>(inst);
    if (!p || !key || !val) return;
    if (!strcmp(key, "state")) { load_state(p, val); return; }
    float f = strtof(val, NULL);
    const char *fld;
    int i = band_key(key, &fld);
    if (i >= 0) {
        Band &b = p->b[i];
        if (!strcmp(fld, "on")) b.on = f > 0.5f;
        else if (!strcmp(fld, "solo")) b.solo = f > 0.5f;
        else if (!strcmp(fld, "in")) b.in = clampf(f, -24, 24);
        else if (!strcmp(fld, "ratio")) b.rpos = clampf(f, 0, 100);
        else if (!strcmp(fld, "out")) b.out = clampf(f, -24, 24);
        else return;
        p->curve_dirty = 1;
        /* touching a band's controls selects it; several bands at once is a preset: no */
        p->pend_sel = p->pend_sel == -1 || p->pend_sel == i ? i : -2;
        return;
    }
    int k = xover_key(key);
    if (k >= 0) {
        set_xover(p, k, f);
        p->pend_sel = p->pend_sel == -1 || p->pend_sel == k ? k : -2;   /* XOVER k sits in band k's column */
        return;
    }
    if (!strcmp(key, "mix")) { p->mixpct = clampf(f, 0, 100); p->curve_dirty = 1; }
    else if (!strcmp(key, "master")) { p->master = clampf(f, -24, 24); p->curve_dirty = 1; }
    else if (!strcmp(key, "speed")) p->speed = (int)clampf((float)lrintf(f), 0, 2);
    else if (!strcmp(key, "bypass")) { p->bypass = f > 0.5f; p->curve_dirty = 1; }
    else if (!strcmp(key, "theme")) p->theme = (int)clampf((float)lrintf(f), 0, 3);
    else if (!strcmp(key, "theme_prev") || !strcmp(key, "theme_next")) {
        /* one step per press, at most ~3 a second (a held press must not race through) */
        if (f < 0.5f) return;
        struct timespec ts;
        clock_gettime(CLOCK_MONOTONIC, &ts);
        double now = ts.tv_sec + ts.tv_nsec * 1e-9;
        if (p->last_step >= 0.0 && now - p->last_step < 0.3) return;
        p->last_step = now;
        p->theme = (p->theme + (key[6] == 'n' ? 1 : 3)) % 4;
        p->theme_changed = 1;
    }
    else if (!strcmp(key, "analyzer")) {
        if ((f > 0.5f) && !p->analyzer) memset(p->an_buf, 0, sizeof p->an_buf);
        p->analyzer = f > 0.5f;
        if (!p->analyzer) {
            bool moved = false;
            for (int j = 0; j < NBAR; ++j) { p->bar_db[j] = BAR_FLOOR - 20; if (p->bar[j]) { p->bar[j] = 0; moved = true; } }
            if (moved) ++p->display_rev;
        }
    }
    else if (!strcmp(key, "sel")) p->sel = (int)clampf((float)lrintf(f), 0, NB - 1);
    else if (!strncmp(key, "pick_", 5)) {          /* a tap on a band's column: select it */
        int b = atoi(key + 5) - 1;
        if (f > 0.5f && b >= 0 && b < NB && b != p->sel) { p->sel = b; p->sel_changed = 1; }
    }
    else if (key[0] == 'c' && key[1] >= '0' && key[1] <= '9') {
        /* a touch on the graph, column c: the nearest crossover line goes there (held for the whole drag, so passing
         * another line doesn't swap them); the band below it is selected */
        int c = atoi(key + 1);
        if (c < 0 || c >= NCOL) return;
        float pos = 1000.0f * (c + 0.5f) / NCOL;
        if (p->drag_x < 0) {
            float e[NX], best = 1e9f;
            x_effective(p, e);
            for (int j = 0; j < NX; ++j) if (fabsf(e[j] - pos) < best) { best = fabsf(e[j] - pos); p->drag_x = j; }
        }
        set_xover(p, p->drag_x, pos);
        p->x_changed[p->drag_x] = 1;                                /* its knob follows the finger */
        if (p->drag_x != p->sel) { p->sel = p->drag_x; p->sel_changed = 1; }
        p->col_touched[c] = 1;                                      /* the host moved its copy of the column: put it back */
        if (p->touch != c + 1) { p->touch = c + 1; ++p->display_rev; }
        p->touch_hold = TOUCH_HOLD;
    }
}

static int fmt_hz(char *buf, int len, float hz)
{
    if (hz >= 10000.0f) return snprintf(buf, (size_t)len, "%.1f kHz", hz / 1000.0f);
    if (hz >= 1000.0f) return snprintf(buf, (size_t)len, "%.2f kHz", hz / 1000.0f);
    return snprintf(buf, (size_t)len, "%d Hz", (int)lrintf(hz));
}

static int get_param(void *inst, const char *key, char *buf, int len)
{
    Comp *p = static_cast<Comp *>(inst);
    if (!p || !key || !buf || len <= 0) return 0;
    if (!strcmp(key, "state")) {
        int n = snprintf(buf, (size_t)len, "%s", STATE_HDR);
        for (int i = 0; i < NSTATE && n < len; ++i) {
            char v[32];
            if (get_param(p, STATE_KEYS[i], v, sizeof v) > 0) n += snprintf(buf + n, (size_t)(len - n), "%s=%s\n", STATE_KEYS[i], v);
        }
        return n < len ? n : 0;
    }
    if (!strcmp(key, "display_rev")) return snprintf(buf, (size_t)len, "%u", p->display_rev);
    if (!strcmp(key, "latency")) return snprintf(buf, (size_t)len, "0");
    if (key[0] == 'c' && key[1] >= '0' && key[1] <= '9') {
        int c = atoi(key + 1);
        if (c < 0 || c >= NCOL) return 0;
        /* a third of a step over the frame: lands on it whether MPC rounds or truncates */
        return snprintf(buf, (size_t)len, "%d.3", p->col[c] < 0 ? CURVE_STEPS / 2 : p->col[c]);
    }
    const char *fld;
    int i = band_key(key, &fld);
    if (i >= 0) {
        const Band &b = p->b[i];
        if (!strcmp(fld, "on")) return snprintf(buf, (size_t)len, "%d", b.on);
        if (!strcmp(fld, "solo")) return snprintf(buf, (size_t)len, "%d", b.solo);
        if (!strcmp(fld, "in")) return snprintf(buf, (size_t)len, "%g", b.in);
        if (!strcmp(fld, "ratio")) return snprintf(buf, (size_t)len, "%g", b.rpos);
        if (!strcmp(fld, "out")) return snprintf(buf, (size_t)len, "%g", b.out);
        if (!strcmp(fld, "in_display")) return snprintf(buf, (size_t)len, "%+.1f dB", b.in);
        if (!strcmp(fld, "out_display")) return snprintf(buf, (size_t)len, "%+.1f dB", b.out);
        if (!strcmp(fld, "ratio_display")) {
            float r = ratio_of(b.rpos);
            return snprintf(buf, (size_t)len, r < 9.95f ? "%.1f:1" : "%.0f:1", r);
        }
        return 0;
    }
    int k = xover_key(key);
    if (k >= 0) return snprintf(buf, (size_t)len, "%g", p->x[k].pos);
    if (key[0] == 'x' && key[1] >= '1' && key[1] <= '0' + NX && !strcmp(key + 2, "_display")) {
        float e[NX];
        x_effective(p, e);
        return fmt_hz(buf, len, pos_to_hz(e[key[1] - '1']));   /* where it plays */
    }
    if (!strcmp(key, "mix")) return snprintf(buf, (size_t)len, "%g", p->mixpct);
    if (!strcmp(key, "mix_display")) return snprintf(buf, (size_t)len, "%d%%", (int)lrintf(p->mixpct));
    if (!strcmp(key, "master")) return snprintf(buf, (size_t)len, "%g", p->master);
    if (!strcmp(key, "master_display")) return snprintf(buf, (size_t)len, "%+.1f dB", p->master);
    if (!strcmp(key, "speed")) return snprintf(buf, (size_t)len, "%d", p->speed);
    if (!strcmp(key, "speed_display")) return snprintf(buf, (size_t)len, "%s", SPEED_NAMES[p->speed]);
    if (!strcmp(key, "bypass")) return snprintf(buf, (size_t)len, "%d", p->bypass);
    if (!strcmp(key, "theme")) return snprintf(buf, (size_t)len, "%d", p->theme);
    if (!strcmp(key, "sel")) return snprintf(buf, (size_t)len, "%d", p->sel);
    if (!strcmp(key, "touch")) return snprintf(buf, (size_t)len, "%d", p->touch);
    if (!strncmp(key, "xm_", 3)) {
        int j = atoi(key + 3) - 1;
        return j >= 0 && j < NX ? snprintf(buf, (size_t)len, "%d", p->xmark[j] < 0 ? 0 : p->xmark[j]) : 0;
    }
    if (key[0] == 'g' && key[1] >= '1' && key[1] <= '0' + NB && !key[2])
        return snprintf(buf, (size_t)len, "%d.3", p->grm[key[1] - '1'] < 0 ? 0 : p->grm[key[1] - '1']);
    if (!strcmp(key, "analyzer")) return snprintf(buf, (size_t)len, "%d", p->analyzer);
    if (key[0] == 'a' && key[1] >= '0' && key[1] <= '9') {
        int j = atoi(key + 1);
        if (j < 0 || j >= NBAR) return 0;
        return snprintf(buf, (size_t)len, "%d.3", p->bar[j]);
    }
    return 0;
}

/* what the engine changed itself, so the screen follows: theme (arrows), the selected band, a crossover the graph moved
 * (or that snapped back to where it plays), and graph columns a touch moved on the host's side (put back) */
extern "C" int mpc_engine_changed(void *inst, char *key, int len)
{
    Comp *p = static_cast<Comp *>(inst);
    if (!p) return 0;
    if (p->theme_changed) { p->theme_changed = 0; snprintf(key, (size_t)len, "theme"); return 1; }
    if (p->sel_changed) { p->sel_changed = 0; snprintf(key, (size_t)len, "sel"); return 1; }
    for (int k = 0; k < NX; ++k)
        if (p->x_changed[k]) { p->x_changed[k] = 0; snprintf(key, (size_t)len, "x%d", k + 1); return 1; }
    if (p->curve_dirty) return 0;
    for (int c = 0; c < NCOL; ++c)
        if (p->col_touched[c]) { p->col_touched[c] = 0; snprintf(key, (size_t)len, "c%d", c); return 1; }
    return 0;
}

static void midi(void *, const uint8_t *, int) {}

static void render(void *, int16_t *out_lr, int frames)
{
    if (out_lr && frames > 0) memset(out_lr, 0, (size_t)frames * 2 * sizeof(int16_t));
}

static inline int16_t to_s16(float x)
{
    x *= 32768.0f;
    return x >= 32767.0f ? 32767 : (x <= -32768.0f ? -32768 : (int16_t)lrintf(x));
}

/* in-place radix-2 FFT (Shapey's) */
static void fft(float *re, float *im, int n)
{
    for (int i = 1, j = 0; i < n; ++i) {
        int bit = n >> 1;
        for (; j & bit; bit >>= 1) j ^= bit;
        j ^= bit;
        if (i < j) { float t = re[i]; re[i] = re[j]; re[j] = t; t = im[i]; im[i] = im[j]; im[j] = t; }
    }
    for (int len = 2; len <= n; len <<= 1) {
        float a = -2.0f * (float)M_PI / len, wr = cosf(a), wi = sinf(a);
        for (int i = 0; i < n; i += len) {
            float cr = 1.0f, ci = 0.0f;
            for (int j = 0; j < len / 2; ++j) {
                float ur = re[i + j], ui = im[i + j];
                float vr = re[i + j + len / 2] * cr - im[i + j + len / 2] * ci;
                float vi = re[i + j + len / 2] * ci + im[i + j + len / 2] * cr;
                re[i + j] = ur + vr; im[i + j] = ui + vi;
                re[i + j + len / 2] = ur - vr; im[i + j + len / 2] = ui - vi;
                float t = cr * wr - ci * wi; ci = cr * wi + ci * wr; cr = t;
            }
        }
    }
}

/* the analyzer: the last FFT_N samples -> NBAR log-spaced columns. A column narrower than two FFT bins reads the power
 * interpolated at its own centre frequency (so the low columns differ, instead of several sharing one bin), a wider one
 * the energy across its range: a tone reads at its level, pink noise reads level. Tilted by AN_TILT dB an octave around 1 kHz. Rises BAR_RISE of the way a picture, falls
 * BAR_FALL dB a picture. Then only AN_BUDGET columns move, by how far they are off times how long they have waited,
 * so every column gets its turn (rising and falling alike) */
static void update_analyzer(Comp *p)
{
    float *re = p->fre, *im = p->fim;
    for (int i = 0; i < FFT_N; ++i) {
        re[i] = p->an_buf[(p->an_pos + i) & (FFT_N - 1)] * p->win[i];
        im[i] = 0.0f;
    }
    fft(re, im, FFT_N);
    for (int i = 0; i <= FFT_N / 2; ++i) re[i] = re[i] * re[i] + im[i] * im[i];   /* power, in place */
    /* a sine of amplitude A puts 3 N^2 A^2 / 32 of power into the positive bins (Hann, Parseval): read it as A^2 */
    const float binhz = SR / FFT_N, norm = 32.0f / (3.0f * (float)FFT_N * (float)FFT_N);
    int target[NBAR], prio[NBAR], order[NBAR], n = 0;
    for (int k = 0; k < NBAR; ++k) {
        float f0 = F_LO * powf(F_HI / F_LO, (float)k / NBAR), f1 = F_LO * powf(F_HI / F_LO, (float)(k + 1) / NBAR);
        float x0 = f0 / binhz, x1 = f1 / binhz, pw = 0.0f;
        if (x1 - x0 < 2.0f) {
            /* narrower than two bins: the power per bin interpolated at the column's centre, times its width in bins */
            float x = sqrtf(x0 * x1);
            int i0 = (int)x;
            float fr = x - i0;
            pw = (re[i0] + (re[i0 + 1] - re[i0]) * fr) * fmaxf(x1 - x0, 1.0f);
        } else {
            /* the energy in [f0, f1): whole bins inside, and the share of the two at its edges */
            int b0 = (int)x0, b1 = (int)x1;
            if (b1 > FFT_N / 2) b1 = FFT_N / 2;
            for (int b = b0; b <= b1; ++b) {
                float lo = fmaxf(x0, (float)b - 0.5f), hi = fminf(x1, (float)b + 0.5f);
                if (hi > lo) pw += re[b] * (hi - lo);
            }
        }
        float db = 10.0f * log10f(pw * norm + 1e-20f) + AN_TILT * log2f(sqrtf(f0 * f1) / 1000.0f);
        if (p->bar_db[k] < BAR_FLOOR - 10) p->bar_db[k] = BAR_FLOOR - 10;
        p->bar_db[k] = db > p->bar_db[k] ? p->bar_db[k] + (db - p->bar_db[k]) * BAR_RISE : fmaxf(db, p->bar_db[k] - BAR_FALL);
        target[k] = (int)lrintf(clampf((p->bar_db[k] - BAR_FLOOR) / (BAR_TOP - BAR_FLOOR) * BAR_STEPS, 0, BAR_STEPS));
        int d = target[k] - p->bar[k];
        if (d) { prio[k] = abs(d) * (1 + p->bar_age[k]); order[n++] = k; }   /* the longer it waited, the sooner */
        else p->bar_age[k] = 0;
    }
    for (int i = 1; i < n; ++i) {                     /* biggest moves first (insertion sort: n <= 72) */
        int k = order[i], j = i - 1;
        while (j >= 0 && prio[order[j]] < prio[k]) { order[j + 1] = order[j]; --j; }
        order[j + 1] = k;
    }
    for (int i = 0; i < n; ++i) {
        int k = order[i];
        if (i < AN_BUDGET) { p->bar[k] = target[k]; p->bar_age[k] = 0; }
        else ++p->bar_age[k];
    }
    if (n) ++p->display_rev;
}

/* a one-pole coefficient for a time constant in ms */
static inline float coef(float ms) { return expf(-1000.0f / (fmaxf(ms, 0.01f) * SR)); }

static inline float step(float v, float t, float d) { return v == t ? t : (fabsf(t - v) <= d ? t : v + (t > v ? d : -d)); }

static void process(void *inst, const int16_t *in_lr, int16_t *out_lr, int frames)
{
    Comp *p = static_cast<Comp *>(inst);
    if (!p || !in_lr || !out_lr || frames <= 0) return;

    /* ---- the screen (block rate) ---- */
    if (p->pend_sel >= 0 && p->pend_sel != p->sel) { p->sel = p->pend_sel; p->sel_changed = 1; }
    p->pend_sel = -1;
    if (p->touch_hold > 0 && --p->touch_hold == 0) {
        p->drag_x = -1;                                   /* the finger is off the graph */
        if (p->touch) { p->touch = 0; ++p->display_rev; }
    }
    /* a crossover pushed against its neighbour plays where it may; once it has rested, its knob goes there too */
    {
        float e[NX];
        x_effective(p, e);
        for (int k = 0; k < NX; ++k)
            if (p->snap_wait[k] > 0 && --p->snap_wait[k] == 0 && fabsf(e[k] - p->x[k].pos) > 0.5f) {
                p->x[k].pos = e[k]; p->x_changed[k] = 1; p->curve_dirty = 1;
            }
    }
    if (p->curve_wait > 0) --p->curve_wait;
    if (p->curve_dirty && p->curve_wait == 0) { p->curve_dirty = 0; p->curve_wait = 3; update_weights(p); update_curve(p, false); }
    if (++p->an_wait >= AN_BLOCKS) {
        p->an_wait = 0;
        if (p->analyzer) update_analyzer(p);
        update_meters(p);
        update_curve(p, true);                            /* the live gain bars follow the compression */
    }

    /* ---- per-block settings ---- */
    const int SUB = 8;                                    /* crossovers follow their glide every 8 samples */
    const float kg = 1.0f - expf(-(float)SUB / (0.02f * SR));   /* ~20 ms glide */
    const float fade = (float)SUB / (0.01f * SR);         /* 10 ms fades */
    const float mg = powf(10.0f, p->master / 20.0f);
    const float mixt = p->mixpct / 100.0f;
    const float byp_t = p->bypass ? 1.0f : 0.0f;
    bool any_solo = false;
    for (int b = 0; b < NB; ++b) any_solo |= p->b[b].solo != 0;
    float slope[NB], aA[NB], aR[NB], ig[NB], og[NB];
    for (int b = 0; b < NB; ++b) {
        Band &d = p->b[b];
        slope[b] = 1.0f / ratio_of(d.rpos) - 1.0f;        /* gain-computer slope above the threshold (0 .. -0.95) */
        aA[b] = coef(SPEED_ATT[p->speed] * BAND_TIME[b]);
        aR[b] = coef(SPEED_REL[p->speed] * BAND_TIME[b]);
        ig[b] = powf(10.0f, d.in / 20.0f);
        og[b] = powf(10.0f, d.out / 20.0f);
    }
    if (!p->started) {                                    /* first block (or after a project load): no fades in */
        p->started = true;
        for (int b = 0; b < NB; ++b) {
            Band &d = p->b[b];
            d.mix = d.on ? 1.0f : 0.0f; d.audible = !any_solo || d.solo ? 1.0f : 0.0f;
            d.in_g = ig[b]; d.out_g = og[b];
        }
        p->mix_s = mixt; p->master_g = mg; p->byp = byp_t;
        for (int k = 0; k < NX; ++k) {                    /* crossovers start where they belong */
            float e[NX];
            x_effective(p, e);
            p->x[k].lf = log2f(pos_to_hz(e[k]));
            xover_design(p, k);
            p->x[k].settled = true;
        }
    }

    for (int i0 = 0; i0 < frames; i0 += SUB) {
        int n = frames - i0 < SUB ? frames - i0 : SUB;
        xover_glide(p, kg);
        float mix0[NB], aud0[NB], in0[NB], out0[NB];
        for (int b = 0; b < NB; ++b) {
            Band &d = p->b[b];
            mix0[b] = d.mix; aud0[b] = d.audible; in0[b] = d.in_g; out0[b] = d.out_g;
            d.mix = step(d.mix, d.on ? 1.0f : 0.0f, fade);
            d.audible = step(d.audible, !any_solo || d.solo ? 1.0f : 0.0f, fade);
            d.in_g += (ig[b] - d.in_g) * kg; if (fabsf(d.in_g - ig[b]) < 1e-6f) d.in_g = ig[b];
            d.out_g += (og[b] - d.out_g) * kg; if (fabsf(d.out_g - og[b]) < 1e-6f) d.out_g = og[b];
        }
        float m0 = p->mix_s, m1 = step(m0, mixt, fade);
        p->mix_s = m1;
        float g0 = p->master_g, g1 = g0 + (mg - g0) * kg;
        p->master_g = fabsf(g1 - mg) < 1e-6f ? mg : g1;
        float b0 = p->byp, b1v = step(b0, byp_t, fade);
        p->byp = b1v;

        for (int j = 0; j < n; ++j) {
            int idx = 2 * (i0 + j);
            float dl = in_lr[idx] / 32768.0f, dr = in_lr[idx + 1] / 32768.0f;
            float t = (float)(j + 1) / n;
            p->noise = p->noise * 1664525u + 1013904223u;
            float tiny = ((int)(p->noise >> 9) - (1 << 22)) * 1e-28f;   /* keeps the filters out of denormals */

            /* split: bl/br[k] = band k */
            float bl[NB], br[NB];
            float hl = dl + tiny, hr = dr + tiny;
            for (int k = 0; k < NX; ++k) {
                Xover &x = p->x[k];
                float ll = hl, lr = hr;
                x.lp[0].run(ll, lr); x.lp[1].run(ll, lr);
                x.hp[0].run(hl, hr); x.hp[1].run(hl, hr);
                bl[k] = ll; br[k] = lr;
            }
            bl[NB - 1] = hl; br[NB - 1] = hr;
            /* the lower bands get the higher crossovers' allpasses, so everything adds back in phase */
            for (int b = 0; b < NX - 1; ++b)
                for (int k = b + 1; k < NX; ++k) p->x[k].ap[b].run(bl[b], br[b]);

            float wl = 0, wr = 0, sl = 0, sr = 0;           /* processed sum, plain sum (the mix's dry side) */
            for (int b = 0; b < NB; ++b) {
                Band &d = p->b[b];
                float gi = in0[b] + (d.in_g - in0[b]) * t;
                float lv = lin_to_db(fmaxf(fabsf(bl[b]), fabsf(br[b])) * gi);
                /* gain computer: dB of reduction at this level (soft knee around the threshold) */
                float over = lv - THRESH_DB, gt;
                if (2.0f * over <= -KNEE_DB) gt = 0.0f;
                else if (2.0f * over < KNEE_DB) { float q = over + KNEE_DB * 0.5f; gt = -slope[b] * q * q / (2.0f * KNEE_DB); }
                else gt = -slope[b] * over;
                /* smooth decoupled peak detector in the log domain: release, then attack */
                d.y1 = fmaxf(gt, aR[b] * d.y1 + (1.0f - aR[b]) * gt);
                d.gr = aA[b] * d.gr + (1.0f - aA[b]) * d.y1;
                if (d.gr > d.gr_peak) d.gr_peak = d.gr;
                float m = mix0[b] + (d.mix - mix0[b]) * t, au = aud0[b] + (d.audible - aud0[b]) * t;
                float go = out0[b] + (d.out_g - out0[b]) * t;
                float g = gi * go * db_to_lin(-d.gr);
                g = (1.0f + (g - 1.0f) * m) * au;           /* a switched-off band passes untouched; solo mutes the rest */
                if (j == n - 1) d.gain_now = g;
                wl += bl[b] * g; wr += br[b] * g;
                sl += bl[b] * au; sr += br[b] * au;
            }
            float mx = m0 + (m1 - m0) * t;
            float l = sl + (wl - sl) * mx, r = sr + (wr - sr) * mx;
            float gg = g0 + (p->master_g - g0) * t, by = b0 + (b1v - b0) * t;
            l *= gg; r *= gg;
            if (by >= 1.0f) { l = dl; r = dr; }
            else if (by > 0.0f) { l += (dl - l) * by; r += (dr - r) * by; }
            out_lr[idx] = to_s16(l);
            out_lr[idx + 1] = to_s16(r);
            if (p->analyzer) { p->an_buf[p->an_pos] = 0.5f * (l + r); p->an_pos = (p->an_pos + 1) & (FFT_N - 1); }
        }
    }
}

static const mpc_engine_t engine = {create, destroy, midi, set_param, get_param, render, process, NULL};

extern "C" const mpc_engine_t *mpc_engine(void) { return &engine; }
