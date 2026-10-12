"""Build the OPTIONAL "ProgramWords" add-on: the ProgramText pack's global-metadata.dat PLUS the single-word literals of meta_words.py.

usage:  python su_words_build.py [--out DIR] [--zip]

It replaces exactly one game file (the same one the ProgramText add-on replaces), so it is built ON TOP of that pack: the manifest's
original_sha256 is the ProgramText pack's patched hash and requires_pack names the ProgramText pack (the same mechanism the MapLabels
add-on uses for the files it shares with the main pack).  The installer therefore installs the ProgramText pack first when needed and
restores this pack first; restoring this pack gives back the ProgramText state.
"""
import sys, time, argparse, shutil, hashlib
from lib_su import *
import su_pack, meta_lib, meta_patch, meta_tm, meta_words, su_meta_build

PACK_NAME = "Suzerain_CN_Plus_ProgramWords_SteamWin_2026-10-10"
BASE_PACK = su_meta_build.PACK_NAME
OUT_ROOT = os.path.join(ROOT, PACK_NAME)
LOGDIR = os.path.join(WORK, "out")
LIVE_TEXT_FILE = os.path.join(DATA, "words_live_text.txt")      # the "实测情况" paragraph; written after the live test, read here

README_HEAD = """Suzerain 汉化补充包：程序内单词（可选附加包，实验性，需要先装“程序内文案包”）
============================================================================

先说结论
--------
这是几个附加包里最激进的一个。它在“程序内文案包”的基础上，再把 @N@ 个程序里的单个常用词改成中文：
确认弹窗按钮的 Yes / No，读取 / 选项两个页面标题，设置页里窗口模式和帧率上限的取值，
以及国家 / 城市信息面板里的 Population / Capital / Government / Leader / Relations / Military / Million / Billion。
装上之后，这两个信息面板就不再中英文混着，确认弹窗的按钮也是“否 / 是”。

为什么单独做成一个包：单个单词在程序里只存一份，所有用到它的地方共用。一个单词既可能是界面文字，也可能同时是“暗号”
（字典的键、字符串比较、游戏物体的名字），改了暗号功能就会失灵，而且不会有任何报错。我在游戏数据文件里查过，这 @N@ 个词
没有这类用法；程序代码里是否另有，我看不到。所以它不并入程序内文案包：想要才装，不想要随时还原，不影响其他任何汉化包。

@LIVE@
这些词的中文译法沿用主包：政府、领导人、首都、人口、关系、军事。

怎么装、怎么还原
----------------
- 本包建立在“程序内文案包”之上：它们改的是同一个文件（global-metadata.dat），本包是“程序内文案包 + 这 @N@ 个词”的完整版本。
- 用汉化安装器：直接勾选本包，安装器会自动先装“程序内文案包”（如果还没装），再装本包；还原本包时只回到“程序内文案包”的状态。
- 单独双击 install.bat：游戏里必须已经装了“程序内文案包”，否则会提示“Unexpected file hashes detected”并什么都不改。
- 还原：双击 restore.bat（或在安装器里还原本包），文件回到装本包之前的状态，也就是“程序内文案包”的版本；
  想回到完全原版，再还原“程序内文案包”，或用 Steam 的“验证游戏文件完整性”。还原不需要游戏能运行。
- 备份在 游戏目录\\_patch_backup\\programwords_时间戳\\。

本包改了哪些（共 @N@ 个）
------------------------
@GROUP_LIST@

每一条的“序号 / 英文原文 / 中文译文”见本文件夹里的 translation_list.txt。

故意没有改的单词（以及为什么）
------------------------------
- Cancel：既是 Unity 的输入轴名，又是场景里 18 个游戏物体的名字，按名字查找会被改坏。
- On / Off：On 是场景里 157 个游戏物体的名字；Off 为了保持一致也不改。设置页的“开 / 关”因此仍是 On / Off。
- Default：是 Unity 的图层名（TagManager 里的 Default 层）。
- OK：这次没有在界面上看到过它；而且 OK 是程序最常拿来和服务器 / SDK 的回复做比较的字符串，改了可能让联网相关的判断失灵，风险和收益不成比例。
- High：我试着改过，游戏里没有任何变化（画质选项显示的取值不是字符串表里的这个 High），所以没有收进来。
- Credits / Collections / Locked / Unlocked / UNKNOWN：收藏页和制作人员页的标题与状态字。实机截图普查里（没装本包的那次启动）看到它们是英文。
  Others：宗教饼图图例的最后一项，装着本包也仍是英文。这几个词我都没有查过是不是“暗号”，所以这一版没收。
- 其余没有在界面上见过的单词，一概不碰。

怎么做的（便于复查）
--------------------
- 和“程序内文案包”一样：文件大小、文件头、各数据段的位置与大小、字符串的条数与顺序都与原版完全相同；
  本包比“程序内文案包”多改了 @N@ 个字符串，省下的字节同样补在那条玩家看不到的 Unity.Collections 错误提示末尾的空格上（序号 @SINK@，共 @DELTA@ 字节）。
- 每一个词在字符串表里恰好出现一次，替换后保持原来的占位符 / 换行不变（这些词没有占位符）。
- 在游戏的全部数据文件（所有 Addressables 包、data.unity3d）里按“游戏物体名 / 输入轴 / 图层 / 动画状态”等位置查过这些词：没有发现暗号用法。

没验证到的部分（请你实机确认）
------------------------------
- 程序代码里是否另有“暗号”用法，我看不到：这是最大的未知数。症状通常是某个按钮点了没反应，或某个界面打不开，而不是报错。
- 上面“实测情况”里没列出的地方，我没有看过。设置页里窗口模式 / 帧率上限的取值：@SETTINGS@
- 单个单词在别处也会出现（例如别的界面里的 Government / Relations / Military 字样）：它们会一起变成中文，这是预期的，但我没有逐处看过。

验证（约 5 分钟）
-----------------
1. 启动游戏，能到主菜单、能“继续”或“读取”进入游戏：说明没有改坏。
2. 暂停菜单 -> 退出（或主菜单）：弹窗按钮应是“否 / 是”；点“否”弹窗关闭，点“是”才真的退出。
3. 点开国家 / 城市信息面板：应看到“人口 / 首都 / 政府 / 领导人 / 关系 / 军事”。
4. 设置页：标题应为“选项”；用左右箭头切换窗口模式 / 目标帧率，看一下取值（不点“应用”就不会生效）。
任何一步异常（按钮没反应、界面打不开、闪退、方框）：先在安装器里还原本包（或运行 restore.bat），并把现象告诉我。

已知局限
--------
- 游戏被 Steam 更新后，补丁会失效或被还原，需要重新验证文件完整性并重装。
- 只替换 global-metadata.dat 这一个文件，不依赖也不覆盖主汉化包、场景界面附加包、教程图片附加包。

构建信息：由 su_words_build.py 生成；词表 meta_words.py（在 meta_tm.py 之上叠加）；字节级改写 meta_patch.py；校验脚本 su_verify_meta.py。
"""


