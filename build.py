#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Suzerain 汉化补丁构建器  (stdlib only; run it with the Python that has requirements.txt installed)

用你自己的游戏文件 + 旧稳定版补丁 + 本仓库的译文与脚本，生成 6 个补丁包和安装器，并把每个负载文件的 SHA-256
与维护者实测过的构建逐个比对（307 个文件）。本脚本只读取你的游戏目录，从不修改它。

用法（在仓库根目录运行）：
    python build.py --game "D:\\SteamLibrary\\steamapps\\common\\Suzerain"     预检 -> 取旧补丁 -> 构建 -> 校验
    python build.py check  --game "..."      只做预检（不构建）
    python build.py fetch                    只下载并校验旧补丁和字体
    python build.py verify                   只校验 out\\ 里已有的包
选项：--out DIR  --work DIR  --base ZIP或文件夹  --font TTF  --only 包名,...  --rebuild

字体：构建 TutorialImages / MapLabels 需要一个固定版本的 Noto Serif SC（OFL 1.1），它不在 git 仓库里，而是本仓库 Release 的
附件。构建器会自动下载并核对 SHA-256；下载不了时退回官方 2.003 版（输出里有 3 个文件会与实测构建不同，校验会如实列出）。
细节见 assets\\fonts\\README.txt 和 data\\font_source.json。
"""
import argparse, hashlib, json, os, platform, shutil, subprocess, sys, time, urllib.request, zipfile
from concurrent.futures import ThreadPoolExecutor
from importlib import metadata

REPO = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(REPO, "tools")
DATA = os.path.join(REPO, "data")
INSTALLER = "Suzerain_CN_Plus_Installer_SteamWin_2026-10-10"
FONT_NAME = "NotoSerifSC-VF.ttf"
FONT_LOCAL = os.path.join(REPO, "assets", "fonts", FONT_NAME)     # 维护者本机的副本；.gitignore 忽略它，不在仓库里
GAME_CATALOG = os.path.join("Suzerain_Data", "StreamingAssets", "aa", "catalog.hash")

# key, 输出文件夹名, 依赖的包, 依次执行的生成器（"@ALL" = 全部地图名）
PACKS = [
    ("sceneui", "Suzerain_CN_Plus_SceneUI_SteamWin_2026-10-10", [], [["su_build3.py"]]),
    ("programtext", "Suzerain_CN_Plus_ProgramText_SteamWin_2026-10-10", [], [["su_meta_build.py"]]),
    ("programwords", "Suzerain_CN_Plus_ProgramWords_SteamWin_2026-10-10", ["programtext"], [["su_words_build.py", "--final"]]),
    ("plus", "Suzerain_CN_Plus_SteamWin_2026-10-10", [], [["probe_ent_mb.py"], ["su_build.py"]]),
    ("tutorialimages", "Suzerain_CN_Plus_TutorialImages_SteamWin_2026-10-10", [], [["su_build_img.py"]]),
    ("maplabels", "Suzerain_CN_Plus_MapLabels_SteamWin_2026-10-10", ["plus"],
     [["map_export_all.py"], ["map_gloss_src.py"], ["map_run.py", "@ALL"], ["su_build_map.py"]]),
]
LABEL = {"sceneui": "场景界面 SceneUI", "programtext": "程序内文案 ProgramText", "programwords": "程序内单词 ProgramWords",
         "plus": "主包 Plus", "tutorialimages": "教程图 TutorialImages", "maplabels": "地图地名 MapLabels"}

LOG = None


def say(msg=""):
    print(msg, flush=True)
    if LOG:
        LOG.write(msg + "\n")
        LOG.flush()


def die(msg, code=1):
    say("")
    say("【出错】" + msg)
    sys.exit(code)


def lp(p):
    """Windows 长路径前缀（输出里最长的路径有 236 个字符）。"""
    p = os.path.abspath(p)
    if p.startswith("\\\\?\\"):
        return p
    if p.startswith("\\\\"):
        return "\\\\?\\UNC\\" + p[2:]
    return "\\\\?\\" + p


def sha256_file(p):
    h = hashlib.sha256()
    with open(lp(p), "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def jload(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


def fmt_size(n):
    return "%.1f MB" % (n / 1e6)


# ---------------------------------------------------------------- 预检
class Report:
    def __init__(self):
        self.fails, self.warns = [], []

    def ok(self, m):
        say("  [通过] " + m)

    def warn(self, m):
        self.warns.append(m)
        say("  [警告] " + m)

    def fail(self, m):
        self.fails.append(m)
        say("  [失败] " + m)


def read_requirements():
    req = {}
    with open(os.path.join(REPO, "requirements.txt"), encoding="utf-8") as f:
        for line in f:
            line = line.split("#")[0].strip()
            if "==" in line:
                n, v = line.split("==", 1)
                req[n.strip()] = v.strip()
    return req


def check_env(r, a, exp_out):
    say("环境")
    if os.name != "nt":
        r.fail("目前只支持 Windows（生成器使用 Windows 长路径，补丁安装器是 PowerShell）。")
    tested = exp_out["tested_with"]
    pyv = platform.python_version()
    if pyv.split(".")[:2] == tested["python"].split(".")[:2]:
        r.ok("Python %s（实测版本 %s）" % (pyv, tested["python"]))
    else:
        r.warn("Python %s，实测用的是 %s；可以尝试，但无法保证与已测试构建逐字节一致。" % (pyv, tested["python"]))
    missing, differ = [], []
    for name, ver in read_requirements().items():
        try:
            have = metadata.version(name)
        except metadata.PackageNotFoundError:
            missing.append(name)
            continue
        if have != ver:
            differ.append("%s %s（要求 %s）" % (name, have, ver))
    if missing:
        r.fail("缺少依赖：%s。请先运行：python -m pip install -r requirements.txt" % ", ".join(missing))
    elif differ:
        r.warn("依赖版本与实测不同：%s。压缩/渲染结果可能不同，校验步骤会如实报告。" % "；".join(differ))
    else:
        r.ok("依赖版本与实测完全一致")
    if a.font_path:                                   # 用户用 --font 指定了字体
        if not os.path.isfile(a.font_path):
            r.fail("找不到字体文件：" + a.font_path)
        elif sha256_file(a.font_path) == tested["font_sha256"]:
            r.ok("字体与实测一致（%s）" % os.path.basename(a.font_path))
        else:
            r.warn("--font 指定的字体与实测版本不同（见 assets\\fonts\\README.txt）：教程图/地图地名里个别字形可能有几十个像素的差异，"
                   "校验会报告对应文件。")
        return
    local = find_local_font(a, tested["font_sha256"])
    if local:
        r.ok("字体与实测一致（%s）" % local)
        return
    f = jload("font_source.json")["font"]
    if "OWNER/REPO" in f["url"]:
        r.warn("字体的下载地址还没有配置（仓库维护者发布前要填写 data\\font_source.json）；将退回官方 noto-cjk 2.003 版，"
               "构建后校验会有 3 个地图文件与实测不同。")
    else:
        r.ok("字体会在构建时自动下载（%s，本仓库 Release 附件，SHA-256 校验）" % fmt_size(f["size"]))


def find_local_font(a, sha):
    """本机上哈希与实测字体一致的那份（维护者副本或之前下载的缓存），没有则 None。"""
    for p in (FONT_LOCAL, os.path.join(a.work, "fonts", FONT_NAME)):
        if os.path.isfile(p) and sha256_file(p) == sha:
            return p
    return None


def check_paths(r, a, exp_out):
    say("路径与磁盘")
    maxrel = max(len(pk) + 1 + len(rel) for pk, p in exp_out["packs"].items() for rel in p)
    total = len(os.path.abspath(a.out)) + 1 + maxrel
    if total > 259:
        r.warn("输出目录较深：最长文件路径约 %d 个字符（超过 Windows 传统的 259 上限）。构建器和安装器按长路径方式读写，不受影响；"
               "但资源管理器、部分压缩软件处理这些文件可能报错。需要的话用 --out 指向更短的目录，例如 D:\\suz_out。" % total)
    else:
        r.ok("输出路径长度没问题（最长约 %d 个字符）" % total)
    seen = set()
    for d in (a.out, a.work):
        os.makedirs(d, exist_ok=True)
        drive = os.path.splitdrive(os.path.abspath(d))[0].lower()
        if drive in seen:
            continue
        seen.add(drive)
        free = shutil.disk_usage(d).free
        if free < 2.0e9:            # 实测：输出 0.5 GB + 缓存 0.3 GB + 旧补丁 0.14 GB
            r.fail("%s 可用空间只有 %s，构建约需要 2 GB（含余量）。" % (drive.upper(), fmt_size(free)))
        else:
            r.ok("%s 可用空间 %.1f GB（构建约需 1 GB）" % (drive.upper(), free / 1e9))


def check_game(r, a, exp_in, workers=6):
    say("游戏文件（只读）")
    game = a.game
    if not game:
        r.fail("请用 --game 指定游戏目录（含 Suzerain.exe 的那个文件夹），或设置环境变量 SUZERAIN_GAME。")
        return
    if not (os.path.isfile(os.path.join(game, "Suzerain.exe")) and os.path.isdir(os.path.join(game, "Suzerain_Data"))):
        r.fail("%s 不是 Suzerain 的游戏目录（里面没有 Suzerain.exe / Suzerain_Data）。" % game)
        return
    want = exp_in["game"]["catalog_hash"]
    cat = os.path.join(game, GAME_CATALOG)
    try:
        with open(cat, encoding="ascii") as f:
            have = f.read().strip()
    except OSError as e:
        r.fail("读不到 %s：%s" % (cat, e))
        return
    if have != want:
        r.fail("游戏版本不对：catalog.hash 是 %s，本构建器针对 3.1.0 Build 175（%s）。请先把游戏更新/回退到该版本。" % (have, want))
        return
    r.ok("catalog.hash 与 3.1.0 Build 175 一致")
    files = exp_in["files"]
    t0 = time.time()

    def one(item):
        rel, v = item
        p = os.path.join(game, rel.replace("/", os.sep))
        if not os.path.isfile(lp(p)):
            return rel, "missing"
        h = sha256_file(p)
        if h == v["original"]:
            return rel, "ok"
        if h in v["patched"]:
            return rel, "patched"
        return rel, "unknown"

    with ThreadPoolExecutor(max_workers=workers) as ex:
        res = list(ex.map(one, files.items()))
    kinds = {}
    for rel, k in res:
        kinds.setdefault(k, []).append(rel)
    n_ok = len(kinds.get("ok", []))
    if n_ok == len(files):
        r.ok("%d 个将被替换的游戏文件全部是原版（%.0f 秒）" % (n_ok, time.time() - t0))
        return
    if kinds.get("patched"):
        r.fail("有 %d 个文件已经被汉化补丁改过（你可能装过汉化包）。构建需要原版文件：请先用安装器「还原」，"
               "或在 Steam 里对 Suzerain 做「验证游戏文件完整性」，然后重试。例：%s" % (len(kinds["patched"]), kinds["patched"][0]))
    if kinds.get("unknown"):
        r.fail("有 %d 个文件的内容既不是原版也不是已知补丁（游戏版本不符或文件损坏）。例：%s" % (len(kinds["unknown"]), kinds["unknown"][0]))
    if kinds.get("missing"):
        r.fail("缺少 %d 个游戏文件。例：%s" % (len(kinds["missing"]), kinds["missing"][0]))


# ---------------------------------------------------------------- 旧补丁
def base_problems(folder, exp_base):
    """旧补丁文件夹与 expected_base.json 的差异。"""
    bad = []
    for rel, e in exp_base["files"].items():
        p = os.path.join(folder, rel.replace("/", os.sep))
        if not os.path.isfile(lp(p)):
            bad.append("缺失 " + rel)
        elif os.path.getsize(lp(p)) != e["size"] or sha256_file(p) != e["sha256"]:
            bad.append("内容不同 " + rel)
    return bad


def find_base_dir(root, top):
    cand = os.path.join(root, top)
    if os.path.isdir(lp(cand)):
        return cand
    for d in sorted(os.listdir(lp(root))):
        p = os.path.join(root, d)
        if os.path.isfile(lp(os.path.join(p, "patch_manifest.json"))):
            return p
    return None


def download(url, dest, size, sha, hint, fatal=True):
    """下载到 dest 并核对大小与 SHA-256，成功返回 True。失败时：fatal 则终止并给出 hint；否则只警告并返回 False。"""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    part = dest + ".part"
    say("  下载 %s（%s）" % (url, fmt_size(size)))
    req = urllib.request.Request(url, headers={"User-Agent": "suzerain-cn-builder"})
    h, got, last = hashlib.sha256(), 0, 0.0

    def fail(msg):
        if os.path.exists(part):
            os.remove(part)
        if fatal:
            die(msg + "\n  " + hint)
        say("  [警告] " + msg)
        return False

    try:
        with urllib.request.urlopen(req, timeout=60) as resp, open(part, "wb") as f:
            while True:
                b = resp.read(1 << 20)
                if not b:
                    break
                f.write(b)
                h.update(b)
                got += len(b)
                if time.time() - last > 1.0:
                    last = time.time()
                    print("\r  已下载 %s / %s" % (fmt_size(got), fmt_size(size)), end="", flush=True)
        print()
    except Exception as e:  # noqa: BLE001
        return fail("下载失败：%s" % e)
    if got != size or h.hexdigest() != sha:
        why = ("大小 %d 字节，期望 %d 字节" % (got, size)) if got != size else ("大小一致，但 SHA-256 是 %s…" % h.hexdigest()[:12])
        return fail("下载的文件与预期不一致（%s），已删除。" % why)
    os.replace(part, dest)
    say("  下载完成，SHA-256 校验通过")
    return True


def fetch_font(a, exp_out):
    """决定构建用的字体并把 a.font_path 设成它：--font > 本机已有的实测字体 > 下载实测字体 > 退回官方 2.003。"""
    say("字体")
    if a.font_path:
        say("  使用 --font 指定的 %s（预检已核对过哈希）" % a.font_path)
        return
    want = exp_out["tested_with"]["font_sha256"]
    src = jload("font_source.json")
    f, fb = src["font"], src["fallback"]
    if f["sha256"] != want:
        die("仓库数据不一致：font_source.json 与 expected_outputs.json 里的字体 SHA-256 不同（请反馈给维护者）。")
    local = find_local_font(a, want)
    if local:
        a.font_path = local
        say("  使用 %s（SHA-256 与实测一致）" % local)
        return
    fdir = os.path.join(a.work, "fonts")
    hint = "可以手动下载字体，再运行：python build.py --font <字体.ttf> --game ...（见 assets\\fonts\\README.txt）"
    dest = os.path.join(fdir, f["file"])
    if "OWNER/REPO" in f["url"]:
        say("  [警告] 字体的下载地址还没有配置（仓库维护者发布前要填写 data\\font_source.json）。")
    elif download(f["url"], dest, f["size"], f["sha256"], hint, fatal=False):
        a.font_path = dest
        return
    say("  [警告] 改用官方 noto-cjk 2.003 版字体。" + fb["note"])
    dest = os.path.join(fdir, fb["file"])
    if not (os.path.isfile(dest) and sha256_file(dest) == fb["sha256"]):
        download(fb["url"], dest, fb["size"], fb["sha256"], hint)        # 再失败就终止
    a.font_path = dest


def extract_zip(zpath, dest_root):
    with zipfile.ZipFile(zpath) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            parts = [x for x in info.filename.replace("\\", "/").split("/") if x]
            if not parts or ".." in parts or ":" in parts[0]:
                die("zip 里有不安全的路径：" + info.filename)
            dst = os.path.join(dest_root, *parts)
            os.makedirs(lp(os.path.dirname(dst)), exist_ok=True)
            with z.open(info) as src, open(lp(dst), "wb") as out:
                shutil.copyfileobj(src, out, 1 << 20)


def fetch_base(a, exp_base):
    """返回已校验的旧补丁文件夹路径。"""
    rel = exp_base["release"]
    top = rel["top_folder"]
    say("旧稳定版补丁（基础补丁）")
    root = os.path.join(a.work, "base")
    if a.base and os.path.isdir(a.base):
        bad = base_problems(a.base, exp_base)
        if bad:
            die("--base 指定的文件夹与预期的旧补丁不一致（%d 处，例：%s）。" % (len(bad), bad[0]))
        say("  使用 %s（%d 个文件校验通过）" % (a.base, len(exp_base["files"])))
        return os.path.abspath(a.base)
    target = find_base_dir(root, top) if os.path.isdir(lp(root)) else None
    if target and not base_problems(target, exp_base):
        say("  已有 %s（%d 个文件校验通过）" % (target, len(exp_base["files"])))
        return target
    if a.base:
        zpath = a.base
        if not os.path.isfile(zpath):
            die("找不到 --base 指定的文件：" + zpath)
    else:
        zpath = os.path.join(a.work, "download", rel["zip_name"])
        if not (os.path.isfile(zpath) and os.path.getsize(zpath) == rel["size"] and sha256_file(zpath) == rel["sha256"]):
            download(rel["url"], zpath, rel["size"], rel["sha256"],
                     "可以用浏览器/网盘自己下载这个 zip，再运行：python build.py --base <zip 路径> --game ...")
    if os.path.isdir(lp(root)):
        shutil.rmtree(lp(root))
    say("  解压到 " + root)
    extract_zip(zpath, root)
    target = find_base_dir(root, top)
    if not target:
        die("解压后没找到旧补丁文件夹（应含 patch_manifest.json）。")
    bad = base_problems(target, exp_base)
    if bad:
        die("旧补丁内容与预期不一致（%d 处，例：%s）。这个 zip 不是本构建器针对的版本。" % (len(bad), bad[0]))
    say("  %d 个文件校验通过" % len(exp_base["files"]))
    return target


# ---------------------------------------------------------------- 校验
def pack_problems(out, name, expected):
    """输出文件夹与 expected_outputs.json 的差异；文件夹不存在返回 None。"""
    root = os.path.join(out, name)
    sd = os.path.join(root, "Suzerain_Data")
    if not os.path.isdir(lp(sd)):
        return None
    present = {}
    for dp, _dn, fn in os.walk(lp(sd)):
        for n in fn:
            full = os.path.join(dp, n)
            present[os.path.relpath(full, lp(root)).replace("\\", "/")] = full
    bad = []
    for rel, e in expected.items():
        full = present.get(rel)
        if full is None:
            bad.append(("缺失", rel))
        elif os.path.getsize(full) != e["size"]:
            bad.append(("大小不同", rel))
        elif sha256_file(full) != e["sha256"]:
            bad.append(("哈希不同", rel))
    for rel in sorted(set(present) - set(expected)):
        bad.append(("多出", rel))
    for f in ("patch_manifest.json", "install.ps1", "restore.ps1", "README.txt"):
        if not os.path.isfile(lp(os.path.join(root, f))):
            bad.append(("缺少说明/脚本文件", f))
    return bad


def verify_all(a, exp_out, keys=None, quiet_ok=False):
    say("校验（与维护者实测过的构建逐文件比对 SHA-256）")
    n_files, n_bad, state = 0, 0, {}
    for key, name, _deps, _cmds in PACKS:
        if keys is not None and key not in keys:
            continue
        exp = exp_out["packs"][name]
        bad = pack_problems(a.out, name, exp)
        if bad is None:
            say("  [未构建] %s" % LABEL[key])
            state[key] = "none"
            n_bad += 1
            continue
        n_files += len(exp)
        if not bad:
            say("  [一致]   %-26s %3d/%d 个文件" % (LABEL[key], len(exp), len(exp)))
            state[key] = "ok"
        else:
            n_bad += 1
            state[key] = "bad"
            say("  [不一致] %-26s %d 处差异：" % (LABEL[key], len(bad)))
            for kind, rel in bad[:8]:
                say("            %s  %s" % (kind, rel.split("/")[-1]))
            if len(bad) > 8:
                say("            ... 另有 %d 处" % (len(bad) - 8))
    return n_files, n_bad, state


# ---------------------------------------------------------------- 构建
def tool_env(a, base_dir):
    env = dict(os.environ)
    env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1",
               SUZERAIN_GAME=os.path.abspath(a.game), SUZERAIN_BASE=os.path.abspath(base_dir),
               SUZERAIN_OUT=os.path.abspath(a.out), SUZERAIN_WORK=os.path.abspath(a.work),
               SUZERAIN_FONT=os.path.abspath(a.font_path) if a.font_path else "")
    return env


def map_names(env):
    out = subprocess.check_output([sys.executable, "-B", "-c", "import map_cfg; print(' '.join(map_cfg.ALL))"],
                                  cwd=TOOLS, env=env)
    return out.decode("utf-8").split()


def run_tool(a, env, key, args):
    log = os.path.join(a.work, "logs", key + ".log")
    os.makedirs(os.path.dirname(log), exist_ok=True)
    argv = [sys.executable, "-B", os.path.join(TOOLS, args[0])] + args[1:]
    with open(log, "ab") as lf:
        lf.write(("\n$ " + " ".join(args[:6]) + (" ..." if len(args) > 6 else "") + "\n").encode("utf-8"))
        lf.flush()
        rc = subprocess.run(argv, cwd=TOOLS, env=env, stdout=lf, stderr=subprocess.STDOUT).returncode
    if rc != 0:
        with open(log, "rb") as f:
            tail = f.read().decode("utf-8", "replace").splitlines()[-25:]
        say("")
        say("【出错】%s 的生成器 %s 失败（退出码 %d）。日志末尾：" % (LABEL[key], args[0], rc))
        for line in tail:
            say("    " + line)
        die("完整日志：" + log)


def build_packs(a, base_dir, exp_out, keys):
    env = tool_env(a, base_dir)
    todo = [p for p in PACKS if p[0] in keys]
    t_all = time.time()
    for i, (key, name, deps, cmds) in enumerate(todo, 1):
        exp = exp_out["packs"][name]
        if not a.rebuild:
            bad = pack_problems(a.out, name, exp)
            if bad is not None and not bad:
                say("[%d/%d] %s：输出已存在且校验通过，跳过（要重做请加 --rebuild）" % (i, len(todo), LABEL[key]))
                continue
        for d in deps:
            dname = next(p[1] for p in PACKS if p[0] == d)
            bad = pack_problems(a.out, dname, exp_out["packs"][dname])
            if bad is None or bad:
                die("构建 %s 需要先构建好 %s（并通过校验）。请去掉 --only，或把它也加进去。" % (LABEL[key], LABEL[d]))
        say("[%d/%d] 构建 %s ..." % (i, len(todo), LABEL[key]))
        t0 = time.time()
        for args in cmds:
            args = list(args)
            if "@ALL" in args:
                k = args.index("@ALL")
                args[k:k + 1] = map_names(env)
            run_tool(a, env, key, args)
        say("      完成，用时 %.0f 秒" % (time.time() - t0))
    say("构建用时共 %.0f 秒" % (time.time() - t_all))


def copy_installer(a):
    src = os.path.join(REPO, "installer")
    if not os.path.isdir(src):
        return None
    dst = os.path.join(a.out, INSTALLER)
    shutil.copytree(lp(src), lp(dst), dirs_exist_ok=True)
    return dst


# ---------------------------------------------------------------- 主流程
def main():
    global LOG
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="Suzerain 汉化补丁构建器", formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__)
    ap.add_argument("command", nargs="?", default="all", choices=["all", "check", "fetch", "verify"])
    ap.add_argument("--game", default=os.environ.get("SUZERAIN_GAME"), help="Suzerain 游戏目录（含 Suzerain.exe）")
    ap.add_argument("--out", default=os.path.join(REPO, "out"), help="输出目录，默认 <仓库>\\out")
    ap.add_argument("--work", default=os.path.join(REPO, "_work"), help="缓存/日志目录，默认 <仓库>\\_work")
    ap.add_argument("--base", help="已有的旧补丁（zip 或解压后的文件夹）；不指定则从 GitHub Release 下载")
    ap.add_argument("--font", help="自己提供字体 TTF（默认自动获取与实测一致的字体，见 assets\\fonts\\README.txt）")
    ap.add_argument("--only", help="只构建这些包（逗号分隔）：" + ",".join(p[0] for p in PACKS))
    ap.add_argument("--rebuild", action="store_true", help="输出已存在且校验通过时也重新构建")
    a = ap.parse_args()

    def clean(p):        # 'D:\...\Suzerain\"' (trailing backslash before the closing quote) reaches us with a stray quote
        return os.path.abspath(p.strip().strip('"')) if p else p

    a.game, a.out, a.work, a.base = clean(a.game), clean(a.out), clean(a.work), clean(a.base)
    a.font_path = clean(a.font) if a.font else None        # 没指定则由 fetch_font 决定
    keys = [p[0] for p in PACKS]
    if a.only:
        keys = [k.strip() for k in a.only.split(",") if k.strip()]
        bad = [k for k in keys if k not in [p[0] for p in PACKS]]
        if bad:
            die("--only 里有不认识的包名：%s（可选：%s）" % (",".join(bad), ",".join(p[0] for p in PACKS)), 2)

    os.makedirs(os.path.join(a.work, "logs"), exist_ok=True)
    LOG = open(os.path.join(a.work, "logs", "build.log"), "a", encoding="utf-8")
    say("=" * 70)
    say("Suzerain 汉化补丁构建器  %s  命令=%s" % (time.strftime("%Y-%m-%d %H:%M:%S"), a.command))
    exp_out, exp_in, exp_base = jload("expected_outputs.json"), jload("expected_inputs.json"), jload("expected_base.json")

    if a.command == "verify":
        n_files, n_bad, _ = verify_all(a, exp_out, keys)
        sys.exit(0 if n_bad == 0 else 3)

    if a.command == "fetch":
        os.makedirs(a.work, exist_ok=True)
        fetch_base(a, exp_base)
        fetch_font(a, exp_out)
        return

    say("预检")
    r = Report()
    check_env(r, a, exp_out)
    check_paths(r, a, exp_out)
    check_game(r, a, exp_in)
    if r.fails:
        say("")
        die("预检没通过（%d 项失败）。请按上面的提示处理后重试；游戏目录没有被改动。" % len(r.fails), 2)
    if a.command == "check":
        say("")
        say("预检通过（%d 条警告）。运行 python build.py --game \"...\" 开始构建。" % len(r.warns))
        return

    base_dir = fetch_base(a, exp_base)
    if {"tutorialimages", "maplabels"} & set(keys):          # 只有这两个包要用字体画中文
        fetch_font(a, exp_out)
    say("")
    say("开始构建（约 4～6 分钟）。每个生成器的详细输出在 %s" % os.path.join(a.work, "logs"))
    build_packs(a, base_dir, exp_out, keys)
    inst = copy_installer(a)
    say("")
    n_files, n_bad, state = verify_all(a, exp_out, keys)
    say("")
    if n_bad == 0:
        say("全部通过：%d 个包、%d 个负载文件与已测试的构建逐字节一致。" % (len(keys), n_files))
        say("补丁包在：" + a.out)
        if inst:
            say("下一步：打开 %s 里的「启动安装器.bat」，按界面提示安装。" % inst)
        return
    say("有 %d 个包与已测试的构建不一致（见上）。常见原因：依赖版本或字体与实测不同（见预检里的警告）。" % n_bad)
    if a.font_path and sha256_file(a.font_path) != exp_out["tested_with"]["font_sha256"]:
        say("本次用的字体（%s）不是实测字体，TutorialImages / MapLabels 里的差异多半来自它。" % os.path.basename(a.font_path))
    say("这不一定表示补丁不可用，但这样得到的包没有经过维护者的测试。")
    sys.exit(3)


if __name__ == "__main__":
    main()
