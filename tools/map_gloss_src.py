"""Read-only: harvest English->Chinese name pairs from the entity-text assets (pristine game vs Plus pack).

writes cache\\gloss_entity_pairs.json : {"container.key": [[en, zh], ...]}
"""
import sys
import json
from collections import defaultdict
from lib_su import *
from jsonspan import scan_strings
from su_scope import is_translatable_leaf, leaf_keys

PLUS = os.path.join(ROOT, "Suzerain_CN_Plus_SteamWin_2026-10-10")
ENT = "defaultlocalgroup_assets_assets_database_entitytextassets"


def mb0(path):
    return list(mb_objects(load_env(path)))[0].read_typetree()


f_orig = mb0(find_bundle(ENT, AA_GAME))
f_new = mb0(find_bundle(ENT, os.path.join(PLUS, AA_REL)))
pairs = defaultdict(list)
seen = set()
for k in sorted(f_orig):
    if not k.endswith("DataJson"):
        continue
    cont = k[:-len("DataJson")]
    so, sn = scan_strings(f_orig[k]), scan_strings(f_new[k])
    for x, z in zip(so, sn):
        o, n = x[3], z[3]
        if o == n or not CJK.search(n) or CJK.search(o):
            continue
        key, parent = leaf_keys(x[0])
        if cont in ("MapTokens", "CodexEntries", "StoryPack", "CountryDetailsPanel", "Operation") and len(o) <= 60:
            tag = f"{cont}.{parent}.{key}"
            if (tag, o, n) in seen:
                continue
            seen.add((tag, o, n))
            pairs[tag].append([o, n])
json.dump(pairs, open(os.path.join(CACHE, "gloss_entity_pairs.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
for tag, v in pairs.items():
    print(tag, len(v))
    for o, n in v[:12]:
        print("    ", repr(o), "=>", repr(n))
