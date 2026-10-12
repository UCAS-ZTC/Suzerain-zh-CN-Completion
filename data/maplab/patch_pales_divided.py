# -*- coding: utf-8 -*-
"""pales_divided (2048x2048 DXT5, transparent): west = red 'PALES ADMINISTRATIVE DISTRICT' block, east = hollow 'PALES' chain."""
INK = (30, 30, 30)
RED = (176, 48, 42)
PATCH = dict(
    drop=[4, 5, 6, 8, 10, 12],
    fix={7: "Ziqes"},
    add=[
        dict(text="PALES ADMINISTRATIVE DISTRICT", cx=843.0, cy=1212.0, theta=0.0, w=728.0, h=165.0, size=46, track=16, wght=500,
             ink=RED, side="below"),
        dict(text="PALES", p0=(1440, 1089), p1=(1794, 1089), h=95, ink=INK, span=0.3, side="below", dx=-60),
    ],
)
