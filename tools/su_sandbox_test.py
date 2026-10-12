"""Exercise a pack's install.ps1 / restore.ps1 against a throw-away copy of the game's files.
The real game directory is only READ (to copy boot.config, catalog.hash and the bundles the manifest names).

usage: python su_sandbox_test.py PACK_DIR [--base pristine|old|build1|plus|stacked]
  --base plus     : the Plus main pack is installed (for add-ons built on it, e.g. MapLabels)
  --base stacked  : the pack named by each entry's requires_pack is installed (e.g. ProgramText for ProgramWords)
  --base pristine : sandbox starts with the original game files (an add-on with requires_pack must REFUSE to install: T0)
  --base old      : sandbox starts with the old stable pack's files where it patched them (tests also_accept_sha256)
  --base build1   : sandbox starts with the files of the pack folder currently delivered at the workspace root
                    (an earlier build of the same release; run BEFORE replacing that folder)
"""
import sys, shutil, subprocess, locale, glob, argparse
from lib_su import *

ap = argparse.ArgumentParser()
ap.add_argument("pack")
ap.add_argument("--base", default="pristine", choices=["pristine", "old", "build1", "plus", "stacked"])
ap.add_argument("--prev", default=os.path.join(ROOT, "Suzerain_CN_Plus_SteamWin_2026-10-10"),
                help="folder of the EARLIER build used by --base build1 (default: the pack folder at the workspace root)")
# plus: sandbox starts with the Plus MAIN pack installed (its copy of every bundle it patches, pristine files otherwise);
#       with 'pristine' a pack that lists requires_pack entries must REFUSE to install (tested below)
a = ap.parse_args()
PACK = a.pack
man = json.load(open(os.path.join(PACK, "patch_manifest.json"), encoding="utf-8-sig"))
SB = os.path.join(WORK, "sandbox", "game")
LOG = open(os.path.join(WORK, "out", f"sandbox_{man['variant']}_{a.base}.txt"), "w", encoding="utf-8")
fails = []


def P(*x):
    print(*x, file=LOG)
    LOG.flush()


def check(cond, msg):
    P(("ok    " if cond else "FAIL  ") + msg)
    if not cond:
        fails.append(msg)


def ps(script, *args):
    # this tool's shell is PowerShell 7: its PSModulePath makes a child Windows PowerShell 5.1 fail to autoload
    # Microsoft.PowerShell.Utility (Get-FileHash not found). A user double-clicking install.bat has the default environment.
    env = {k: v for k, v in os.environ.items() if k.upper() != "PSMODULEPATH"}
    p = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", os.path.join(PACK, script),
                        "-GameRoot", SB, *args], capture_output=True, stdin=subprocess.DEVNULL, env=env)
    enc = locale.getpreferredencoding(False)
    return p.returncode, (p.stdout.decode(enc, "replace") + p.stderr.decode(enc, "replace"))


def sha(p):
    return sha256_file(p)


# ---- build the sandbox
if os.path.isdir(lp(SB)):
    shutil.rmtree(lp(SB))
os.makedirs(lp(os.path.join(SB, "Suzerain_Data", "StreamingAssets", "aa", "StandaloneWindows64")))
shutil.copyfile(os.path.join(GAME, "Suzerain_Data", "boot.config"), os.path.join(SB, "Suzerain_Data", "boot.config"))
shutil.copyfile(os.path.join(GAME, "Suzerain_Data", "StreamingAssets", "aa", "catalog.hash"),
                os.path.join(SB, "Suzerain_Data", "StreamingAssets", "aa", "catalog.hash"))
open(os.path.join(SB, "Suzerain.exe"), "wb").close()
base = {}
PLUS_FILES = {f["file_name"]: f for f in json.load(open(os.path.join(ROOT, "Suzerain_CN_Plus_SteamWin_2026-10-10", "patch_manifest.json"),
                                                         encoding="utf-8-sig"))["files"]}
for f in man["files"]:
    name = f["file_name"]
    # relative_path is relative to the game root, so this also works for a non-bundle file (e.g. global-metadata.dat)
    src = os.path.join(AA_OLD, name) if a.base == "old" and os.path.exists(lp(os.path.join(AA_OLD, name))) else os.path.join(GAME, f["relative_path"])
    if a.base == "build1":
        b1 = os.path.join(a.prev, f["relative_path"])
        assert os.path.exists(lp(b1)), b1
        src = b1
    if a.base == "plus":
        plus_files = PLUS_FILES
        if name in plus_files:
            src = os.path.join(ROOT, "Suzerain_CN_Plus_SteamWin_2026-10-10", plus_files[name]["relative_path"])
    if a.base == "stacked" and f.get("requires_pack"):
        # the pack this one is built on (e.g. ProgramText for ProgramWords) is installed: its delivered copy of the file
        src = os.path.join(ROOT, f["requires_pack"], f["relative_path"])
        assert os.path.exists(lp(src)), src
    dst = os.path.join(SB, f["relative_path"])
    os.makedirs(os.path.dirname(lp(dst)), exist_ok=True)
    shutil.copyfile(lp(src), lp(dst))
    base[name] = sha(dst)
P(f"pack {man['release_name']} variant={man['variant']} files={len(man['files'])} base={a.base}")
same_as_pack = {f["file_name"] for f in man["files"] if base[f["file_name"]] == f["patched_sha256"]}     # already this pack's version
replaced = [f for f in man["files"] if f["file_name"] not in same_as_pack]
P("base states: original =", sum(1 for f in man["files"] if base[f["file_name"]] == f["original_sha256"]),
  "| earlier patch (also_accept) =", sum(1 for f in man["files"] if base[f["file_name"]] in f.get("also_accept_sha256", [])),
  "| already identical to this pack =", len(same_as_pack),
  "| other =", sum(1 for f in man["files"] if base[f["file_name"]] != f["original_sha256"]
                   and base[f["file_name"]] not in f.get("also_accept_sha256", []) and f["file_name"] not in same_as_pack))


