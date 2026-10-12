# -*- coding: utf-8 -*-
"""T_Map_Sordland_04 (4096x4096, DXT1): curated exceptions to the OCR candidates (raw OCR indices)."""
RED = (130, 36, 22)
TEAL = (0, 96, 104)
PATCH = dict(
    drop=[12],
    fix={79: "Sarea Nueva", 75: "Markher"},
    merge=[
        dict(idx=[75, 76], text="Markher Bay", wght=500),
        dict(idx=[60, 61, 64], text="Bay of Benfi", wght=500),       # three-line sea label: 'Bay' / 'of' / 'Benfi'
    ],
    add=[
        dict(text="HOLSORD", p0=(96, 1092), p1=(890, 1090), h=76, ink=RED, span=0.6),
        dict(text="GRUNI", p0=(1110, 1585), p1=(2400, 1790), h=76, ink=RED, span=0.5),
        dict(text="LORREN", p0=(1215, 990), p1=(1975, 375), h=70, ink=RED),
        dict(text="ANTACEAN SEA", zh="安塔西亚海", pts=[(2388, 2968), (2528, 2760), (2660, 2620), (2800, 2380), (2951, 2171),
                                                      (3106, 1998), (3240, 1814), (3312, 1568), (3374, 1140), (3385, 900), (3405, 674)],
             size=62, span=0.55, off=130, ink=TEAL, wght=500, upright=True),
    ],
)
