# -*- coding: utf-8 -*-
"""T_Map_World_01 (4096x4096, DXT1): curated exceptions to the OCR candidates (raw OCR indices)."""
INK = (28, 30, 36)
PATCH = dict(
    drop=[1, 26, 7, 14, 23, 36, 40, 33, 37],
    fix={0: "Thompsfort", 9: "New Citadel"},
    merge=[
        dict(idx=[3, 6], text="Fortress City"),
        dict(idx=[36, 40], text="ADANIAN FEDERATION", kind="chain", theta=22, ink=INK, span=0.6),
        dict(idx=[33, 37, 42], text="KINGDOM OF ERDMARG", kind="chain", theta=17, ink=INK, span=0.5, scale=1.25),
    ],
    add=[
        dict(text="PRINCIPALITIES", p0=(390, 1275), p1=(1340, 1740), h=89, ink=INK, span=0.5),
        dict(text="NAHRBURK", p0=(140, 2140), p1=(1161, 2658), h=100, ink=INK, span=0.5),
        dict(text="KINGDOM OF RUMBURG", zh="伦堡王国", p0=(2196, 1166), p1=(3990, 1717), h=125, ink=INK, span=0.5),
    ],
)
