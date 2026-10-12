"""English place name -> Chinese rendering used for the map annotations.

Sources (highest priority first):  MANUAL (this file, maplab\\names_*.py)  >  names already used by the pack for map tokens /
capitals / province subtitles (entity text)  >  corpus lookup results kept in maplab\\corpus_names.json.
Keys are compared case-insensitively with spaces / hyphens / dots collapsed.
"""
import os
import re
import json
import glob

from lib_su import ROOT, WORK, CACHE, MAPLAB_DIR


def key(s):
    s = s.lower().replace("’", "'")
    s = re.sub(r"^[^a-z0-9]+|[^a-z0-9]+$", "", s)          # OCR debris around the name (':', '?', '.' ...)
    s = re.sub(r"[\s\-\.]+", " ", s).strip()
    return s


def _load_entity():
    p = os.path.join(CACHE, "gloss_entity_pairs.json")
    d = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    out = {}
    for tag in ("MapTokens.MapTokenProperties.Title", "MapTokens.MapTokenProperties.Subtitle",
                "MapTokens.CountryDetailsProperties.Capital", "CountryDetailsPanel.CountryDetailsPanelProperties.Capital"):
        for en, zh in d.get(tag, []):
            if len(en) <= 40:
                out[key(en)] = zh
    return out


def _load_manual():
    out = {}
    for p in sorted(glob.glob(os.path.join(MAPLAB_DIR, "names_*.py"))):
        ns = {}
        exec(compile(open(p, encoding="utf-8").read(), p, "exec"), ns)
        for k, v in ns.get("NAMES", {}).items():
            out[key(k)] = v
    p = os.path.join(MAPLAB_DIR, "corpus_names.json")
    corp = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    return out, {key(k): v for k, v in corp.items()}


ENTITY = _load_entity()
MANUAL, CORPUS = _load_manual()


SUFFIX = {"bay": "湾", "gulf": "湾", "lake": "湖", "island": "岛", "isles": "群岛", "islands": "群岛", "sea": "海", "strait": "海峡",
          "river": "河", "peninsula": "半岛", "cape": "角", "pass": "隘", "falls": "瀑布", "mountains": "山脉", "forest": "森林",
          "city": "市", "harbor": "港", "harbour": "港", "port": "港"}
PREFIX = {"port": "港", "porte": "港", "fort": "堡", "lake": "湖", "mount": "山", "cape": "角", "bay of": "湾", "gulf of": "湾",
          "isle of": "岛", "sea of": "海", "isles of": "群岛", "island of": "岛", "strait of": "海峡"}
SAINT = ("st", "san", "saint", "sant")


def _direct(k):
    for src in (MANUAL, ENTITY, CORPUS):
        if k in src:
            return src[k]
    return None


def lookup(text):
    k = key(text)
    z = _direct(k)
    if z:
        return z
    w = k.split(" ")
    if len(w) >= 2:                                   # compounds:  X Bay / Port X / Gulf of X / St X
        if w[-1] in SUFFIX:
            b = _direct(" ".join(w[:-1]))
            if b:
                return b + SUFFIX[w[-1]]
        for n in (2, 1):
            if len(w) > n and " ".join(w[:n]) in PREFIX:
                b = _direct(" ".join(w[n:]))
                if b:
                    return b + PREFIX[" ".join(w[:n])]
        if w[0] in SAINT:
            b = _direct(" ".join(w[1:]))
            if b:
                return "圣" + b
    return None


def reload():
    global ENTITY, MANUAL, CORPUS
    ENTITY = _load_entity()
    MANUAL, CORPUS = _load_manual()
