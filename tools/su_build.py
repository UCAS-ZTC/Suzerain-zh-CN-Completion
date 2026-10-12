"""Build the new patch pack: old pack's patched bundles + stage 0/1/2 supplements.

usage:  python su_build.py [--strict] [--only db|entity|all] [--out DIR] [--zip]
"""
import sys, time, shutil, argparse, pickle, glob
from lib_su import *
from su_apply import *
import su_pack
import su_stage2

PACK_NAME = "Suzerain_CN_Plus_SteamWin_2026-10-10"
OUT_ROOT = os.path.join(ROOT, PACK_NAME)
LOGDIR = os.path.join(WORK, "out")
os.makedirs(LOGDIR, exist_ok=True)

DB_PREFIX = "database_assets_all_"
ENT_PREFIX = "defaultlocalgroup_assets_assets_database_entitytextassets"


class Logger:
    def __init__(self, path):
        self.f = open(path, "w", encoding="utf-8")

    def __call__(self, s=""):
        self.f.write(s + "\n")
        self.f.flush()


def old_manifest():
    return json.load(open(os.path.join(OLD_PACK, "patch_manifest.json"), encoding="utf-8-sig"))


def single_mb(env):
    mbs = list(mb_objects(env))
    assert len(mbs) == 1, len(mbs)
    return mbs[0]


def build_db(out_dir, log):
    src = find_bundle(DB_PREFIX, AA_OLD)
    env = load_env(src)
    obj = single_mb(env)
    tree = obj.read_typetree()
    tm0 = load_stage0()
    touched, used = apply_db(tree, tm0, log)
    obj.save_typetree(tree)
    out = os.path.join(out_dir, AA_REL, os.path.basename(src))
    n = save_bundle(env, out)
    log(f"DB bundle written: {n} bytes, touched items: {len(touched)}")
    jdump([list(t) for t in touched], os.path.join(LOGDIR, "db_touched.json"))
    return out, used


def build_entity(out_dir, log, strict):
    src = find_bundle(ENT_PREFIX, AA_OLD)
    env = load_env(src)
    obj = single_mb(env)
    tree = obj.read_typetree()
    orig = pickle.load(open(os.path.join(CACHE, "ent_mb.pkl"), "rb"))["orig"]
    tm0 = load_stage0()
    force = load_ent_force()
    ed = EntityEditor(tree, orig, tm0, load_ent_text(), load_ent_fixes(), log, force)
    changed = ed.run()
    log(f"entity: changed fields {len(changed)}; leaf edits {sum(ed.n_changed_leaves.values())}")
    n_forced = sum(n for (c, t), n in ed.n_changed_leaves.items() if t == "force")
    unused_force = sorted(set(force) - ed.used_force)
    log(f"entity: forced (stale-refresh) leaves: {n_forced} leaves from {len(ed.used_force)}/{len(force)} forced ids")
    for t in unused_force:
        log(f"   UNUSED forced id {t}")
    if strict and unused_force:
        raise SystemExit("strict build: unused forced translations")
    miss_total = sum(len(v) for v in ed.missing.values())
    log(f"entity: missing translations: {miss_total} leaves ({len({e for v in ed.missing.values() for e in v})} distinct)")
    for k, v in sorted(ed.missing.items()):
        log(f"   missing {k}: {len(v)} leaves / {len(set(v))} distinct")
    if strict and miss_total:
        raise SystemExit("strict build: missing entity translations")
    unused_fix = [i for i in range(len(ed.fixes)) if ed.used_fix[i] == 0]
    log(f"entity: fixes unused: {unused_fix}")
    unused_tm = set(ed.ent_text) - ed.used_text
    log(f"entity: TM ids never used: {len(unused_tm)}")
    for u in sorted(unused_tm)[:80]:
        log(f"   UNUSED TM id {u} -> {ed.ent_text[u][:30]!r}")
    for (cont, key, tid, w) in ed.warns[:300]:
        log(f"   warn [{cont}.{key}] {tid}: {w}")
    log(f"entity: total warnings {len(ed.warns)}")
    for jk, text in changed.items():
        tree[jk] = text
    obj.save_typetree(tree)
    out = os.path.join(out_dir, AA_REL, os.path.basename(src))
    n = save_bundle(env, out)
    log(f"Entity bundle written: {n} bytes")
    return out, ed


