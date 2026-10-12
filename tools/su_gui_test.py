"""End-to-end test of the GUI installer (Installer.ps1) against a throw-away copy of the game's files.
The real game directory is only READ (boot.config, catalog.hash and the bundles the manifests name are copied out).

usage: python su_gui_test.py [--no-gui] [--keep]
  --no-gui : only the headless scenarios (no WinForms window)
  --keep   : keep the sandbox when finished

What is checked (hashes of EVERY file any pack touches are compared with the state that must follow from the
operations performed, so a wrong layering / wrong restore order shows up as a hash mismatch):
  H0-H11  headless scenarios: status, install with auto-added dependency, restore with auto-included dependents,
          install all, partial restore, restore all, no-op restore, damaged / missing game files (must be refused,
          nothing changed), partial install repair, wrong game version (must be refused, nothing changed)
  H13-H15 a stacked add-on that replaces the SAME file as its base (programwords on programtext): auto-added base, restoring only the
          add-on gives back the base's version, restoring the base first auto-includes the add-on
  G1-G5   the same engine driven through the real WinForms window (-SelfTest: same handlers as the buttons, no dialogs),
          with screenshots, plus the two .bat launchers
"""
import os, sys, json, shutil, subprocess, hashlib, locale, glob, time, argparse

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.abspath(os.environ.get("SUZERAIN_OUT") or os.path.join(_REPO, "out"))      # folder holding the built packs + the installer folder
WORK = os.path.abspath(os.environ.get("SUZERAIN_WORK") or os.path.join(_REPO, "_work"))
GAME = os.environ.get("SUZERAIN_GAME")                                                   # the game is only READ (files are copied into a sandbox)
if not GAME:
    sys.exit("set the SUZERAIN_GAME environment variable to your Suzerain install folder")
INST_DIR = os.path.join(ROOT, "Suzerain_CN_Plus_Installer_SteamWin_2026-10-10")
INST = os.path.join(INST_DIR, "Installer.ps1")
BAT = os.path.join(INST_DIR, "启动安装器.bat")
BAT_DBG = os.path.join(INST_DIR, "启动安装器（调试，显示控制台）.bat")
SB_ROOT = os.path.join(WORK, "sandbox_gui")
SB = os.path.join(SB_ROOT, "game")
OUTDIR = os.path.join(WORK, "out", "gui_test")
REPORT = os.path.join(WORK, "out", "gui_test_report.txt")
ORDER = ["plus", "maplabels", "tutorialimg", "sceneui", "programtext", "programwords"]      # install order (= layering order)

ap = argparse.ArgumentParser()
ap.add_argument("--no-gui", action="store_true")
ap.add_argument("--keep", action="store_true")
ap.add_argument("--gui-only", action="store_true", help="skip the headless H-series (the sandbox is still rebuilt)")
args = ap.parse_args()


def lp(p):
    p = os.path.abspath(p)
    return p if p.startswith("\\\\?\\") else "\\\\?\\" + p


