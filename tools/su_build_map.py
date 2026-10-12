# -*- coding: utf-8 -*-
"""Build the OPTIONAL map-label add-on pack (Chinese annotations beside the English place names on map / overlay textures).

usage:  python su_build_map.py [--out DIR] [--zip] [--only PREFIX[,PREFIX...]]
Input : cache\\map\\out\\<texture>.png (+ .labels.json)  produced by map_run.py
Output: Suzerain_CN_Plus_MapLabels_SteamWin_2026-10-10\\ (bundles, patch_manifest.json, install/restore scripts, README.txt, 地名对照表.csv)
Bundles that the Plus main pack also patches (commonassets_*, storypack_rizia_*) are built ON TOP of the main pack's copy.
"""
import sys, time, json, csv, shutil, argparse, collections, re, statistics
from lib_su import *
import su_pack
import map_cfg
import map_stage as MS
import map_names as MN

PACK_NAME = "Suzerain_CN_Plus_MapLabels_SteamWin_2026-10-10"
MAIN_PACK = "Suzerain_CN_Plus_SteamWin_2026-10-10"
OUT_ROOT = os.path.join(ROOT, PACK_NAME)
LOGDIR = os.path.join(WORK, "out")
MAPOUT = os.path.join(CACHE, "map", "out")
os.makedirs(LOGDIR, exist_ok=True)

GROUPS = [
    ("世界地图（T_Map_World_01–06）", lambda n: n.startswith("T_Map_World_")),
    ("索德兰地图（T_Map_Sordland_01–04）", lambda n: n.startswith("T_Map_Sordland_")),
    ("里齐亚地图（T_Map_Rizia_01–04）", lambda n: n.startswith("T_Map_Rizia_")),
    ("帕雷地图（T_Map_Pales_01–06）", lambda n: n.startswith("T_Map_Pales_")),
    ("伦堡战争地图（T_Map_RumburgWar_01–02）", lambda n: n.startswith("T_Map_RumburgWar_")),
    ("帕雷 / 齐勒 叠加层（pales_*、zille_*）", lambda n: n.startswith("pales_") or n.startswith("zille_")),
    ("赫吉岛叠加层（Heljiland_*）", lambda n: n.startswith("Heljiland_")),
    ("世界地图上的国名 / 岛名标签（world_*）", lambda n: n.startswith("world_")),
    ("图鉴里的地区地图（c_*region）", lambda n: n.startswith("c_")),
]

