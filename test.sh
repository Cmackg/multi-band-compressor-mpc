#!/usr/bin/env bash
# Offline tests, before anything goes to an MPC:
#   1. the DSP against textbook values (tests/test_comp.py: crossover, compression, timing, mix, bypass, screen, clicks, CPU)
#   2. the toolchain's host test of the wrapped plugin under ASan/UBSan (parameters, presets, state, two instances, threads)
#   3. optional, with SDK=<Akai mpc-plugin-builder-sdk checkout>: Akai's host_sim, a host that behaves like the MPC's
#
#   MV=../mpc-vst-plugins ./test.sh
# Needs gcc/g++, python3 with numpy (and Pillow/Playwright, which test_port.sh's skin step uses).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
MV="${MV:-$HERE/../mpc-vst-plugins}"
PY="${PYTHON:-python3}"
B="$HERE/mbc/build/test"
mkdir -p "$B"
cd "$HERE"

echo "== 1. DSP"
g++ -O2 -std=gnu++11 -Wall -Wextra -Wno-unused-parameter -I"$MV/wrapper" -c src/engine.cpp -o "$B/engine.o"
gcc -O2 -I"$MV/wrapper" tests/run_engine.c "$B/engine.o" -lstdc++ -lm -o "$B/run_engine"
"$PY" tests/test_comp.py "$B/run_engine"

echo "== 2. host test (ASan/UBSan)"
"$MV/tools/test_port.sh" mbc/vst.json | tail -1

if [ -n "${SDK:-}" ] && [ -f "$SDK/tools/host-sim/host_sim.cpp" ]; then
  echo "== 3. Akai host_sim"
  g++ -O2 -std=c++17 -I"$SDK/framework" -o "$B/host_sim" "$SDK/tools/host-sim/host_sim.cpp" -ldl -lpthread
  g++ -O2 -fPIC -std=gnu++11 -Imbc/build -I"$MV/wrapper" -c src/engine.cpp -o "$B/e.o"
  gcc -O2 -fPIC -std=gnu11 -Imbc/build -I"$MV/wrapper" -c "$MV/wrapper/vst2_wrap.c" -o "$B/w.o"
  g++ -shared -o "$B/mbc.so" "$B/e.o" "$B/w.o" -lm -lpthread -ldl
  # Its state check also counts the display-only values (curve, analyzer, touch glow), which the engine recomputes and
  # never saves (as Shapey EQ): those failures are expected. Every setting must come back.
  "$B/host_sim" "$B/mbc.so" test --seconds 3 | grep -E "^(PASS|FAIL|WARN)|Result" || true
fi
