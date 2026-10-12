# -*- coding: utf-8 -*-
"""T_Map_Rizia_04 (4096x4096, DXT1)."""
RED = (175, 35, 30)
TEAL = (30, 92, 112)
PATCH = dict(
    drop=[19, 26, 37],
    merge=[
        dict(idx=[46, 47], text="ISLAND OF CALEQABIZ"),
        dict(idx=[14, 15], text="Bay of Matus", ink=TEAL, wght=500),
        dict(idx=[41, 44], text="GULF OF PALES", ink=TEAL, wght=500),
        dict(idx=[48, 50], text="GULF OF REMAZ", ink=TEAL, wght=500),
    ],
    add=[
        dict(text="VALENQIRIS", p0=(561, 374), p1=(1778, 353), h=70, ink=RED, span=0.5),
        dict(text="GULF OF ALES", cx=845, cy=1895, theta=-2, w=170, h=70, ink=TEAL, wght=500, size=26),
        dict(text="ANTACEAN SEA", pts=[(1000, 3020), (1200, 2840), (1380, 2680), (1590, 2500), (1760, 2320), (1940, 2140),
                                       (2120, 1960), (2300, 1760), (2600, 1420), (2772, 1220), (2940, 1040)],
             size=60, span=0.55, off=150, ink=TEAL, wght=500, upright=True),
    ],
)
