"""Independent verification of a built pack.

usage: python su_verify.py PACK_DIR
Reloads every bundle from disk and checks that ONLY intended leaves differ from the old (patched) pack.
"""
import sys, glob
from collections import Counter, defaultdict
from lib_su import *
from jsonspan import scan_strings
from lualit import scan as lua_scan
from scriptlits import classify, has_english, maybe_code
from su_scope import *
from su_apply import check_pair, field_of, fix_typos

PACK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "Suzerain_CN_Plus_SteamWin_2026-10-10")
OUT = open(os.path.join(WORK, "out", "verify_report.txt"), "w", encoding="utf-8")


def P(*a):
    print(*a, file=OUT)
    OUT.flush()


problems = []


def bad(msg):
    problems.append(msg)
    P("PROBLEM:", msg)


def skeleton(code):
    """code with every string-literal span blanked out"""
    ls = sorted((l["start"], l["end"]) for l in lua_scan(code))
    out, pos = [], 0
    for s, e in ls:
        out.append(code[pos:s])
        out.append("§")
        pos = e
    out.append(code[pos:])
    return "".join(out)


def diff_tree(a, b, path=()):
    """yield (path, a_leaf, b_leaf) for differing leaves of two nested structures with identical shape"""
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


# ---------------------------------------------------------------- 1. manifest / hashes
P("== manifest / hashes ==")
man = json.load(open(os.path.join(PACK, "patch_manifest.json"), encoding="utf-8-sig"))
P("release:", man["release_name"], "| files:", len(man["files"]))
for f in man["files"]:
    p = os.path.join(PACK, f["relative_path"])
    if not os.path.exists(lp(p)):
        bad(f"payload missing {f['file_name']}")
        continue
    if os.path.getsize(lp(p)) != f["size"]:
        bad(f"size mismatch {f['file_name']}")
    if sha256_file(p) != f["patched_sha256"]:
        bad(f"patched hash mismatch {f['file_name']}")
    g = os.path.join(GAME, f["relative_path"])
    if sha256_file(g) != f["original_sha256"]:
        bad(f"original hash != game file {f['file_name']}")
on_disk = {n for n in os.listdir(lp(os.path.join(PACK, AA_REL))) if n.endswith(".bundle")}
listed = {f["file_name"] for f in man["files"]}
if on_disk != listed:
    bad(f"payload/manifest mismatch: only-disk {on_disk - listed} only-manifest {listed - on_disk}")
P("hash check done")

# ---------------------------------------------------------------- 2. dialogue DB
P("\n== dialogue DB ==")
DBP = "database_assets_all_"
new_db_path = find_bundle(DBP, os.path.join(PACK, AA_REL))
old_db_path = find_bundle(DBP, AA_OLD)
if os.path.exists(new_db_path) and new_db_path != old_db_path:
    t_new = list(mb_objects(load_env(new_db_path)))[0].read_typetree()
    t_old = list(mb_objects(load_env(old_db_path)))[0].read_typetree()
    convs_new = t_new["conversations"]
    n_diff = Counter()
    for path, a, b in diff_tree(t_old, t_new):
        if path[0] == "conversations":
            ci, di = path[1], path[3]
            c = convs_new[ci]
            de = c["dialogueEntries"][di]
            loc = (c["id"], de["id"])
            if path[4] == "fields":
                title = de["fields"][path[5]]["title"]
                if isinstance(a, str) and isinstance(b, str):
                    e, w = check_pair(a, b) if CJK.search(b) else (["no cjk"], [])
                    if title == "Script":
                        if skeleton(a) != skeleton(b):
                            bad(f"DB script skeleton changed conv{loc}")
                        n_diff["script-field"] += 1
                    else:
                        # old->new text change: allow English->CJK rows (check markup) or CJK fixes
                        ee, _ = check_pair(a, b)
                        if ee and not has_english(a):
                            ee = [x for x in ee if not x.startswith("empty")]
                        if ee:
                            bad(f"DB markup changed conv{loc} {title}: {ee}")
                        n_diff["text:" + title] += 1
                else:
                    bad(f"DB non-string diff {path}")
            elif path[4] == "userScript":
                if skeleton(a) != skeleton(b):
                    bad(f"DB userScript skeleton changed conv{loc}")
                n_diff["userScript"] += 1
            else:
                bad(f"DB unexpected diff {path[:6]}")
        elif path[0] == "variables":
            n_diff["variable"] += 1
        else:
            bad(f"DB unexpected diff {path[:3]}")
    P("DB diffs by kind:", dict(n_diff))
    del t_old
