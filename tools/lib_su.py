"""Shared helpers for the Suzerain localization pipeline.

Nothing here is tied to one machine: every location comes from an environment variable (build.py sets them from its
command line), with the defaults below.

  SUZERAIN_GAME  Steam game folder (the one that contains Suzerain.exe)                needed to build
  SUZERAIN_BASE  unpacked base patch folder (Suzerain_CN_Stable_SteamWin_2026-06-10)    needed for the main pack
  SUZERAIN_OUT   where the generated pack folders are written                           default <repo>/out
  SUZERAIN_WORK  scratch: caches, logs, sandboxes                                       default <repo>/_work
  SUZERAIN_FONT  Noto Serif SC variable font (NotoSerifSC-VF.ttf)                       build.py fetches the pinned one (assets/fonts/README.txt) and sets this;
                                                                                         default <repo>/assets/fonts/NotoSerifSC-VF.ttf (a local copy, not in git)

Names are kept from the original scripts: ROOT is the folder that holds the generated pack folders (= SUZERAIN_OUT).
"""
import os, re, io, json, hashlib, pickle, sys
import UnityPy

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, "data")
ROOT = os.path.abspath(os.environ.get("SUZERAIN_OUT") or os.path.join(REPO, "out"))
WORK = os.path.abspath(os.environ.get("SUZERAIN_WORK") or os.path.join(REPO, "_work"))
CACHE = os.path.join(WORK, "cache")
TM_DIR = os.path.join(DATA, "tm")
MAPLAB_DIR = os.path.join(DATA, "maplab")
OLD_PACK = os.path.abspath(os.environ.get("SUZERAIN_BASE") or os.path.join(WORK, "base", "Suzerain_CN_Stable_SteamWin_2026-06-10"))
GAME = os.path.abspath(os.environ["SUZERAIN_GAME"]) if os.environ.get("SUZERAIN_GAME") else r"<SUZERAIN_GAME is not set>"
FONT = os.path.abspath(os.environ.get("SUZERAIN_FONT") or os.path.join(REPO, "assets", "fonts", "NotoSerifSC-VF.ttf"))
AA_REL = r"Suzerain_Data\StreamingAssets\aa\StandaloneWindows64"
AA_GAME = os.path.join(GAME, AA_REL)
AA_OLD = os.path.join(OLD_PACK, AA_REL)

os.makedirs(os.path.join(WORK, "out"), exist_ok=True)      # logs / reports written by the generators
os.makedirs(CACHE, exist_ok=True)

CJK = re.compile(r"[\u4e00-\u9fff]")
WORD = re.compile(r"[A-Za-z][A-Za-z'’\-]*")


def lp(p):
    """Windows long-path prefix."""
    p = os.path.abspath(p)
    return p if p.startswith("\\\\?\\") else "\\\\?\\" + p


def sha256_file(p):
    h = hashlib.sha256()
    with open(lp(p), "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def find_bundle(prefix, base=AA_GAME):
    """Return full path of the unique bundle whose file name starts with prefix."""
    names = [n for n in os.listdir(lp(base)) if n.startswith(prefix)]
    if len(names) != 1:
        raise FileNotFoundError(f"{prefix!r} -> {len(names)} matches in {base}")
    return os.path.join(base, names[0])


def load_env(path):
    """Load a bundle from its raw bytes.  (UnityPy.load(<\\\\?\\ long path>) silently returns an EMPTY environment when the
    path is longer than 260 characters, which made verification of deep pack paths look like 'bundle has 0 objects'.)"""
    with open(lp(path), "rb") as f:
        data = f.read()
    return UnityPy.load(data)


def mb_objects(env):
    for obj in env.objects:
        if obj.type.name == "MonoBehaviour":
            yield obj


def save_bundle(env, out_path, packer="original"):
    """Save a UnityPy environment's bundle to out_path, keeping the original compression by default."""
    data = env.file.save(packer=packer)
    os.makedirs(os.path.dirname(lp(out_path)), exist_ok=True)
    with open(lp(out_path), "wb") as f:
        f.write(data)
    return len(data)


def jdump(obj, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def jload(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)
