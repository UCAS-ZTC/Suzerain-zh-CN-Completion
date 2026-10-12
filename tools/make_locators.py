"""Maintainer tool: derive the two small locator files the builder ships from the whole-game scans.

    data/maplab/tex_locator.json         where each map texture lives (which bundle, which object)
    data/stage2_tutorial_bundles.json    which bundles carry the war-tutorial strings

A player's build never scans the whole game (that takes minutes and ~40 MB of cache): build.py checks that the game is exactly the
build these files were made from, and the generators read them instead.  After a game update, regenerate them:

    python tools/tex_inventory.py     -> <work>/cache/tex_inventory.json   (every texture of every bundle)
    python tools/census_all.py        -> <work>/cache/bundle_census.json   (object types per bundle)
    python tools/scan_groups.py       -> <work>/cache/scan_groups.jsonl    (string leaves per bundle)
    python tools/make_locators.py     -> rewrites the two files           (--check: compare only, change nothing)

then rebuild, and regenerate the expected hashes with tools/make_expected.py.
"""
import argparse, json, os, sys

from lib_su import CACHE, DATA, MAPLAB_DIR
import map_cfg


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, indent=0).encode("utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="only compare the result with the shipped files")
    a = ap.parse_args()

    names = list(map_cfg.ALL)
    with open(os.path.join(CACHE, "tex_inventory.json"), encoding="utf-8") as f:
        rows = json.load(f)
    want = set(names)
    loc = [r for r in rows if r["t"] == "Texture2D" and r["n"] in want]
    missing = [n for n in names if n not in {r["n"] for r in loc}]
    if missing:
        sys.exit("textures of map_cfg.ALL that are not in the inventory: %s" % missing)
    loc.sort(key=lambda r: (r["n"], r["f"], r["pid"]))

    bundles = set()
    with open(os.path.join(CACHE, "scan_groups.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            if any(k.startswith("tutorialData") for k, _ in r.get("strs", [])):
                bundles.add(r["bundle"])
    print("map textures: %d names, %d locator rows; war-tutorial bundles: %d" % (len(names), len(loc), len(bundles)))

    outs = [(os.path.join(MAPLAB_DIR, "tex_locator.json"), dumps(loc)),
            (os.path.join(DATA, "stage2_tutorial_bundles.json"), dumps(sorted(bundles)))]
    bad = 0
    for path, blob in outs:
        have = open(path, "rb").read() if os.path.isfile(path) else None
        same = have == blob
        print("  %-60s %s" % (os.path.relpath(path, os.path.dirname(DATA)), "identical" if same else "DIFFERENT"))
        bad += 0 if same else 1
        if not a.check and not same:
            with open(path, "wb") as f:
                f.write(blob)
            print("    rewritten")
    sys.exit(1 if (a.check and bad) else 0)


if __name__ == "__main__":
    main()
