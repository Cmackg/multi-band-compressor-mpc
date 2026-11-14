#!/usr/bin/env python3
"""Multi-Band Compressor skin touch-up, run by gen_vst.py after the skin is built (vst.json "skin_post"):

    python3 skin_post.py "<skin dir>"

The SPEED field's text gets bigger (FIELD_TEXT) and the field's full width (the builder keeps 44 px for a list arrow this
field doesn't draw). As Shapey EQ's skin_post.py. Fails if the field is not found, so a builder change can't silently undo it.
"""
import json
import os
import sys

skin = sys.argv[1]
path = os.path.join(skin, "Plugin Skins", "TUI.json") if os.path.isdir(os.path.join(skin, "Plugin Skins")) else os.path.join(skin, "TUI.json")
tui = json.load(open(path))
FIELD_TEXT = 24.0   # MPC font height
fields = 0


def walk(o):
    global fields
    if isinstance(o, dict):
        if str(o.get("key", "")).startswith("shPopField"):
            for c in o.get("value", {}).get("componentsData", []):
                cd = c.get("componentData", {})
                if cd.get("type") == "Label" and cd.get("data", {}).get("type") == "Value":
                    cd["data"]["textStyle"]["font"]["height"] = FIELD_TEXT
                    b = c["bounds"] if "bounds" in c else None
                    if b and isinstance(b.get("bounds"), str):
                        x, y, w, h = (int(v) for v in b["bounds"].split())
                        b["bounds"] = "%d %d %d %d" % (2, y, w + 40, h)
                    fields += 1
        for v in o.values():
            walk(v)
    elif isinstance(o, list):
        for v in o:
            walk(v)


walk(tui)
if not fields:
    raise SystemExit("skin_post.py: no SPEED field found (did the skin builder change?)")
json.dump(tui, open(path, "w"), indent=1)
print("skin_post.py: %d field(s) resized" % fields)