else:
    t_new = None
    P("DB bundle not rebuilt (same as old pack)")

# remaining english display literals / rows in DB (live conversations only is out of scope; just count)
if t_new is not None:
    left = Counter()
    ex = []
    for c in t_new["conversations"]:
        for de in c["dialogueEntries"]:
            for code in (de.get("userScript") or "", (field_of(de, "Script") or {}).get("value") or ""):
                if code and maybe_code(code):
                    for l in lua_scan(code):
                        k = classify(l)
                        if k and k[0] != "compare":
                            left[k] += 1
                            if len(ex) < 60:
                                ex.append((c["id"], de["id"], k, l["val"]))
    P("remaining English display literals in DB code:", sum(left.values()), "(distinct", len(left), ")")
    for e in ex:
        P("   ", e)

    # none of the typo rules (tm/typo_rules.json) may still match the delivered dialogue text
    n_typo_db = 0
    for c in t_new["conversations"]:
        for de in c["dialogueEntries"]:
            for f_ in de["fields"]:
                if f_["title"] == "Script" or not isinstance(f_.get("value"), str):
                    continue
                if fix_typos(f_["value"])[1]:
                    n_typo_db += 1
                    bad(f"DB typo rule still matches conv{c['id']}#{de['id']} {f_['title']}: {f_['value'][:60]!r}")
    P("residual typo-rule matches in DB text fields:", n_typo_db)

# ---------------------------------------------------------------- 3. entity text
P("\n== entity text ==")
ENT = "defaultlocalgroup_assets_assets_database_entitytextassets"
new_e_path = find_bundle(ENT, os.path.join(PACK, AA_REL))
old_e_path = find_bundle(ENT, AA_OLD)
f_new = list(mb_objects(load_env(new_e_path)))[0].read_typetree()
f_old = list(mb_objects(load_env(old_e_path)))[0].read_typetree()
if f_new.keys() != f_old.keys():
    bad("entity MB key set differs")
kinds = Counter()
import pickle
from su_apply import load_ent_force
ent_orig = pickle.load(open(os.path.join(CACHE, "ent_mb.pkl"), "rb"))["orig"]
FORCE = load_ent_force()
for k in sorted(f_old):
    if f_new[k] == f_old[k]:
        continue
    if not (isinstance(f_old[k], str) and k.endswith("DataJson")):
        bad(f"entity non-json field changed: {k}")
        continue
    cont = k[:-len("DataJson")]
    a = scan_strings(f_old[k])
    b = scan_strings(f_new[k])
    po_orig = {tuple(p0): v0 for p0, s0, e0, v0 in scan_strings(ent_orig[k])}
    if len(a) != len(b) or any(x[0] != y[0] for x, y in zip(a, b)):
        bad(f"{k}: JSON structure changed")
        continue
    # text outside the edited string literals must be byte-identical
    import re as _re
    def mask(text, spans):
        out, pos = [], 0
        for s, e in spans:
            out.append(text[pos:s]); pos = e
        out.append(text[pos:])
        return "".join(out)
    ch_old = [(x[1], x[2]) for x, y in zip(a, b) if x[3] != y[3]]
    ch_new = [(y[1], y[2]) for x, y in zip(a, b) if x[3] != y[3]]
    if mask(f_old[k], ch_old) != mask(f_new[k], ch_new):
        bad(f"{k}: bytes outside edited literals changed")
    for x, y in zip(a, b):
        if x[3] == y[3]:
            continue
        path = x[0]
        o, n = x[3], y[3]
        key, parent = leaf_keys(path)
        if cont == "TokenStatusEffects" and key == "CodexEntryTitle":
            kinds[(cont, "title-sync")] += 1
            continue
        if is_translatable_leaf(cont, path):
            ov = po_orig.get(tuple(path))
            if ov is not None and CJK.search(o) and text_id(ov) in FORCE:
                # stale-refresh leaf: the reference is the CURRENT English, not the old Chinese
                e, w = check_pair(ov, n)
                kinds[(cont, key, "force")] += 1
            else:
                e, w = check_pair(o, n)
                kinds[(cont, key, "text")] += 1
            if e:
                bad(f"{cont}.{key} markup: {e} :: {o[:60]!r}")
        elif maybe_code(o):
            if skeleton(o) != skeleton(n):
                bad(f"{cont}: code skeleton changed {path}")
            kinds[(cont, "script")] += 1
        elif CJK.search(o) and n != o and fix_typos(o)[0] == n:
            # an already-translated leaf outside the translation scope (e.g. GraphPanel.Subtitle): the ONLY allowed change is
            # exactly what the typo rules produce, with the markup untouched
            e, w = check_pair(o, n)
            if e:
                bad(f"{cont}.{key} typo-only change altered markup: {e} :: {o[:60]!r}")
            kinds[(cont, key, "typo-only")] += 1
        else:
            bad(f"{cont}: unexpected change {path} {o[:60]!r} -> {n[:60]!r}")