def vis(s):
    return s.replace("\r", "\\r").replace("\n", "\\n")


def read_live_text():
    if not os.path.isfile(LIVE_TEXT_FILE):
        return "实测情况：【待填】", "【待填】"
    t = open(LIVE_TEXT_FILE, encoding="utf-8").read().replace("\r\n", "\n").strip("\n")
    head, _, settings = t.partition("\n@@SETTINGS@@\n")
    return head, settings.strip() or "【待填】"


def make_readme(info, n_words):
    groups = [f"  - {g}：{', '.join(en + ' -> ' + zh for en, zh in items)}" for g, items in meta_words.GROUPS]
    live, settings = read_live_text()
    t = README_HEAD
    t = t.replace("@LIVE@", live).replace("@SETTINGS@", settings)
    t = t.replace("@N@", str(n_words))
    t = t.replace("@GROUP_LIST@", "\n".join(groups))
    t = t.replace("@DELTA@", str(info["delta"]))
    t = t.replace("@SINK@", str(info["sink"]))
    return t


def make_list(info):
    words = {en for g, en, zh in meta_words.PAIRS}
    by = {}
    for i, g, en, zh in info["changes"]:
        if en in words:
            by.setdefault(g, []).append((i, en, zh))
    lines = [f"程序内单词附加包：译文清单（共 {sum(len(v) for v in by.values())} 条，在程序内文案包之上）",
             "格式：[字符串表序号] 英文原文  =>  中文译文", ""]
    for g, items in meta_words.GROUPS:
        lines.append(f"## {g}（{len(items)} 条）")
        for i, en, zh in sorted(by[g]):
            lines.append(f"[{i}] {vis(en)}  =>  {vis(zh)}")
        lines.append("")
    return "\n".join(lines)