README_HEAD = """Suzerain 汉化补充包：地图与地名贴图的中文标注（可选附加包）
==========================================================

这是什么
--------
游戏里的地图（世界地图、索德兰、里齐亚、帕雷、伦堡战争图）和一批地名贴图（帕雷 / 齐勒 / 赫吉岛的叠加层、图鉴里的地区地图）
把地名直接画在图片上，主汉化包只改数据文字，改不到它们。
本包的做法是“标注”而不是“替换”：英文地名原样保留，在它旁边（通常是下方，其次是上方或侧面）加一行中文，两者一一对应、
可以对照着看；字母间隔很大的国名 / 海名（例如 B R E N A S）则把中文字沿着字母链排开。

包含什么（共 @N_TEX@ 张贴图、@N_LABELS@ 处标注、@N_PAIRS@ 个不同的“英文 → 中文”对照）
------------------------------------------------------------------------------------
@GROUP_LIST@
（“处”按落笔位置计：字母间隔很大的名字，如 B E R G I A，每个中文字算一处。）

完整的“英文 → 中文”对照在本文件夹的 地名对照表.csv 里（带“来源”列：沿用主包 / 新拟），觉得哪个译名不顺眼，可以直接告诉我批量改。

和其他补丁包的关系
------------------
- 需要先安装主汉化包 @MAIN_PACK@。原因：世界地图（T_Map_World_*）和帕雷地图（T_Map_Pales_*）所在的两个资源文件
  （commonassets_… 和 storypack_rizia_…）主包也改过，本包是在“主包版本”的基础上再加地图标注。
  没装主包就运行本包的安装器，会因为这两个文件的哈希不是“主包版本”而拒绝安装（此时不会改动任何文件）。
- 其余 @N_INDEP@ 个文件是只含地图贴图的资源文件，主包 / 场景界面包 / 战争教程图片包 / 程序文字包都没有动过它们，互不覆盖。
- 顺序：安装 = 先主包、后本包；卸载 = 先本包（restore.bat）、后主包。以后要重新安装主包（例如主包更新）时，
  也请先运行本包的 restore.bat，装完主包再装本包。如果顺序弄反了（先运行了主包的还原），主包的还原脚本会因为那两个
  共享文件的哈希对不上而保持它们不动并提示；这时先运行本包的 restore.bat，再重新运行主包的还原即可。不要对这两个文件用 -Force。
  万一状态乱了，最稳的办法是 Steam“验证游戏文件完整性”回到原版，再依次重装主包和本包。

怎么做的（便于复查）
--------------------
1. 把每张地图贴图解出来，用 RapidOCR 找出英文地名的位置（含倾斜角度）。大地图逐张目视检查，修正识别错的字、
   补上漏掉的地名（例如字母间隔很大的区域名）、去掉被误认的碎片。
2. 中文译名来源（优先级从高到低）：本包新拟 / 校对的地名表 → 主汉化包里地图图标和首都已经用过的译名 → 主包对话 / 图鉴文字里已有的译名。
   虚构语言的地名没有官方中文，没有现成译名的按主包的音译风格新拟。@N_PAIRS@ 个对照里：@N_REUSE@ 个沿用主包已有的译名，
   @N_NEW@ 个是新拟或校对的，@N_COMB@ 个由前后缀与已有名组合而成（逐条的来源见 地名对照表.csv 的“来源”列）。
   主包里已有同名译名的，全部逐一比对过，零冲突；新拟的那部分没有官方译名可比，是否顺耳要你来把关（直接改 csv 告诉我即可批量替换）。
3. 用 Noto Serif SC（与游戏界面所用的中文字体同一字体家族）写中文：字号随英文字高、倾斜角随英文走向；
   描边（光晕）取标签局部的底图颜色，不会在底图上留下突兀的白边；位置从“下 / 上 / 右 / 左”候选里选压到的线条最少、
   不盖住其他英文和地图图标的那一个。带透明通道的贴图（叠加层、图鉴地区图）只在已有内容上加光晕，文字本身带自己的透明度。
4. 图像编码：原图是 DXT1 / DXT5 压缩。没有被写到的 4x4 像素块保留原始压缩数据，只有写了字的块重新压缩；
   能原位更新的贴图数据（大地图）直接在资源文件内原位改写，文件大小不变。原本是 Crunch 压缩的贴图（图鉴地区图、叠加层等）
   手头没有 Crunch 压缩器，改存为同类的普通 DXT 并直接存进文件里（这批文件会变大；运行时显存占用据我所知不变，
   因为 Unity 本来就把 Crunch 解码成 DXT 再上传显卡）。
5. 校验（脚本 su_verify_map.py 对成品包逐文件检查，不是抽查；下面每一条都是脚本实际检查过的）：
@VERIFY_NOTE@
安装
----
1. 先装主汉化包（见上）。把本包解压到较短的路径（例如 D:\\SuzerainMapLabels\\）：包里最长的相对路径有 @MAXREL@ 个字符，
   解压到太深的文件夹，资源管理器会报“路径过长”；也请用 install.bat 安装，不要手动复制（install.bat 已按长路径方式处理）。
   关闭游戏，双击本文件夹里的 install.bat（会自动找到 Steam 里的 Suzerain，校验版本，
   备份原文件到游戏目录下 _patch_backup\\maplabels_时间戳\\，再复制 @N_FILES@ 个资源文件）。
2. 如果提示 “Unexpected file hashes detected”：这些文件不是预期的版本。最常见的原因是还没装主包，其次是游戏被 Steam 更新过、
   或被其他补丁改过。装好主包（或先在 Steam 里“验证游戏文件完整性”）后重新运行 install.bat。

验证（约 3 分钟）
-----------------
进入游戏后打开地图（世界地图 / 国家地图 / 战争地图），英文地名旁边应当有中文；图鉴里的地区条目（例如 Brenas、Holsord）的配图里也有。
实测情况（2026-10-12，作者自己的一台机器，Windows 11，Steam 版 3.1.0 Build 175，同时装着主汉化包和其他附加包）：读档进入游戏后，
索德兰及周边的主地图上，英文地名旁边有中文标注，放大缩小后仍清晰可读，游戏运行日志里没有报错。
没有逐张看过的：里齐亚章节的地图、战争地图、叠加层、图鉴里的地区地图等其余贴图。

还原
----
双击 restore.bat：只还原本包改过的文件（从游戏目录 _patch_backup\\maplabels_* 里取回备份并校验哈希），还原后回到“只装了主包”的状态。
找不到备份时，用 Steam 的“验证游戏文件完整性”也能还原，但那两个共享文件会连主包的改动一起回到原版，需要重装主包。

已知局限
--------
- OCR 不是 100%：特别小的字、被图标 / 线条压住的字、沿曲线很弯的海域名，可能没有标到。大地图我逐张看过，漏标的是少数（没有做定量统计）；
  图鉴地区图（c_*）里的小字号城镇名只标了 OCR 能识别且有译名的那部分，保证的是每张图的区域大名和主要城市。
@MISSING@- 地名是音译，没有官方中文可对照；与主包对话里已经出现过的同名地点保持一致。
- 标注是画在贴图上的像素：游戏里放大 / 缩小地图时中文与英文同比例缩放。
- 实机截图普查（2026-10-12，装着本包）里，主菜单背景那张装饰地图上还能看到少量没有中文标注的英文字（例如设置页左侧的大号字母 RUM…）；
  这类漏标我没有逐一统计。
- 只实测了索德兰及周边的主地图（见上面“验证”），其余贴图没有逐张在游戏里看过，请自行确认。只换贴图是低风险改动（不涉及场景、存档、代码）。游戏被 Steam 更新后补丁会失效，需要重新验证文件完整性并重装。

构建信息：由 su_build_map.py 生成；标注脚本 map_run.py / map_render.py / map_lab.py；校验脚本 su_verify_map.py。
"""


