# -*- coding: utf-8 -*-
"""T_Map_Rizia_03 (4096x4096, DXT1)."""
INK = (30, 30, 30)
RED = (170, 40, 30)
TEAL = (30, 92, 112)
PATCH = dict(
    drop=[13, 14, 15, 28, 33, 48],
    merge=[
        dict(idx=[34, 35, 36], text="PALES ADMINISTRATIVE DISTRICT", size=44, track=4),
        dict(idx=[46, 47], text="GULF OF NAL", ink=TEAL, wght=500),
    ],
    add=[
        dict(text="MORELLA", p0=(684, 922), p1=(2591, 1597), h=150, ink=INK, span=0.5),
        dict(text="CARDESSE-MONTAKLAR", p0=(2900, 1057), p1=(4060, 1068), h=75, ink=RED, span=0.6),
    ],
)
