"""Stage 3 (optional add-on): translate the English UI text that lives inside the three scene bundles
(mainmenu / sordland / rizia).

Only *display* string leaves of MonoBehaviours (TMP `m_text`, StaticUIText `locaId`, a few config leaves, see WL) and the
text of three TextAssets (levelsConfig titles, Credits_* roles) are edited.  Everything else in the bundle is copied byte for byte:
no font / PPtr / structure / animation / method-name change.  Base file = the pristine game bundle (the old pack ships them unmodified).
"""
import csv, io, json, re, time
from lib_su import *
from jsonspan import scan_strings, encode_literal, detect_escape_style, splice

TM_FILE = os.path.join(TM_DIR, "stage3.json")
TAG = re.compile(r"<[^>]+>")
PH = re.compile(r"\{[^}]*\}")

SCENES = {
    "mainmenu": "scenes_scenes_assets_scenes_mainmenu.unity_",
    "sordland": "scenes_scenes_assets_scenes_sordland.unity_",
    "rizia": "scenes_scenes_assets_scenes_rizia.unity_",
}

# normalised leaf paths ('[]' = list index) that hold text the player reads
WL = {
    "m_text", "locaId", "inputFieldDescription",
    "profileImagesConfigs[]/title", "profileImagesConfigs[]/subtitle", "affiliationConfigs[]/title",
    "warTokenStatusEffects[]/statusEffectName", "warTokenStatusEffects[]/statusEffectDescription",
    "warTileStatusEffect[]/statusEffectName", "warTileStatusEffect[]/statusEffectDescription",
    "tutorialData[]/confirmationPanelData/titleData", "tutorialData[]/confirmationPanelData/subtitleData",
    "tutorialData[]/confirmationPanelData/buttonTextData_1", "productionUnitStateTexts[]/reason",
    "bombButtonData/tooltipTitleText", "bombButtonData/tooltipSubtitleText",
    "airSupportButtonData/tooltipTitleText", "airSupportButtonData/tooltipSubtitleText",
    "paratrooperButtonData/tooltipTitleText", "paratrooperButtonData/tooltipSubtitleText",
    "navalInvasionButtonData/tooltipTitleText", "navalInvasionButtonData/tooltipSubtitleText",
    "enterProfileNameTitle", "invalidProfileNameTitle", "invalidProfileNameDescription",
}
SKIP_ROOT = {"m_GameObject", "m_Script", "m_Name", "m_EditorClassIdentifier"}
CREDIT_TYPES = {"primary-group-title", "primary-role", "tertiary-group-title", "tertiary-role"}
WORD = re.compile(r"[A-Za-z][A-Za-z'’\-]*")


def split_ws(s):
    core = s.strip()
    if not core:
        return s, "", ""
    a = s.index(core[0])
    return s[:a], core, s[len(s.rstrip()):]


def needs_tr(s):
    t = PH.sub(" ", TAG.sub(" ", s))
    return bool(WORD.search(t)) and not CJK.search(s)


def norm_path(path):
    return re.sub(r"/\d+", "[]", "/".join(str(p) for p in path))


