# 许可范围与第三方声明

**Licenses at a glance.** Code, tooling and the installer: MIT (`LICENSE`). The Chinese translations (the English -> Chinese tables): CC BY-NC-SA 4.0 (`LICENSE-TRANSLATIONS.txt`). The font used to paint Chinese into textures is a separate download under the SIL OFL 1.1. The game's text and art, and the old base patch, are covered by neither license and are not distributed in this repository.

下面用中文逐项说明。这里的概括不是法律意见，以各许可证全文为准。

## 1. 本仓库自己的内容

### MIT：代码与工具（见 `LICENSE`）

- `build.py`，`tools/` 里的生成器和校验脚本，`installer/`（安装器），`docs/`，`.github/`
- `data/` 里的构建数据：`expected_*.json`、`font_source.json`、`stage2_tutorial_bundles.json`、`maplab/tex_locator.json`，以及 `maplab/patch_*.py` 里的坐标、字号、颜色等排版参数

### CC BY-NC-SA 4.0：译文（见 `LICENSE-TRANSLATIONS.txt`）

“译文”指“英文原文 -> 中文”的对照内容：

- `data/tm/` 下的全部文件
- `data/maplab/names_*.py`（地图地名译名），以及 `data/maplab/patch_*.py` 里的 `zh=` 译名
- `tools/meta_tm.py`、`tools/meta_words.py` 里的对照表（程序内文案、程序内单词）
- `tools/tut_repaint.py` 里的教程图标签、`tools/map_names.py` 里的地名后缀对照

一个文件里既有代码又有译文时（例如 `tools/meta_tm.py`），译文部分适用 CC BY-NC-SA 4.0，代码部分适用 MIT。

用一句话说这个许可：可以自由使用、修改、转载；必须署名并说明改动；不得用于商业目的；基于它的衍生作品要用同样的许可发布。具体条款以许可证全文为准。

### 不在任何许可范围内

- 游戏《Suzerain》的文字与美术素材，权利归 Torpor Games 所有。这包括译文表里作为“查找键”的英文原文，以及 `data/maplab/ocr/` 里对游戏贴图上英文地名的识别记录（它们只是构建输入，不随译文许可授权）。
- 构建器生成的补丁包。它们含有你自己游戏文件的改动版本，请只在自己的电脑上使用，不要上传或转发。

## 2. 构建时下载的外部文件（不在本仓库里）

- **Noto Serif SC 可变字体**：SIL Open Font License 1.1，(c) 2017-2023 Adobe。它作为本仓库 Release `fonts-v1` 的附件提供，随附 OFL 全文；来源与校验信息见 `assets/fonts/`。
- **旧稳定版补丁（基础补丁）**：作者是百度贴吧用户“虾饺面z”，GitHub 上由 SweeneyJun 镜像（`Suzerain-CN-Stable-SteamWin`）。该仓库目前没有声明许可证。本仓库不含它的任何文件：构建器在你的电脑上从它的 GitHub Release 下载并校验 SHA-256，只作为构建的输入。本项目译文与它的重合度、核查方法见 `docs/PROVENANCE.md`。

## 3. Python 依赖（用 pip 安装，不随本仓库分发）

信息取自各包的元数据（PyPI），以包自带的许可文本为准：

- UnityPy 1.25.4：MIT
- Pillow 12.3.0：MIT-CMU
- numpy 2.4.3：BSD-3-Clause（包元数据里还列有 0BSD、MIT、Zlib、CC0-1.0，对应其中打包的组件）
- scipy 1.17.1：BSD 类许可
- etcpak 0.9.15：MIT
- texture2ddecoder 1.0.6：MIT
- lz4 4.4.5：BSD 类许可
- brotli 1.2.0：MIT
- RapidOCR：Apache-2.0。只有维护者在生成 `data/maplab/ocr/` 时用过；构建器不需要它，仓库里也没有它的代码或模型。

## 4. AI 辅助

本项目的译文、脚本与文档，大部分由 AI（Anthropic 的 Claude Sonnet 5.5）在维护者的指导和逐项实测下完成。AI 生成内容的版权归属在各个法域并不明确；上面的许可是维护者对外作出的授权声明，不构成对这个问题的法律结论。

## 5. 非官方声明

游戏《Suzerain》及其全部素材的版权归 Torpor Games 所有。本项目与 Torpor Games 无关联，未获其授权或背书。请先购买正版。
