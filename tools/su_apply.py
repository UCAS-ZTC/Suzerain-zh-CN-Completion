"""Apply translation memories to the dialogue DB tree and to the entity-text MonoBehaviour fields."""
import re, glob
from collections import Counter, defaultdict
from lib_su import *
from jsonspan import scan_strings, encode_literal, detect_escape_style, splice
from scriptlits import translate_code, maybe_code, classify
from su_scope import *

CJK_OR_PUNCT = re.compile(r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef“”‘’—…·]")
TAG_RX = re.compile(r"<[^>]+>")
PH_RX = re.compile(r"\{[^}]*\}")
NUM_RX = re.compile(r"\d+(?:[.,]\d+)*")


# ------------------------------------------------------------------ helpers
def rep_cjk(text, old, new):
    """replace `old` by `new`; drop one adjacent space on a side if the neighbour char is CJK / CJK punctuation."""
    pat = re.compile(r"( ?)" + re.escape(old) + r"( ?)")
    n = [0]

    def f(m):
        n[0] += 1
        a, b = m.start(), m.end()
        pre = text[a - 1] if a > 0 else ""
        post = text[b] if b < len(text) else ""
        out = ""
        if m.group(1) and not (pre == "" or CJK_OR_PUNCT.match(pre)):
            out += m.group(1)
        out += new
        if m.group(2) and not (post == "" or CJK_OR_PUNCT.match(post)):
            out += m.group(2)
        return out

    return pat.sub(f, text), n[0]


def check_pair(en, zh):
    """-> (errors, warnings) comparing protected markup between source and translation"""
    errs, warns = [], []
    if TAG_RX.findall(en) != TAG_RX.findall(zh):
        errs.append(f"tags differ {TAG_RX.findall(en)} vs {TAG_RX.findall(zh)}")
    if Counter(PH_RX.findall(en)) != Counter(PH_RX.findall(zh)):
        errs.append(f"placeholders differ {PH_RX.findall(en)} vs {PH_RX.findall(zh)}")
    if en.count("\n") != zh.count("\n"):
        warns.append(f"newline count {en.count(chr(10))} vs {zh.count(chr(10))}")
    ne = Counter(x.replace(",", "") for x in NUM_RX.findall(en))
    nz = Counter(x.replace(",", "") for x in NUM_RX.findall(zh))
    if ne != nz:
        warns.append(f"numbers differ: only-en {dict(ne - nz)} only-zh {dict(nz - ne)}")
    if not zh.strip():
        errs.append("empty translation")
    if WORD.search(PH_RX.sub(" ", TAG_RX.sub(" ", zh))) and not CJK.search(zh):
        warns.append("translation has no CJK")
    return errs, warns


def load_stage0():
    return jload(os.path.join(TM_DIR, "stage0.json"))


def script_map(tm0):
    return {(u["kind"], u["key"], u["en"]): u["zh"] for u in tm0["script"]}


def load_ent_text():
    """merge tm/ent_text_*.json ({id: zh} or [[id, zh], ...]) -> {id: zh}"""
    out = {}
    for p in sorted(glob.glob(os.path.join(TM_DIR, "ent_text_*.json"))):
        d = jload(p)
        if isinstance(d, list):
            d = {k: v for k, v in d}
        for k, v in d.items():
            if k in out and out[k] != v:
                raise ValueError(f"conflicting translation for id {k} in {p}")
            out[k] = v
    return out


def load_ent_force():
    """merge tm/ent_force_*.json ({text_id(ORIGINAL English leaf): zh}) -> {id: zh}.
    Unlike ent_text (which only fills leaves that are still English), these REPLACE a leaf the old pack already translated
    but whose Chinese no longer matches the current English (the English was extended / rewritten after the old pack was made)."""
    out = {}
    for p in sorted(glob.glob(os.path.join(TM_DIR, "ent_force_*.json"))):
        d = jload(p)
        for k, v in d.items():
            if k.startswith("_"):
                continue
            if k in out and out[k] != v:
                raise ValueError(f"conflicting forced translation for id {k} in {p}")
            out[k] = v
    return out


