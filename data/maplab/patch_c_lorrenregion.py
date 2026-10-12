# -*- coding: utf-8 -*-
"""c_lorrenregion: LORREN letter chain + HOLSORD city label."""
PATCH = dict(
    fix={0: "HOLSORD"},
    add=[
        dict(text="LORREN", p0=(207, 275), p1=(497, 278), h=34, ink=(195, 100, 50), span=0.5, scale=1.25, side="below"),
        dict(text="Vesord", cx=608.0, cy=261.0, theta=28.0, w=40.0, h=14.0),
    ],
)
