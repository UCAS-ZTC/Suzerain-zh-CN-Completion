# -*- coding: utf-8 -*-
"""T_Map_Rizia_01 (4096x4096, DXT1)."""
INK = (30, 30, 30)
RED = (170, 40, 30)
TEAL = (30, 92, 112)
PATCH = dict(
    drop=[23, 28, 31, 55],
    merge=[
        dict(idx=[42, 46], text="Gulf of Moridia", ink=TEAL, wght=500),
    ],
    add=[
        dict(text="WEHLEN", p0=(732, 1045), p1=(1981, 1396), h=120, ink=INK, span=0.5),
        dict(text="DERDIA", p0=(520, 2272), p1=(1460, 1988), h=140, ink=INK, span=0.5),
        dict(text="BRENAS", p0=(2628, 3076), p1=(3338, 3082), h=70, ink=RED, span=0.5),
    ],
)