def load_ent_fixes():
    p = os.path.join(TM_DIR, "ent_fixes.json")
    return jload(p) if os.path.exists(p) else []


# ------------------------------------------------------------------ translation slips (tm/typo_rules.json)
# Doubled words ("先生先生"), doubled particles ("他们的的权力"), 形式/形势, half-width punctuation ...  Every rule is a regex
# with its own "min" (the number of hits the current game text must contain; su_build.py asserts it so a stale rule is noticed).
# The rules only rewrite text that contains CJK and are applied (1) to every dialogue text field of the DB and (2) to every
# translatable-or-old entity leaf except the "forced" stale-refresh leaves (those are taken verbatim from tm/ent_force_*.json,
# which must be clean themselves; su_verify.py checks that).
_TYPO = None
TYPO_HITS = Counter()
TYPO_LOG = []            # (where, context before, context after) for the review list written by su_build.py


def typo_rules():
    global _TYPO
    if _TYPO is None:
        p = os.path.join(TM_DIR, "typo_rules.json")
        raw = jload(p) if os.path.exists(p) else []
        _TYPO = [(re.compile(r["re"]), r["to"], r) for r in raw]
    return _TYPO


def fix_typos(text, where=""):
    """-> (new_text, number_of_replacements); text without CJK is returned untouched."""
    if not CJK.search(text):
        return text, 0
    total = 0
    for i, (rx, to, meta) in enumerate(typo_rules()):
        def _sub(m, i=i, to=to):
            TYPO_HITS[i] += 1
            s = m.string
            a, e = max(0, m.start() - 12), min(len(s), m.end() + 12)
            TYPO_LOG.append((where, i, s[a:m.start()] + "[" + m.group(0) + "]" + s[m.end():e],
                             s[a:m.start()] + "[" + to + "]" + s[m.end():e]))
            return to
        text, n = rx.subn(_sub, text)
        total += n
    return text, total


# ------------------------------------------------------------------ dialogue DB
def field_of(de, title):
    for f in de["fields"]:
        if f["title"] == title:
            return f
    return None


