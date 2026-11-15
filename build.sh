#!/usr/bin/env bash
# Build Multi-Band Compressor: skin, both MPC binaries, and the MPC OS 3.10.1 plugin folder (zip) for every MPC.
#
#   ./build.sh [version]          e.g. ./build.sh 1.0.5   (default: the VERSION file; it is also drawn in the skin's header)
#
# Needs (no Docker):
#   MV   a checkout of github.com/3dthc/mpc-vst-plugins at the commit in TOOLCHAIN_REF (default: ../mpc-vst-plugins)
#   python3 with Pillow and Playwright (Chromium) for the skin, and ziglang (pip install ziglang) or zig on PATH
#   SDK  optional: a checkout of Akai's mpc-plugin-builder-sdk, to run its validator on the result
#
# Output: dist/Multi-Band-Compressor-<version>-mpc.zip holding just one folder, "Cmackg - VST - Multi-Band Compressor",
# with plugin.json (file32 + file64), both .so files, Plugin Skins/, version.xml and INSTALL.md. Copy that folder itself
# into "VST2 Plugins" (VST2 Plugins/Cmackg - VST - Multi-Band Compressor/plugin.json).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
VERSION="${1:-$(cat "$HERE/VERSION")}"
MV="${MV:-$HERE/../mpc-vst-plugins}"
TOOLCHAIN_REF=860807012d78a1b997863fae618f72d0da5945d1     # the mpc-vst-plugins commit Shapey EQ releases with
PY="${PYTHON:-python3}"
[ -f "$MV/wrapper/vst2_wrap.c" ] || { echo "MV=$MV is not an mpc-vst-plugins checkout" >&2; exit 1; }
if [ "$(git -C "$MV" rev-parse HEAD 2>/dev/null)" != "$TOOLCHAIN_REF" ]; then
  echo "note: $MV is not at $TOOLCHAIN_REF (the tested toolchain commit)" >&2
fi
if command -v zig >/dev/null; then ZIG=(zig); else ZIG=("$PY" -m ziglang); fi
SO=multi_band_compressor.so
SKIN="mbc/build/skin/Cmackg - VST - Multi-Band Compressor"
cd "$HERE"

echo "== skin artwork (the version in the header: $VERSION)"
MBC_VERSION="$VERSION" "$PY" tools/make_skin_art.py

echo "== skin and params.h"
"$PY" "$MV/tools/gen_vst.py" mbc/vst.json

echo "== wrapper, patched (patches/: settings the host sets are never reported back as automation)"
cp "$MV/wrapper/vst2_wrap.c" mbc/build/vst2_wrap.c
for p in patches/*.patch; do patch -s --no-backup-if-mismatch mbc/build/vst2_wrap.c "$p"; echo "applied $p"; done

echo "== binaries (zig: glibc 2.31 floor, C++ runtime linked in)"
for T in arm32 arm64; do
  case $T in
    arm32) TGT=(-target arm-linux-gnueabihf.2.31 -mcpu=cortex_a17); OUT=mbc/build ;;
    arm64) TGT=(-target aarch64-linux-gnu.2.31 -mcpu=cortex_a55); OUT=mbc/build/aarch64 ;;
  esac
  mkdir -p "$OUT/obj"
  "${ZIG[@]}" c++ "${TGT[@]}" -O2 -fPIC -fvisibility=hidden -std=gnu++11 -Wall -Wextra -Wno-unused-parameter \
      -Imbc/build -I"$MV/wrapper" -c src/engine.cpp -o "$OUT/obj/engine.o"
  "${ZIG[@]}" cc "${TGT[@]}" -O2 -fPIC -fvisibility=hidden -std=gnu11 -Wno-unused-parameter \
      -Imbc/build -I"$MV/wrapper" -c mbc/build/vst2_wrap.c -o "$OUT/obj/vst2_wrap.o"
  "${ZIG[@]}" c++ "${TGT[@]}" -shared -fPIC -s "$OUT/obj/engine.o" "$OUT/obj/vst2_wrap.o" -lm -lpthread -ldl \
      -Wl,--no-undefined -o "$OUT/$SO"
  echo "$T: $(readelf -h "$OUT/$SO" | awk -F: '/Machine/{gsub(/^ +/,"",$2);print $2}'), highest glibc" \
       "$(readelf -V "$OUT/$SO" | grep -o 'GLIBC_[0-9.]*' | sort -uV | tail -1), needs:" \
       "$(readelf -d "$OUT/$SO" | grep NEEDED | grep -o '\[.*\]' | tr '\n' ' ')"
done

echo "== package"
REL="$(mktemp -d)"
trap 'rm -rf "$REL"' EXIT
ABOUT="A 5-band compressor: drag the crossovers, set each band's input, ratio and output. Built on Shapey 5-Band EQ."
"$PY" "$MV/tools/release.py" --so mbc/build/$SO --skin "$SKIN" --entry mbc/build/pluginlist-entry.xml --version "$VERSION" \
      --id multi-band-compressor --license MIT --about "$ABOUT" -o "$REL/a" | tail -1
"$PY" "$MV/tools/release.py" --so mbc/build/aarch64/$SO --skin "$SKIN" --entry mbc/build/pluginlist-entry.xml --version "$VERSION" \
      --id multi-band-compressor --license MIT --about "$ABOUT" -o "$REL/b" | tail -1
"$PY" "$MV/tools/sdk_zip.py" "$REL/sdk.zip" "$REL"/a/*.zip "$REL"/b/*.zip
# version.xml: add the scripted-UI version the skins need, as Akai's SDK writes it (0.1.0.0, never higher)
mkdir -p "$REL/x" && (cd "$REL/x" && unzip -q ../sdk.zip)
DIR="$(ls -d "$REL"/x/*/)"
"$PY" - "$DIR/version.xml" <<'EOF'
import sys
p = sys.argv[1]
s = open(p).read()
if "<uiversion>" not in s:
    s = s.replace("</version>", "</version>\n\t<uiversion>0.1.0.0</uiversion>", 1)
open(p, "w").write(s)
EOF
mkdir -p dist
ZIP="$HERE/dist/Multi-Band-Compressor-$VERSION-mpc.zip"
rm -f "$ZIP"
# ONE top-level item: the plugin folder (install notes inside it). With anything else beside it, macOS and Windows
# unzip into an extra wrapper folder, and copying that into "VST2 Plugins" leaves the plugin one level too deep to be found
cp INSTALL.md "$DIR/INSTALL.md"
(cd "$REL/x" && zip -qr -X "$ZIP" "$(basename "$DIR")")
echo "$ZIP"

if [ -n "${SDK:-}" ] && [ -f "$SDK/tools/validate.py" ]; then
  echo "== Akai SDK validator"
  "$PY" "$SDK/tools/validate.py" "$DIR" | tail -2
fi
