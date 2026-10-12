# -*- coding: utf-8 -*-
"""T_Map_World_03 (4096x4096, DXT1): central ocean, Nordland, Galmland coast."""
TEAL = (30, 92, 112)
PATCH = dict(
    drop=[1, 2, 3, 17],
    merge=[
        dict(idx=[21, 20], text="GALMISH SEA", ink=TEAL, wght=500),
    ],
    add=[
        dict(text="CENTRAL OCEAN", p0=(890, 3219), p1=(3490, 2274), h=145, ink=TEAL, span=0.45, wght=600, scale=1.5),
    ],
)
