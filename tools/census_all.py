"""Type census of every bundle in the game (and nothing else). Output: cache/bundle_census.json"""
import os, sys, json, time, re
from collections import Counter
from multiprocessing import Pool
import UnityPy

from lib_su import AA_GAME as GAME, CACHE   # SUZERAIN_GAME / SUZERAIN_WORK (see lib_su)


def lp(p):
    p = os.path.abspath(p)
    return p if p.startswith("\\\\?\\") else "\\\\?\\" + p


def census(name):
    path = os.path.join(GAME, name)
    t0 = time.time()
    try:
        env = UnityPy.load(lp(path))
        c = Counter()
        sz = Counter()
        for obj in env.objects:
            c[obj.type.name] += 1
            sz[obj.type.name] += obj.byte_size
        return name, {"types": dict(c), "bytes": dict(sz), "t": round(time.time() - t0, 2)}
    except Exception as ex:
        return name, {"error": f"{type(ex).__name__}: {ex}"}


if __name__ == "__main__":
    with os.scandir(lp(GAME)) as it:
        names = sorted(e.name for e in it if e.name.endswith(".bundle"))
    print("bundles:", len(names), flush=True)
    t0 = time.time()
    res = {}
    with Pool(8) as pool:
        for i, (name, r) in enumerate(pool.imap_unordered(census, names, chunksize=4)):
            res[name] = r
            if (i + 1) % 200 == 0:
                print(f"  {i+1}/{len(names)} done, {time.time()-t0:.0f}s", flush=True)
    json.dump(res, open(os.path.join(CACHE, "bundle_census.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print("done in %.0fs" % (time.time() - t0))
    errs = {k: v for k, v in res.items() if "error" in v}
    print("errors:", len(errs))
    for k, v in list(errs.items())[:10]:
        print("  ", k[:90], v["error"][:150])
