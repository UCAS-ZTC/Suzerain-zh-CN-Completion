"""Verify the program-text pack's global-metadata.dat against the ORIGINAL game file, independently of meta_patch.apply().

usage: python su_verify_meta.py PACK_DIR      -> work/out/verify_meta_report.txt, exit code 1 on any problem
Works for both metadata add-ons (decided by the manifest's variant):
  programtext  : meta_tm.PAIRS, built on the pristine game file
  programwords : meta_tm.PAIRS + meta_words.PAIRS (the full file), built ON the delivered ProgramText pack (manifest original hash ==
                 that pack's patched hash, requires_pack names it); additionally the file is compared literal by literal with the
                 ProgramText payload: only the word literals and the sink may differ.
Checks: same size; header (380 bytes) identical; literal offset table keeps its place/size; every byte after the literal data blob
identical; literal count equal; offsets monotonic with sentinel == blob size; per literal: translated -> exactly the Chinese UTF-8,
sink -> original + only spaces (count == bytes saved), every other literal byte-identical; placeholders / tags / line breaks preserved;
manifest hashes / sizes; pack file list; translation_list.txt entry count.
"""
import sys, os, hashlib, struct, json, collections
from lib_su import *
import meta_lib, meta_patch, meta_tm

PACK = sys.argv[1]
rep = open(os.path.join(WORK, "out", "verify_meta_report.txt"), "w", encoding="utf-8")
problems = []


def P(s=""):
    print(s, file=rep)
    rep.flush()


def bad(msg):
    problems.append(msg)
    P("PROBLEM: " + msg)


def ok(cond, msg):
    if cond:
        P("ok    " + msg)
    else:
        bad(msg)


man = json.load(open(os.path.join(PACK, "patch_manifest.json"), encoding="utf-8-sig"))
WORDS = man["variant"] == "programwords"
if WORDS:
    import meta_words
BASE_NAME = "Suzerain_CN_Plus_ProgramText_SteamWin_2026-10-10"

orig = open(lp(meta_lib.MD_GAME), "rb").read()
pp = os.path.join(PACK, meta_lib.MD_REL)
new = open(lp(pp), "rb").read()
mo, mn = meta_lib.Meta(orig), meta_lib.Meta(new)

ok(len(orig) == len(new), f"file size identical ({len(orig)} / {len(new)})")
ok(orig[:mo.hdr_size] == new[:mn.hdr_size], "380-byte header identical")
ok(mo.trip == mn.trip, "all 31 section triplets identical")
ok(mo.n_lit == mn.n_lit, f"literal count identical ({mo.n_lit})")
ok(mn.offs[0] == 0 and mn.offs[-1] == mn.data_size == mo.data_size, "offset table starts at 0 and ends at the unchanged blob size")
ok(all(a <= b for a, b in zip(mn.offs, mn.offs[1:])), "offsets monotonic")
tail_o = orig[mo.data_off + mo.data_size:]
tail_n = new[mn.data_off + mn.data_size:]
ok(tail_o == tail_n, f"{len(tail_o)} bytes after the literal blob identical")
ok(orig[mo.off_tab + mo.trip[0][1] - 0:mo.data_off] == new[mn.off_tab + mn.trip[0][1] - 0:mn.data_off] == b"", "offset table directly followed by the blob")

# expected changes recomputed here from the translation table
where = collections.defaultdict(list)
for i, l in enumerate(mo.lits):
    where[l].append(i)
exp = {}
PAIRS_CHECK = list(meta_tm.PAIRS)
if WORDS:
    PAIRS_CHECK += meta_words.PAIRS
for g, en, zh in PAIRS_CHECK:
    ids = where[en.encode("utf-8")]
    if len(ids) != 1:
        bad(f"english literal occurs {len(ids)} times: {en!r}")
        continue
    for pr in meta_patch.check_pair(en, zh):
        bad(f"{pr}: {en!r}")
    exp[ids[0]] = (en, zh)
delta = sum(len(mo.lits[i]) - len(zh.encode("utf-8")) for i, (en, zh) in exp.items())
P(f"expected translated literals: {len(exp)}; bytes saved: {delta}")
sink_ids = where[meta_patch.SINK_TEXT.encode("utf-8")]
ok(len(sink_ids) == 1, "sink literal unique in the original")
sink = sink_ids[0]
n_tr = n_same = n_sink = 0
for i in range(mo.n_lit):
    a, b = mo.raw(i), mn.raw(i)
    if i in exp:
        want = exp[i][1].encode("utf-8")
        if b != want:
            bad(f"literal {i}: not the expected Chinese ({b!r})")
        else:
            try:
                b.decode("utf-8")
            except UnicodeDecodeError:
                bad(f"literal {i}: invalid UTF-8")
            n_tr += 1
    elif i == sink:
        extra = b[len(a):]
        if not (b.startswith(a) and set(extra) <= {0x20} and len(extra) == delta):
            bad(f"sink literal {i} is not original + {delta} spaces")
        else:
            n_sink += 1
    elif a != b:
        bad(f"literal {i} changed unexpectedly: {a[:60]!r} -> {b[:60]!r}")
    else:
        n_same += 1
