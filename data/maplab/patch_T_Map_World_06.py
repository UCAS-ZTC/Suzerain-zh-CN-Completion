# -*- coding: utf-8 -*-
"""T_Map_World_06 (4096x4096, DXT1): Zaerland, Sonsamia, Nibiya, Dorghuk, Zanza, Marabone, Zhao, Galmland islands."""
INK = (28, 30, 36)
TEAL = (30, 92, 112)
PATCH = dict(
    drop=[0, 1, 5, 8, 9, 10, 12, 25, 29, 30, 32, 33, 37, 39, 46, 55, 57, 59, 78, 81, 82, 92, 97, 101],
    fix={19: "Port Tokol", 83: "Jamir"},
    merge=[
        dict(idx=[28], text="ZAERLAND", kind="chain", ink=INK, span=0.5),
        dict(idx=[21], text="SONSAMIA", kind="chain", ink=INK, span=0.5),
        dict(idx=[52], text="MAWAI", kind="chain", ink=INK, span=0.5),
        dict(idx=[51], text="IMALAND", kind="chain", ink=INK, span=0.5),
        dict(idx=[65, 66, 68], text="WEST DORGHUK", kind="chain", theta=-19, ink=INK, span=0.5),
        dict(idx=[72, 76], text="EAST DORGHUK", kind="chain", theta=-16.5, ink=INK, span=0.5),
        dict(idx=[98], text="MARABONE", kind="chain", ink=INK, span=0.5),
        dict(idx=[88, 87, 93], text="DEMOCRATIC ZANZA", kind="chain", theta=-11, ink=INK, span=0.5),
    ],
    add=[
        dict(text="NIBIYA", p0=(1866, 2754), p1=(2583, 2593), h=90, ink=INK, span=0.5),
        dict(text="ZHAO", p0=(3405, 3508), p1=(3930, 3355), h=93, ink=INK, span=0.4),
        dict(text="NORTH RIKAN SEA", p0=(2060, 745), p1=(3110, 445), h=55, ink=TEAL, span=0.5, wght=500),
        dict(text="GULF OF RIKA", p0=(1060, 2160), p1=(2110, 1950), h=60, ink=TEAL, span=0.5, wght=500),
        dict(text="SONSAMIAN SEA", zh="松萨米亚海", p0=(3564, 1158), p1=(3988, 1516), h=45, ink=TEAL, span=0.5, wght=500),
    ],
)
