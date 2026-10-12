"""Read-only: export every texture of map_cfg.ALL (pristine game) to cache\\map\\NAME.png (skips existing).
Groups by bundle so each bundle is parsed once."""
import sys
import json
import time
from collections import defaultdict
from PIL import Image
from lib_su import *
import map_cfg

MAPDIR = os.path.join(CACHE, "map")
os.makedirs(os.path.join(MAPDIR, "prev"), exist_ok=True)
names = sys.argv[1:] or map_cfg.ALL
rows = json.load(open(os.path.join(MAPLAB_DIR, "tex_locator.json"), encoding="utf-8"))
todo = defaultdict(dict)
missing = []
for n in names:
    if os.path.exists(os.path.join(MAPDIR, n + ".png")):
        continue
    rr = [r for r in rows if r["t"] == "Texture2D" and r["n"] == n]
    if not rr:
        missing.append(n)
        continue
    r = rr[0]
    todo[r["f"]][r["pid"]] = n
t0 = time.time()
for f, d in todo.items():
    src = os.path.join(GAME, "Suzerain_Data", "data.unity3d") if f == "data.unity3d" else os.path.join(AA_GAME, f)
    env = load_env(src)
    for o in env.objects:
        if o.type.name == "Texture2D" and o.path_id in d:
            n = d[o.path_id]
            tex = o.read()
            img = tex.image
            img.save(os.path.join(MAPDIR, n + ".png"))
            pv = img.convert("RGB")
            pv.thumbnail((1024, 1024), Image.LANCZOS)
            pv.save(os.path.join(MAPDIR, "prev", n + ".jpg"), quality=88)
            print("%-34s %s fmt=%s mips=%s  [%.0fs]" % (n, img.size, tex.m_TextureFormat, tex.m_MipCount, time.time() - t0), flush=True)
print("missing:", missing)
