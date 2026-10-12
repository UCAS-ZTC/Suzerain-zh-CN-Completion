"""Regenerate data/expected_*.json  (maintainer tool - players never need to run this).

build.py checks everything against these three files:

  expected_outputs.json  SHA-256 of every payload file (Suzerain_Data/**) of the six packs, taken from packs that were
                         tested on a real game.  A rebuild must reproduce them byte for byte.
  expected_inputs.json   for every game file the packs replace: the pristine SHA-256, plus the hashes of the patched
                         versions (so build.py can tell "wrong game version" from "a patch is already installed").
  expected_base.json     the files of the base patch (the old stable pack the main pack is built on) and where it is
                         downloaded from.

usage:
  python tools/make_expected.py --packs <folder that holds the six tested Suzerain_CN_Plus_* pack folders>
                                --base <unpacked base patch folder> --base-zip <the base patch zip>
                                [--font <the font the tested packs were built with>]

--font defaults to assets/fonts/NotoSerifSC-VF.ttf (the maintainer's local copy; the font is a Release asset, not in git).
Its SHA-256 must equal font.sha256 in data/font_source.json - the script refuses to write otherwise.
"""
import argparse, hashlib, json, os, sys, platform
from importlib import metadata

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, "data")

BASE_RELEASE = {
    "title": "Suzerain-CN-Stable-SteamWin (original author: Tieba user 虾饺面z; GitHub mirror: SweeneyJun)",
    "repo": "https://github.com/SweeneyJun/Suzerain-CN-Stable-SteamWin",
    "tag": "v2026.06.09-3.1.0.1.175",
    "url": "https://github.com/SweeneyJun/Suzerain-CN-Stable-SteamWin/releases/download/v2026.06.09-3.1.0.1.175/Suzerain_CN_Stable_SteamWin_2026-06-10.zip",
    "zip_name": "Suzerain_CN_Stable_SteamWin_2026-06-10.zip",
    "top_folder": "Suzerain_CN_Stable_SteamWin_2026-06-10",
}


def lp(p):
    p = os.path.abspath(p)
    return p if p.startswith("\\\\?\\") else "\\\\?\\" + p


def sha256_file(p):
    h = hashlib.sha256()
    with open(lp(p), "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def tree(root, sub=None):
    """{relative path with '/': {size, sha256}} for every file under root (or root/sub)."""
    top = os.path.join(root, sub) if sub else root
    out = {}
    for dp, _dn, fn in os.walk(lp(top)):
        for n in fn:
            full = os.path.join(dp, n)
            rel = os.path.relpath(full, lp(root)).replace("\\", "/")
            out[rel] = {"size": os.path.getsize(full), "sha256": sha256_file(full)}
    return dict(sorted(out.items()))


def dump(name, obj):
    path = os.path.join(DATA, name)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, sort_keys=False)
        f.write("\n")
    print("wrote", path, os.path.getsize(path), "bytes")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--packs", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--base-zip", required=True)
    ap.add_argument("--font", default=os.path.join(REPO, "assets", "fonts", "NotoSerifSC-VF.ttf"))
    a = ap.parse_args()

    packs = sorted(d for d in os.listdir(a.packs)
                   if d.startswith("Suzerain_CN_Plus_") and os.path.isfile(os.path.join(a.packs, d, "patch_manifest.json")))
    print("packs:", *packs, sep="\n  ")

    # ---- outputs ----
    outputs, manifests = {}, {}
    for p in packs:
        outputs[p] = tree(os.path.join(a.packs, p), "Suzerain_Data")
        with open(os.path.join(a.packs, p, "patch_manifest.json"), encoding="utf-8-sig") as f:
            manifests[p] = json.load(f)
        print("  %-52s %4d payload files" % (p, len(outputs[p])))
    # the manifest must describe exactly the payload on disk
    for p in packs:
        for f in manifests[p]["files"]:
            rel = f["relative_path"].replace("\\", "/")
            assert rel in outputs[p], (p, rel)
            assert outputs[p][rel]["sha256"].lower() == f["patched_sha256"].lower(), (p, rel)
            assert outputs[p][rel]["size"] == f["size"], (p, rel)
        assert len(manifests[p]["files"]) == len(outputs[p]), p

    ident = manifests[packs[0]]
    versions = {}
    for pk in ["UnityPy", "Pillow", "numpy", "scipy", "etcpak", "texture2ddecoder", "lz4", "brotli"]:
        try:
            versions[pk] = metadata.version(pk)
        except metadata.PackageNotFoundError:
            versions[pk] = None
    if not os.path.isfile(a.font):
        sys.exit("font not found: %s  (pass --font <the font the tested packs were built with>)" % a.font)
    font_sha = sha256_file(a.font)
    with open(os.path.join(DATA, "font_source.json"), encoding="utf-8") as f:
        pinned = json.load(f)["font"]["sha256"]
    if font_sha != pinned:
        sys.exit("font SHA-256 %s != font.sha256 in data/font_source.json (%s): fix one of them before writing the manifests"
                 % (font_sha, pinned))
    dump("expected_outputs.json", {
        "_comment": "SHA-256 of every payload file of the six packs, from packs tested on a real game. build.py verify compares against this.",
        "tested_with": {"python": platform.python_version(), "packages": versions,
                        "font_sha256": font_sha},
        "game": {"steam_appid": ident["steam_appid"], "steam_buildid": ident["steam_buildid"],
                 "catalog_hash": ident["catalog_hash"], "build_guid": ident["build_guid"]},
        "packs": outputs,
    })

    # ---- base pack ----
    base_files = tree(a.base)
    dump("expected_base.json", {
        "_comment": "The base patch (old stable pack) the main pack is built on. build.py fetch downloads release.url and checks release.sha256; "
                    "the extracted files are always checked against 'files'.",
        "release": dict(BASE_RELEASE, size=os.path.getsize(a.base_zip), sha256=sha256_file(a.base_zip)),
        "files": base_files,
    })

    # ---- inputs ----
    orig, patched = {}, {}
    for p in packs:
        for f in manifests[p]["files"]:
            rel = f["relative_path"].replace("\\", "/")
            orig.setdefault(rel, set()).add(f["original_sha256"].lower())
            ps = patched.setdefault(rel, set())
            ps.add(f["patched_sha256"].lower())
            also = f.get("also_accept_sha256") or []
            for h in ([also] if isinstance(also, str) else also):
                ps.add(h.lower())
    inputs = {}
    for rel in sorted(orig):
        pristine = orig[rel] - patched[rel]          # an original that is another pack's output is a *stacked* input
        assert len(pristine) == 1, (rel, orig[rel], patched[rel])
        pr = next(iter(pristine))
        pat = set(patched[rel])
        if rel in base_files:
            pat.add(base_files[rel]["sha256"])
        pat.discard(pr)
        inputs[rel] = {"original": pr, "patched": sorted(pat)}
    dump("expected_inputs.json", {
        "_comment": "Game 3.1.0 Build 175 (Steam). Per replaced game file: pristine SHA-256 and the hashes of known patched versions.",
        "game": expected_game(ident),
        "files": inputs,
    })
    print("inputs: %d game files; payload files: %d; base files: %d" % (
        len(inputs), sum(len(v) for v in outputs.values()), len(base_files)))


def expected_game(ident):
    return {"steam_appid": ident["steam_appid"], "steam_buildid": ident["steam_buildid"],
            "catalog_hash": ident["catalog_hash"], "build_guid": ident["build_guid"]}


if __name__ == "__main__":
    main()