def sha(p):
    h = hashlib.sha256()
    with open(lp(p), "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest().lower()


def key(rp):
    return rp.replace("/", "\\").lower()


os.makedirs(OUTDIR, exist_ok=True)
REP = open(REPORT, "w", encoding="utf-8")
fails = []


def P(*x):
    s = " ".join(str(i) for i in x)
    print(s, file=REP)
    REP.flush()


def check(cond, msg):
    P(("ok    " if cond else "FAIL  ") + msg)
    if not cond:
        fails.append(msg)
    return cond


# ---------------------------------------------------------------- packs
MAN = {}
for d in sorted(glob.glob(os.path.join(ROOT, "Suzerain_CN_Plus_*"))):
    mp = os.path.join(d, "patch_manifest.json")
    if os.path.isfile(mp):
        m = json.load(open(mp, encoding="utf-8-sig"))
        MAN[m["variant"]] = (d, m)
assert set(MAN) == set(ORDER), sorted(MAN)
TOTAL = {v: len(MAN[v][1]["files"]) for v in ORDER}
P("packs:", {v: (os.path.basename(MAN[v][0]), TOTAL[v]) for v in ORDER})

# ---------------------------------------------------------------- sandbox
PRISTINE = {}      # key(relative_path) -> sha256 of the original game file
TRACKED = {}       # key(relative_path) -> relative_path


def build_sandbox():
    if os.path.isdir(lp(SB_ROOT)):
        shutil.rmtree(lp(SB_ROOT))
    for rel in [r"Suzerain_Data\boot.config", r"Suzerain_Data\StreamingAssets\aa\catalog.hash"]:
        dst = os.path.join(SB, rel)
        os.makedirs(os.path.dirname(lp(dst)), exist_ok=True)
        shutil.copyfile(os.path.join(GAME, rel), dst)
    open(os.path.join(SB, "Suzerain.exe"), "wb").close()
    for v in ORDER:
        for f in MAN[v][1]["files"]:
            rp = f["relative_path"]
            k = key(rp)
            if k in PRISTINE:
                continue
            dst = os.path.join(SB, rp)
            os.makedirs(os.path.dirname(lp(dst)), exist_ok=True)
            shutil.copyfile(lp(os.path.join(GAME, rp)), lp(dst))
            PRISTINE[k] = sha(dst)
            TRACKED[k] = rp
    # the real game files must be the ORIGINAL ones (otherwise the whole test says nothing)
    bad = 0
    for v in ORDER:
        for f in MAN[v][1]["files"]:
            h = PRISTINE[key(f["relative_path"])]
            if f.get("requires_pack"):
                bm = [m_ for (d_, m_) in MAN.values() if m_["release_name"] == f["requires_pack"]][0]
                base = {x["file_name"]: x for x in bm["files"]}[f["file_name"]]
                ok = (h == base["original_sha256"].lower())
            else:
                ok = (h == f["original_sha256"].lower())
            bad += 0 if ok else 1
    check(bad == 0, f"sandbox starts from the original game files ({len(PRISTINE)} distinct files, {bad} not original)")


def snapshot():
    return {k: sha(os.path.join(SB, rp)) if os.path.isfile(lp(os.path.join(SB, rp))) else "MISSING" for k, rp in TRACKED.items()}


def expected(installed):
    exp = dict(PRISTINE)
    for v in ORDER:                      # layering order: later packs overwrite earlier ones on shared files
        if v in installed:
            for f in MAN[v][1]["files"]:
                exp[key(f["relative_path"])] = f["patched_sha256"].lower()
    return exp


def diff_state(label, exp, snap=None):
    snap = snap or snapshot()
    bad = [k for k in exp if snap.get(k) != exp[k]]
    check(not bad, f"{label}: all {len(exp)} tracked game files have the expected hash" + (f"  ({len(bad)} differ, e.g. {bad[:2]})" if bad else ""))
    return not bad


def backups(variant):
    return sorted(glob.glob(os.path.join(lp(SB), "_patch_backup", variant + "_*")))


# ---------------------------------------------------------------- running the installer
def run_ps(argv, timeout=2400):
    env = {k: v for k, v in os.environ.items() if k.upper() != "PSMODULEPATH"}   # see su_sandbox_test.py: tool-shell artefact
    cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-STA", "-File", INST, *argv]
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, stdin=subprocess.DEVNULL, env=env, timeout=timeout)
    enc = locale.getpreferredencoding(False)
    return p.returncode, p.stdout.decode(enc, "replace") + p.stderr.decode(enc, "replace"), time.time() - t0


