# -*- coding: utf-8 -*-
"""T_Map_Sordland_02 (4096x4096, DXT1): curated exceptions to the OCR candidates (raw OCR indices)."""
GREY = (60, 60, 60)
TEAL = (0, 96, 104)
PATCH = dict(
    frame=(0, 540, 3560, 4096),
    drop=[0, 1, 33, 63, 48, 51, 52, 14],              # 14: 'els' = right part of the 'Niels' label (re-added below with its true box)
    fix={25: "Staalport", 73: "AntelRock"},
    merge=[
        dict(idx=[26, 28], text="Staal Bay", zh="斯塔尔湾", track=6),
        dict(idx=[29, 30, 31], text="Bay of Gelbja"),
        dict(idx=[37, 36], text="Gelbja Island"),
        dict(idx=[59, 61, 64], text="Gulf of Stanisen"),
        dict(idx=[50, 53, 56], text="Bay of Arvory"),
        dict(idx=[68, 69], text="Duru Island"),
    ],
    add=[
        dict(text="Niels", cx=1715.0, cy=1161.0, theta=0.0, w=90.0, h=28.0),
        dict(text="AGNOLIA", zh="阿格诺利亚", p0=(882, 1743), p1=(2010, 1090), h=125, span=0.5, ink=GREY, dx=-150),
        dict(text="VALGSLAND", zh="瓦尔戈斯兰", p0=(2672, 3448), p1=(3352, 1880), h=130, span=0.5, ink=GREY),
        dict(text="MARKIAN SEA", zh="马尔基安海", p0=(300, 3380), p1=(1620, 2942), h=75, span=0.5, wght=500, ink=TEAL),
        dict(text="NERMENLANDER SEA", zh="内尔门兰德海", p0=(2110, 2990), p1=(2750, 2790), h=40, span=0.7, wght=500, ink=TEAL),
        dict(text="VALGOS CHANNEL", zh="瓦尔戈斯水道", p0=(2428, 1732), p1=(2688, 800), h=55, span=0.6, wght=500, ink=TEAL),
    ],
)
