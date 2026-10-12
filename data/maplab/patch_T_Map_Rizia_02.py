# -*- coding: utf-8 -*-
"""T_Map_Rizia_02 (4096x4096, DXT1)."""
INK = (30, 30, 30)
TEAL = (30, 92, 112)
PATCH = dict(
    drop=[9],
    merge=[
        dict(idx=[27, 24], text="Gulf of Valenqiris", ink=TEAL, wght=500),
    ],
    add=[
        dict(text="LESPIA", p0=(264, 1444), p1=(2362, 2144), h=140, ink=INK, span=0.5),
        dict(text="SUDIS SEA", p0=(20, 2272), p1=(980, 2900), h=70, ink=TEAL, span=0.45, wght=500),
    ],
)
