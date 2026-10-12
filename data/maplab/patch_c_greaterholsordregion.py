# -*- coding: utf-8 -*-
"""c_greaterholsordregion: HOLSORD letter chain + black city labels."""
PATCH = dict(
    drop=[0, 1, 7, 10],
    fix={2: "Gelsord", 6: "HOLSORD"},
    add=[
        dict(text="HOLSORD", p0=(207, 227), p1=(520, 242), h=34, ink=(200, 100, 60), span=0.5, scale=1.25, side="below"),
    ],
)