class Logger:
    def __init__(self, path):
        self.f = open(path, "w", encoding="utf-8")

    def __call__(self, s=""):
        self.f.write(s + "\n")
        self.f.flush()


def annotated_names(only=None):
    names = []
    for n in map_cfg.ALL:
        p, j = os.path.join(MAPOUT, n + ".png"), os.path.join(MAPOUT, n + ".labels.json")
        if not (os.path.exists(p) and os.path.exists(j)):
            continue
        if not json.load(open(j, encoding="utf-8"))["placed"]:
            continue
        if only and not any(n.startswith(o) for o in only):
            continue
        names.append(n)
    return names


def label_stats(names):
    per, pairs, missing = {}, collections.Counter(), collections.Counter()
    for n in names:
        d = json.load(open(os.path.join(MAPOUT, n + ".labels.json"), encoding="utf-8"))
        per[n] = len(d["placed"])
        for p in d["placed"]:
            pairs[(p["text"], p["zh"])] += 1
        for m in d["missing"]:
            missing[m] += 1
    # letter-spaced names (B E R G I A) are placed one Chinese character per letter group, so `placed` holds a per-character
    # record next to the full-name record; the glossary lists the full name only
    by_en = collections.defaultdict(list)
    for en, zh in pairs:
        by_en[en.lower()].append(zh)
    for en, zh in list(pairs):
        if len(zh) == 1 and any(len(z) > 1 and zh in z for z in by_en[en.lower()]):
            del pairs[(en, zh)]
    return per, pairs, missing


def source_of(en, zh):
    k = MN.key(en)
    est = ESTABLISHED
    if k in est or k in MN.ENTITY or k in MN.CORPUS:
        return "沿用主包"
    if k in MN.MANUAL:
        return "新拟/校对"
    return "组合(前后缀+已有名)"


def _established():
    ns = {}
    p = os.path.join(MAPLAB_DIR, "names_established.py")
    exec(compile(open(p, encoding="utf-8").read(), p, "exec"), ns)
    return {MN.key(k) for k in ns.get("NAMES", {})}


ESTABLISHED = _established()


