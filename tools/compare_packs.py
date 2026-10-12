"""Compare two pack folders file by file (size + SHA-256).  Read-only, standard library only.

usage:  python compare_packs.py BUILT_DIR REFERENCE_DIR [--payload-only]

A pack folder = the files a pack ships: the replaced game files under Suzerain_Data\\ (the "payload") plus install.ps1,
restore.ps1, patch_manifest.json, README.txt ... (the "metadata").  Exit code 0 only when nothing differs.
"""
import os, sys, hashlib


def lp(p):
    p = os.path.abspath(p)
    return p if p.startswith("\\\\?\\") else "\\\\?\\" + p


def hash_tree(root):
    out = {}
    root = os.path.abspath(root)
    for dirpath, _dirs, files in os.walk(lp(root)):
        for f in files:
            full = os.path.join(dirpath, f)
            rel = os.path.relpath(full, lp(root)).replace("\\", "/")
            h = hashlib.sha256()
            with open(full, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
            out[rel] = (os.path.getsize(full), h.hexdigest())
    return out


def is_payload(rel):
    return rel.startswith("Suzerain_Data/")


def compare(a_root, b_root, payload_only=False):
    a, b = hash_tree(a_root), hash_tree(b_root)
    keys = sorted(set(a) | set(b))
    rows = {"same": [], "diff": [], "only_built": [], "only_ref": []}
    for k in keys:
        if payload_only and not is_payload(k):
            continue
        if k in a and k in b:
            rows["same" if a[k] == b[k] else "diff"].append(k)
        elif k in a:
            rows["only_built"].append(k)
        else:
            rows["only_ref"].append(k)
    return rows, a, b


def main(argv):
    payload_only = "--payload-only" in argv
    args = [x for x in argv if not x.startswith("--")]
    if len(args) != 2:
        print(__doc__)
        return 2
    rows, a, b = compare(args[0], args[1], payload_only)
    n_pay = sum(1 for k in rows["same"] if is_payload(k))
    print(f"identical: {len(rows['same'])} files ({n_pay} payload)   different: {len(rows['diff'])}   "
          f"only in built: {len(rows['only_built'])}   only in reference: {len(rows['only_ref'])}")
    for k in rows["diff"]:
        print(f"  DIFF  {k}   built {a[k][0]} B / ref {b[k][0]} B")
    for k in rows["only_built"]:
        print(f"  EXTRA {k}")
    for k in rows["only_ref"]:
        print(f"  MISSING {k}")
    return 0 if not (rows["diff"] or rows["only_built"] or rows["only_ref"]) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
