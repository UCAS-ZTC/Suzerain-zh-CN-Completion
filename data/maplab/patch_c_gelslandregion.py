# -*- coding: utf-8 -*-
"""c_gelslandregion: curved GELSLAND chain + labels."""
PATCH = dict(
    drop=[0],
    add=[
        dict(text="GELSLAND", pts=[(167, 236), (224, 234), (278, 215), (331, 207), (385, 207), (442, 208), (504, 217), (560, 234)],
             size=30, span=0.55, off=40, ink=(205, 98, 70), upright=True),
        dict(text="Ribery", cx=440.0, cy=49.0, theta=30.0, w=48.0, h=16.0),
        dict(text="Gelsord", cx=273.0, cy=159.0, theta=30.0, w=48.0, h=16.0),
        dict(text="Antel", cx=709.0, cy=272.0, theta=0.0, w=34.0, h=14.0),
    ],
)
