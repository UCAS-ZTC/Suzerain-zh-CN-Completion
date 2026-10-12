# -*- coding: utf-8 -*-
"""pales_rizia (2048x2048 DXT5, transparent): red letter chain P A L E S + city labels."""
RED = (176, 48, 42)
PATCH = dict(
    drop=[7, 8, 9, 10],
    merge=[dict(idx=[0, 1], text="Fort Ales")],
    add=[
        dict(text="PALES", p0=(690, 1201), p1=(1187, 1203), h=56, ink=RED, span=0.45, side="below", scale=1.3),
    ],
)