def make_readme(names, per, pairs, missing, n_files, n_indep, verify_note, max_rel):
    glines = []
    for title, pred in GROUPS:
        ns = [n for n in names if pred(n)]
        if ns:
            glines.append(f"  {title}：{len(ns)} 张，{sum(per[n] for n in ns)} 处标注")
    t = README_HEAD
    t = t.replace("@N_TEX@", str(len(names))).replace("@N_LABELS@", str(sum(per.values()))).replace("@N_PAIRS@", str(len(pairs)))
    t = t.replace("@GROUP_LIST@", "\n".join(glines)).replace("@MAIN_PACK@", MAIN_PACK)
    src = collections.Counter(source_of(en, zh) for en, zh in pairs)
    t = t.replace("@N_REUSE@", str(src["沿用主包"])).replace("@N_NEW@", str(src["新拟/校对"])).replace("@N_COMB@", str(src["组合(前后缀+已有名)"]))
    assert sum(src.values()) == len(pairs)
    t = t.replace("@N_INDEP@", str(n_indep)).replace("@N_FILES@", str(n_files)).replace("@MAXREL@", str(max_rel))
    t = t.replace("@VERIFY_NOTE@", verify_note)
    if missing:
        t = t.replace("@MISSING@", "- 有 %d 个地名在主包和语料里都没有现成译名、也没有把握新拟，保持英文未标：%s。\n"
                      % (len(missing), "、".join(sorted(missing))))
    else:
        t = t.replace("@MISSING@", "")
    return t


def verify_note(out_dir, n_tex):
    """README facts about verification, taken from the reports the checkers actually wrote -- so the README can never claim more
    than was checked. Reports older than the bundles in the pack are treated as missing."""
    aa = os.path.join(out_dir, AA_REL)
    newest = max(os.path.getmtime(lp(os.path.join(aa, f))) for f in os.listdir(lp(aa)))
    rep = os.path.join(LOGDIR, "verify_map_report.txt")
    if not os.path.exists(rep) or os.path.getmtime(rep) < newest:
        return "   （构建之后还没有运行校验脚本，所以这里不作任何校验声明。）\n"
    txt = open(rep, encoding="utf-8").read()
    m = re.search(r"textures checked: (\d+); problems: (\d+)", txt)
    if not m or int(m.group(2)) != 0:
        raise SystemExit("verify report shows problems -- refusing to write a README that claims a clean verification")
    n_obj = int(m.group(1))
    per_tex = {}
    for name, p in re.findall(r"^\s+(\S+): \d+x\d+ fmt \d+ mips \d+ \w+ \| .*?min PSNR ([\d.]+) dB", txt, re.M):
        per_tex[name] = float(p)
    assert len(per_tex) == n_tex, (len(per_tex), n_tex)
    lo, med = min(per_tex.values()), statistics.median(per_tex.values())
    lines = [
        "   - 共 %d 个贴图对象（%d 张不同的贴图；伦堡战争图的 2 张在两个资源文件里各有一份）全部通过，0 个问题。" % (n_obj, n_tex),
        "   - 每个资源文件里的对象清单与基底版本一致，非贴图对象逐字节相同；外部数据（.resS）只有被标注的那几张贴图自己的数据段发生变化，",
        "     其余字节 0 处改动；清单里每个文件的哈希与实际文件一致。",
        "   - 解码回来的贴图：写了字的 4x4 块以外，所有像素（包括所有 mip 层）与基底版本逐像素相同，0 个例外。",
        "   - 写了字的块重新压缩后，与标注原图相比 PSNR 最低 %.1f dB、中位数 %.1f dB（DXT 压缩对细笔画的正常损失：放大看边缘比标注原图略软，不影响阅读）。" % (lo, med),
    ]
    sb = []
    for tag in ("plus", "pristine"):
        p = os.path.join(LOGDIR, "sandbox_maplabels_%s.txt" % tag)
        if os.path.exists(p) and os.path.getmtime(p) >= newest:
            ls = open(p, encoding="utf-8").read().splitlines()
            sb.append((tag, sum(1 for l in ls if l.startswith("ok ")), sum(1 for l in ls if l.startswith("FAIL "))))     # check() writes "FAIL  msg"; the summary line "FAILS: n" must not count
    if len(sb) == 2 and all(f == 0 for _, _, f in sb):
        lines.append("   - 沙盒安装测试（在游戏文件的临时副本里做，没动真实游戏目录）：安装 / 重复安装 / 还原 / 重复还原 / 遇到未知文件拒绝 /")
        lines.append("     游戏版本不符拒绝 / 没装主包时拒绝（且不改动任何文件），共 %d 项检查全部通过。" % sum(n for _, n, _ in sb))
    else:
        lines.append("   - （沙盒安装测试在本次构建之后还没有全部跑完，这里不作声明。）")
    return "\n".join(lines) + "\n"


