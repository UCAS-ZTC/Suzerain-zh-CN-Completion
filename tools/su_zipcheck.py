"""usage: python su_zipcheck.py PACK_DIR [PACK_DIR ...] : the .zip next to each folder must contain exactly the folder's files, byte-identical."""
import sys, os, zipfile, hashlib
from lib_su import lp

bad = 0
for d in sys.argv[1:]:
    d = os.path.abspath(d)
    zp = d + ".zip"
    root = os.path.dirname(d)
    z = zipfile.ZipFile(zp)
    t = z.testzip()
    disk = {}
    for dp, dn, fn in os.walk(d):
        for n in fn:
            full = os.path.join(dp, n)
            disk[os.path.relpath(full, root).replace(os.sep, "/")] = full
    names = {i.filename for i in z.infolist() if not i.is_dir()}
    diff = names ^ set(disk)
    mism = 0
    for n in sorted(names & set(disk)):
        h1, h2 = hashlib.sha256(), hashlib.sha256()
        with z.open(n) as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h1.update(chunk)
        with open(lp(disk[n]), "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h2.update(chunk)
        if h1.digest() != h2.digest():
            mism += 1
    print(os.path.basename(zp), "| testzip:", t, "| entries:", len(names), "| name diffs:", len(diff), "| content mismatches:", mism,
          "| top-level folder:", {n.split('/')[0] for n in names})
    bad += (t is not None) + len(diff) + mism
print("bad:", bad)