def copy_old_payload(out_dir, names, log):
    for nme in names:
        s = os.path.join(AA_OLD, nme)
        d = os.path.join(out_dir, AA_REL, nme)
        os.makedirs(os.path.dirname(lp(d)), exist_ok=True)
        shutil.copyfile(lp(s), lp(d))
    log(f"copied {len(names)} unchanged payload bundles from old pack")


README = """Suzerain 汉化补全包（Plus）
===========================

这是什么
--------
在旧版“稳定版汉化补丁”（Suzerain_CN_Stable_SteamWin_2026-06-10）的基础上，补译还没翻译的英文。
可以直接装在原版游戏上，也可以覆盖在旧汉化包之上（安装器认得这两种状态，替换前都会备份）。

版本信息
--------
- 发布名称：Suzerain_CN_Plus_SteamWin_2026-10-10
- 适用平台：Windows Steam，AppID 1207650，Steam buildid 23568265
- 目标 catalog.hash：f65497d562f96d21d9cf26514449e829
- 目标 build-guid：d466538e3d5d44a6b1bb183072d159ad
- 内容：258 个资源包文件，只替换 Suzerain_Data\\StreamingAssets\\aa\\StandaloneWindows64 下的 .bundle，不改程序和存档。

修订记录
--------
- 第 4 版（2026-10-12，重要修复）：第 1-3 版把地图标记里的“国家宗教 / 民族名称”（如 Sordish、Wruhecism，共 413 处）也译成了中文。
  实机测试发现：这些名称译成中文后，进入游戏里的地图界面时整套界面（左上角国徽、经济条、右侧按钮、
  新闻角标、人物头像）都不显示；只把这 413 处改回英文就恢复正常（推测游戏内部按这些英文名称查找数据）。
  本版把它们改回英文，其余译文一字未动（下面的错字修正除外）。
  代价：国家 / 城市信息面板里的民族、宗教饼图图例保持英文。
  同版另外修正了旧译文（和少量新译文）里的错字与重复字，共 @N_TYPOS@ 处，例如：统计图副标题“经济形式”→“经济形势”，
  “国际形式”→“国际形势”，“他们的的权力”→“他们的权力”，“先生先生”→“先生”，“正在在进行”→“正在进行”，
  “瓦尔尔戈兰”→“瓦尔戈斯兰”。对白和资料文本里都有；每一处的前后对照见本文件夹里的 typo_changes.txt。
  已装过第 1-3 版的：直接重新运行 install.bat 即可升级（安装器认得这些旧版本）。

相比旧版补译了什么
------------------
1. 资料类文本：百科词条、新闻、地图标记（国家/城市/人物卡片，旧版这部分几乎全是英文）、决策、政策、报告、
   章节标题、剧情包引言等，共约 @N_TEXT_LEAVES@ 处字段，里齐亚 DLC 的内容占大头。
2. 对话库：夹在中文对白里的残余英文行、菜单文本，以及对白脚本里直接拼进句子的称谓、势力名单、地名（约 80 处）。
3. 成就（名称与描述，约 230 个文件）、战争教程弹窗、战争目标、状态效果名称。
4. 状态效果上的“百科链接标题”：旧版还是英文，而对应的百科词条标题已经是中文，两边对不上；本包已对齐。
5. 旧译文已经过时的条目（@N_FORCE_TEXTS@ 条不同的文本，出现在 @N_FORCE_LEAVES@ 处；以百科词条和新闻/报告为主，也有日志和决策）：
   游戏英文在旧汉化包做完之后又被改写或扩写（改了年份和数字、新增句子和段落、整条重写，例如伦堡王国、
   碧翠斯·利文斯顿、皇家商业交流联盟、国际联盟等词条），旧中文与现版英文对不上；本包按现版英文重译了
   对不上的段落（漏译的句子也一并补上），其余仍沿用旧译文。

翻译约定：沿用旧版已有译名；人名写作“名·姓”；剧中人造语（索德兰语、里齐亚语等）保留原文。

仍然是英文的部分
----------------
- 写在三个场景文件里的界面文字：主菜单、设置、存档/账号界面、战争界面的按钮和提示、人物卡片的姓名与头衔、
  制作人员名单的职务、等级称号等。这部分放在“可选附加包” Suzerain_CN_Plus_SceneUI_SteamWin_2026-10-10 里，
  因为它改动场景文件，旧版作者曾因此遇到读档闪退（原因不明），所以单独提供。作者已在自己的机器上实测过：装上后启动游戏 7 次、每次都读了档，
  没有闪退（细节见该包的 README）；但这不能保证你的机器和存档上一定没有问题，装完请读一次档确认。
- 剧中人造语、缩写、制作名单里的人名等，有意保留。
- 枚举型字段（如国家关系、军事条件结果）：游戏代码按英文解析，改了会出错。
- 国家 / 城市信息面板里民族、宗教饼图图例的名称（Sordish、Wruhecism 等 413 处）：见上面“修订记录”，译成中文会让地图界面整体消失（原因未查明，推测它们同时是游戏内部的查找键），所以保持英文。
- 教程截图里烧进图片的英文；编译进游戏程序里的文字（其中的整句和多词文案放在可选附加包 Suzerain_CN_Plus_ProgramText_SteamWin_2026-10-10 里；
  单个常用词如 Yes / No / Options 没有改，其中 17 个放在一个更激进的可选附加包 Suzerain_CN_Plus_ProgramWords_SteamWin_2026-10-10 里，
  它需要先装 ProgramText 那个包）；开发用的草稿对话（玩家进不去）。
- 对白脚本里还残留一些英文变量赋值，经检查已不再被任何文本引用，游戏里不会显示。
- 旧译文里仍可能有少量与现版英文对不上的地方：判断是否过时靠的是年份、数字、段落结构、句数、长度等线索，
  英文被悄悄改写、而这些线索都没变的条目查不出来。发现的话请记下条目名反馈。
- 2026-10-12 的实机截图普查（装全所有附加包之后）里，仍然显示英文的界面文字主要是：日期时间、城市 / 国家弹窗上的按钮、序数词（1st / 2nd）、
  关系和军力的等级名、读取窗口里的存档名；设置页下拉框的取值（On / Off / High / Default）也仍是英文。
  逐项说明和原因见汉化安装器文件夹里的 README.txt（第八节）。

安装
----
1. 关闭游戏，解压后双击 install.bat（或右键 install.ps1 用 PowerShell 运行）。
2. 脚本会自动找到 Steam 里的 Suzerain，校验 catalog.hash / build-guid 和每个文件的哈希，
   把将被替换的文件备份到游戏目录 _patch_backup\\plus_时间戳\\，再复制补丁并逐个校验。
3. 如果提示 “Unexpected file hashes detected”：说明文件既不是原版，也不是旧汉化包的版本（游戏被 Steam 更新过，
   或被其他补丁改过）。请先在 Steam 里“验证游戏文件完整性”，再重新安装。不要随手加 -Force。
4. 游戏不在 Steam 的常规库里时，可以手动指定路径：
   powershell -ExecutionPolicy Bypass -File install.ps1 -GameRoot "D:\\Games\\Suzerain"

实测情况
--------
2026-10-12 在作者自己的一台机器，Windows 11，Steam 版 3.1.0 Build 175（用作者自己的存档）上实机测过：启动，从“继续”和读取窗口读档进入游戏，
点过几段对白，百科（含对白里的百科链接）、新闻、日志、笔记、国家 / 城市信息面板都显示为中文，游戏运行日志里没有与汉化相关的报错。
没有测过：新开一局、成就界面、里齐亚章节和战争界面（含教程弹窗）。其他机器、其他存档上的表现没有验证。

装完建议过一遍（约 10 分钟）
----------------------------
- 新开一局，看开场对话；存档，退回主菜单，再读档。
- 打开百科、日志、新闻；点开几张地图标记卡片（国家/城市/人物）。
- 打开成就界面。
- 里齐亚的战争界面和教程弹窗（如已解锁）。
- 看到方块、乱码、文字超出框的地方，请记下位置反馈。

还原
----
- 双击 restore.bat：把本包改过的文件换回安装前的样子（取自 _patch_backup\\plus_*），逐个校验哈希。
  只处理“当前确实是本包版本”的文件；其他状态的文件（例如被 Steam 更新过的）不会被覆盖。
- 或在 Steam 里“验证游戏文件完整性”：只会重下被改动的文件，同时也会去掉旧汉化包。

注意
----
- 只支持当前这版 Windows Steam 游戏。游戏被 Steam 更新后，补丁会失效或被还原，需要先验证文件完整性再重新安装。
  Steam → Suzerain → 属性 → 更新 里把自动更新设为“仅在启动游戏时更新”，可以减少被悄悄覆盖的机会。
- 请用 install.bat 安装，不建议手动复制：补丁里有文件名很长的资源包（相对路径最长 199 个字符），
  Windows 资源管理器和普通 PowerShell 命令在较深的目录下复制会报“路径过长”，install.bat 已按长路径方式处理。

构建信息：由 su_build.py 生成；翻译记忆库 tm\\*.json；校验脚本 su_verify.py。
"""