def run_mode(label, scenario, mode="headless", yes=True):
    j = os.path.join(OUTDIR, f"{label}.json")
    if os.path.exists(j):
        os.remove(j)
    a = ["-GameRoot", SB, "-Scenario", scenario, "-OutJson", j, "-LogDir", os.path.join(OUTDIR, "logs")]
    if mode == "headless":
        a = ["-Headless"] + a + (["-Yes"] if yes else [])
    else:
        shots = os.path.join(OUTDIR, "shots_" + label)
        if os.path.isdir(shots):
            shutil.rmtree(shots)
        a = ["-SelfTest", "-ScreenshotDir", shots] + a
    rc, out, dt = run_ps(a)
    data = json.load(open(j, encoding="utf-8")) if os.path.exists(j) else None
    P(f"\n=== {label}  [{mode}] scenario='{scenario}'  rc={rc}  {dt:.0f}s")
    P(out.strip()[-3500:])
    return rc, out, data


def step(data, i):
    return data["steps"][i]


def codes(entry):
    return {v: s["code"] for v, s in entry["status"].items()}


def counts(entry):
    return {v: (s["installed"], s["total"]) for v, s in entry["status"].items()}


# ================================================================= tests
build_sandbox()
ALL = set(ORDER)

if not args.gui_only:
    # ---- H0 status on the pristine game
    rc, out, d = run_mode("H0_status", "status", yes=False)
    check(rc == 0 and d is not None, "H0 headless status runs (rc 0, JSON written)")
    if d:
        c = codes(step(d, 0))
        check(c == {"plus": "none", "maplabels": "needbase", "tutorialimg": "none", "sceneui": "none", "programtext": "none", "programwords": "needbase"},
              f"H0 pristine game: statuses = {c}")
        txt = {v: s["text"] for v, s in step(d, 0)["status"].items()}
        check(txt["maplabels"] == "未安装（需先装主汉化包）" and txt["programwords"] == "未安装（需先装程序内文案包）",
              f"H0 the needbase text names the component it must be stacked on: {txt['maplabels']} / {txt['programwords']}")
        check({v: t for v, (i, t) in counts(step(d, 0)).items()} == TOTAL, "H0 file counts per component match the manifests")
    diff_state("H0", expected(set()))

    # ---- H1 install the map labels only: the main pack must be added automatically and installed first
    rc, out, d = run_mode("H1_install_maplabels", "install:maplabels")
    check(rc == 0 and d is not None and d["ok"], "H1 install:maplabels succeeds")
    if d:
        s1 = step(d, 1)
        check(s1["plan"] == ["plus", "maplabels"] and s1["added"] == ["plus"] and s1["blockers"] == [],
              f"H1 plan = {s1['plan']} (auto-added {s1['added']}, blockers {s1['blockers']})")
        check(codes(s1) == {"plus": "installed", "maplabels": "installed", "tutorialimg": "none", "sceneui": "none", "programtext": "none", "programwords": "needbase"},
              f"H1 statuses after = {codes(s1)}")
    diff_state("H1", expected({"plus", "maplabels"}))
    check(len(backups("plus")) == 1 and len(backups("maplabels")) == 1, "H1 one backup folder each for plus and maplabels")

    # ---- H2 restore the main pack: the map labels sit on top of it and must be restored FIRST (automatically)
    rc, out, d = run_mode("H2_restore_plus", "restore:plus")
    check(rc == 0 and d is not None and d["ok"], "H2 restore:plus succeeds")
    if d:
        s1 = step(d, 1)
        check(s1["plan"] == ["maplabels", "plus"] and s1["added"] == ["maplabels"],
              f"H2 plan = {s1['plan']} (auto-included {s1['added']})")
        check(codes(s1) == {"plus": "none", "maplabels": "needbase", "tutorialimg": "none", "sceneui": "none", "programtext": "none", "programwords": "needbase"},
              f"H2 statuses after = {codes(s1)}")
    diff_state("H2 (back to original)", expected(set()))

    # ---- H3 install everything
    rc, out, d = run_mode("H3_install_all", "install:*")
    check(rc == 0 and d is not None and d["ok"], "H3 install:* succeeds")
    if d:
        s1 = step(d, 1)
        check(s1["plan"] == ORDER, f"H3 plan order = {s1['plan']}")
        check(all(v == "installed" for v in codes(s1).values()), f"H3 statuses after = {codes(s1)}")
    diff_state("H3 (everything installed)", expected(ALL))

    # ---- H4 restore only the map labels: the shared files must return to the MAIN pack's version, not to the original
    rc, out, d = run_mode("H4_restore_maplabels", "restore:maplabels")
    check(rc == 0 and d is not None and d["ok"], "H4 restore:maplabels succeeds")
    if d:
        s1 = step(d, 1)
        check(s1["plan"] == ["maplabels"] and s1["added"] == [], f"H4 plan = {s1['plan']}")
        check(codes(s1) == {"plus": "installed", "maplabels": "none", "tutorialimg": "installed", "sceneui": "installed", "programtext": "installed", "programwords": "installed"},
              f"H4 statuses after = {codes(s1)}")
    diff_state("H4 (all except maplabels)", expected(ALL - {"maplabels"}))

    # ---- H5 install the map labels again on top of the installed main pack (main pack must NOT be re-run)
    rc, out, d = run_mode("H5_install_maplabels_again", "install:maplabels")
    check(rc == 0 and d is not None and d["ok"], "H5 install:maplabels (main pack already there) succeeds")
    if d:
        s1 = step(d, 1)
        check(s1["plan"] == ["maplabels"] and s1["added"] == [] and s1["skipped"] == ["plus"] or s1["plan"] == ["maplabels"] and s1["added"] == [],
              f"H5 plan = {s1['plan']} skipped={s1['skipped']} added={s1['added']}")
    diff_state("H5 (everything installed again)", expected(ALL))

    # ---- H6 restore all
    rc, out, d = run_mode("H6_restoreall", "restoreall")
    check(rc == 0 and d is not None and d["ok"], "H6 restoreall succeeds")
    if d:
        s1 = step(d, 1)
        check(s1["plan"] == list(reversed(ORDER)), f"H6 plan order = {s1['plan']}")
    diff_state("H6 (restore all => original)", expected(set()))

    # ---- H7 restoring something that is not installed is a no-op
    rc, out, d = run_mode("H7_restore_noop", "restore:sceneui")
    check(rc == 0 and d is not None and d["ok"] and step(d, 1)["plan"] == [], "H7 restore of a not-installed component: empty plan, rc 0")
    diff_state("H7 (unchanged)", expected(set()))

    # ---- H8 a damaged game file: install must be refused and nothing may change
    victim = TRACKED[key(MAN["tutorialimg"][1]["files"][0]["relative_path"])]
    vpath = os.path.join(SB, victim)
    with open(lp(vpath), "ab") as f:
        f.write(b"x")
    snap0 = snapshot()
    nb0 = len(backups("tutorialimg"))
    rc, out, d = run_mode("H8_damaged", "install:tutorialimg")
    check(rc != 0 and d is not None and not d["ok"], f"H8 install is refused (rc {rc})")
    if d:
        s1 = step(d, 1)
        check(len(s1["blockers"]) >= 1 and s1["status"]["tutorialimg"]["code"] == "mismatch",
              f"H8 blocker reported, tutorialimg status = {s1['status']['tutorialimg']['code']}")
    check(snapshot() == snap0, "H8 nothing changed (the damaged file was not touched, no other file either)")
    check(len(backups("tutorialimg")) == nb0, f"H8 no new backup folder created ({nb0} -> {len(backups('tutorialimg'))})")
    shutil.copyfile(lp(os.path.join(GAME, victim)), lp(vpath))
    diff_state("H8 healed", expected(set()))

    # ---- H9 a missing game file
    victim = TRACKED[key(MAN["sceneui"][1]["files"][0]["relative_path"])]
    vpath = os.path.join(SB, victim)
    os.remove(lp(vpath))
    nb0 = len(backups("sceneui"))
    rc, out, d = run_mode("H9_missing", "install:sceneui")
    check(rc != 0 and d is not None and not d["ok"], f"H9 install is refused (rc {rc})")
    if d:
        s1 = step(d, 1)
        check(s1["status"]["sceneui"]["code"] == "missing", f"H9 sceneui status = {s1['status']['sceneui']['code']}")
    check(len(backups("sceneui")) == nb0, f"H9 no new backup folder created ({nb0} -> {len(backups('sceneui'))})")
    shutil.copyfile(lp(os.path.join(GAME, victim)), lp(vpath))
    diff_state("H9 healed", expected(set()))

    # ---- H10 half-installed state (one file back to original): status says partial, installing again repairs it
    rc, out, d = run_mode("H10a_install_plus", "install:plus")
    check(rc == 0 and d is not None and d["ok"], "H10 install:plus succeeds")
    victim = TRACKED[key(MAN["plus"][1]["files"][5]["relative_path"])]
    shutil.copyfile(lp(os.path.join(GAME, victim)), lp(os.path.join(SB, victim)))
    rc, out, d = run_mode("H10b_partial", "status", yes=False)
    if d:
        c = step(d, 0)["status"]["plus"]
        check(c["code"] == "partial" and c["installed"] == TOTAL["plus"] - 1, f"H10 partial detected: {c['code']} {c['installed']}/{c['total']}")
    rc, out, d = run_mode("H10c_repair", "install:plus")
    check(rc == 0 and d is not None and d["ok"], "H10 install:plus on a partial state succeeds")
    diff_state("H10 repaired", expected({"plus"}))
    rc, out, d = run_mode("H10d_restoreall", "restoreall")
    check(rc == 0 and d is not None and d["ok"], "H10 restoreall succeeds")
    diff_state("H10 (original again)", expected(set()))

    # ---- H11 wrong game version (catalog.hash changed): the packs' own scripts must refuse, nothing changes
    cat = os.path.join(SB, r"Suzerain_Data\StreamingAssets\aa\catalog.hash")
    orig_cat = open(cat, "rb").read()
    open(cat, "wb").write(b"0" * 32)
    snap0 = snapshot()
    rc, out, d = run_mode("H11_version", "install:plus")
    check(rc != 0, f"H11 install under a different game version is refused (rc {rc})")
    check(snapshot() == snap0, "H11 nothing changed")
    open(cat, "wb").write(orig_cat)
    diff_state("H11 (unchanged)", expected(set()))

    # ---- H12 a game that still has the OLD stable pack installed (the user may well have used it before):
    #      the main pack must install over it, SceneUI (the old pack ships unchanged scene files) must install too, and restoring
    #      must give back exactly the old pack's files (= the state before each install).  Starts WITHOUT earlier backups:
    #      restore.ps1 picks, per file, the newest backup that holds a clean copy, so leftovers of earlier tests would be picked up.
    shutil.rmtree(lp(os.path.join(SB, "_patch_backup")), ignore_errors=True)
    LEG_DIR = os.path.abspath(os.environ.get("SUZERAIN_BASE") or os.path.join(WORK, "base", "Suzerain_CN_Stable_SteamWin_2026-06-10"))
    leg = json.load(open(os.path.join(LEG_DIR, "patch_manifest.json"), encoding="utf-8-sig"))
    legacy_hash = {}
    for f in leg["files"]:
        src = os.path.join(LEG_DIR, f["relative_path"])
        dst = os.path.join(SB, f["relative_path"])
        shutil.copyfile(lp(src), lp(dst))
        legacy_hash[key(f["relative_path"])] = sha(dst)
    check(all(k in TRACKED for k in legacy_hash), f"H12 the old pack's {len(legacy_hash)} files are all among the files the new packs track")
    snap_leg = snapshot()
    rc, out, d = run_mode("H12a_legacy_status", "status", yes=False)
    if d:
        cs = codes(step(d, 0))
        check(cs["plus"] not in ("mismatch", "missing"), f"H12 old pack installed: plus status = {cs['plus']} (must be installable)")
        check(cs["sceneui"] == "none", f"H12 old pack installed: sceneui status = {cs['sceneui']} (the old pack ships its 3 scene files unchanged)")
    rc, out, d = run_mode("H12b_install_over_legacy", "install:plus")
    check(rc == 0 and d is not None and d["ok"], f"H12 install:plus over the old pack succeeds (rc {rc})")
    exp = expected({"plus"})
    for k, h in legacy_hash.items():          # files the old pack changed that the main pack does not touch stay as the old pack left them
        if k not in {key(f["relative_path"]) for f in MAN["plus"][1]["files"]}:
            exp[k] = h
    diff_state("H12 (main pack over the old pack)", exp)
    rc, out, d = run_mode("H12c_sceneui_over_legacy", "install:sceneui")
    check(rc == 0 and d is not None and d["ok"], f"H12 sceneui installs over the old pack (rc {rc})")
    exp2 = dict(exp)
    for f in MAN["sceneui"][1]["files"]:
        exp2[key(f["relative_path"])] = f["patched_sha256"].lower()
    diff_state("H12 (main pack + sceneui over the old pack)", exp2)
    rc, out, d = run_mode("H12d_restoreall", "restoreall")
    check(rc == 0 and d is not None and d["ok"], f"H12 restoreall succeeds (rc {rc})")
    diff_state("H12 (restore gives the old pack's files back, exactly)", dict(snap_leg), snapshot())
    for f in leg["files"]:                      # back to the original game for the following tests
        shutil.copyfile(lp(os.path.join(GAME, f["relative_path"])), lp(os.path.join(SB, f["relative_path"])))
    shutil.rmtree(lp(os.path.join(SB, "_patch_backup")), ignore_errors=True)
    diff_state("H12 healed", expected(set()))

    # ---- H13 stacked add-on: programwords sits on programtext and both replace the SAME file.  Selecting only the add-on must add its
    #      base automatically and install it first; the final file is the add-on's version; the base then reports "installed" (covered by the add-on)
    rc, out, d = run_mode("H13_install_programwords", "install:programwords")
    check(rc == 0 and d is not None and d["ok"], "H13 install:programwords succeeds")
    if d:
        s1 = step(d, 1)
        check(s1["plan"] == ["programtext", "programwords"] and s1["added"] == ["programtext"] and s1["blockers"] == [],
              f"H13 plan = {s1['plan']} (auto-added {s1['added']}, blockers {s1['blockers']})")
        cs = codes(s1)
        check(cs == {"plus": "none", "maplabels": "needbase", "tutorialimg": "none", "sceneui": "none", "programtext": "installed", "programwords": "installed"},
              f"H13 statuses after = {cs}")
    diff_state("H13", expected({"programtext", "programwords"}))
    check(len(backups("programtext")) == 1 and len(backups("programwords")) == 1, "H13 one backup folder each for programtext and programwords")

    # ---- H14 restore only the add-on: the file goes back to the BASE's version (programtext stays installed), not to the original
    rc, out, d = run_mode("H14_restore_programwords", "restore:programwords")
    check(rc == 0 and d is not None and d["ok"], "H14 restore:programwords succeeds")
    if d:
        s1 = step(d, 1)
        check(s1["plan"] == ["programwords"] and s1["added"] == [], f"H14 plan = {s1['plan']} added={s1['added']}")
        cs = codes(s1)
        check(cs["programtext"] == "installed" and cs["programwords"] == "none", f"H14 statuses after = {cs}")
    diff_state("H14 (programtext only)", expected({"programtext"}))

    # ---- H15 install the add-on again on the installed base (the base must NOT be re-run), then restore the BASE: the add-on has to be
    #      restored first, automatically, and the file must end up original
    rc, out, d = run_mode("H15a_install_programwords_again", "install:programwords")
    check(rc == 0 and d is not None and d["ok"], "H15 install:programwords (base already installed) succeeds")
    if d:
        s1 = step(d, 1)
        check(s1["plan"] == ["programwords"] and s1["added"] == [], f"H15 plan = {s1['plan']} added={s1['added']}")
    diff_state("H15 (both installed)", expected({"programtext", "programwords"}))
    rc, out, d = run_mode("H15b_restore_programtext", "restore:programtext")
    check(rc == 0 and d is not None and d["ok"], "H15 restore:programtext succeeds")
    if d:
        s1 = step(d, 1)
        check(s1["plan"] == ["programwords", "programtext"] and s1["added"] == ["programwords"],
              f"H15 plan = {s1['plan']} (auto-included {s1['added']})")
        check(codes(s1)["programtext"] == "none" and codes(s1)["programwords"] == "needbase", f"H15 statuses after = {codes(s1)}")
    diff_state("H15 (back to original)", expected(set()))
    shutil.rmtree(lp(os.path.join(SB, "_patch_backup")), ignore_errors=True)

