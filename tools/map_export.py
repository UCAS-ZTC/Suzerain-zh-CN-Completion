"""Read-only: export map textures (pristine game) to work\\cache\\map\\<name>.png (+ 1024px preview jpg).

usage: python map_export.py NAME [NAME ...]      (NAME as in tex_inventory.json; first matching bundle is used)
       python map_export.py --all-big            (every >=2048px map-like texture, see map_cfg.MAP_NAMES)
"""
import sys
import json
import time
import numpy as np
from PIL import Image
from lib_su import *

MAPDIR = os.path.join(CACHE, "map")
os.makedirs(os.path.join(MAPDIR, "prev"), exist_ok=True)


def inv_rows():
    return json.load(open(os.path.join(CACHE, "tex_inventory.json"), encoding="utf-8"))


def find_rows(name, rows=None):
    rows = rows or inv_rows()
    return [r for r in rows if r["t"] == "Texture2D" and r["n"] == name]


def export(name, prefer=None):
    rr = find_rows(name)
    if prefer:
        rr = [r for r in rr if prefer in r["f"]] or rr
    r = rr[0]
    src = os.path.join(GAME, "Suzerain_Data", "data.unity3d") if r["f"] == "data.unity3d" else os.path.join(AA_GAME, r["f"])
    env = load_env(src)
    for o in env.objects:
        if o.type.name == "Texture2D" and o.path_id == r["pid"]:
            tex = o.read()
            img = tex.image  # PIL RGBA, top-down
            p = os.path.join(MAPDIR, name + ".png")
            img.save(p)
            prev = img.convert("RGB")
            prev.thumbnail((1024, 1024), Image.LANCZOS)
            prev.save(os.path.join(MAPDIR, "prev", name + ".jpg"), quality=88)
            return r, tex, img
    raise KeyError(name)


if __name__ == "__main__":
    t0 = time.time()
    for n in sys.argv[1:]:
        r, tex, img = export(n)
        print(n, img.size, img.mode, "fmt", tex.m_TextureFormat, "mips", tex.m_MipCount, "stream", tex.m_StreamData.path, tex.m_StreamData.size,
              "| bundle", r["f"][:70], "| %.1fs" % (time.time() - t0))
