# -*- coding: utf-8 -*-
"""c_riziaimperiiregion: RIZIA IMPERII chain, PORTE DRAZON, black labels."""
PATCH = dict(
    drop=[0],
    fix={5: "RIZIA IMPERII", 1: "Qaleo"},
    merge=[dict(idx=[4, 3], text="PORTE DRAZON")],
    style={5: dict(kind="chain", ink=(160, 35, 35), span=0.5, scale=1.2, side="below")},
    add=[
        dict(text="Qalus", cx=648.0, cy=427.0, theta=0.0, w=44.0, h=16.0),
    ],
)
