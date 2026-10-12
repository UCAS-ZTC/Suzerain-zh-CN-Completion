import os, json, pickle
import UnityPy

BASE = r"StreamingAssets\aa\StandaloneWindows64\defaultlocalgroup_assets_assets_database_entitytextassets.asset_ec95223fa5819b4eb4d612c0ee4914b6.bundle"
from lib_su import GAME, OLD_PACK, CACHE, load_env
ORIG = os.path.join(GAME, "Suzerain_Data") + "\\" + BASE
PATCHED = os.path.join(OLD_PACK, "Suzerain_Data") + "\\" + BASE
OUT = open(os.path.join(CACHE, "ent_mb_probe.txt"), "w", encoding="utf-8")


def P(*a):
    print(*a, file=OUT)


def lp(p):
    p = os.path.abspath(p)
    return p if p.startswith("\\\\?\\") else "\\\\?\\" + p


def get_mb(path):
    env = load_env(path)
    for obj in env.objects:
        if obj.type.name == "MonoBehaviour":
            return obj.read_typetree()


o = get_mb(ORIG)
p = get_mb(PATCHED)
pickle.dump({"orig": o, "patched": p}, open(os.path.join(CACHE, "ent_mb.pkl"), "wb"), protocol=4)


def describe(x, depth=0, key="root", maxd=3):
    pad = "  " * depth
    if isinstance(x, dict):
        P(f"{pad}{key}: dict[{len(x)}]")
        if depth < maxd:
            for k, v in list(x.items())[:60]:
                describe(v, depth + 1, k, maxd)
    elif isinstance(x, list):
        P(f"{pad}{key}: list[{len(x)}]")
        if x and depth < maxd:
            describe(x[0], depth + 1, key + "[0]", maxd)
    else:
        s = repr(x)
        P(f"{pad}{key}: {type(x).__name__} {s[:160]}")


describe(o)
OUT.close()
