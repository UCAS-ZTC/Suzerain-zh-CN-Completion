"""Independent verification of the stage-3 scene-UI add-on pack.

usage: python su_verify3.py [PACK_DIR]
Reloads the three scene bundles from disk and compares them with the pristine game bundles:
  * identical bundle members; .resS streams byte-identical; serialized-file headers / externals identical
  * identical object sets; every object byte-identical EXCEPT edited MonoBehaviours / three TextAssets
  * MonoBehaviour typetree differences only in whitelisted display leaves; translation == TM entry;
    surrounding whitespace preserved; tags / placeholders identical; CJK present
  * for GameObjects whose TMP m_text equalled StaticUIText.locaId before, they still are equal afterwards
  * TextAssets: levelsConfig JSON identical apart from level titles; Credits CSV identical apart from role / group rows
  * no English display text left in whitelisted leaves except the deliberate keep list
"""
import sys, collections, csv, io, json
from lib_su import *
from su_apply import check_pair
import su_stage3 as S3

PACK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "Suzerain_CN_Plus_SceneUI_SteamWin_2026-10-10")
OUT = open(os.path.join(WORK, "out", "verify3_report.txt"), "w", encoding="utf-8")
CHG = open(os.path.join(WORK, "out", "verify3_changes_utf8.txt"), "w", encoding="utf-8")
TM = jload(os.path.join(TM_DIR, "stage3.json"))
UI, KEEP = TM["ui"], set(TM["keep"])
TMP_SCRIPT = 7477354737935883349
STATIC_SCRIPT = 7343663649919329368


def P(*a):
    print(*a, file=OUT)
    OUT.flush()


problems = []


def bad(msg):
    problems.append(msg)
    P("PROBLEM:", msg)


def diff_tree(a, b, path=()):
    if a == b:
        return
    if isinstance(a, dict) and isinstance(b, dict):
        if a.keys() != b.keys():
            yield (path, "<keys>", "<keys>")
            return
        for k in a:
            if a[k] != b[k]:
                yield from diff_tree(a[k], b[k], path + (k,))
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            yield (path, "<len>", "<len>")
            return
        for i, (x, y) in enumerate(zip(a, b)):
            if x != y:
                yield from diff_tree(x, y, path + (i,))
    else:
        yield (path, a, b)


def lead(s):
    return s[:len(s) - len(s.lstrip())]


def trail(s):
    return s[len(s.rstrip()):]


def text_of(tree):
    raw = tree["m_Script"]
    return raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw


# ---------------------------------------------------------------- 1. manifest / hashes
P("== manifest / hashes ==")
man = json.load(open(os.path.join(PACK, "patch_manifest.json"), encoding="utf-8-sig"))
P("release:", man["release_name"], "variant:", man["variant"], "| files:", len(man["files"]))
if man["variant"] != "sceneui":
    bad("variant is not sceneui")
for f in man["files"]:
    p = os.path.join(PACK, f["relative_path"])
    if not os.path.exists(lp(p)):
        bad(f"payload missing {f['file_name']}")
        continue
    if os.path.getsize(lp(p)) != f["size"]:
        bad(f"size mismatch {f['file_name']}")
    if sha256_file(p) != f["patched_sha256"]:
        bad(f"patched hash mismatch {f['file_name']}")
    if sha256_file(os.path.join(GAME, f["relative_path"])) != f["original_sha256"]:
        bad(f"original hash != game file {f['file_name']}")
on_disk = {n for n in os.listdir(lp(os.path.join(PACK, AA_REL))) if n.endswith(".bundle")}
if on_disk != {f["file_name"] for f in man["files"]}:
    bad("payload / manifest mismatch")
if len(on_disk) != 3:
    bad(f"expected 3 scene bundles, found {len(on_disk)}")
for n in ("install.ps1", "install.bat", "restore.ps1", "restore.bat", "README.txt", "patch_manifest.json"):
    if not os.path.exists(os.path.join(PACK, n)):
        bad(f"missing {n}")
P("hash check done")


# ---------------------------------------------------------------- 2. scene bundles
def go_pairs(objs):
    """go_pid -> {'m_text': ..., 'locaId': ...} for MonoBehaviours of the scene serialized file"""
    d = collections.defaultdict(dict)
    for pid, o in objs.items():
        if o.type.name != "MonoBehaviour":
            continue
        try:
            t = o.read_typetree()
        except Exception:
            continue
        gp = t.get("m_GameObject", {}).get("m_PathID")
        if "m_text" in t:
            d[gp]["m_text"] = t["m_text"]
        if "locaId" in t:
            d[gp]["locaId"] = t["locaId"]
    return d


