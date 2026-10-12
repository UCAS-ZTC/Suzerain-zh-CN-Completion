# -*- coding: utf-8 -*-
"""T_Map_Sordland_03 (4096x4096, DXT1): curated exceptions to the OCR candidates (raw OCR indices)."""
GREY = (60, 60, 60)
BROWN_RED = (92, 26, 20)
RED = (140, 42, 26)
PATCH = dict(
    drop=[84],
    fix={59: "Czerna", 85: "San Montua"},
    merge=[
        dict(idx=[61, 63], text="Lake Mizen"),
        dict(idx=[66, 67], text="Lake Zen"),
    ],
    add=[
        dict(text="WEHLEN", p0=(780, 2528), p1=(1580, 1368), h=80, ink=GREY),
        dict(text="BERGIA", p0=(1864, 930), p1=(3040, 940), h=75, ink=BROWN_RED, span=0.5),
        dict(text="GELSLAND", p0=(3380, 600), p1=(3948, 160), h=70, ink=RED, span=0.7),
        dict(text="LESPIA", p0=(3082, 2303), p1=(4060, 2655), h=110, ink=GREY, span=0.7),
    ],
    # Anrica / Descat / Maradunord: pinned to the sides of the shipped, live-tested render of this texture (it was rendered
    # with an earlier revision of the placement scoring in map_render.py; without the pins a rebuild moves these three labels)
    style={11: dict(side=("below",)), 17: dict(side=("below",)), 48: dict(side=("above",))},
)
