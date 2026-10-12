"""Scan MonoBehaviours / TextAssets in all non-scene, non-database bundles and dump latin-bearing strings with field paths."""
import os, sys, json, re, time
from collections import Counter, defaultdict
from multiprocessing import Pool
import UnityPy

from lib_su import AA_GAME as GAME, CACHE
LAT = re.compile(r"[A-Za-z]{2,}")


def lp(p):
    p = os.path.abspath(p)
    return p if p.startswith("\\\\?\\") else "\\\\?\\" + p


def group(name):
    m = re.match(r"^(.*?)_assets_", name)
    return m.group(1) if m else name.split("_")[0]


def walk(x, path=()):
    if isinstance(x, dict):
        for k, v in x.items():
            yield from walk(v, path + (str(k),))
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from walk(v, path + (i,))
    elif isinstance(x, str):
        yield path, x


def scan(name):
    rows = []
    try:
        env = UnityPy.load(lp(os.path.join(GAME, name)))
        for obj in env.objects:
            tn = obj.type.name
            if tn == "TextAsset":
                d = obj.read()
                raw = d.m_Script
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", "replace")
                rows.append({"bundle": name, "kind": "TextAsset", "pid": obj.path_id, "name": d.m_Name, "text": raw})
            elif tn == "MonoBehaviour":
                try:
                    tt = obj.read_typetree()
                except Exception as ex:
                    rows.append({"bundle": name, "kind": "MB_FAIL", "pid": obj.path_id, "err": str(ex)[:100]})
                    continue
                strs = []
                for path, s in walk(tt):
                    if path and path[0] in ("m_GameObject", "m_Script", "m_EditorClassIdentifier"):
                        continue
                    if s and LAT.search(s):
                        strs.append(["/".join(map(str, path)), s])
                if strs:
                    rows.append({"bundle": name, "kind": "MB", "pid": obj.path_id, "name": tt.get("m_Name"), "keys": list(tt.keys())[:20], "strs": strs})
    except Exception as ex:
        rows.append({"bundle": name, "kind": "ERR", "err": f"{type(ex).__name__}: {ex}"})
    return rows


SKIP_GROUPS = {"database", "scenes_scenes"}
if __name__ == "__main__":
    census = json.load(open(os.path.join(CACHE, "bundle_census.json"), encoding="utf-8"))
    names = [n for n, r in census.items()
             if group(n) not in SKIP_GROUPS and (r["types"].get("MonoBehaviour") or r["types"].get("TextAsset"))]
    print("bundles to scan:", len(names), flush=True)
    t0 = time.time()
    out = open(os.path.join(CACHE, "scan_groups.jsonl"), "w", encoding="utf-8")
    with Pool(6) as pool:
        for i, rows in enumerate(pool.imap_unordered(scan, names, chunksize=2)):
            for r in rows:
                out.write(json.dumps(r, ensure_ascii=False) + "\n")
            if (i + 1) % 100 == 0:
                print(f"  {i+1}/{len(names)} {time.time()-t0:.0f}s", flush=True)
    out.close()
    print("done %.0fs" % (time.time() - t0))
