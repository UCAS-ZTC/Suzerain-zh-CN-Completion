# -*- coding: utf-8 -*-
"""c_bergiaregion: curved BERGIA letter chain (B..A) + black labels."""
RED = (196, 74, 58)
PATCH = dict(
    drop=[4],
    fix={1: "Datefort", 2: "Anrica", 6: "Wizen"},
    add=[
        dict(text="BERGIA", pts=[(180, 215), (246, 212), (313, 209), (380, 218), (440, 236), (501, 258)],
             size=30, span=0.55, off=36, ink=RED, upright=True),
        dict(text="DEYR", cx=455.0, cy=182.0, theta=0.0, w=42.0, h=16.0),
        dict(text="Erzaren", cx=331.0, cy=114.0, theta=0.0, w=40.0, h=12.0),
        dict(text="Sarna", cx=559.0, cy=274.0, theta=0.0, w=34.0, h=13.0),
    ],
)