class Logger:
    def __init__(self, path):
        self.f = open(path, "w", encoding="utf-8")

    def __call__(self, s=""):
        self.f.write(s + "\n")
        self.f.flush()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT_ROOT)
    ap.add_argument("--zip", action="store_true")
    ap.add_argument("--final", action="store_true", help="refuse to build while the README still has the 【待填】 placeholder")
    a = ap.parse_args()
    out_dir = a.out
    log = Logger(os.path.join(LOGDIR, "build_words_log.txt"))
    t0 = time.time()
    if os.path.isdir(lp(out_dir)):
        shutil.rmtree(lp(out_dir))
    with open(lp(meta_lib.MD_GAME), "rb") as f:
        orig = f.read()
    # the base: exactly the ProgramText pack's payload (recomputed here, and it must equal the delivered ProgramText pack)
    base_bytes, base_info = meta_patch.apply(orig, meta_tm.PAIRS)
    base_hash = hashlib.sha256(base_bytes).hexdigest().upper()
    delivered = os.path.join(ROOT, BASE_PACK, meta_lib.MD_REL)
    assert sha256_file(delivered) == base_hash, "the delivered ProgramText payload is not what meta_tm.PAIRS produces: rebuild/redeploy it first"
    new, info = meta_patch.apply(orig, list(meta_tm.PAIRS) + list(meta_words.PAIRS))
    n_words = len(meta_words.PAIRS)
    assert len(info["changes"]) == len(meta_tm.PAIRS) + n_words
    log(f"base (ProgramText) {len(base_info['changes'])} literals, sha {base_hash[:16]}; + {n_words} words -> {len(info['changes'])} literals; "
        f"delta {info['delta']} bytes absorbed by literal #{info['sink']}; size {len(orig)} -> {len(new)}")
    dst = os.path.join(out_dir, meta_lib.MD_REL)
    os.makedirs(os.path.dirname(lp(dst)), exist_ok=True)
    with open(lp(dst), "wb") as f:
        f.write(new)
    ents = [{
        "relative_path": meta_lib.MD_REL,
        "file_name": os.path.basename(meta_lib.MD_REL),
        "size": len(new),
        "original_sha256": base_hash,                    # built on the ProgramText pack
        "patched_sha256": hashlib.sha256(new).hexdigest().upper(),
        "requires_pack": BASE_PACK,
    }]
    notes = {
        "base": f"附加包：需要先安装程序内文案包 {BASE_PACK}（本包是它加上 {n_words} 个单词的完整版本，改的是同一个文件）。",
        "optional": True,
        "warning": "实验性：把程序字符串表里的单个常用词改成中文。这些词被程序里所有用到它的地方共用，代码里若有拿它做比较或查找键的用法会失灵。"
                   "游戏启动异常或某个按钮没反应时，运行 restore.bat 或在安装器里还原本包。",
    }
    readme = make_readme(info, n_words)
    if a.final and "【待填】" in readme:
        raise SystemExit("README still has the 【待填】 placeholder (write data\\words_live_text.txt after the live test)")
    su_pack.write_manifest(out_dir, PACK_NAME, "programwords", ents, notes)
    su_pack.write_installer(out_dir)
    su_pack.write_restore(out_dir)
    su_pack.write_readme(out_dir, readme)
    with open(os.path.join(out_dir, "translation_list.txt"), "w", encoding="utf-8-sig", newline="") as f:
        f.write(su_pack._crlf(make_list(info)))
    log(f"pack written: {out_dir} [{time.time() - t0:.0f}s]")
    if a.zip:
        log("zip: " + su_pack.zip_pack(out_dir))
    log("done")


if __name__ == "__main__":
    main()
