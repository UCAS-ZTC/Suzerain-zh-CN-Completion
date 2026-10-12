# -*- coding: utf-8 -*-
"""T_Map_World_02 (4096x4096, DXT1): curated exceptions to the OCR candidates (raw OCR indices)."""
INK = (28, 30, 36)
TEAL = (22, 88, 104)
PATCH = dict(
    drop=[0, 14, 19, 56, 60, 37, 29, 44, 70],
    fix={36: "AGNOLIA", 49: "GELBJA", 7: "Port Norkis"},
    merge=[
        dict(idx=[9, 8, 10], text="BARONIES OF SORADIS", side=["above", "below"]),
        dict(idx=[67, 69], text="GULF OF NARGIS"),
        dict(idx=[72, 73], text="GULF OF CONRIAT"),
        dict(idx=[58, 62], text="MARKIAN SEA"),
    ],
    add=[
        dict(text="MARKANISSA", p0=(1672, 510), p1=(3082, 504), h=85, ink=INK, span=0.5),
        dict(text="RUMBURG", p0=(230, 1800), p1=(1500, 1950), h=125, ink=INK, span=0.5),
        dict(text="VALGSLAND", p0=(3108, 3742), p1=(3990, 3640), h=90, ink=INK, span=0.6),
        dict(text="VALGOS CHANNEL", p0=(2990, 2170), p1=(3790, 1320), h=55, ink=TEAL, span=0.6),
    ],
)
