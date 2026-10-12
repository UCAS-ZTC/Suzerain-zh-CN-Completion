# -*- coding: utf-8 -*-
"""c_gruniregion: GRUNI arc chain, Bay labels, a few city labels."""
PATCH = dict(
    drop=[1, 2, 5, 9],
    merge=[dict(idx=[0, 3], text="Borin Bay"), dict(idx=[7, 8], text="Markher Bay")],
    add=[
        dict(text="GRUNI", pts=[(163, 245), (256, 222), (354, 217), (447, 238), (540, 272)],
             size=30, span=0.6, off=-42, ink=(190, 92, 70), upright=True),
        dict(text="Borin", cx=474.0, cy=66.0, theta=0.0, w=36.0, h=14.0),
        dict(text="Benfi", cx=639.0, cy=217.0, theta=0.0, w=34.0, h=13.0),
    ],
)
