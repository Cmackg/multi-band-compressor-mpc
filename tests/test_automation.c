/* Automation check: the plugin, loaded as the MPC loads it, must not report back the settings the host set.
 *
 *   tests/test_automation <native plugin .so>        (built with mbc/build/params.h, as test.sh does)
 *
 * MPC records a plugin's audioMasterAutomate as a change the user made: on a playing track it lands in the track's
 * automation and repeats on every loop. So, while loud audio keeps the meters moving:
 *   - turning knobs and switches (host setParameter), loading a project (effSetChunk) and MPC's own nudge of parameter 0
 *     must report nothing for any setting;
 *   - the display values (curve, meters, analyzer) must keep being reported (that is how the screen moves), and must
 *     answer "no" to effCanBeAutomated so they can't be recorded and replayed into the engine;
 *   - a crossover dragged on the graph is the engine moving a setting itself: it is reported, so its knob follows;
 *   - the screen stays within its budget of reports a second (each one is a repaint on MPC's screen thread).
 * Prints PASS / FAIL lines and exits 1 on any failure. */
#include <dlfcn.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "params.h"

#define NP ((int)(sizeof PARAMS / sizeof PARAMS[0]))

typedef struct AEffect AEffect;
typedef intptr_t (*audioMasterCallback)(AEffect *, int32_t, int32_t, intptr_t, void *, float);
struct AEffect {                                  /* the VST 2.4 binary layout (as wrapper/vst2_wrap.c declares it) */
    int32_t magic;
    intptr_t (*dispatcher)(AEffect *, int32_t, int32_t, intptr_t, void *, float);
    void (*process)(AEffect *, float **, float **, int32_t);
    void (*setParameter)(AEffect *, int32_t, float);
    float (*getParameter)(AEffect *, int32_t);
    int32_t numPrograms, numParams, numInputs, numOutputs, flags;
    intptr_t resvd1, resvd2;
    int32_t initialDelay, realQualities, offQualities;
    float ioRatio;
    void *object, *user;
    int32_t uniqueID, version;
    void (*processReplacing)(AEffect *, float **, float **, int32_t);
    void (*processDoubleReplacing)(AEffect *, double **, double **, int32_t);
    char future[56];
};
enum { effOpen = 0, effClose = 1, effSetSampleRate = 10, effSetBlockSize = 11, effMainsChanged = 12, effGetChunk = 23,
       effSetChunk = 24, effCanBeAutomated = 26 };

static int automated[NP];                          /* audioMasterAutomate calls per parameter (any thread) */
static int failures;

static intptr_t host(AEffect *e, int32_t op, int32_t idx, intptr_t v, void *p, float opt)
{
    (void)e; (void)v; (void)p; (void)opt;
    if (op == 0 && idx >= 0 && idx < NP) __atomic_add_fetch(&automated[idx], 1, __ATOMIC_RELAXED);
    if (op == 1) return 2400;                      /* audioMasterVersion */
    return 0;
}

static int index_of(const char *key)
{
    for (int i = 0; i < NP; i++) if (!strcmp(PARAMS[i].key, key)) return i;
    fprintf(stderr, "no parameter %s\n", key);
    exit(2);
}

static int display_only(int i)
{
    for (int k = 0; k < PLUG_HOST_HIDDEN_COUNT; k++) if (PLUG_HOST_HIDDEN[k] == i) return 1;
    return 0;
}

static float norm(const char *key, float plain)
{
    const param_t *p = &PARAMS[index_of(key)];
    return (plain - p->min) / (p->max - p->min);
}

static void check(const char *what, int ok, const char *detail)
{
    printf("%-72s %s  %s\n", what, ok ? "PASS" : "FAIL", detail);
    if (!ok) failures++;
}

static unsigned rng = 12345;
static void play(AEffect *e, double seconds)
{
    static float l[128], r[128];
    float *io[2] = {l, r};
    for (int b = 0; b < (int)(seconds * 44100 / 128); b++) {
        for (int i = 0; i < 128; i++) {
            rng = rng * 1664525u + 1013904223u;
            l[i] = r[i] = 0.5f * ((float)(rng >> 8) / 16777216.0f - 0.5f);   /* loud noise: every band compresses */
        }
        e->processReplacing(e, io, io, 128);                                 /* in place, as MPC does */
        struct timespec ts = {0, 2902494};                                   /* real time: the wrapper's reporter */
        nanosleep(&ts, NULL);                                                /* thread runs every 100 ms of it */
    }
}

/* the settings (not display-only) reported since the counters were cleared: a list for the message, and how many */
static int reported_settings(char *list, size_t len)
{
    int n = 0;
    list[0] = 0;
    for (int i = 0; i < NP; i++)
        if (!display_only(i) && automated[i]) {
            n++;
            size_t used = strlen(list);
            if (used + 32 < len) snprintf(list + used, len - used, "%s%s x%d", n > 1 ? ", " : "", PARAMS[i].key, automated[i]);
        }
    return n;
}

static int reported_display(void)
{
    int n = 0;
    for (int i = 0; i < NP; i++) if (display_only(i)) n += automated[i];
    return n;
}

