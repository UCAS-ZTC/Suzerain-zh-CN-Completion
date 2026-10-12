# -*- coding: utf-8 -*-
"""c_palesadmindistrictregion: red 3-line district name, rotated hollow PALES, a few black labels."""
RED = (170, 40, 40)
PATCH = dict(
    fix={5: "Ziqes"},
    merge=[dict(idx=[2, 3, 4], text="PALES ADMINISTRATIVE DISTRICT", ink=RED, side="below", scale=1.1)],
    style={6: dict(kind="chain", ink=(40, 40, 40), span=0.5, scale=1.15)},
    add=[
        dict(text="Fort Ales", cx=516.0, cy=220.0, theta=22.0, w=66.0, h=16.0),
        dict(text="Solles", cx=667.0, cy=282.0, theta=20.0, w=40.0, h=14.0),
        dict(text="Remaz", cx=622.0, cy=363.0, theta=15.0, w=38.0, h=14.0),
    ],
)
