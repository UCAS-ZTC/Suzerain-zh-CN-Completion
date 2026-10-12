"""Build the OPTIONAL tutorial-image add-on pack (war tutorial screenshots with Chinese labels).

usage:  python su_build_img.py [--out DIR] [--zip]
The add-on replaces only the repainted tutorial texture bundles (tut_repaint.LABELS) and ships its own installer + restore script.
"""
import sys, time, argparse, shutil
from lib_su import *
import su_pack
import su_stage_img
import tut_repaint

PACK_NAME = "Suzerain_CN_Plus_TutorialImages_SteamWin_2026-10-10"
OUT_ROOT = os.path.join(ROOT, PACK_NAME)
LOGDIR = os.path.join(WORK, "out")
os.makedirs(LOGDIR, exist_ok=True)

ALL_TUTORIAL = ["tutorial_war_actionpoints", "tutorial_war_attack", "tutorial_war_battle", "tutorial_war_bombing", "tutorial_war_fortify",
                "tutorial_war_movement", "tutorial_war_navalbattle", "tutorial_war_navalblockade", "tutorial_war_navalinvasion",
                "tutorial_war_navallandsupport", "tutorial_war_navalmove", "tutorial_war_placingunit", "tutorial_war_siege",
                "tutorial_war_supplylines", "tutorial_war_support",
                "tutorial_warproduction_availableunits", "tutorial_warproduction_deployedunits", "tutorial_warproduction_gainingresources",
                "tutorial_warproduction_intraining", "tutorial_warproduction_resources"]
# screenshots that contain no English at all (only map place names in the game's invented languages, icons and digits)
NO_ENGLISH = ["tutorial_war_battle", "tutorial_war_navalblockade", "tutorial_war_siege", "tutorial_war_supplylines"]

README_HEAD = """Suzerain 汉化补充包：战争教程截图里的中文标签（可选附加包）
==========================================================

这是什么
--------
游戏的战争教程页里配有一批游戏截图，截图上的按钮/提示文字是画在图片里的，所以主汉化包（只改数据文字）改不到它们。
本附加包把其中一部分截图上的英文标签重新绘制成中文：只替换图片本身，其余像素与原图逐像素相同（见下面的“怎么做的”）。

改了哪些图（共 @N_IMAGES@ 张）
--------------------------
@IMAGE_LIST@

没有改的图
----------
@UNCHANGED_LIST@

和其他补丁包的关系
------------------
- 完全独立：只替换上面 @N_IMAGES@ 个教程图片文件，不依赖也不覆盖主汉化包、场景界面附加包，可以先装也可以后装，也可以单独装。
- 截图里的词沿用补丁里的现有译名（攻击、支援、固守、行动点、结束回合、步兵、坦克、山地师、登陆舰、军舰、潜艇、
  里齐亚陆军、阿扎罗家族、选择以部署、重置部署……海军陆战队沿用单位名）。补丁里查不到现成译名的只有四处，按同一风格新拟：
  行动开始（OPERATION START）、阿扎罗的部署方案、阿扎罗精锐、萨宗征召兵（“征召兵”沿用主包里 levies 的译法）。
  真正的游戏界面是否也是这些词，取决于你有没有装“场景界面附加包”，两者没有联动。

怎么做的（便于复查）
--------------------
- 每张图：找到英文字的像素 → 用该标签自身的底色擦掉 → 用 Noto Serif SC（与游戏界面所用的中文字体同一字体家族）写上中文。
- 原图是 Crunch 压缩的 DXT（10 张是 DXT1，带透明通道的部署面板是 DXT5）。手头没有 Crunch 压缩器，无法写回 Crunch，
  所以改成同类的普通 DXT1 / DXT5 并直接存进文件里（运行时显存占用应与原来相同：据我所知 Unity 会把 Crunch 解码成 DXT 再上传显卡；
  代价是这 11 个文件合计从约 2.0 MB 变成约 6.4 MB）。
  没有被改动的 4x4 像素块原样保留原始数据，只有写了字的那几百到几千个块重新压缩；校验脚本确认：文字区域以外，
  解码后的图片与原图逐像素相同，透明通道也与原图相同。
- 图片所在文件里的其他对象（精灵、资源表）与原版逐字节相同。

安装
----
1. 关闭游戏，双击本文件夹里的 install.bat（会自动找到 Steam 里的 Suzerain，校验版本，备份原文件到游戏目录下
   _patch_backup\\tutorialimg_时间戳\\，再复制 @N_IMAGES@ 个图片文件）。
2. 如果提示 “Unexpected file hashes detected”：说明这些图片文件不是原版（游戏被 Steam 更新过，或被其他补丁改过）。
   先在 Steam 里“验证游戏文件完整性”，再重新运行 install.bat。

验证（约 2 分钟）
-----------------
在游戏里找到战争教程（里齐亚章节进入战争阶段时的教程提示；具体入口我没法实机确认），逐页翻到上面列出的图片：
标签应为中文，位置与原来的英文一致；图片其他部分应与原来一样清晰。
实测情况（2026-10-12，作者自己的一台机器，Windows 11，Steam 版 3.1.0 Build 175）：装着本包启动游戏、读档、玩了几步，游戏运行日志里没有报错；
但这些图只在里齐亚的战争教程里才会出现，我没有进过战争，所以图片本身是否显示正常，仍然没有在游戏里看过。

还原
----
双击 restore.bat：从游戏目录 _patch_backup\\tutorialimg_* 里取回原版图片文件并校验哈希。
找不到备份时，用 Steam 的“验证游戏文件完整性”也能还原（只会重下被改动的文件）。

已知局限
--------
- 截图里地图上的地名是游戏的虚构语言，按约定保留原文，没有改。
- 图片本身没有在游戏里看过（见上面“验证”）：图片替换属于“只换贴图”的低风险改动（不涉及场景、存档、代码），但仍请自行确认。
- 游戏被 Steam 更新后补丁会失效，需要重新验证文件完整性并重装。

构建信息：由 su_build_img.py 生成；重绘脚本 tut_repaint.py；校验脚本 su_verify_img.py。
"""


