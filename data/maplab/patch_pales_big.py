# -*- coding: utf-8 -*-
"""pales_big (2048x2048 DXT5, transparent): hollow letter chain P A L E S + city labels."""
INK = (30, 30, 30)
PATCH = dict(
    drop=[4, 6, 7, 8, 9, 10],
    add=[
        dict(text="PALES", p0=(555, 1200), p1=(1261, 1195), h=100, ink=INK, span=0.45, side="below"),
        dict(text="Ziqes", cx=1057.0, cy=1143.0, theta=3.0, w=95.0, h=30.0),
    ],
)
