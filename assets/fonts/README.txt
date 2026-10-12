NotoSerifSC-VF.ttf  -  构建 TutorialImages / MapLabels 两个包时用来画中文的字体
=====================================================================================

这个目录里只有说明和许可证。字体文件本身（25 MB）不在 git 仓库里，而是本仓库 Release「fonts-v1」的附件
（地址写在 data/font_source.json，python build.py 会自动下载并校验，一般不需要你手动处理）。

文件      NotoSerifSC-VF.ttf（Noto Serif SC 可变字体，未做任何修改）
大小      25,129,160 字节
SHA-256   a4aed9985a5916fbf6690456f8732a9fccd517938e353165d4142b4f11a39280
版本串    Version 2.02;241114204558;non-release   (name 表 ID 5；font revision 2.02)
版权      (c) 2017-2023 Adobe (http://www.adobe.com/).   Noto is a trademark of Google Inc.
许可      SIL Open Font License 1.1，全文见同目录 OFL.txt（Release 附件里也带一份；字体文件内部 name 表 ID 13 也写有同一许可声明）


构建器怎么拿到字体
------------------
python build.py 按下面的顺序找字体，第一个可用的就用：
  1. --font <路径>          你自己指定的文件。哈希与实测不同时会警告。
  2. 本机已有的实测字体      assets\fonts\NotoSerifSC-VF.ttf，或 <work>\fonts\ 里（之前下载过的）SHA-256 对得上的文件。
  3. 下载实测字体            从 data/font_source.json 里的 Release 附件地址下载，核对大小与 SHA-256，不一致就删除并走第 4 步。
  4. 退回官方 2.003 版       notofonts/noto-cjk 里一个固定提交上的文件（同样核对 SHA-256）。会明确警告，构建后校验会列出
                            与实测不同的 3 个 MapLabels 文件（见下）。
网络访问不了 GitHub Release 时：用浏览器打开本仓库 Releases 页，下载 fonts-v1 里的 NotoSerifSC-VF.ttf，放进本目录
（.gitignore 已忽略 *.ttf，不会被提交），或用 --font 指定它的路径。


为什么要固定一份字体（而不是用随便哪个 Noto Serif SC）
----------------------------------------------------
构建器的目标是：同样的游戏 + 同样的输入 -> 与维护者实测过的补丁包逐字节一致。贴图是用这个字体渲染的，字体不同，
字形的几十个像素就可能不同，哈希就对不上。OFL 允许原样再分发字体，所以把这一份固定为 Release 附件，不要求玩家自己
去找“对的版本”。放在 Release 而不是 git 里，是为了让仓库保持很小（约 1.5 MB），克隆很快；代价是构建多一次 25 MB 的
下载，并且依赖 Release 附件一直在（附件被删时构建器会自动退回官方 2.003 版）。


关于来源（如实说明）
--------------------
这份文件取自维护者电脑上已安装的字体（NotoSerifSC-VF.ttf）。我们没能找到它在公开发行渠道里的出处：
  - notofonts/noto-cjk 仓库里 Serif/Variable/TTF/Subset/NotoSerifSC-VF.ttf 的全部 5 个历史版本，
    大小都与这份不同（最新 2.003 为 25,125,232 字节，2.002 为 25,129,044 字节）；
  - google/fonts 仓库里的 NotoSerifSC[wght].ttf（2.003-H1，25,125,512 字节）同样不同。
  这份是 2024-11-14 的一次 "non-release" 构建（含 gasp 表）。


用官方 2.003 版会怎样（已实测）
--------------------------------
用 notofonts/noto-cjk 的 2.003 版重新渲染并打包：53 张地图贴图里只有 3 张有差异，每张都只是一个字形附近几十个
像素（T_Map_RumburgWar_01 / T_Map_RumburgWar_02 最大色差 3~4；world_pales_Text 为 31x34 像素区域内的一个字形），
对应 3 个 bundle（commonassets_assets_all_8bc088c7...、两个 sordland_war prefab）字节不同；TutorialImages 的
11 个文件仍然逐字节一致。也就是说换成官方 2.003 版，肉眼几乎看不出区别，但“逐字节一致”的校验会报这 3 个文件。


如果你想用别的字体
------------------
  python build.py --font <你的字体.ttf> ...
构建器会警告“输出可能与已测试构建不同”，校验步骤会把有差异的文件列出来。这不会让补丁不可用，但那样得到的包
没有经过维护者的测试。


OFL 的义务（再分发本字体时）
-----------------------------
随字体附上版权声明与 OFL.txt（本目录和 Release 附件里都有）；不单独出售字体；修改过的版本不得使用保留字体名。


Release 附件（仅仓库维护者）
----------------------------
字体作为本仓库 Release「fonts-v1」的附件发布（NotoSerifSC-VF.ttf、OFL.txt），地址写在 data/font_source.json。
请不要删除这个 Release。如果以后要换字体：新建一个标签（例如 fonts-v2），更新 data/font_source.json，
用 tools/make_expected.py --font <新字体> 重新生成 expected_*.json，并重新做一遍端到端构建。
