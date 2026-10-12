# -*- coding: utf-8 -*-
"""c_agnlandregion (1024x1024 crunched DXT5, content 750x450): AGNLAND letter chain + a few black city labels."""
RED = (178, 83, 60)
PATCH = dict(
    drop=[0, 1],
    add=[
        dict(text="AGNLAND", p0=(211, 216), p1=(595, 180), h=34, ink=RED, span=0.5, scale=1.25, side="below"),
        dict(text="Lenkurg", cx=161.0, cy=314.0, theta=25.0, w=50.0, h=16.0),
        dict(text="Arvory", cx=388.0, cy=318.0, theta=18.0, w=44.0, h=15.0),
        dict(text="Rachaster", cx=421.0, cy=39.0, theta=30.0, w=56.0, h=15.0),
    ],
)
