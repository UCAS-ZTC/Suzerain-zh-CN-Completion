"""Which entity-JSON leaves are DISPLAY text (translatable) and which must be left alone."""
import re, hashlib

CJK = re.compile(r"[\u4e00-\u9fff]")
WORD = re.compile(r"[A-Za-z][A-Za-z'’\-]*")
TAG = re.compile(r"<[^>]+>")
PH = re.compile(r"\{[^}]*\}")

# container -> leaf keys that are display text
TRANSLATE = {
    "CodexEntries": {"Title", "Description"},
    "News": {"Title", "Description"},
    "Reports": {"Title", "Description"},
    "Policies": {"Title", "Description"},
    "Decisions": {"Title", "Description", "HubTitle", "HubDescription", "Text"},
    "JournalEntries": {"Description", "Title"},
    "GameFlow": {"TransitionTitle"},
    "Operation": {"OperationName"},
    "StoryPack": {"QuoteText", "QuoteAuthor"},          # CountryNameShort deliberately NOT translated (may be used as a key)
    "CollectionItem": {"GroupName", "Title", "Description"},
    "DLCCollectionItem": {"Title", "Description"},
    "CharacterDetailsSection": {"Value", "Title"},
    "CountryDetailsPanel": {"GdpWorldRank"},
    "Conversations": {"Title", "Subtitle"},
    "ReminderPanelSegment": {"Title", "Text"},
}
# MapTokens: (parent key, key).  Relations / MilitaryStrengthConditions.Result are ENUM values -> never translated.
# ReligionDatas.Name / EthnicityDatas.Name are deliberately NOT here (Plus build 4): translating those 413 leaves (build 1-3) made
# the whole in-game map HUD (coat of arms, economy bar, side buttons, news counter, portrait) disappear in a live test.
# Bisected in the real game: reverting only these leaves restores the HUD; reverting Title/Subtitle did not.
# Effect of leaving them English: the ethnicity / religion pie-chart legend in the country / city panel stays English.
MAP_KEYS = {
    ("MapTokenProperties", "Title"), ("MapTokenProperties", "Subtitle"),
    ("DescriptionProperties", "Description"),
    ("CountryDetailsProperties", "Capital"), ("CountryDetailsProperties", "Language"),
    ("CountryDetailsProperties", "President"), ("CountryDetailsProperties", "Government"),
}
# leaves that must stay byte-identical to the original game (checked by su_verify.py): (container, parent key, key)
MUST_STAY_ENGLISH = {("MapTokens", "ReligionDatas", "Name"), ("MapTokens", "EthnicityDatas", "Name")}
# English strings that are intentionally kept (conlang / placeholders / possible sentinel values)
KEEP_EN = {"None", "Glovurius axa Rizia!", "{RiziaDLCText.FinalChapterTitle}",
           "{RiziaDLCText.CharacterDetails_GrandVizierPM}", "A Morgna wes core"}


def leaf_keys(path):
    strs = [p for p in path if isinstance(p, str)]
    key = strs[-1] if strs else ""
    parent = strs[-2] if len(strs) >= 2 else ""
    return key, parent


def is_translatable_leaf(cont, path):
    key, parent = leaf_keys(path)
    if cont == "MapTokens":
        return (parent, key) in MAP_KEYS
    return key in TRANSLATE.get(cont, ())


def needs_translation(s):
    """English text with at least one real word left after removing {placeholders} and <tags>."""
    if s in KEEP_EN:
        return False
    t = PH.sub(" ", TAG.sub(" ", s))
    return bool(WORD.search(t)) and not CJK.search(s)


def text_id(en):
    return hashlib.sha1(en.encode("utf-8")).hexdigest()[:10]
