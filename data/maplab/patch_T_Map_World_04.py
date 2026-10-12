# -*- coding: utf-8 -*-
"""T_Map_World_04 (4096x4096, DXT1): Kalrad / Agard / Solme-Maor / Free Cities / Lasomby / Hijana / Neqis."""
INK = (28, 30, 36)
TEAL = (30, 92, 112)
PATCH = dict(
    drop=[0, 19, 30, 34, 38, 40, 42, 52, 53, 59, 61, 67, 74, 92, 95, 97, 100, 113, 133],
    fix={26: "Nielle", 28: "Sesoux", 41: "Jymanly", 51: "Wahr City", 71: "St. Sayette", 49: "St. Ard", 77: "Lassa",
         94: "Oqitan", 111: "Omrybaras"},
    merge=[
        dict(idx=[4, 9, 8], text="UNITED STATES OF KALRAD", size=64, track=8, side=["below", "above", "right"]),
        dict(idx=[10, 13], text="Kalrad City"),
        dict(idx=[55], text="HIJANA", kind="chain", ink=INK, span=0.5),
        dict(idx=[33], text="SOLME-MAOR", kind="chain", ink=INK, span=0.45),
        dict(idx=[63], text="MONTESAYETTE", kind="chain", ink=INK, span=0.45),
        dict(idx=[91], text="FREE CITIES", kind="chain", ink=INK, span=0.5),
        dict(idx=[135, 136], text="NEQIS", kind="chain", ink=INK, span=0.5),
        dict(idx=[101, 104], text="LASOMBIAN SEA", ink=TEAL, size=44, wght=500),
        dict(idx=[112, 115], text="SEA OF MALKAV", ink=TEAL, size=40, wght=500),
        dict(idx=[81, 84], text="GULF OF JATHLAS", ink=TEAL, size=34, wght=500),
        dict(idx=[119, 121], text="GULF OF FAZ", ink=TEAL, size=34, wght=500),
    ],
    add=[
        dict(text="AGARD", p0=(3310, 716), p1=(3844, 824), h=87, ink=INK, span=0.5),
        dict(text="G'ALEROI", p0=(760, 1150), p1=(1440, 1425), h=95, ink=INK, span=0.5),
        dict(text="LASOMBY", p0=(1330, 1915), p1=(2260, 2130), h=88, ink=INK, span=0.5),
        dict(text="SEA OF NEM", p0=(1845, 2705), p1=(3432, 3010), h=110, ink=TEAL, span=0.45, wght=500),
    ],
)