P("entity leaf changes:")
for k, v in sorted(kinds.items(), key=lambda kv: str(kv[0])):
    P("  ", k, v)

# stale-refresh (forced) leaves, checked against the CURRENT English of the pristine game
YEAR_RX = re.compile(r"(?<![\d,.])(1[6-9]\d\d)(?![\d]|s\b|’s|'s)")
seen_force, n_force_leaves = set(), 0
for k in sorted(f_new):
    if not k.endswith("DataJson"):
        continue
    cont = k[:-len("DataJson")]
    po_orig = {tuple(p0): v0 for p0, s0, e0, v0 in scan_strings(ent_orig[k])}
    for path, s, e, n in scan_strings(f_new[k]):
        ov = po_orig.get(tuple(path))
        if ov is None or not is_translatable_leaf(cont, path) or not ov.strip():
            continue
        tid = text_id(ov)
        if tid not in FORCE:
            continue
        seen_force.add(tid)
        n_force_leaves += 1
        want = FORCE[tid].replace("\r\n", "\n")
        if "\r\n" in ov:
            want = want.replace("\n", "\r\n")
        if n != want:
            bad(f"forced leaf not applied: {cont} {tid}")
            continue
        e, w = check_pair(ov, n)
        if e:
            bad(f"forced leaf {cont} {tid}: {e}")
        if ov.count("\n") != n.count("\n"):
            bad(f"forced leaf {cont} {tid}: line structure differs ({ov.count(chr(10))} vs {n.count(chr(10))})")
        miss = sorted(set(YEAR_RX.findall(ov)) - set(re.findall(r"\d{4}", n)))
        if miss:
            P(f"   note: forced leaf {tid} lacks years {miss} (check wording)")
        if not CJK.search(n):
            bad(f"forced leaf {cont} {tid}: no CJK")
unseen = sorted(set(FORCE) - seen_force)
if unseen:
    bad(f"forced ids never found in the built bundle: {unseen}")
P(f"forced (stale-refresh) leaves verified: {n_force_leaves} leaves, {len(seen_force)}/{len(FORCE)} ids")

# leaves that must stay ORIGINAL English (internal lookup keys; translating them removes the in-game map HUD): byte-identical to the pristine game
n_keep = 0
for (cont_k, parent_k, key_k) in sorted(MUST_STAY_ENGLISH):
    jk_k = cont_k + "DataJson"
    po_k = {tuple(p0): v0 for p0, s0, e0, v0 in scan_strings(ent_orig[jk_k])}
    for path, s, e, n in scan_strings(f_new[jk_k]):
        key_, parent_ = leaf_keys(path)
        if (parent_, key_) != (parent_k, key_k):
            continue
        n_keep += 1
        if po_k.get(tuple(path)) != n:
            bad(f"{cont_k}.{parent_k}.{key_k} must stay original English but differs at {path}: {n[:40]!r}")
if n_keep == 0:
    bad("must-stay-English check matched no leaves (scope keys wrong?)")
P(f"must-stay-English leaves verified identical to the pristine game: {n_keep}")

