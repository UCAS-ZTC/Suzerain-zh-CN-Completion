# -*- coding: utf-8 -*-
"""world_fortales_text (512x128, black italic 'Fort Ales' filling the sprite).
No room for an annotation -> pre(): shrink the English to 56 % at the top of the same sprite, Chinese goes below it."""
import numpy as np
from PIL import Image

S = 0.56
BOX = (4, 16, 509, 106)          # content bbox of the original sprite


def pre(rgba):
    im = Image.fromarray(rgba, "RGBA").crop(BOX)
    nw, nh = int(round(im.width * S)), int(round(im.height * S))
    small = im.resize((nw, nh), Image.LANCZOS)          # PIL resizes RGBA premultiplied
    out = Image.new("RGBA", (rgba.shape[1], rgba.shape[0]), (0, 0, 0, 0))
    out.paste(small, ((rgba.shape[1] - nw) // 2, 3))
    return np.asarray(out).copy()


PATCH = dict(
    pre=pre,
    drop=[0, 1, 2, 3, 4, 5],
    nomerge=True,
    add=[dict(text="Fort Ales", cx=255.5, cy=28.0, theta=0.0, w=283.0, h=50.0, size=44, wght=700, ink=(15, 15, 15), side="below")],
)