def finalize(out_dir, log, extra_notes=None, readme_vars=None):
    om = old_manifest()
    accept_old = {f["file_name"]: [f["patched_sha256"]] for f in om["files"]}
    # an earlier build of this very pack (snapshot of its manifest) is an installable state too
    for prev in sorted(glob.glob(os.path.join(LOGDIR, "plus_build*_manifest.json"))):
        pm = json.load(open(prev, encoding="utf-8-sig"))
        for f in pm["files"]:
            lst = accept_old.setdefault(f["file_name"], [])
            if f["patched_sha256"] not in lst:
                lst.append(f["patched_sha256"])
        log(f"accepting {len(pm['files'])} patched hashes of {os.path.basename(prev)} ({pm.get('built_at')}) as installable states")
    entries = su_pack.file_entries(out_dir, accept_old)
    notes = {
        "base": "在 Suzerain_CN_Stable_SteamWin_2026-06-10 基础上补译；可直接装在原版游戏上，也可覆盖在旧汉化包之上。",
        "known_gaps": [
            "写在场景文件里的界面文字（主菜单/设置/存档/账号/战争界面、人物卡片姓名与头衔、制作人员职务）仍为英文；"
            "见可选附加包 Suzerain_CN_Plus_SceneUI_SteamWin_2026-10-10。",
            "Relations / MilitaryStrengthConditions.Result 等枚举型字段按设计保持英文（游戏代码按英文解析）。",
            "MapTokens 的 ReligionDatas.Name / EthnicityDatas.Name（413 处，民族/宗教饼图图例）保持英文：翻译后游戏内地图界面整体消失（实机二分定位，第 4 版起恢复英文）。",
            "剧中人造语（索德兰语/里齐亚语）、缩写、制作名单人名按设计保留原文。",
            "对白脚本里残留的英文变量赋值经检查已不再被任何文本引用，不会显示。",
            "旧译文是否过时是用年份、数字、段落结构、句数、长度比等线索检测的；英文被悄悄改写、但段落长度和数字都没变的条目无法检出，仍保留旧译文。",
        ],
    }
    if extra_notes:
        notes.update(extra_notes)
    su_pack.write_manifest(out_dir, PACK_NAME, "plus", entries, notes)
    su_pack.write_installer(out_dir)
    su_pack.write_restore(out_dir)
    readme = README
    for k, v in (readme_vars or {}).items():
        readme = readme.replace(k, str(v))
    if "@N_" in readme:
        raise SystemExit("README placeholders not filled: build without entity stage?")
    su_pack.write_readme(out_dir, readme)
    log(f"manifest written: {len(entries)} files")
    return entries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--only", default="all", choices=["db", "entity", "stage2", "all"])
    ap.add_argument("--out", default=OUT_ROOT)
    ap.add_argument("--zip", action="store_true")
    a = ap.parse_args()
    out_dir = a.out
    log = Logger(os.path.join(LOGDIR, "build_log.txt"))
    t0 = time.time()
    used_db = ed = None
    if a.only in ("db", "all"):
        _, used_db = build_db(out_dir, log)
        log(f"[{time.time() - t0:.0f}s] db done")
    if a.only in ("entity", "all"):
        _, ed = build_entity(out_dir, log, a.strict)
        log(f"[{time.time() - t0:.0f}s] entity done")
    if a.only == "stage2":
        su_stage2.build(out_dir, log, a.strict)
        log(f"[{time.time() - t0:.0f}s] stage2 done")
    if used_db is not None and ed is not None:
        smap = script_map(load_stage0())
        unused = [k for k in smap if k not in used_db and k not in ed.used_script]
        log(f"script TM units unused in BOTH db and entity: {len(unused)}")
        for u in unused:
            log(f"   UNUSED {u}")
        if unused and a.strict:
            raise SystemExit("strict build: unused script units")
    if a.only == "all":
        om = old_manifest()
        keep = [f["file_name"] for f in om["files"]
                if f["original_sha256"] != f["patched_sha256"]
                and not f["file_name"].startswith(DB_PREFIX)
                and not f["file_name"].startswith(ENT_PREFIX)]
        copy_old_payload(out_dir, keep, log)
        su_stage2.build(out_dir, log, a.strict)      # after the payload copy: stage 2 may rebuild a copied bundle
        log(f"[{time.time() - t0:.0f}s] stage2 done")
        n_forced = sum(n for (c, t), n in ed.n_changed_leaves.items() if t == "force")
        n_text = sum(n for (c, t), n in ed.n_changed_leaves.items() if t in ("text", "fix"))
        log(f"entity: first-time translated leaves (text+fix): {n_text}")
        # translation-slip rules: every rule must still match (stale rule = the game text changed), report + review list
        low = []
        for i, (rx, to, meta) in enumerate(typo_rules()):
            n = TYPO_HITS[i]
            need = meta.get("min", 1)
            log(f"typo rule {i:2d} {'ok ' if n >= need else 'LOW'} hits={n:3d} (min {need}) {meta['re']!r} -> {to!r}")
            if n < need:
                low.append(i)
        n_typos = sum(TYPO_HITS.values())
        log(f"typo rules: {n_typos} replacements in total ({len(TYPO_LOG)} logged)")
        with open(os.path.join(LOGDIR, "typo_changes.txt"), "w", encoding="utf-8") as tf:
            tf.write(f"translation-slip fixes applied by this build: {n_typos}\n\n")
            for where, i, before, after in TYPO_LOG:
                tf.write(f"{where}\n    {before}\n -> {after}\n")
        if low and a.strict:
            raise SystemExit(f"strict build: typo rules with fewer hits than expected: {low}")
        finalize(out_dir, log, readme_vars={"@N_FORCE_TEXTS@": len(ed.used_force),
                                            "@N_FORCE_LEAVES@": n_forced,
                                            "@N_TEXT_LEAVES@": int(round(n_text / 10.0)) * 10,
                                            "@N_TYPOS@": n_typos})
        # change list for the user: every typo fix with its surrounding text (before -> after)
        tl = ["错字与重复字修正清单（共 %d 处）" % n_typos,
              "格式：位置，然后是“修正前”与“修正后”的上下文，方括号里是被改的那一段。",
              "位置：DB = 对话库（conv 对话编号 # 条目编号），ENT = 资料文本（容器.字段）。", ""]
        for where, i, before, after in TYPO_LOG:
            tl += [where, "    前：" + before.replace("\n", "\\n"), "    后：" + after.replace("\n", "\\n"), ""]
        with open(os.path.join(out_dir, "typo_changes.txt"), "w", encoding="utf-8-sig", newline="") as tf:
            tf.write(su_pack._crlf("\n".join(tl)))
        if a.zip:
            log("zip: " + su_pack.zip_pack(out_dir))
    log("done")


if __name__ == "__main__":
    main()
