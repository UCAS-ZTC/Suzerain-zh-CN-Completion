"""Build the OPTIONAL scene-UI add-on pack (stage 3).

usage:  python su_build3.py [--strict] [--out DIR] [--zip]
The add-on only replaces the three scene bundles and ships its own installer + restore script.
"""
import sys, time, argparse
from lib_su import *
import su_pack
import su_stage3

PACK_NAME = "Suzerain_CN_Plus_SceneUI_SteamWin_2026-10-10"
OUT_ROOT = os.path.join(ROOT, PACK_NAME)
LOGDIR = os.path.join(WORK, "out")
os.makedirs(LOGDIR, exist_ok=True)

README = """Suzerain 汉化补充包：场景界面文字（可选附加包）
====================================================

这是什么
--------
主汉化包（Suzerain_CN_Plus_SteamWin_2026-10-10）翻译的是对话、百科、新闻、地图标记、成就、战争教程等“数据里的文字”。
游戏里还有一批文字直接写在三个场景文件里（主菜单、索德兰、里齐亚的界面控件），例如：
  主菜单与设置项、存档/读档界面、账号相关界面、战争界面的按钮和提示、地图/百科的各类标签、
  人物卡片上的姓名与头衔、制作人员名单的职务、等级称号。
本附加包只替换这三个场景文件，把其中的英文显示文字改成中文。除显示文字外，场景文件里其余所有对象的数据都与原版
逐字节相同（不改字体、不改引用、不改结构、不改程序用到的标识符）；文件本身经过重新打包，所以哈希与原版不同。

为什么是“可选”
---------------
旧汉化包（Suzerain_CN_Stable_SteamWin_2026-06-10）的说明里提到：早期的“场景字体增强/内嵌提示词”版本会在读取存档时崩溃，所以被移出了稳定版。
本附加包的做法不同（只改字符串，不动字体和结构），但仍然改动了场景文件。
实测情况（2026-10-12，作者自己的一台机器，Windows 11，Steam 版 3.1.0 Build 175，用作者自己的存档，同时装着主汉化包和其他附加包）：
  - 装着本包启动游戏 7 次，每次都读了档（主菜单“继续”或“读取”窗口）进入游戏，没有闪退，游戏运行日志里没有报错；
  - 主菜单（继续 / 读取 / 选项 / 制作人员）、设置页、制作人员名单、读取窗口、暂停菜单（含退出确认弹窗）都显示为中文；
  - 索德兰场景里的经济走势、当前建议、政府 / 司法 / 局势、关系、笔记、日志、新闻、收藏等面板都显示为中文，点开都正常。
  没有测过：里齐亚场景和战争界面（本包改了里齐亚场景文件，这部分一次也没有进去过）、新开一局、手动存档。
旧汉化包说明里提到的“读档崩溃”没有复现，但原因不明，不能保证你的机器和存档上一定没有。
所以仍请把它当作“可选项”：先装主汉化包并确认游戏正常，再装本附加包，按下面的清单测一遍；有任何异常，运行 restore.bat 即可还原。

安装
----
1. 先安装主汉化包，并确认能正常进游戏、读档。
2. 关闭游戏，双击本文件夹里的 install.bat（会自动找到 Steam 里的 Suzerain，校验版本，备份原文件到游戏目录下
   _patch_backup\\sceneui_时间戳\\，再复制三个场景文件）。
3. 如果提示 “Unexpected file hashes detected”：说明场景文件不是原版（游戏被 Steam 更新过，或被其他补丁改过）。
   先在 Steam 里“验证游戏文件完整性”，再重新运行 install.bat。

验证清单（建议逐项过一遍，约 10 分钟）
------------------------------------
- 主菜单：能显示、按钮文字为中文、点击正常；设置界面各项文字正常；制作人员名单能打开。
- 新开一局并进入游戏，再存档；退出到主菜单后“读取存档”——这一步最重要（旧版就是死在读档）。
- 分别读取索德兰、里齐亚（如有）的存档，确认不会崩溃；打开百科、日志、新闻、人物卡片。
- 里齐亚战争界面：单位提示、行动按钮、教程弹窗的文字是否完整显示（没有被截断或变成方块）。
- 如果有汉字显示成方块/问号：说明该处界面字体没有中文回退，请反馈具体位置。

还原
----
双击 restore.bat：从游戏目录 _patch_backup\\sceneui_* 里取回三个原版场景文件并校验哈希。
找不到备份时，用 Steam 的“验证游戏文件完整性”也能还原（只会重下被改动的文件）。

已知局限
--------
- 没有改的内容：编译进游戏程序里的文字（无法通过替换资源文件翻译）、虚构语言（索德兰语/里齐亚语）、人名/网名/公司名（制作名单里的人名）、
  仅供开发使用的占位文字与调试界面。
- 场景文件里已经是中文、实机里却仍显示英文的文字：看起来是游戏运行时用程序里的英文把它盖掉了，改场景文件解决不了（我没有反编译程序，这是推断）。
  我拿本包的场景文件逐个核对过：城市弹窗上的按钮“Open City Information”在文件里已经是“打开城市信息”，收藏页和制作人员页用到的
  “收藏 / 制作人员 / 未解锁”在文件里也已是中文；但实机里城市弹窗按钮仍是英文，收藏页和制作人员页的标题仍是 COLLECTIONS / CREDITS、
  条目状态仍是 Locked（后两处是在没装程序内文案包的那次启动里看到的）。“Open Country Information”在场景文件里根本不存在，是程序拼出来的。
  其他仍是英文的地方，见汉化安装器文件夹里的 README.txt（第八节）。
- 内购商店配置（store/offers，PC 版不显示）没有翻译。
- 文字长度与界面排版：上面实测看过的界面里，中文都能正常显示（没有方框）；其余界面（尤其是里齐亚战争界面）没有检查，个别按钮可能仍会换行或被裁切。
- 游戏被 Steam 更新后补丁会失效，需要重新验证文件完整性并重装。

构建信息：由 su_build3.py 生成；翻译记忆库 tm/stage3.json；校验脚本 su_verify3.py。
"""


