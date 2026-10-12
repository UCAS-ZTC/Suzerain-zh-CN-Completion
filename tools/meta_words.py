# -*- coding: utf-8 -*-
"""Single-word UI literals of global-metadata.dat -> the OPTIONAL "ProgramWords" add-on (stacked on the ProgramText add-on).

Each English word below is stored ONCE in the program's string table and shared by every place in the code that uses that literal:
a button caption, but possibly also a comparison / dictionary key / GameObject name for Transform.Find / Input axis / Animator state.
Translating the shared literal fixes the first kind and breaks the others, and the code cannot be inspected here.  That is why these
entries are NOT part of meta_tm.PAIRS (the ProgramText pack) but of a separate, experimental pack (su_words_build.py).

Selection: words that were SEEN in English on a screen of the live test AND that have no exact-string hit in the game data as a
GameObject name / Input axis / layer (meta_words_dual.py).  Left out on purpose:
  * Cancel   - Input axis "Cancel" + 18 GameObjects named Cancel
  * On / Off - 157 GameObjects named On (Off follows for consistency)
  * Default  - the "Default" layer of the TagManager
  * OK       - never seen on a screen in the live test, and "OK" is the classic status string compared against server / SDK replies
  * High     - translating it changed nothing on screen (the quality drop-down does not take its values from this literal)
Live test (2026-10-12, throw-away variant incl. OK / High): game starts, loads a save, HUD intact, Yes / No dialogs work in both directions,
Options / Load headers, window-mode value and the country / city panels show the Chinese text.
"""

GROUPS = [
    ("确认弹窗按钮", [
        ("Yes", "是"), ("No", "否"),
    ]),
    ("页面标题", [
        ("Load", "读取"), ("Options", "选项"), ("OPTIONS", "选项"),
    ]),
    ("设置页的取值（窗口模式、帧率上限）", [
        ("Fullscreen", "全屏"), ("Windowed", "窗口"), ("Borderless", "无边框窗口"), ("Unlimited", "无限制"),
    ]),
    ("国家 / 城市信息面板", [
        ("Population", "人口"), ("Million", "百万"), ("Billion", "十亿"), ("Capital", "首都"), ("Government", "政府"),
        ("Leader", "领导人"), ("Relations", "关系"), ("Military", "军事"),
    ]),
]

PAIRS = [(g, en, zh) for g, items in GROUPS for en, zh in items]
