# -*- coding: utf-8 -*-
"""c_cardessemontaklarregion: region name chain, rotated hollow PALES, rotated MONTAKLAR, rotated admin-district block."""
RED = (170, 42, 38)
PATCH = dict(
    drop=[0, 1],
    fix={2: "CARDESSE-MONTAKLAR"},
    style={2: dict(kind="chain", ink=RED, span=0.5, scale=1.2, side="below")},
    add=[
        dict(text="PALES", p0=(667, 172), p1=(688, 86), h=30, ink=(40, 40, 40), span=0.5, scale=1.1),
        dict(text="MONTAKLAR", p0=(373, 278), p1=(401, 216), h=13, ink=(20, 20, 20), span=0.5, scale=1.1),
        dict(text="PALES ADMINISTRATIVE DISTRICT", cx=607.0, cy=302.0, theta=-76.0, w=135.0, h=56.0, kind="chain", size=17,
             ink=RED, span=0.5),
    ],
)
