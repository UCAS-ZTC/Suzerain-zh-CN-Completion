"""Read-only inventory of Texture2D / Sprite assets in the (pristine) game: all Addressables bundles + data.unity3d.
usage: python tex_inventory.py   -> cache\\tex_inventory.json  (+ progress in cache\\tex_inventory.log)
"""
import os
import sys
import glob
import json
import time
import collections
import UnityPy
from lib_su import *

LOGP = os.path.join(CACHE, "tex_inventory.log")
log = open(LOGP, "w", encoding="utf-8")


def L(s):
    log.write(s + "\n")
    log.flush()


files = sorted(glob.glob(os.path.join(AA_GAME, "*.bundle")))
files.append(os.path.join(GAME, "Suzerain_Data", "data.unity3d"))
rows = []
t0 = time.time()
for i, p in enumerate(files):
    base = os.path.basename(p)
    n_before = len(rows)
    try:
        env = UnityPy.load(p)
        for obj in env.objects:
            t = obj.type.name
            if t not in ("Texture2D", "Sprite"):
                continue
            try:
                d = obj.read()
                name = getattr(d, "m_Name", "") or ""
                if t == "Texture2D":
                    w, h, fmt = int(d.m_Width), int(d.m_Height), str(d.m_TextureFormat)
                else:
                    r = d.m_Rect
                    w, h, fmt = int(r.width), int(r.height), "sprite"
                rows.append(dict(f=base, pid=obj.path_id, t=t, n=name, w=w, h=h, fmt=fmt))
            except Exception as e:
                rows.append(dict(f=base, pid=obj.path_id, t=t, n="<err %s>" % e, w=0, h=0, fmt="?"))
    except Exception as e:
        L(f"ERR load {base}: {e}")
    L(f"[{i + 1}/{len(files)} {time.time() - t0:.0f}s] {base[:90]} +{len(rows) - n_before}")

with open(os.path.join(CACHE, "tex_inventory.json"), "w", encoding="utf-8") as f:
    json.dump(rows, f, ensure_ascii=False)
c = collections.Counter((r["t"]) for r in rows)
L(f"DONE rows={len(rows)} {dict(c)} in {time.time() - t0:.0f}s")
print("done", len(rows), dict(c))
