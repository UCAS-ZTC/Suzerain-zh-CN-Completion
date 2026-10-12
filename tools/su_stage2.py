"""Stage 2: translate achievements, war objectives, war tutorial hints, tile effect names and the 'Objective' unit name.

Base file for each bundle = the old pack's bundle if it ships one, else the pristine game bundle.
Only the listed display leaves are touched (IDs / LocaIds / identifiers are never edited).
"""
import json, copy, re
from lib_su import *

TM_FILE = os.path.join(TM_DIR, "stage2.json")
LATIN = re.compile(r"[A-Za-z]{2,}")


def split_ws(s):
    core = s.strip()
    if not core:
        return s, "", ""
    a = s.index(core[0])
    pre = s[:a]
    suf = s[len(s.rstrip()):]
    return pre, core, suf


class Stage2:
    def __init__(self, log):
        self.log = log
        self.tm = jload(TM_FILE)
        self.keep = set(self.tm["keep"])
        self.stats = {}
        self.missing = []
        self.used = {k: set() for k in self.tm if k != "keep"}

    # ------------------------------------------------------------------ targets
    def targets(self):
        """-> {bundle file name: set of categories}"""
        out = {}
        names = os.listdir(lp(AA_GAME))
        for n in names:
            if n.startswith("achievements_"):
                out.setdefault(n, set()).add("ach")
            elif n.startswith("warobjectives_"):
                out.setdefault(n, set()).add("obj")
            elif n.startswith("commonassets_"):
                out.setdefault(n, set()).add("eff")
            elif n.startswith("warunitytypes_") and "city_tutorial" in n.lower():
                out.setdefault(n, set()).add("unit")
        # bundles with war tutorial data (default local group copies + the Rizia story pack copy).  The list was derived once
        # from a whole-game scan (scan_groups.py: rows that carry tutorialData strings) and is pinned together with the game build.
        for b in jload(os.path.join(DATA, "stage2_tutorial_bundles.json")):
            out.setdefault(b, set()).add("tut")
        return out

    # ------------------------------------------------------------------ editing
    def tr(self, section, en, where):
        pre, core, suf = split_ws(en)
        if not core:
            return None
        if CJK.search(core):
            return None
        sect = self.tm.get(section, {})
        if core in sect:
            self.used[section].add(core)
            return pre + sect[core] + suf
        if core in self.keep:
            return None
        if LATIN.search(core):
            self.missing.append((section, where, core))
        return None

    def walk(self, node, cats, where, cnt):
        if isinstance(node, dict):
            for k, v in list(node.items()):
                if isinstance(v, str):
                    new = None
                    if "ach" in cats and k == "displayName":
                        new = self.tr("achievements.displayName", v, where + "." + k)
                    elif "ach" in cats and k == "description":
                        new = self.tr("achievements.description", v, where + "." + k)
                    elif "obj" in cats and k == "objectiveName":
                        new = self.tr("objectives.objectiveName", v, where + "." + k)
                    elif "obj" in cats and k == "objectiveDescription":
                        new = self.tr("objectives.objectiveDescription", v, where + "." + k)
                    elif "eff" in cats and k == "effectName":
                        new = self.tr("effects.effectName", v, where + "." + k)
                    elif "tut" in cats and k in ("titleData", "subtitleData", "buttonTextData_1"):
                        new = self.tr("tutorial", v, where + "." + k)
                    elif "unit" in cats and k == "unitName":
                        new = self.tr("units.unitName", v, where + "." + k)
                    if new is not None and new != v:
                        node[k] = new
                        cnt[k] = cnt.get(k, 0) + 1
                else:
                    self.walk(v, cats, where + "." + k, cnt)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                self.walk(v, cats, where + f"[{i}]", cnt)

    def build_one(self, name, cats, out_dir):
        old = os.path.join(AA_OLD, name)
        base = old if os.path.exists(lp(old)) else os.path.join(AA_GAME, name)
        env = load_env(base)
        cnt = {}
        for obj in mb_objects(env):
            try:
                tree = obj.read_typetree()
            except Exception as e:  # noqa
                continue
            c = {}
            self.walk(tree, cats, "", c)
            if c:
                obj.save_typetree(tree)
                for k, v in c.items():
                    cnt[k] = cnt.get(k, 0) + v
        if not cnt:
            return None
        out = os.path.join(out_dir, AA_REL, name)
        save_bundle(env, out)
        for k, v in cnt.items():
            self.stats[k] = self.stats.get(k, 0) + v
        return out

    def run(self, out_dir):
        written = []
        tg = self.targets()
        self.log(f"stage2: {len(tg)} candidate bundles")
        for name in sorted(tg):
            o = self.build_one(name, tg[name], out_dir)
            if o:
                written.append(name)
        self.log(f"stage2: bundles written {len(written)}; edited leaves {self.stats}")
        self.log(f"stage2: missing translations: {len(self.missing)}")
        for m in self.missing[:40]:
            self.log(f"   MISSING {m}")
        for sect, used in self.used.items():
            unused = [k for k in self.tm[sect] if k not in used]
            self.log(f"stage2: TM section {sect}: {len(self.tm[sect])} entries, unused {len(unused)}")
            for u in unused[:20]:
                self.log(f"   UNUSED {sect} {u[:80]!r}")
        return written


def build(out_dir, log, strict=False):
    s2 = Stage2(log)
    written = s2.run(out_dir)
    if strict and s2.missing:
        raise SystemExit("strict build: stage2 missing translations")
    return written, s2
