# -*- coding: utf-8 -*-
"""T_Map_Sordland_01 (4096x4096, DXT1): curated exceptions to the OCR candidates (raw OCR indices)."""
GREY = (60, 60, 60)
RED = (165, 62, 34)
PATCH = dict(
    drop=[2],
    merge=[
        dict(idx=[11, 13, 12], text="TRANQUIL SEA", track=14, wght=500),
        dict(idx=[64, 67, 70], text="Gulf of Nargis"),
        dict(idx=[49, 53], text="Lenkurg Bay"),
        dict(idx=[18, 23, 26, 29, 34], text="RUMBURG", kind="chain", ink=GREY, scale=1.3, span=0.5),
        dict(idx=[0, 1], text="REPUBLIK DEI SORDLAND", side=["below"], track=10),
    ],
    add=[
        dict(text="NARGIS", zh="纳尔吉斯", p0=(1600, 4040), p1=(2976, 3287), h=90, span=0.5, ink=RED),
        dict(text="AGNLAND", zh="阿格兰", p0=(3589, 2761), p1=(4045, 2405), h=90, span=0.9, ink=RED),
    ],
)