def apply_db(tree, tm0, log):
    """in-place edit of the DB typetree; returns set of touched (kind, conv, entry, field)"""
    touched = []
    convs = {c["id"]: c for c in tree["conversations"]}

    def entry(cid, eid):
        for de in convs[cid]["dialogueEntries"]:
            if de["id"] == eid:
                return de
        raise KeyError((cid, eid))

    # 1. whole-row translations
    for r in tm0["rows"]:
        de = entry(r["conv"], r["entry"])
        f = field_of(de, r["key"])
        assert f is not None and f["value"] == r["en"], f"row mismatch conv{r['conv']}#{r['entry']} {r['key']}: {f and f['value']!r}"
        errs, warns = check_pair(r["en"], r["zh"])
        assert not errs, (r, errs)
        for w in warns:
            log(f"   warn conv{r['conv']}#{r['entry']}: {w}")
        f["value"] = r["zh"]
        touched.append(("row", r["conv"], r["entry"], r["key"]))
    # 2. in-row fixes
    for fx in tm0["fixes"]:
        de = entry(fx["conv"], fx["entry"])
        f = field_of(de, fx["key"])
        new, n = rep_cjk(f["value"], fx["old"], fx["new"])
        assert n >= 1, f"fix not applicable conv{fx['conv']}#{fx['entry']}: {fx['old']!r} in {f['value']!r}"
        log(f"   fix conv{fx['conv']}#{fx['entry']} {fx['old']!r}->{fx['new']!r} x{n}")
        f["value"] = new
        touched.append(("fix", fx["conv"], fx["entry"], fx["key"]))
    # 3. display literals inside Lua scripts
    smap = script_map(tm0)
    used = set()
    n_scripts = 0
    for c in tree["conversations"]:
        for de in c["dialogueEntries"]:
            for holder, key in ((de, "userScript"),):
                code = holder.get(key) or ""
                new, n = translate_code(code, smap, used)
                if n:
                    holder[key] = new
                    n_scripts += n
                    touched.append(("script", c["id"], de["id"], key))
            f = field_of(de, "Script")
            if f is not None and isinstance(f["value"], str):
                new, n = translate_code(f["value"], smap, used)
                if n:
                    f["value"] = new
                    n_scripts += n
                    touched.append(("script", c["id"], de["id"], "fields.Script"))
    log(f"   db script literals replaced: {n_scripts}; distinct units used: {len(used)}")
    unused = [k for k in smap if k not in used]
    log(f"   script TM units not found in DB code (may live in entity JSON): {len(unused)}")
    # 4. variable initial values
    vars_by_name = {}
    for v in tree["variables"]:
        nm = field_of(v, "Name")
        if nm:
            vars_by_name[nm["value"]] = v
    for vv in tm0["vars"]:
        v = vars_by_name[vv["name"]]
        f = field_of(v, "Initial Value")
        assert f["value"] == vv["en"], (vv, f["value"])
        f["value"] = vv["zh"]
        touched.append(("var", vv["name"], None, "Initial Value"))
    # 5. translation slips (tm/typo_rules.json) in every dialogue text field; runs last so the row/fix steps above still see
    #    the exact old strings they assert against
    n_typo = 0
    for c in tree["conversations"]:
        for de in c["dialogueEntries"]:
            for f in de["fields"]:
                if f["title"] == "Script" or not isinstance(f.get("value"), str):
                    continue
                new, n = fix_typos(f["value"], f"DB conv{c['id']}#{de['id']} {f['title']}")
                if n:
                    f["value"] = new
                    n_typo += n
                    touched.append(("typo", c["id"], de["id"], f["title"]))
    log(f"   typo rules applied to dialogue text fields: {n_typo} replacements")
    return touched, used