changed_rows = set()
kinds = collections.Counter()
warn_kinds = collections.Counter()
samples = collections.defaultdict(list)

for scene, prefix in S3.SCENES.items():
    P(f"\n== {scene} ==")
    gpath = find_bundle(prefix, AA_GAME)
    npath = find_bundle(prefix, os.path.join(PACK, AA_REL))
    bg = list(load_env(gpath).files.values())[0]
    bn = list(load_env(npath).files.values())[0]
    if list(bg.files) != list(bn.files):
        bad(f"{scene}: bundle members differ {list(bg.files)} vs {list(bn.files)}")
        continue
    for name in bg.files:
        fg, fn = bg.files[name], bn.files[name]
        if not hasattr(fg, "objects"):
            if bytes(fg.bytes) != bytes(fn.bytes):
                bad(f"{scene}: stream file {name} differs")
            else:
                kinds["stream files identical"] += 1
            continue
        # serialized file header-level facts
        for attr in ("unity_version", "version", "target_platform"):
            if str(getattr(fg, attr, None)) != str(getattr(fn, attr, None)):
                bad(f"{scene}/{name}: {attr} changed {getattr(fg, attr, None)} -> {getattr(fn, attr, None)}")
        ext_g = [getattr(e, "path", str(e)) for e in fg.externals]
        ext_n = [getattr(e, "path", str(e)) for e in fn.externals]
        if ext_g != ext_n:
            bad(f"{scene}/{name}: externals changed")
        if len(fg.script_types) != len(fn.script_types) or len(fg.types) != len(fn.types):
            bad(f"{scene}/{name}: types / script types changed")
        og, on = fg.objects, fn.objects
        if set(og) != set(on):
            bad(f"{scene}/{name}: object set differs ({len(set(og) ^ set(on))} ids)")
            continue
        same = 0
        for pid in og:
            a, b = og[pid], on[pid]
            if a.type.name != b.type.name:
                bad(f"{scene}/{name}: type changed {pid}")
                continue
            ra, rb = a.get_raw_data(), b.get_raw_data()
            if ra == rb:
                same += 1
                continue
            tn = a.type.name
            if tn == "MonoBehaviour":
                ta, tb = a.read_typetree(), b.read_typetree()
                nd = 0
                for path, x, y in diff_tree(ta, tb):
                    nd += 1
                    norm = S3.norm_path(path)
                    if norm not in S3.WL or not isinstance(x, str) or not isinstance(y, str):
                        bad(f"{scene}: unexpected MB change {pid} {path[:6]} {str(x)[:40]!r} -> {str(y)[:40]!r}")
                        continue
                    core_x, core_y = x.strip(), y.strip()
                    if lead(x) != lead(y) or trail(x) != trail(y):
                        bad(f"{scene}: whitespace not preserved {x!r} -> {y!r}")
                    if core_x not in UI:
                        bad(f"{scene}: changed string not in TM {core_x[:60]!r}")
                    elif y != lead(x) + UI[core_x] + trail(x):
                        bad(f"{scene}: text differs from TM {core_x[:60]!r} -> {y[:60]!r}")
                    if not CJK.search(core_y):
                        bad(f"{scene}: no CJK after edit {core_x[:60]!r}")
                    e, w = check_pair(core_x, core_y)
                    e = [z for z in e]
                    if e:
                        bad(f"{scene}: markup problem {norm}: {e} :: {core_x[:60]!r}")
                    for z in w:
                        warn_kinds[z.split(":")[0].split(" ")[0] + " " + z.split(" ")[1] if " " in z else z] += 1
                    kinds[norm] += 1
                    changed_rows.add((norm, core_x, core_y))
                    if len(samples[norm]) < 3:
                        samples[norm].append((core_x[:60], core_y[:60]))
                if nd == 0:
                    bad(f"{scene}: raw bytes differ but typetrees equal {pid}")
            elif tn == "TextAsset":
                ta, tb = a.read_typetree(), b.read_typetree()
                if ta.keys() != tb.keys() or ta["m_Name"] != tb["m_Name"] or ta.get("m_PathName") != tb.get("m_PathName"):
                    bad(f"{scene}: TextAsset header changed {ta['m_Name']}")
                xa, xb = text_of(ta), text_of(tb)
                nm = ta["m_Name"]
                if nm == "levelsConfig":
                    ja, jb = json.loads(xa), json.loads(xb)
                    if ja.keys() != jb.keys() or len(ja["levels"]) != len(jb["levels"]):
                        bad(f"{scene}: levelsConfig structure changed")
                    for la, lb in zip(ja["levels"], jb["levels"]):
                        da = {k: v for k, v in la.items() if k != "title"}
                        db = {k: v for k, v in lb.items() if k != "title"}
                        if da != db:
                            bad(f"{scene}: levelsConfig non-title field changed")
                        if TM["levels"].get(la["title"]) != lb["title"]:
                            bad(f"{scene}: level title mismatch {la['title']!r} -> {lb['title']!r}")
                        changed_rows.add(("levelsConfig.title", la["title"], lb["title"]))
                        kinds["levelsConfig.title"] += 1
                elif nm.startswith("Credits_"):
                    la, lb = xa.splitlines(keepends=True), xb.splitlines(keepends=True)
                    if len(la) != len(lb):
                        bad(f"{scene}: {nm} line count changed {len(la)} -> {len(lb)}")
                    else:
                        for i, (p, q) in enumerate(zip(la, lb)):
                            if p == q:
                                continue
                            bp, bq = p.rstrip("\r\n"), q.rstrip("\r\n")
                            if p[len(bp):] != q[len(bq):]:
                                bad(f"{scene}: {nm} line {i} ending changed")
                            ra_, rb_ = next(csv.reader([bp])), next(csv.reader([bq]))
                            if len(ra_) != 2 or len(rb_) != 2 or ra_[1] != rb_[1] or ra_[1] not in S3.CREDIT_TYPES:
                                bad(f"{scene}: {nm} line {i} unexpected change {bp!r} -> {bq!r}")
                                continue
                            if not CJK.search(rb_[0]):
                                bad(f"{scene}: {nm} line {i} no CJK {bq!r}")
                            exp = TM["credits"].get(ra_[0].strip()) or UI.get(ra_[0].strip())
                            if exp != rb_[0]:
                                bad(f"{scene}: {nm} line {i} differs from TM {bq!r}")
                            changed_rows.add((f"{nm}:{ra_[1]}", ra_[0], rb_[0]))
                            kinds[f"credits:{ra_[1]}"] += 1
                else:
                    bad(f"{scene}: unexpected TextAsset changed {nm}")
            else:
                bad(f"{scene}: non-MB/TextAsset object changed {tn} {pid}")
        kinds["objects byte-identical"] += same
        P(f"   {name}: objects {len(og)}, byte-identical {same}")
    # TMP / StaticUIText pairs stay in sync
    name_main = [n for n in bg.files if hasattr(bg.files[n], "objects") and len(bg.files[n].objects) > 1000]
    for nm in name_main:
        pg, pn = go_pairs(bg.files[nm].objects), go_pairs(bn.files[nm].objects)
        broke = 0
        n_pairs = 0
        for gp, d in pg.items():
            if "m_text" in d and "locaId" in d:
                n_pairs += 1
                eq_before = d["m_text"].strip() == d["locaId"].strip()
                dn = pn.get(gp, {})
                eq_after = dn.get("m_text", "").strip() == dn.get("locaId", "").strip()
                if eq_before and not eq_after:
                    broke += 1
                    if broke <= 5:
                        bad(f"{scene}: m_text / locaId out of sync on go {gp}: {dn.get('m_text')!r} vs {dn.get('locaId')!r}")
        P(f"   TMP+StaticUIText pairs: {n_pairs}; out of sync after edit: {broke}")
        kinds["tmp/locaId pairs checked"] += n_pairs

    # residual English display text in the whitelisted leaves of the NEW bundle
    resid = collections.Counter()
    for nm in name_main:
        for pid, o in bn.files[nm].objects.items():
            if o.type.name != "MonoBehaviour":
                continue
            try:
                t = o.read_typetree()
            except Exception:
                continue

            def rec(node, path):
                if isinstance(node, dict):
                    for k, v in node.items():
                        if not path and k in S3.SKIP_ROOT:
                            continue
                        rec(v, path + (k,))
                elif isinstance(node, list):
                    for i, v in enumerate(node):
                        rec(v, path + (i,))
                elif isinstance(node, str):
                    n_ = S3.norm_path(path)
                    if n_ in S3.WL and S3.needs_tr(node.strip()) and node.strip() not in KEEP:
                        resid[(n_, node.strip()[:70])] += 1
            rec(t, ())
    P(f"   residual English (outside keep list): {sum(resid.values())}")
    for (n_, s_), c in resid.most_common(40):
        P(f"      {n_}: {s_!r} x{c}")
        bad(f"{scene}: residual English {n_} {s_!r}")

P("\n== summary ==")
for k, v in sorted(kinds.items()):
    P(f"  {k}: {v}")
P("  check_pair warnings (informational):", dict(warn_kinds))
P("problems:", len(problems))
for r in sorted(changed_rows):
    CHG.write(f"{r[0]}\t{r[1]!r}\t{r[2]!r}\n")
CHG.close()
print("problems:", len(problems))
