"""Shared classification + replacement of DISPLAY string literals inside Lua / instruction-DSL code.

Only literals that are (a) assigned to a *Text variable or (b) passed as the display argument of a known setter
are considered display text.  Everything else (actor keys, token keys, enum values, ...) is never touched.
"""
from lualit import scan, replace_literals
import re

CJK = re.compile(r"[\u4e00-\u9fff]")
WORD = re.compile(r"[A-Za-z][A-Za-z'’\-]*")

# function -> set of argument indexes that are DISPLAY text (None = every argument)
DISPLAY_CALLS = {
    "UpdateCharacterTitle": {1},
    "UpdateCountryPresident": {1},
    "UpdateCountryGovernment": {1},
    "UpdatePlayerCountryGovernment": None,
    "UpdateCitySubtitle": {1},
    "UpdateCityTitle": {1},
    "UpdateCountryCapital": {1},
    "UpdateCountryLanguage": {1},
    "Concat": {1},
}


def has_english(s):
    return bool(WORD.search(s)) and not CJK.search(s)


def classify(l):
    """-> (kind, key) for a display literal, else None."""
    if l["idx"]:
        return None
    if l["cmp"] and "Text" in l["cmp"] and has_english(l["val"]):
        return ("compare", l["cmp"])
    if not has_english(l["val"]):
        return None
    if l["assign"] and "Text" in l["assign"]:
        return ("assign", l["assign"])
    if l["fn"] in DISPLAY_CALLS:
        allowed = DISPLAY_CALLS[l["fn"]]
        if allowed is None or l["arg"] in allowed:
            return ("call", f"{l['fn']}#{l['arg']}")
    return None


def maybe_code(s):
    """cheap pre-filter used for entity JSON string leaves"""
    return ('"' in s or "'" in s) and ("=" in s or "(" in s)


def translate_code(code, tm_map, used=None, skip_vars=()):
    """tm_map: {(kind, key, en): zh}.  returns (new_code, n_replaced)."""
    if not code or not maybe_code(code):
        return code, 0
    repl = {}
    for l in scan(code):
        k = classify(l)
        if not k:
            continue
        if k[0] == "assign" and k[1] in skip_vars:
            continue
        if k[0] == "compare":
            continue          # comparisons are logic, never rewritten here
        tk = (k[0], k[1], l["val"])
        zh = tm_map.get(tk)
        if zh is None:
            continue
        repl[(l["start"], l["end"])] = zh
        if used is not None:
            used.add(tk)
    if not repl:
        return code, 0
    return replace_literals(code, repl), len(repl)