def finish(out_dir, do_zip):
    """No rebuild: rewrite README.txt with the verification facts (after su_verify_map.py / su_sandbox_test.py ran), optionally zip."""
    man = json.load(open(os.path.join(out_dir, "patch_manifest.json"), encoding="utf-8-sig"))
    names = annotated_names()
    built = json.load(open(os.path.join(LOGDIR, "map_build_info.json"), encoding="utf-8"))
    assert {t for i in built for t in i["textures"]} == set(names), "annotated textures changed since the pack was built -- rebuild first"
    per, pairs, missing = label_stats(names)
    n_files = len(man["files"])
    n_plus = sum(1 for f in man["files"] if f.get("requires_pack"))
    max_rel = max(len(f["relative_path"]) for f in man["files"])
    su_pack.write_readme(out_dir, make_readme(names, per, pairs, missing, n_files, n_files - n_plus, verify_note(out_dir, len(names)), max_rel))
    write_glossary(out_dir, pairs)
    print("README + glossary rewritten;", len(names), "textures,", sum(per.values()), "labels,", len(pairs), "pairs,", n_files, "files")
    if do_zip:
        print("zip:", su_pack.zip_pack(out_dir))


def write_glossary(out_dir, pairs):
    rows = sorted(pairs.items(), key=lambda kv: kv[0][0].lower())
    with open(os.path.join(out_dir, "地名对照表.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["英文", "中文", "出现次数", "来源"])
        for (en, zh), c in rows:
            w.writerow([en, zh, c, source_of(en, zh)])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT_ROOT)
    ap.add_argument("--zip", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--finish", action="store_true", help="do not rebuild: rewrite README with the verification facts, optionally zip")
    a = ap.parse_args()
    out_dir = a.out
    if a.finish:
        finish(out_dir, a.zip)
        return
    only = [s for s in a.only.split(",") if s]
    log = Logger(os.path.join(LOGDIR, "build_map_log.txt"))
    t0 = time.time()
    if os.path.isdir(lp(out_dir)):
        shutil.rmtree(lp(out_dir))              # rebuild from scratch
    names = annotated_names(only)
    per, pairs, missing = label_stats(names)
    log(f"textures {len(names)}, labels {sum(per.values())}, pairs {len(pairs)}, missing {dict(missing)}")
    idx = MS.tex_index()
    by_file = collections.defaultdict(dict)
    for n in names:
        assert idx.get(n), n
        for f in idx[n]:
            by_file[f][n] = os.path.join(MAPOUT, n + ".png")
    log(f"bundles to build: {len(by_file)}")
    infos = []
    for f, imgs in sorted(by_file.items()):
        infos.append(MS.build_bundle(f, imgs, out_dir, log))
    json.dump(infos, open(os.path.join(LOGDIR, "map_build_info.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    entries = []
    for inf in infos:
        p = os.path.join(out_dir, AA_REL, inf["file"])
        e = {"relative_path": AA_REL + "\\" + inf["file"], "file_name": inf["file"], "size": os.path.getsize(lp(p)),
             "original_sha256": inf["original_sha256"], "patched_sha256": sha256_file(p)}
        if inf["base"] == "plus":
            e["requires_pack"] = MAIN_PACK
        entries.append(e)
    n_plus = sum(1 for inf in infos if inf["base"] == "plus")
    notes = {
        "base": f"附加包：需要先安装主汉化包 {MAIN_PACK}（其中 {n_plus} 个文件是在主包版本之上再加地图标注；其余文件独立）。",
        "optional": True,
        "warning": "只换地图贴图（文字区域以外逐像素相同）。2026-10-12 在 Windows Steam 版 3.1.0 Build 175 上实机看过索德兰及周边的主地图，其余贴图没有逐张在游戏里验证。异常时运行 restore.bat 还原。",
    }
    su_pack.write_manifest(out_dir, PACK_NAME, "maplabels", entries, notes)
    su_pack.write_installer(out_dir)
    su_pack.write_restore(out_dir)
    vn = "   （构建之后还没有运行校验脚本，所以这里不作任何校验声明。）\n"     # `--finish` rewrites this after su_verify_map.py / sandbox tests ran
    su_pack.write_readme(out_dir, make_readme(names, per, pairs, missing, len(entries), len(entries) - n_plus, vn,
                                              max(len(e["relative_path"]) for e in entries)))
    write_glossary(out_dir, pairs)
    log(f"manifest written: {len(entries)} files ({n_plus} on top of the main pack); [{time.time() - t0:.0f}s]")
    if a.zip:
        log("zip: " + su_pack.zip_pack(out_dir))
    log("done")


if __name__ == "__main__":
    main()