ok(n_tr == len(exp), f"translated literals exact: {n_tr}/{len(exp)}")
ok(n_sink == 1, "sink literal = original + spaces only")
ok(n_tr + n_sink + n_same == mo.n_lit, f"all {mo.n_lit} literals accounted for ({n_same} untouched)")
ok(sink > max(exp), f"sink {sink} lies after the last translated literal {max(exp)}")
# the two blobs differ only inside [first translated literal, sink end]; the offset table only for entries in (first, sink]
lo = mo.data_off + mo.offs[min(exp)]
hi = mo.data_off + mo.offs[sink + 1]
ok(orig[mo.data_off:lo] == new[mn.data_off:lo] and orig[hi:] == new[hi:],
   "blob bytes before the first translated literal and from the sink end on are identical")
ok(all(mo.offs[k] == mn.offs[k] for k in range(len(mo.offs)) if k <= min(exp) or k >= sink + 1),
   f"offset entries outside ({min(exp)}, {sink}] unchanged")
ok(mo.offs[sink + 1] == mn.offs[sink + 1], "offset after the sink literal unchanged (sink absorbs the whole size difference)")

# manifest / pack contents
ok(len(man["files"]) == 1 and man["files"][0]["relative_path"] == meta_lib.MD_REL, "manifest lists exactly the metadata file")
f0 = man["files"][0]
ok(f0["patched_sha256"] == hashlib.sha256(new).hexdigest().upper(), "manifest patched hash == payload hash")
ok(f0["size"] == len(new), "manifest size == payload size")
if not WORDS:
    ok(f0["original_sha256"] == hashlib.sha256(orig).hexdigest().upper(), "manifest original hash == game file hash")
    ok(man["variant"] == "programtext", "variant programtext")
    ok("requires_pack" not in f0, "no requires_pack (independent pack)")
else:
    # built on the delivered ProgramText pack: its payload must be exactly meta_tm.PAIRS applied to the pristine file
    base_path = os.path.join(ROOT, BASE_NAME, meta_lib.MD_REL)
    base = open(lp(base_path), "rb").read()
    base_expect, _ = meta_patch.apply(orig, meta_tm.PAIRS)
    ok(base == base_expect, "delivered ProgramText payload == meta_tm.PAIRS applied to the original")
    ok(f0["original_sha256"] == hashlib.sha256(base).hexdigest().upper(), "manifest original hash == the ProgramText pack's patched hash")
    ok(f0.get("requires_pack") == BASE_NAME, "requires_pack names the ProgramText pack")
    ok("also_accept_sha256" not in f0, "no also_accept (only the ProgramText state is a valid base)")
    ok(man["variant"] == "programwords", "variant programwords")
    mb = meta_lib.Meta(base)
    word_ids = {where[en.encode("utf-8")][0] for g, en, zh in meta_words.PAIRS}
    n_diff = 0
    for i in range(mo.n_lit):
        if mb.raw(i) != mn.raw(i):
            n_diff += 1
            if i not in word_ids and i != sink:
                bad(f"literal {i} differs from the ProgramText payload but is neither a word nor the sink: {mn.raw(i)[:50]!r}")
    ok(n_diff == len(word_ids) + 1, f"payload differs from the ProgramText payload in exactly {len(word_ids)} word literals + the sink ({n_diff})")
    ok(mb.hdr_size == mn.hdr_size and base[:mb.hdr_size] == new[:mn.hdr_size], "header identical to the ProgramText payload")
    ok(len(base) == len(new), "same size as the ProgramText payload")
names = sorted(os.path.relpath(os.path.join(dp, n), PACK) for dp, dn, fn in os.walk(PACK) for n in fn)
want = sorted(["README.txt", "install.bat", "install.ps1", "restore.bat", "restore.ps1", "patch_manifest.json", "translation_list.txt",
               meta_lib.MD_REL])
ok(names == want, f"pack files exactly: {names}")
lst = open(os.path.join(PACK, "translation_list.txt"), encoding="utf-8-sig").read().splitlines()
n_ent = sum(1 for l in lst if l.startswith("["))
n_want = len(meta_words.PAIRS) if WORDS else len(exp)
ok(n_ent == n_want, f"translation_list.txt has {n_ent} entries (expected {n_want})")
P("")
P(f"PROBLEMS: {len(problems)}")
rep.close()
print("problems:", len(problems))
sys.exit(1 if problems else 0)