int main(int argc, char **argv)
{
    if (argc < 2) { fprintf(stderr, "usage: %s plugin.so\n", argv[0]); return 2; }
    void *lib = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (!lib) { fprintf(stderr, "%s\n", dlerror()); return 2; }
    AEffect *(*entry)(audioMasterCallback) = (AEffect *(*)(audioMasterCallback))dlsym(lib, "VSTPluginMain");
    if (!entry) { fprintf(stderr, "no VSTPluginMain\n"); return 2; }
    AEffect *e = entry(host);
    if (!e || e->numParams != NP) { fprintf(stderr, "plugin and params.h disagree (%d vs %d)\n", e ? e->numParams : -1, NP); return 2; }
    e->dispatcher(e, effSetSampleRate, 0, 0, NULL, 44100.0f);
    e->dispatcher(e, effSetBlockSize, 0, 128, NULL, 0.0f);
    e->dispatcher(e, effOpen, 0, 0, NULL, 0.0f);
    e->dispatcher(e, effMainsChanged, 0, 1, NULL, 0.0f);
    char msg[512];

    /* effCanBeAutomated: every setting yes, every display value no */
    int bad_set = 0, bad_disp = 0;
    for (int i = 0; i < NP; i++) {
        int can = (int)e->dispatcher(e, effCanBeAutomated, i, 0, NULL, 0.0f);
        if (display_only(i) && can) bad_disp++;
        if (!display_only(i) && !can && !PARAMS[i].momentary) bad_set++;
    }
    snprintf(msg, sizeof msg, "%d settings not automatable, %d display values automatable", bad_set, bad_disp);
    check("automation lanes: settings can be automated, display values can't", !bad_set && !bad_disp, msg);

    /* drive every band hard, let the screen run */
    for (int b = 1; b <= 5; b++) {
        char k[16];
        snprintf(k, sizeof k, "b%d_in", b); e->setParameter(e, index_of(k), norm(k, 18));
        snprintf(k, sizeof k, "b%d_ratio", b); e->setParameter(e, index_of(k), 1.0f);
    }
    e->setParameter(e, index_of("analyzer"), 1.0f);
    play(e, 1.0);

    /* 1. the user turns knobs and flips switches while it plays */
    memset(automated, 0, sizeof automated);
    const char *keys[] = {"b3_in", "b2_ratio", "b4_out", "x2", "speed", "master", "b1_on", "b5_solo", "analyzer"};
    const float vals[] = {0.3f, 0.5f, 0.7f, 0.42f, 1.0f, 0.4f, 0.0f, 1.0f, 0.0f};
    for (int s = 0; s < 3; s++)
        for (int k = 0; k < (int)(sizeof keys / sizeof keys[0]); k++) {
            e->setParameter(e, index_of(keys[k]), vals[k] + 0.05f * s);
            play(e, 0.15);
        }
    e->setParameter(e, index_of("analyzer"), 1.0f);
    e->setParameter(e, index_of("b5_solo"), 0.0f);
    play(e, 0.5);
    int n = reported_settings(msg, sizeof msg);
    check("knob and switch changes are not reported back (not recorded)", n == 0, n ? msg : "none reported");
    snprintf(msg, sizeof msg, "%d reports", reported_display());
    check("the screen still moves: display values reported", reported_display() > 50, msg);

    /* the screen budget: every report costs MPC's screen thread a repaint, and a screen that falls behind looks frozen.
     * Loud, busy audio with the analyzer on, 5 s in real time (before the budget: ~960 reports a second) */
    e->setParameter(e, index_of("analyzer"), 1.0f);
    play(e, 0.5);
    memset(automated, 0, sizeof automated);
    play(e, 5.0);
    snprintf(msg, sizeof msg, "%.0f reports a second (analyzer, gain bars, meters)", reported_display() / 5.0);
    check("screen budget: at most 450 display reports a second", reported_display() / 5.0 <= 450, msg);

    /* 2. MPC's nudge of parameter 0 (MIX) at prepare, and a project load */
    memset(automated, 0, sizeof automated);
    e->setParameter(e, 0, 1.0f); e->setParameter(e, 0, 0.0f); e->setParameter(e, 0, 1.0f);
    play(e, 0.3);
    void *chunk = NULL;
    intptr_t len = e->dispatcher(e, effGetChunk, 0, 0, &chunk, 0.0f);
    static char saved[16384];
    if (len > 0 && len < (intptr_t)sizeof saved) memcpy(saved, chunk, (size_t)len);
    e->setParameter(e, index_of("b3_in"), 0.9f);
    e->setParameter(e, index_of("x3"), 0.8f);
    play(e, 0.3);
    memset(automated, 0, sizeof automated);
    e->dispatcher(e, effSetChunk, 0, len, saved, 0.0f);
    play(e, 1.0);
    n = reported_settings(msg, sizeof msg);
    check("a project load (effSetChunk) reports no settings", len > 0 && n == 0, n ? msg : "none reported");

    /* 3. a crossover dragged on the graph: the engine moves XOVER itself, so it is reported (its knob follows) */
    memset(automated, 0, sizeof automated);
    char ck[8];
    snprintf(ck, sizeof ck, "c%d", 50);
    e->setParameter(e, index_of(ck), 0.5f);
    play(e, 0.5);
    int x_rep = automated[index_of("x1")] + automated[index_of("x2")] + automated[index_of("x3")] + automated[index_of("x4")];
    snprintf(msg, sizeof msg, "x1..x4 reported %d time(s)", x_rep);
    check("a crossover dragged on the graph is reported, so its knob follows", x_rep > 0, msg);

    e->dispatcher(e, effMainsChanged, 0, 0, NULL, 0.0f);
    e->dispatcher(e, effClose, 0, 0, NULL, 0.0f);
    printf("\n%d failure(s)\n", failures);
    return failures ? 1 : 0;
}