# ================================================================= GUI (WinForms) through -SelfTest
if not args.no_gui:
    rc, out, d = run_mode("G1_gui_install_maplabels", "install:maplabels", mode="gui")
    check(rc == 0 and d is not None and d["ok"], f"G1 GUI install:maplabels (rc {rc})")
    if d:
        check(len(d["steps"]) == 2 and d["steps"][1]["ok"], "G1 step reported ok")
        check(codes(step(d, 1)).get("plus") == "installed" and codes(step(d, 1)).get("maplabels") == "installed", f"G1 statuses = {codes(step(d, 1))}")
    diff_state("G1", expected({"plus", "maplabels"}))
    shots = sorted(os.listdir(os.path.join(OUTDIR, "shots_G1_gui_install_maplabels"))) if os.path.isdir(os.path.join(OUTDIR, "shots_G1_gui_install_maplabels")) else []
    check(len(shots) >= 2, f"G1 screenshots: {shots}")

    rc, out, d = run_mode("G2_gui_restore_plus_then_install", "restore:plus;install:plus,tutorialimg", mode="gui")
    check(rc == 0 and d is not None and d["ok"], f"G2 GUI restore:plus (auto-includes maplabels) then install:plus,tutorialimg (rc {rc})")
    diff_state("G2", expected({"plus", "tutorialimg"}))

    victim = TRACKED[key(MAN["sceneui"][1]["files"][0]["relative_path"])]
    with open(lp(os.path.join(SB, victim)), "ab") as f:
        f.write(b"x")
    snap0 = snapshot()
    rc, out, d = run_mode("G3_gui_blocked", "install:sceneui", mode="gui")
    check(d is not None and len(d["steps"]) == 2 and d["steps"][1]["ok"] is False and d["steps"][1].get("blocked") is True,
          "G3 GUI refuses to install onto a damaged file (blocked, no dialog needed)")
    check(snapshot() == snap0, "G3 nothing changed")
    shutil.copyfile(lp(os.path.join(GAME, victim)), lp(os.path.join(SB, victim)))

    rc, out, d = run_mode("G4_gui_restoreall", "restoreall", mode="gui")
    check(rc == 0 and d is not None and d["ok"], f"G4 GUI restoreall (rc {rc})")
    diff_state("G4 (original again)", expected(set()))

    # launchers
    j = os.path.join(OUTDIR, "G5_bat.json")
    if os.path.exists(j):
        os.remove(j)
    env = {k: v for k, v in os.environ.items() if k.upper() != "PSMODULEPATH"}
    subprocess.Popen(["cmd.exe", "/c", BAT, "-SelfTest", "-GameRoot", SB, "-Scenario", "status", "-OutJson", j,
                      "-LogDir", os.path.join(OUTDIR, "logs")], env=env, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while not os.path.exists(j) and time.time() - t0 < 120:
        time.sleep(1)
    time.sleep(1)
    check(os.path.exists(j) and json.load(open(j, encoding="utf-8"))["ok"], f"G5 启动安装器.bat starts the GUI and passes the arguments ({time.time() - t0:.0f}s)")

    j2 = os.path.join(OUTDIR, "G5_bat_debug.json")
    if os.path.exists(j2):
        os.remove(j2)
    p = subprocess.run(["cmd.exe", "/c", BAT_DBG, "-SelfTest", "-GameRoot", SB, "-Scenario", "status", "-OutJson", j2,
                        "-LogDir", os.path.join(OUTDIR, "logs")], env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=300)
    check(p.returncode == 0 and os.path.exists(j2), f"G5 debug launcher runs synchronously (rc {p.returncode})")

    # ---- U: the REAL window (real MessageBox dialogs, real handlers) clicked through UI Automation
    DRIVER = os.path.join(WORK, "su_gui_uia_driver.ps1")

    def uia(flow):
        jj = os.path.join(OUTDIR, f"U_{flow}.json")
        if os.path.exists(jj):
            os.remove(jj)
        cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-STA", "-File", DRIVER, "-Installer", INST, "-Game", SB,
               "-LogDir", os.path.join(OUTDIR, "logs"), "-ResultJson", jj, "-Flow", flow]
        t0 = time.time()
        pr = subprocess.run(cmd, capture_output=True, stdin=subprocess.DEVNULL, env=env, timeout=900)
        dd = json.load(open(jj, encoding="utf-8")) if os.path.exists(jj) else None
        P(f"\n=== U_{flow}  [real window + UI Automation]  rc={pr.returncode}  {time.time() - t0:.0f}s")
        P(json.dumps(dd, ensure_ascii=False, indent=1)[:5000] if dd else (pr.stdout + pr.stderr).decode(locale.getpreferredencoding(False), "replace")[-2000:])
        return pr.returncode, dd

    def dialogs(dd):
        return [e for e in (dd or {}).get("events", []) if "dialog" in e]

    rcu, dd = uia("install")
    check(rcu == 0 and dd is not None and not dd["errors"] and dd["exit_code"] == 0, f"U1 real window: recommended set installed through the real dialogs, window closed (rc {rcu}, errors {dd and dd['errors']})")
    if dd:
        dl = {e["dialog"]: e["text"] for e in dialogs(dd)}
        check("确认安装" in dl and dl["确认安装"].find("主汉化包") < dl["确认安装"].find("地图中文标注包") < dl["确认安装"].find("战争教程图片包"),
              "U1 the confirmation lists plus -> maplabels -> tutorialimg in that order")
        check("请稍等" in dl, "U1 closing the window while the install runs is refused with a dialog")
    diff_state("U1 (recommended set installed)", expected({"plus", "maplabels", "tutorialimg"}))

    rcu, dd = uia("restoreall")
    check(rcu == 0 and dd is not None and not dd["errors"] and dd["exit_code"] == 0, f"U2 real window: restore all through the real dialogs (rc {rcu}, errors {dd and dd['errors']})")
    if dd:
        dl = {e["dialog"]: e["text"] for e in dialogs(dd)}
        check("请先在列表里勾选要安装的组件" in dl.get("Suzerain 汉化安装器", ""), "U2 installing with nothing ticked only shows the hint box")
        t = dl.get("确认还原（全部）", "")
        check(0 <= t.find("战争教程图片包") < t.find("地图中文标注包") < t.find("主汉化包"), "U2 restore order shown: tutorialimg -> maplabels -> plus (dependents first)")
    diff_state("U2 (original again)", expected(set()))

P("\nFAILS:", len(fails))
for f in fails:
    P("  ", f)
print("fails:", len(fails))
for f in fails:
    print("  ", f)
if not args.keep:
    shutil.rmtree(lp(SB_ROOT), ignore_errors=True)
sys.exit(1 if fails else 0)
