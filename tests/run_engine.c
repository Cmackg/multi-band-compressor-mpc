/* Offline harness: tests/run_engine in.f32 out.s16 [key=value | @block:key=value ...]
 * in.f32: mono float32 at 44.1 kHz (fed as stereo), or stereo when the env STEREO=1 (interleaved L R).
 * Writes interleaved int16 stereo. Prints, one line each: the latency; the 72 curve columns (0..60); the 72 analyzer
 * columns (0..24); the 5 gain-reduction meter frames; the 4 crossover knob values; the dashed crossover lines' columns;
 * then the saved state round trip ("state ok" when a second instance loaded from it saves the same text). */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "engine.h"

static void apply(const mpc_engine_t *e, void *inst, const char *arg)
{
    char k[64]; const char *eq = strchr(arg, '=');
    if (!eq) return;
    snprintf(k, sizeof k, "%.*s", (int)(eq - arg), arg);
    e->set_param(inst, k, eq + 1);
}

static int geti(const mpc_engine_t *e, void *inst, const char *key)
{
    char v[32];
    return e->get_param(inst, key, v, sizeof v) > 0 ? atoi(v) : -999;
}

int main(int argc, char **argv)
{
    if (argc < 3) { fprintf(stderr, "usage: %s in.f32 out.s16 [key=value ...]\n", argv[0]); return 2; }
    FILE *fi = fopen(argv[1], "rb"), *fo = fopen(argv[2], "wb");
    if (!fi || !fo) { perror("open"); return 1; }
    int stereo = getenv("STEREO") && atoi(getenv("STEREO"));
    const mpc_engine_t *e = mpc_engine();
    void *inst = e->create(NULL);
    for (int a = 3; a < argc; ++a) if (argv[a][0] != '@') apply(e, inst, argv[a]);
    float buf[256]; int16_t in[256], out[256]; size_t n;
    int ch = stereo ? 2 : 1;
    for (long blk = 0; (n = fread(buf, sizeof(float) * ch, 128, fi)) > 0; ++blk) {
        for (int a = 3; a < argc; ++a)
            if (argv[a][0] == '@' && atol(argv[a] + 1) == blk) apply(e, inst, strchr(argv[a], ':') + 1);
        for (size_t i = 0; i < 128; ++i)
            for (int c = 0; c < 2; ++c) {
                float v = i < n ? buf[i * ch + (stereo ? c : 0)] : 0.0f;
                int s = (int)(v * 32767.0f); if (s > 32767) s = 32767; if (s < -32768) s = -32768;
                in[2 * i + c] = (int16_t)s;
            }
        e->process(inst, in, out, 128);
        fwrite(out, sizeof(int16_t), 256, fo);
    }
    char v[32], key[16];
    e->get_param(inst, "latency", v, sizeof v);
    printf("%s\n", v);
    for (int c = 0; c < 72; ++c) { snprintf(key, sizeof key, "c%d", c); printf("%d ", geti(e, inst, key)); }
    printf("\n");
    for (int k = 0; k < 72; ++k) { snprintf(key, sizeof key, "a%d", k); printf("%d ", geti(e, inst, key)); }
    printf("\n");
    for (int b = 1; b <= 5; ++b) { snprintf(key, sizeof key, "g%d", b); printf("%d ", geti(e, inst, key)); }
    printf("\n");
    for (int k = 1; k <= 4; ++k) { snprintf(key, sizeof key, "x%d", k); e->get_param(inst, key, v, sizeof v); printf("%s ", v); }
    printf("\n");
    for (int k = 1; k <= 4; ++k) { snprintf(key, sizeof key, "xm_%d", k); printf("%d ", geti(e, inst, key)); }
    printf("\n");
    /* state round trip */
    static char s1[8192], s2[8192];
    int n1 = e->get_param(inst, "state", s1, sizeof s1);
    void *other = e->create(NULL);
    e->set_param(other, "state", s1);
    int n2 = e->get_param(other, "state", s2, sizeof s2);
    printf("%s\n", n1 > 0 && n1 == n2 && !memcmp(s1, s2, (size_t)n1) ? "state ok" : "state DIFFERS");
    if (getenv("PRINT_STATE")) fputs(s1, stderr);
    e->destroy(other);
    e->destroy(inst);
    fclose(fi); fclose(fo);
    return 0;
}