class Stage3:
    def __init__(self, log):
        self.log = log
        self.tm = jload(TM_FILE)
        self.ui = self.tm["ui"]
        self.keep = set(self.tm["keep"])
        self.used = set()
        self.missing = collections_counter()
        self.stats = {}
        self.text_assets = {}

    # ------------------------------------------------------------------ strings
    def tr(self, en, where):
        pre, core, suf = split_ws(en)
        if not core or CJK.search(core):
            return None
        zh = self.ui.get(core)
        if zh is not None:
            self.used.add(core)
            return pre + zh + suf
        if core in self.keep:
            return None
        if needs_tr(core):
            self.missing[(where, core)] += 1
        return None

    def walk(self, node, path, cnt):
        """edit whitelisted display leaves in place; returns nothing, increments cnt[norm path]"""
        if isinstance(node, dict):
            for k, v in list(node.items()):
                if not path and k in SKIP_ROOT:
                    continue
                p = path + (k,)
                if isinstance(v, str):
                    n = norm_path(p)
                    if n in WL:
                        new = self.tr(v, n)
                        if new is not None and new != v:
                            node[k] = new
                            cnt[n] = cnt.get(n, 0) + 1
                else:
                    self.walk(v, p, cnt)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                p = path + (i,)
                if isinstance(v, str):
                    n = norm_path(p)
                    if n in WL:
                        new = self.tr(v, n)
                        if new is not None and new != v:
                            node[i] = new
                            cnt[n] = cnt.get(n, 0) + 1
                else:
                    self.walk(v, p, cnt)

    # ------------------------------------------------------------------ text assets
    @staticmethod
    def _csv_row(cells):
        buf = io.StringIO()
        csv.writer(buf, lineterminator="").writerow(cells)
        return buf.getvalue()

    def edit_credits(self, text):
        out, n = [], 0
        for ln in text.splitlines(keepends=True):
            body = ln.rstrip("\r\n")
            eol = ln[len(body):]
            try:
                row = next(csv.reader([body]))
            except Exception:
                row = None
            if row and len(row) == 2 and row[1] in CREDIT_TYPES:
                en = row[0].strip()
                zh = self.tm["credits"].get(en) or self.ui.get(en)
                if zh and not CJK.search(en):
                    self.used.add(en)
                    ln = self._csv_row([zh, row[1]]) + eol
                    n += 1
                elif needs_tr(en) and en not in self.tm["credits_keep"] and en not in self.keep:
                    self.missing[("credits", en)] += 1
            out.append(ln)
        return "".join(out), n

    def edit_levels(self, text):
        esc = detect_escape_style(text)
        edits = {}
        for path, s, e, val in scan_strings(text):
            if len(path) == 3 and path[0] == "levels" and path[2] == "title":
                zh = self.tm["levels"].get(val.strip())
                if zh and not CJK.search(val):
                    edits[(s, e)] = encode_literal(zh, esc)
                elif needs_tr(val):
                    self.missing[("levels", val)] += 1
        return splice(text, edits), len(edits)

    def edit_text_asset(self, obj, scene):
        tree = obj.read_typetree()
        name = tree.get("m_Name", "")
        if name != "levelsConfig" and not name.startswith("Credits_"):
            return 0
        raw = tree["m_Script"]
        as_bytes = isinstance(raw, (bytes, bytearray))
        text = raw.decode("utf-8") if as_bytes else raw
        if name == "levelsConfig":
            new, n = self.edit_levels(text)
        else:
            new, n = self.edit_credits(text)
        if n:
            tree["m_Script"] = new.encode("utf-8") if as_bytes else new
            obj.save_typetree(tree)
            self.stats[f"textasset:{name}"] = self.stats.get(f"textasset:{name}", 0) + n
        return n

    # ------------------------------------------------------------------ bundles
    def build_scene(self, scene, prefix, out_dir):
        src = find_bundle(prefix, AA_GAME)
        env = load_env(src)
        cnt, mbs, tas = {}, 0, 0
        for obj in env.objects:
            tn = obj.type.name
            if tn == "MonoBehaviour":
                try:
                    tree = obj.read_typetree()
                except Exception:
                    continue
                c = {}
                self.walk(tree, (), c)
                if c:
                    obj.save_typetree(tree)
                    mbs += 1
                    for k, v in c.items():
                        cnt[k] = cnt.get(k, 0) + v
            elif tn == "TextAsset":
                if self.edit_text_asset(obj, scene):
                    tas += 1
        out = os.path.join(out_dir, AA_REL, os.path.basename(src))
        size = save_bundle(env, out)
        for k, v in cnt.items():
            self.stats[k] = self.stats.get(k, 0) + v
        self.log(f"stage3 {scene}: edited MonoBehaviours {mbs}, text assets {tas}, leaves {sum(cnt.values())}, bundle {size} bytes")
        return out

    def run(self, out_dir):
        t0 = time.time()
        written = []
        for scene, prefix in SCENES.items():
            written.append(self.build_scene(scene, prefix, out_dir))
            self.log(f"   [{time.time() - t0:.0f}s]")
        self.log(f"stage3: edited leaves by path: {dict(sorted(self.stats.items()))}")
        miss = sorted(self.missing.items(), key=lambda kv: (kv[0][0], kv[0][1]))
        self.log(f"stage3: missing translations: {len(miss)} distinct (where, text)")
        for (where, text), n in miss[:80]:
            self.log(f"   MISSING {where}: {text[:90]!r} x{n}")
        unused = [k for k in self.ui if k not in self.used]
        self.log(f"stage3: TM ui entries: {len(self.ui)}, unused {len(unused)}")
        for u in unused[:60]:
            self.log(f"   UNUSED {u[:80]!r}")
        return written


def collections_counter():
    import collections
    return collections.Counter()


def build(out_dir, log, strict=False):
    s3 = Stage3(log)
    written = s3.run(out_dir)
    if strict and s3.missing:
        raise SystemExit("strict build: stage3 missing translations")
    return written, s3
