"""Build the OPTIONAL program-text add-on pack (Chinese text for strings compiled into global-metadata.dat).

usage:  python su_meta_build.py [--out DIR] [--zip]
The add-on replaces exactly one game file, Suzerain_Data/il2cpp_data/Metadata/global-metadata.dat, with a file of identical size in
which meta_tm.PAIRS are translated (see meta_patch.py for the byte-level design) and ships its own installer + restore script.
"""
import sys, time, argparse, shutil, hashlib, glob
from lib_su import *
import su_pack, meta_lib, meta_patch, meta_tm

PACK_NAME = "Suzerain_CN_Plus_ProgramText_SteamWin_2026-10-10"
OUT_ROOT = os.path.join(ROOT, PACK_NAME)
LOGDIR = os.path.join(WORK, "out")
os.makedirs(LOGDIR, exist_ok=True)

README_HEAD = """Suzerain 汉化补充包：程序内文案（可选附加包，实验性）
====================================================

先说结论
--------
这是几个附加包里风险最高的一个：它改的不是数据文件，而是游戏程序自带的字符串表（global-metadata.dat）。
实测情况（2026-10-12，Windows，Steam 版 3.1.0 Build 175，在真实游戏里运行，主汉化包和其他附加包同时装着）：
游戏能正常启动、读档、进入游戏。游戏运行日志里除了一条与汉化无关的“找不到 playersettings.dat”（没装任何汉化包时也有）之外没有报错。
我在游戏里亲眼看到、已经显示为中文的有：
  - “退出到桌面”“返回主菜单”两个确认弹窗的正文（弹窗按钮上的 Yes / No 不在本包范围，见下面“没有改的”）；
  - 主菜单“继续”栏里的“游戏进程 / 当前故事 / 日期”，读取存档窗口里的“日期 / 版本”；
  - 国家、城市信息面板里的“人口排名 / GDP 排名 / GDP 世界排名 / 官方语言”。
其余条目（战争里的头顶文字、屏幕通知、多选题提示、存档覆盖 / 删除弹窗等）我没有在游戏里逐条触发看过，见后面“没验证到的部分”。
只想要稳妥的话可以不装它，不装不影响其他任何汉化包。
万一装完游戏启动不了：双击 restore.bat 还原即可（还原不需要游戏能运行）。

这是什么
--------
游戏里有一批界面文字不放在数据文件里，而是直接写在程序里（编译进 GameAssembly.dll 的字符串表，文字本体存放在
Suzerain_Data\\il2cpp_data\\Metadata\\global-metadata.dat）。主汉化包和场景界面附加包都改不到它们。
本包把其中 @N@ 条整句或多词文案改成中文：
@GROUP_LIST@

每一条的“序号 / 英文原文 / 中文译文”见本文件夹里的 translation_list.txt（译文清单）。译名沿用主包：百科、法令、游戏进程、档案、所属组织、
训练队列、行动点、陆地支援、海军支援、剧情包、故事选择、原型等。

修订记录：第 1 版（2026-10-11）136 条；第 2 版（2026-10-12，本版）144 条。新增的 8 条是实机测试时发现仍为英文的：
主菜单“继续”栏的“当前故事 / 日期”、读取存档窗口的“日期 / 版本”、国家 / 城市信息面板的 4 个标签。
说明更正（2026-10-12，包的内容没有变）：下面“没有改的”第 5 点原先把日期时间和“Open City Information”按钮也写成了“改字符串表改不到”，
这说错了：它们的格式串是程序里固定的字符串，改得到，只是我没有在游戏里验证过，所以没放进来。已更正，并新增了第 6 点。

没有改的（以及为什么）
----------------------
1. 单个常用词：是 / 否 / 确定 / 取消 / 返回 / 保存 / 读取 / 选项 / 菜单 / 全屏 / 窗口 / 已轰炸 / 已固守 / 已补给 / 增援 ……
   程序里相同的英文只存一份，所有用到它的地方共用。一个单词既可能是界面文字，也可能同时是“暗号”（动画状态名、
   字典的键、字符串比较、游戏物体的名字），改了暗号功能就会失灵，所以一概不碰。
   因此确认弹窗按钮上的 Yes / No 仍是英文；国家 / 城市信息面板里的 Relations / Military / Leader / Government / Capital /
   Population 也是这类单词，所以那两个面板目前是中英文混着的（本包只改了其中的“人口排名 / GDP 排名 / GDP 世界排名 / 官方语言”）。
   设置菜单里下拉框的取值（High / On / Off / Default 等）也仍是英文：On / Off / Default 属于上述单词，没有改；
   High 我试着改过，游戏里没有任何变化，说明这类取值显示的不是字符串表里的那个 High。
   （战争里单位头顶带感叹号的版本，例如 Bombed!，是独立的一条，已改。）
   想把其中 17 个单词（弹窗按钮 Yes / No、读取 / 选项标题、窗口模式和帧率上限的取值、首都 / 政府 / 人口等）也改成中文，
   有一个单独的可选附加包 Suzerain_CN_Plus_ProgramWords_SteamWin_2026-10-10：它建立在本包之上，风险更高，所以没有并进本包。
2. 同名物体：Enemy Turn、New Save、Story Pack Completed 在场景里同时是游戏物体的名字，按名字查找会被改坏，所以没动
   （它们在场景里的显示文字，场景界面附加包已经译了）。
3. 账号 / 云存档 / 商店 / 广告 / 礼品码 / 推送通知相关文案：与账号体系有关，Steam 版里是否会出现我没法确认，不动。
4. 调试日志，以及 Unity、.NET、第三方库自带的英文：玩家看不到。
5. 由程序运行时拼出来的文字，它们不是字符串表里的现成整句，本包都没有处理，原因分两种：
   a) 程序里有一条固定的格式串，改得到，但我没有在游戏里验证过，所以没放进来：日期时间（如 Oct 12, 2026, 3:18 PM，
      格式串是 MMM d, yyyy, h:mm tt）；城市 / 国家弹窗上的按钮 Open City Information / Open Country Information
      （格式串是 Open {0} Information，City / Country 由程序运行时填进去）。
   b) 改字符串表改不到：序数词（1st / 2nd，程序把数字和 st / nd / rd / th 现拼在一起）；关系和军力的等级名
      （Neutral / Strong / Overwhelming / Unfriendly 等，来自枚举名，硬改会破坏程序按名字的查找）；
      存档标签 Autosave / Turn Save，以及读取窗口里的存档名 Turn 5（存档名写在你的存档文件里）。
6. 收藏页和制作人员页：2026-10-12 的实机截图普查里，在没装本包的那次启动中看到它们仍是英文。多词整句 All Story Packs、
   Visit the store to purchase this item. 原则上可以改，但是做完这一版之后才发现，没有收进来；页面标题 CREDITS / COLLECTIONS、
   状态字 Locked / Unlocked、名字栏 UNKNOWN 是单个单词，属于上面第 1 点那一类。
   所有仍是英文的地方的清单，见汉化安装器文件夹里的 README.txt（第八节）。

怎么做的（便于复查）
--------------------
- 文件大小、文件头、各数据段的位置与大小、字符串的条数与顺序，都与原版完全相同；只有上面这 @N@ 条字符串的内容变了。
- 中文通常比英文短，省下的 @DELTA@ 字节补成一条游戏库自带、玩家不会看到的 Unity.Collections 错误提示末尾的空格
  （序号 @SINK@），所以字符串数据区的总长度不变、后面各段的位置也不变；偏移表按新长度重新计算。
- 每一条译文都检查过：原文在字符串表里恰好出现一次；占位符 {0}、换行符、<br>、<sprite name=…> 等标记与原文一致。
- 另外在游戏的全部数据文件（所有 Addressables 包、data.unity3d）里检索了同样的英文：除上面第 2 点的三条外，只有
  Achievement Unlocked! 出现过，而且是场景里的显示文字（场景界面附加包已译成中文），不是“暗号”。
  也就是在数据文件里没有发现“暗号”用法。程序代码里是否另有暗号用法，我看不到，这是最大的未知数。

没验证到的部分（请你实机确认）
------------------------------
- 上面“先说结论”里没列出的条目，我没有在游戏里逐条触发看过。它们在界面里的位置，是用本地化键名（Confirmation.AreYouSure.… 之类）
  与文案配对推出来的，没有反编译程序。个别条目可能在你的游戏版本里并不出现，也可能有我没发现的第二处用法。
- 字体：这些中文由 TextMeshPro 渲染。已经看到的条目都能正常显示中文（没有方框）；没看到的条目如果用的是只含英文的静态字体，
  能否回退到中文字体我没法保证。若某处显示成方框，请告诉我具体位置。
- 程序代码里是否另有“暗号”用法，我看不到（见上一节最后一条）。实测游戏没有因为这个文件被改而拒绝启动，也没有出现功能失灵，
  但我只走了启动、读档、主要界面和上面列出的几个弹窗，没有通关，也没有把每个界面都试一遍。
- 装着本包期间新建的存档：存档文件里存着一个名字（读取窗口里显示的“Turn 5”）。我在程序的字符串表里查过，能拼出这个名字的只有
  一条格式串 Turn {0}，而本包把它改成了“第 {0} 回合”，所以装着本包期间游戏新建的自动存档 / 回合存档，名字很可能存成中文的“第 N 回合”。
  这一点我没有验证过：实测每次结束都把存档目录还原了，没有留下新存档，也不知道程序会不会按这个名字去判断存档类型。
  本包本身不碰存档文件，已有的存档不会被本包改动；想稳妥的话，装着本包玩的存档请另外备份一份。

安装
----
1. 关闭游戏，双击本文件夹里的 install.bat（会自动找到 Steam 里的 Suzerain，校验版本，把 global-metadata.dat 备份到游戏目录下
   _patch_backup\\programtext_时间戳\\，再替换）。
2. 如果提示 “Unexpected file hashes detected”：说明这个文件不是原版（游戏被 Steam 更新过，或被其他工具改过）。
   先在 Steam 里“验证游戏文件完整性”，再重新运行 install.bat。
3. 已经装过本包第 1 版（136 条）的话，不用先还原，直接运行 install.bat 就会升级到本版（安装脚本认得第 1 版的文件，并把它备份下来）。
   升级之后运行 restore.bat 只会退回升级前的状态（第 1 版）；要回到完全原版，用 Steam 的“验证游戏文件完整性”。

验证（约 5 分钟）
-----------------
1. 启动游戏，能到主菜单：说明程序没有被改坏。启动就黑屏或闪退：立刻运行 restore.bat，并告诉我。
2. 主菜单“继续”栏应显示“当前故事：…  日期：…”；点“读取”，存档窗口里应是“日期：… 版本：…”。
3. 进入游戏后点开国家 / 城市信息面板，应有“人口排名 / GDP 排名 / GDP 世界排名 / 官方语言”。
4. 在存档界面试试“删除存档”“覆盖存档”，在暂停菜单试试“退出”“主菜单”，看确认弹窗的正文是不是中文。
5. 遇到多选题时，看题目上方“从以下选项中……”那一行。
6. 进入战争：看单位头顶的提示（进攻中！已固守！……）和状态说明；点结束回合时若还有行动点，看确认弹窗。
7. 读到新百科词条、数值变化时，看屏幕弹出的通知。
任何一步异常（闪退、方框、文字错位）：运行 restore.bat 还原，并把现象告诉我。

还原
----
双击 restore.bat：从游戏目录 _patch_backup\\programtext_* 里取回原版文件并校验哈希。
找不到备份时，用 Steam 的“验证游戏文件完整性”也能还原（只会重下被改动的文件）。

已知局限
--------
- 游戏被 Steam 更新后，补丁会失效或被还原，需要重新验证文件完整性并重装。
- 与主汉化包、场景界面附加包、教程图片附加包互不依赖、互不覆盖，装卸顺序随意。
- 例外：可选的“程序内单词附加包”（Suzerain_CN_Plus_ProgramWords_SteamWin_2026-10-10）改的是同一个文件，建立在本包之上。装了它之后，
  要先还原它、再还原本包（用汉化安装器会自动按这个顺序）；直接对本包运行 restore.bat 会因为文件已是单词包的版本而拒绝，并保持文件不动。

构建信息：由 su_meta_build.py 生成；译文表 meta_tm.py；字节级改写 meta_patch.py；校验脚本 su_verify_meta.py。
"""


