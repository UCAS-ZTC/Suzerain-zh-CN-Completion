# -*- coding: utf-8 -*-
"""T_Map_World_05 (4096x4096, DXT1): Sordland south, Lespia, Rizia, Morella, Qinal, Kyrute."""
INK = (28, 30, 36)
TEAL = (30, 92, 112)
PATCH = dict(
    drop=[0, 29, 32, 38, 40, 45, 47, 52, 55, 57, 58, 60, 64, 66, 68, 85, 87, 96],
    fix={104: "Toustapat", 98: "KYRUTIUM", 88: "CALEGABIZ"},
    merge=[
        dict(idx=[19], text="VALGOS SEA", kind="chain", ink=TEAL, span=0.45, wght=500),
        dict(idx=[21], text="WEHLEN", kind="chain", ink=INK, span=0.5),
        dict(idx=[84], text="MORELLA", kind="chain", ink=INK, span=0.5),
        dict(idx=[86], text="KYRUTE", kind="chain", ink=INK, span=0.5),
        dict(idx=[106, 107], text="REPUBLIC OF QINAL", size=64, track=8),
        dict(idx=[78, 79, 81], text="KINGDOM OF RIZIA", size=62, track=8, side=["below", "above"], dy=95),
        dict(idx=[100, 101], text="GULF OF NAL", ink=TEAL, size=34, wght=500),
        dict(idx=[65, 67], text="Gulf of Moridia", ink=TEAL, size=30, wght=500),
        dict(idx=[42, 48], text="VERLOA BAY", ink=TEAL, size=28, wght=500),
        dict(idx=[46, 50], text="GIOS BAY", ink=TEAL, size=28, wght=500),
    ],
    add=[
        dict(text="SORDLAND", p0=(1036, 96), p1=(2180, 146), h=85, ink=INK, span=0.5),
        dict(text="LESPIA", p0=(1390, 1052), p1=(2134, 1085), h=85, ink=INK, span=0.5),
        dict(text="ANTACEAN SEA", p0=(2600, 2001), p1=(4022, 1878), h=111, ink=TEAL, span=0.45, wght=500),
    ],
)
