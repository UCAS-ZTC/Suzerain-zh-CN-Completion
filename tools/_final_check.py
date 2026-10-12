"""Read-only final consistency check of every delivered pack folder at the workspace root:
every file listed in patch_manifest.json must exist with the listed size and patched_sha256; no unlisted payload files (Suzerain_Data\\**)."""
import os, sys, json, hashlib, glob

ROOT = os.path.abspath(os.environ.get("SUZERAIN_OUT") or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out"))
bad = 0
for d in sorted(glob.glob(os.path.join(ROOT, "Suzerain_CN_*"))):
    if not os.path.isdir(d):
        continue
    mp = os.path.join(d, "patch_manifest.json")
    if not os.path.isfile(mp):
        print(f"{os.path.basename(d)}: (no patch_manifest.json - installer package)")
        continue
    m = json.load(open(mp, encoding="utf-8-sig"))
    listed = set()
    probs = []
    for f in m["files"]:
        rel = f["relative_path"]
        listed.add(os.path.normcase(os.path.normpath(rel)))
        p = "\\\\?\\" + os.path.join(d, rel)
        if not os.path.isfile(p):
            probs.append("missing " + rel)
            continue
        if os.path.getsize(p) != f["size"]:
            probs.append("size " + rel)
            continue
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        if h.hexdigest().upper() != f["patched_sha256"].upper():
            probs.append("sha " + rel)
    extra = []
    sd = os.path.join(d, "Suzerain_Data")
    for dp, dn, fn in os.walk("\\\\?\\" + sd):
        for n in fn:
            rel = os.path.relpath(os.path.join(dp, n), "\\\\?\\" + d)
            if os.path.normcase(os.path.normpath(rel)) not in listed:
                extra.append(rel)
    zp = d + ".zip"
    print(f"{os.path.basename(d)}: files {len(m['files'])}, problems {len(probs)}, unlisted payload files {len(extra)}, "
          f"zip {'present ' + str(os.path.getsize(zp)) if os.path.isfile(zp) else 'MISSING'}, built_at {m.get('built_at')}")
    for x in probs[:5] + extra[:5]:
        print("   ", x)
    bad += len(probs) + len(extra)
print("TOTAL problems:", bad)
