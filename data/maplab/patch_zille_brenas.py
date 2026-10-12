# -*- coding: utf-8 -*-
"""zille_brenas (2048x2048 DXT5, transparent): Brenas map overlay."""
RED = (172, 50, 45)
PATCH = dict(
    drop=[9, 11],
    add=[
        dict(text="BRENAS", p0=(896, 820), p1=(1308, 822), h=44, ink=RED, span=0.6, side="below"),
    ],
)