class Logger:
    def __init__(self, path):
        self.f = open(path, "w", encoding="utf-8")

    def __call__(self, s=""):
        self.f.write(s + "\n")
        self.f.flush()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--out", default=OUT_ROOT)
    ap.add_argument("--zip", action="store_true")
    a = ap.parse_args()
    out_dir = a.out
    log = Logger(os.path.join(LOGDIR, "build3_log.txt"))
    t0 = time.time()
    written, s3 = su_stage3.build(out_dir, log, a.strict)
    entries = su_pack.file_entries(out_dir)
    notes = {
        "base": "建议先安装主汉化包 Suzerain_CN_Plus_SteamWin_2026-10-10 并确认游戏正常，再安装本包；两者互不覆盖（本包只替换三个场景文件）。",
        "optional": True,
        "warning": "改动了场景文件，旧汉化包曾因场景改动在读档时崩溃；本包只改字符串。2026-10-12 在 Windows Steam 版 3.1.0 Build 175 上装着本包启动游戏 7 次、每次都读档进入游戏，没有闪退；里齐亚战争界面没有检查。异常时运行 restore.bat 还原。",
    }
    su_pack.write_manifest(out_dir, PACK_NAME, "sceneui", entries, notes)
    su_pack.write_installer(out_dir)
    su_pack.write_restore(out_dir)
    su_pack.write_readme(out_dir, README)
    log(f"manifest written: {len(entries)} files; [{time.time() - t0:.0f}s]")
    if a.zip:
        log("zip: " + su_pack.zip_pack(out_dir))
    log("done")


if __name__ == "__main__":
    main()