# residual english in translatable leaves + mixed-language words
resid = defaultdict(list)
typo_left = []
mixed = Counter()
mixed_ex = {}
code_left = Counter()
for k in sorted(f_new):
    if not k.endswith("DataJson"):
        continue
    cont = k[:-len("DataJson")]
    for path, s, e, v in scan_strings(f_new[k]):
        key, parent = leaf_keys(path)
        if CJK.search(v) and not maybe_code(v) and fix_typos(v)[1]:      # every string leaf, in or out of the translation scope
            typo_left.append((f"{cont}.{key}", v))
        if is_translatable_leaf(cont, path):
            if needs_translation(v):
                resid[f"{cont}.{key}"].append(v)
            elif CJK.search(v):
                t = PH.sub(" ", TAG.sub(" ", v))
                for w in WORD.findall(t):
                    mixed[w] += 1
                    mixed_ex.setdefault(w, (f"{cont}.{key}", v[:100]))
        if maybe_code(v):
            for l in lua_scan(v):
                kk = classify(l)
                if kk and kk[0] != "compare":
                    code_left[(kk, l["val"])] += 1
P("\nresidual typo-rule matches in entity text leaves:", len(typo_left))
for kk, v in typo_left:
    bad(f"entity typo rule still matches {kk}: {v[:60]!r}")
P("\nresidual English-only leaves in translatable keys:", sum(len(v) for v in resid.values()))
for kk, v in sorted(resid.items()):
    P("  ", kk, len(v), "e.g.", repr(v[0][:70]))
P("\nremaining English display literals in entity code:", sum(code_left.values()))
for kk, n in code_left.most_common(60):
    P("  ", kk, n)
P("\nLatin words inside CJK text (translatable keys), top 120 of", len(mixed))
for w, n in mixed.most_common(120):
    P(f"  {w}: {n}   [{mixed_ex[w][0]}] {mixed_ex[w][1]!r}")

# ---------------------------------------------------------------- 4. all other bundles (stage 2 and old-pack payload)
P("\n== other bundles ==")
S2_KEYS = {"displayName", "description", "objectiveName", "objectiveDescription", "effectName",
           "titleData", "subtitleData", "buttonTextData_1", "unitName"}
kinds4 = Counter()
for f in man["files"]:
    n = f["file_name"]
    if n.startswith(DBP) or n.startswith(ENT):
        continue
    newp = os.path.join(PACK, f["relative_path"])
    oldp = os.path.join(AA_OLD, n)
    if os.path.exists(lp(oldp)) and sha256_file(oldp) == f["patched_sha256"]:
        kinds4["old-pack payload copied unchanged"] += 1
        continue
    base = oldp if os.path.exists(lp(oldp)) else os.path.join(AA_GAME, n)
    e_new, e_base = load_env(newp), load_env(base)
    o_new = {o.path_id: o for o in e_new.objects}
    o_old = {o.path_id: o for o in e_base.objects}
    if set(o_new) != set(o_old):
        bad(f"{n}: object set differs")
        continue
    for pid, on in o_new.items():
        oo = o_old[pid]
        if on.type.name != oo.type.name:
            bad(f"{n}: object type changed {pid}")
            continue
        if on.get_raw_data() == oo.get_raw_data():
            continue
        if on.type.name != "MonoBehaviour":
            bad(f"{n}: non-MB object bytes changed {pid} {on.type.name}")
            continue
        ta, tb = oo.read_typetree(), on.read_typetree()
        for path, a, b in diff_tree(ta, tb):
            key = next((p for p in reversed(path) if isinstance(p, str)), "")
            if key not in S2_KEYS or not isinstance(a, str) or not isinstance(b, str):
                bad(f"{n}: unexpected typetree change {path[:6]} {str(a)[:40]!r} -> {str(b)[:40]!r}")
                continue
            e, w = check_pair(a.strip(), b.strip())
            e = [x for x in e if not x.startswith("translation has no CJK")]
            if e or not CJK.search(b):
                bad(f"{n}: markup/translation problem {key}: {e} {a[:50]!r} -> {b[:50]!r}")
            if a != a.strip() and (a[:len(a) - len(a.lstrip())] != b[:len(b) - len(b.lstrip())] or a[len(a.rstrip()):] != b[len(b.rstrip()):]):
                bad(f"{n}: surrounding whitespace not preserved {a!r} -> {b!r}")
            kinds4[key] += 1
P("other-bundle leaf changes / copies:", dict(kinds4))

P("\n== summary ==")
P("problems:", len(problems))
print("problems:", len(problems))
