# -*- coding: utf-8 -*-
"""zille_ownstate (2048x2048 DXT5, transparent): Brenas map overlay with the purple Zille territory."""
RED = (172, 50, 45)
PATCH = dict(
    drop=[1, 2, 12, 14, 15],
    fix={6: "ZILLE"},
    add=[
        dict(text="ZILLE", p0=(715, 257), p1=(925, 257), h=40, ink=RED, span=0.6, side="below"),
        dict(text="BRENAS", p0=(795, 972), p1=(1217, 972), h=45, ink=RED, span=0.6, side="below"),
    ],
)