def make_readme():
    lines = []
    for name in sorted(tut_repaint.LABELS):
        pairs = []
        for l in tut_repaint.LABELS[name]:
            p = f"{l['en']} → {l['zh']}"
            if p not in pairs:                     # the deployment panel repeats "Rizian Army" on every row
                pairs.append(p)
        lines.append(f"  {name.replace('tutorial_', '')}：" + "、".join(pairs))
    changed = set(tut_repaint.LABELS)
    left = [n for n in ALL_TUTORIAL if n not in changed and n not in NO_ENGLISH]
    unchanged = [f"  {n.replace('tutorial_', '')}" for n in NO_ENGLISH if n not in changed]
    t = README_HEAD
    t = t.replace("@N_IMAGES@", str(len(changed)))
    t = t.replace("@IMAGE_LIST@", "\n".join(lines))
    parts = []
    if unchanged:
        parts.append("这些图里本来就没有英文（只有地图地名、图标和数字），不需要改：\n" + "\n".join(unchanged))
    if left:
        parts.append("这些图是“生产面板”的整块界面截图（文字很多，还夹着图标、数字和进度条），重绘风险和工作量都明显更高，本包没有改，仍是英文：\n"
                     + "\n".join(f"  {n.replace('tutorial_', '')}" for n in left))
    t = t.replace("@UNCHANGED_LIST@", "\n\n".join(parts) if parts else "（无）")
    return t


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
    log = Logger(os.path.join(LOGDIR, "build_img_log.txt"))
    t0 = time.time()
    if os.path.isdir(lp(out_dir)):
        shutil.rmtree(lp(out_dir))          # rebuild from scratch: no stale files from an earlier configuration
    # 1. repaint (pristine decode -> repainted PNG)
    infos = []
    for name in tut_repaint.LABELS:
        infos += tut_repaint.process(name)
    log(f"repainted {len(tut_repaint.LABELS)} images, {len(infos)} labels")
    for i in infos:
        if i["touches_window"]:
            raise SystemExit(f"search window too small: {i['name']} {i['en']}")
    # 2. bundles
    su_stage_img.build(out_dir, log)
    entries = su_pack.file_entries(out_dir)
    notes = {
        "base": "独立附加包：不依赖也不覆盖主汉化包和场景界面附加包，可单独安装；只替换战争教程截图的贴图文件。",
        "optional": True,
        "warning": "只换贴图（Crunch DXT 改为普通 DXT1/DXT5，文字区域以外逐像素相同），未经实机验证。异常时运行 restore.bat 还原。",
    }
    su_pack.write_manifest(out_dir, PACK_NAME, "tutorialimg", entries, notes)
    su_pack.write_installer(out_dir)
    su_pack.write_restore(out_dir)
    su_pack.write_readme(out_dir, make_readme())
    log(f"manifest written: {len(entries)} files; [{time.time() - t0:.0f}s]")
    if a.zip:
        log("zip: " + su_pack.zip_pack(out_dir))
    log("done")


if __name__ == "__main__":
    main()