def vis(s):
    return s.replace("\r", "\\r").replace("\n", "\\n")


def make_readme(info):
    groups = []
    for g, items in meta_tm.GROUPS:
        groups.append(f"  - {g}：{len(items)} 条")
    t = README_HEAD
    t = t.replace("@N@", str(len(info["changes"])))
    t = t.replace("@GROUP_LIST@", "\n".join(groups))
    t = t.replace("@DELTA@", str(info["delta"]))
    t = t.replace("@SINK@", str(info["sink"]))
    return t


def make_list(info):
    by = {}
    for i, g, en, zh in info["changes"]:
        by.setdefault(g, []).append((i, en, zh))
    lines = [f"程序内文案附加包：译文清单（共 {len(info['changes'])} 条）",
             "格式：[字符串表序号] 英文原文  =>  中文译文    （\\n \\r 表示换行符）", ""]
    for g, items in meta_tm.GROUPS:
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
    a = ap.parse_args()
    out_dir = a.out
    pairs = list(meta_tm.PAIRS)
    log = Logger(os.path.join(LOGDIR, "build_meta_log.txt"))
    t0 = time.time()
    if os.path.isdir(lp(out_dir)):
        shutil.rmtree(lp(out_dir))
    with open(lp(meta_lib.MD_GAME), "rb") as f:
        orig = f.read()
    new, info = meta_patch.apply(orig, pairs)
    log(f"translated {len(info['changes'])} literals; delta {info['delta']} bytes absorbed by literal #{info['sink']}; "
        f"offsets changed {info['offsets_changed']}/{info['n_lit'] + 1}; size {len(orig)} -> {len(new)}")
    dst = os.path.join(out_dir, meta_lib.MD_REL)
    os.makedirs(os.path.dirname(lp(dst)), exist_ok=True)
    with open(lp(dst), "wb") as f:
        f.write(new)
    ents = [{
        "relative_path": meta_lib.MD_REL,
        "file_name": os.path.basename(meta_lib.MD_REL),
        "size": len(new),
        "original_sha256": hashlib.sha256(orig).hexdigest().upper(),
        "patched_sha256": hashlib.sha256(new).hexdigest().upper(),
    }]
    assert ents[0]["original_sha256"] == sha256_file(meta_lib.MD_GAME)
    # earlier builds of this pack (snapshots of their manifests, work\out\programtext_build*_manifest.json) are installable states too,
    # so that a game that already has the previous build can be upgraded in place by install.bat
    prev_hashes = []
    for pm_path in sorted(glob.glob(os.path.join(LOGDIR, "programtext_build*_manifest.json"))):
        pm = json.load(open(pm_path, encoding="utf-8-sig"))
        for pf in pm["files"]:
            h = pf["patched_sha256"]
            if pf["file_name"] == ents[0]["file_name"] and h not in (ents[0]["original_sha256"], ents[0]["patched_sha256"]) and h not in prev_hashes:
                prev_hashes.append(h)
        log(f"accepting the patched hash of {os.path.basename(pm_path)} ({pm.get('built_at')}) as an installable state")
    if prev_hashes:
        ents[0]["also_accept_sha256"] = prev_hashes
    notes = {
        "base": "独立附加包：只替换 global-metadata.dat 一个文件，不依赖也不覆盖主汉化包、场景界面附加包、教程图片附加包，可单独安装。",
        "optional": True,
        "warning": "实验性：改的是游戏程序自带的字符串表（文件大小、文件头、段位置不变，只替换文案）。"
                   "2026-10-12 在 Windows Steam 版 3.1.0 Build 175 上实机测试过启动、读档和主要界面，只逐条确认了其中少数条目的显示，其余未逐条验证。"
                   "游戏启动异常时运行 restore.bat 还原。",
    }
    su_pack.write_manifest(out_dir, PACK_NAME, "programtext", ents, notes)
    su_pack.write_installer(out_dir)
    su_pack.write_restore(out_dir)
    su_pack.write_readme(out_dir, make_readme(info))
    with open(os.path.join(out_dir, "translation_list.txt"), "w", encoding="utf-8-sig", newline="") as f:
        f.write(su_pack._crlf(make_list(info)))
    log(f"pack written: {out_dir} [{time.time() - t0:.0f}s]")
    if a.zip:
        log("zip: " + su_pack.zip_pack(out_dir))
    log("done")


if __name__ == "__main__":
    main()