def states():
    return {f["file_name"]: sha(os.path.join(SB, f["relative_path"])) for f in man["files"]}


def backups():
    return sorted(glob.glob(os.path.join(lp(SB), "_patch_backup", man["variant"] + "_*")))


# ---- T0 (packs that need the main pack): on a game WITHOUT the main pack the installer must refuse and change nothing
need_main = [f for f in man["files"] if f.get("requires_pack")]
if a.base == "pristine" and need_main:
    before = states()
    rc, out = ps("install.ps1")
    P("--- T0 install without the main pack rc", rc)
    P(out[-900:])
    check(rc != 0 and "Unexpected file hashes" in out, "T0 install refuses when the main pack is missing")
    check(out.count(" => ") == len(need_main) and all(f["relative_path"].split("\\")[-1] in out for f in need_main),
          f"T0 the message names exactly the {len(need_main)} files that need the main pack ({out.count(' => ')} listed)")
    check(states() == before, "T0 no file changed")
    check(len(backups()) == 0, "T0 no backup directory created")
    P("\nFAILS:", len(fails))
    for f in fails:
        P("  ", f)
    print("fails:", len(fails))
    shutil.rmtree(lp(os.path.join(WORK, "sandbox")), ignore_errors=True)
    sys.exit(0)


# ---- T1 install
rc, out = ps("install.ps1")
P("--- T1 install rc", rc)
P(out[-600:])
check(rc == 0, "T1 install exits 0")
st = states()
check(all(st[f["file_name"]] == f["patched_sha256"] for f in man["files"]), "T1 every file now has the patched hash")
bk = backups()
check(len(bk) == 1, f"T1 exactly one backup dir ({len(bk)})")
if bk:
    ok = True
    for f in replaced:
        bp = os.path.join(bk[0], f["relative_path"])
        if not os.path.exists(lp(bp)) or sha(bp) != base[f["file_name"]]:
            ok = False
    check(ok, f"T1 backup holds the pre-install state of each of the {len(replaced)} replaced files")
    check(not any(os.path.exists(lp(os.path.join(bk[0], f["relative_path"]))) for f in man["files"] if f["file_name"] in same_as_pack),
          "T1 files that were already identical were not backed up")
    check(os.path.exists(os.path.join(bk[0], "install_record.json")), "T1 install_record.json written")

# ---- T2 install again
rc, out = ps("install.ps1")
P("--- T2 install again rc", rc)
check(rc == 0, "T2 second install exits 0")
check("Nothing to install" in out, "T2 reports nothing to install")
check(len(backups()) == 1, "T2 no extra backup created")

# ---- T3 restore
rc, out = ps("restore.ps1") if os.path.exists(os.path.join(PACK, "restore.ps1")) else (None, "")
if rc is None:
    P("--- T3..T6 skipped: pack has no restore.ps1")
else:
    P("--- T3 restore rc", rc)
    P(out[-400:])
    check(rc == 0, "T3 restore exits 0")
    st = states()
    check(all(st[f["file_name"]] == base[f["file_name"]] for f in man["files"]), "T3 every file is back to its pre-install state")
    # ---- T4 restore again
    rc, out = ps("restore.ps1")
    P("--- T4 restore again rc", rc)
    check(rc == 0, "T4 second restore exits 0")
    check(out.count("[Skip]") == len(man["files"]), f"T4 all files skipped ({out.count('[Skip]')})")
    # ---- T5 reinstall, damage one file, install / restore behaviour with an unknown file
    rc, out = ps("install.ps1")
    check(rc == 0, "T5 reinstall exits 0")
    victim = replaced[0]
    vp = os.path.join(SB, victim["relative_path"])
    with open(lp(vp), "ab") as fh:
        fh.write(b"\0")
    dam = sha(vp)
    rc, out = ps("install.ps1")
    P("--- T5 install with an unknown file rc", rc)
    check(rc == 1 and "Unexpected file hashes" in out, "T5 install refuses an unknown file")
    check(sha(vp) == dam, "T5 unknown file untouched by install")
    rc, out = ps("restore.ps1")
    P("--- T5 restore with an unknown file rc", rc)
    check(rc == 1, "T5 restore reports the unknown file (exit 1)")
    check(sha(vp) == dam, "T5 restore leaves the unknown file alone")
    st = states()
    others = [f for f in man["files"] if f is not victim]
    check(all(st[f["file_name"]] == base[f["file_name"]] for f in others), "T5 the other files were restored")
    rc, out = ps("restore.ps1", "-Force")
    P("--- T5 restore -Force rc", rc)
    check(rc == 0 and sha(vp) == base[victim["file_name"]], "T5 restore -Force restores the unknown file from backup")
    # ---- T6 wrong build: nothing may change
    shutil.copyfile(os.path.join(SB, "Suzerain_Data", "StreamingAssets", "aa", "catalog.hash"), os.path.join(WORK, "sandbox", "catalog.hash.bak"))
    with open(os.path.join(SB, "Suzerain_Data", "StreamingAssets", "aa", "catalog.hash"), "w") as fh:
        fh.write("00000000000000000000000000000000")
    before = states()
    rc, out = ps("install.ps1")
    P("--- T6 wrong catalog.hash rc", rc)
    check(rc != 0, "T6 install aborts on a different game build")
    check(states() == before, "T6 no file changed")

P("\nFAILS:", len(fails))
for f in fails:
    P("  ", f)
print("fails:", len(fails))
shutil.rmtree(lp(os.path.join(WORK, "sandbox")), ignore_errors=True)