# ------------------------------------------------------------------ entity text
class EntityEditor:
    def __init__(self, fields_old, fields_orig, tm0, ent_text, fixes, log, force=None):
        self.old = fields_old          # patched (old pack) MB fields
        self.orig = fields_orig        # pristine MB fields
        self.tm0 = tm0
        self.smap = script_map(tm0)
        self.ent_text = ent_text
        self.fixes = fixes
        self.force = force or {}       # text_id(original English) -> Chinese that replaces a stale old-pack translation
        self.log = log
        self.used_script = set()
        self.used_text = set()
        self.used_force = set()
        self.used_fix = Counter()
        self.missing = defaultdict(list)       # cont.key -> [en,...]
        self.n_changed_leaves = Counter()
        self.title_map = {}
        self.warns = []

    def json_keys(self):
        return sorted(k for k, v in self.old.items() if isinstance(v, str) and k.endswith("DataJson"))

    # ---- per leaf
    def edit_leaf(self, cont, path, v, ov=None):
        """v = value in the old pack, ov = value at the same path in the pristine game (current English)"""
        key, parent = leaf_keys(path)
        new = v
        tag = None
        tid_o = text_id(ov) if (self.force and isinstance(ov, str) and ov.strip()) else None
        if tid_o in self.force and is_translatable_leaf(cont, path) and (CJK.search(v) or v == ov):
            # forced: the old Chinese is stale against the current English (or the leaf is still English and a
            # forced translation exists for the same sentence, which then must win to keep both copies consistent)
            zh = self.force[tid_o]
            label = f"{cont}.{key}"
            errs, warns = check_pair(ov, zh)
            if errs:
                raise ValueError(f"[{label}] forced {tid_o}: {errs} :: {ov[:80]!r}")
            for w in warns:
                self.warns.append((cont, key, tid_o, "force: " + w))
            if "\r\n" in ov:
                zh = zh.replace("\r\n", "\n").replace("\n", "\r\n")
            new = zh
            self.used_force.add(tid_o)
            return new, "force"
        if is_translatable_leaf(cont, path) and needs_translation(v):
            tid = text_id(v)
            label = f"{cont}.{parent}.{key}" if cont == "MapTokens" else f"{cont}.{key}"
            used_key = f"{tid}@{label}"
            zh = self.ent_text.get(used_key)          # context-specific translation wins
            if zh is None:
                used_key = tid
                zh = self.ent_text.get(tid)
            if zh is None:
                self.missing[label].append(v)
            else:
                errs, warns = check_pair(v, zh)
                if errs:
                    raise ValueError(f"[{label}] {errs} :: {v[:80]!r}")
                for w in warns:
                    self.warns.append((cont, key, tid, w))
                if "\r\n" in v:
                    zh = zh.replace("\r\n", "\n").replace("\n", "\r\n")
                new = zh
                self.used_text.add(used_key)
                tag = "text"
        elif maybe_code(v):
            new2, n = translate_code(v, self.smap, self.used_script)
            if n:
                new = new2
                tag = "script"
        # leaf-level fixes for leftovers inside already-translated text; each fix names its exact scopes
        if tag != "script" and not maybe_code(new):
            scope = f"{cont}.{key}"
            for i, fx in enumerate(self.fixes):
                if scope in fx["scope"] and fx["old"] in new:
                    new, n = rep_cjk(new, fx["old"], fx["new"])
                    self.used_fix[i] += n
                    tag = tag or "fix"
        # translation slips (tm/typo_rules.json); forced leaves come verbatim from tm/ent_force_*.json (kept clean at the source)
        if tag not in ("force", "script") and not maybe_code(new):
            new2, n = fix_typos(new, f"ENT {cont}.{key}")
            if n:
                new = new2
                tag = tag or "typo"
        if cont == "TokenStatusEffects" and key == "CodexEntryTitle" and v in self.title_map:
            new = self.title_map[v]
            tag = "title-sync"
        return new, tag

    def run_field(self, jk):
        cont = jk[:-len("DataJson")]
        text = self.old[jk]
        esc = detect_escape_style(text)
        edits = {}
        changed = Counter()
        po = {tuple(p0): v0 for p0, s0, e0, v0 in scan_strings(self.orig[jk])} if self.force else {}
        for path, s, e, v in scan_strings(text):
            new, tag = self.edit_leaf(cont, path, v, po.get(tuple(path)))
            if new != v:
                edits[(s, e)] = encode_literal(new, esc)
                changed[tag] += 1
        for t, n in changed.items():
            self.n_changed_leaves[(cont, t)] += n
        return (splice(text, edits) if edits else text), changed

    def compute_title_map(self, codex_jk="CodexEntriesDataJson", new_text=None):
        """orig English codex Title -> final Chinese Title (by item position)."""
        import json as _json
        o = _json.loads(self.orig[codex_jk])["items"]
        n = _json.loads(new_text)["items"]
        assert len(o) == len(n)
        m = defaultdict(set)
        for a, b in zip(o, n):
            assert a["Id"] == b["Id"]
            m[a["CodexEntryProperties"]["Title"]].add(b["CodexEntryProperties"]["Title"])
        amb = {k: v for k, v in m.items() if len(v) > 1}
        self.title_map = {k: next(iter(v)) for k, v in m.items() if len(v) == 1}
        self.log(f"   codex title map: {len(self.title_map)} titles ({len(amb)} ambiguous)")
        for k, v in list(amb.items())[:10]:
            self.log(f"      ambiguous: {k!r} -> {sorted(v)}")

    def run(self):
        out = {}
        order = ["CodexEntriesDataJson"] + [k for k in self.json_keys() if k != "CodexEntriesDataJson"]
        for jk in order:
            new_text, changed = self.run_field(jk)
            if jk == "CodexEntriesDataJson":
                self.compute_title_map(new_text=new_text)
            if new_text != self.old[jk]:
                out[jk] = new_text
                self.log(f"   {jk:44s} changed leaves: {dict(changed)}")
        return out
