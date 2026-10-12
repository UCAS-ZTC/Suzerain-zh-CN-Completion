"""Chinese annotations next to the English labels of a map texture (library).

geometry   : OCR quad -> centre / angle / width / height
candidates : raw OCR boxes -> cleaned label list (fragments / duplicates / junk removed)
placement  : below / above / right / left of the English label, scored against other labels, earlier annotations and
             edge density of the map art
drawing    : Noto Serif SC (variable font) with a thin halo in the local background colour, rotated like the English text
"""
import os
import re
import json
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from lib_su import ROOT, CACHE, MAPLAB_DIR, FONT
MAPDIR = os.path.join(CACHE, "map")

LETTERS = re.compile(r"[A-Za-z]")
JUNK = re.compile(r"[^\x20-\x7e\u00c0-\u017f'’.\-]")


# ------------------------------------------------------------------------------------------------ geometry
def geom(box):
    """(cx, cy, theta_deg, w, h) of an OCR quad ordered TL,TR,BR,BL (text direction = TL->TR)."""
    b = np.asarray(box, dtype=np.float64)
    cx, cy = b[:, 0].mean(), b[:, 1].mean()
    u = (b[1] - b[0] + b[2] - b[3]) / 2.0
    v = (b[3] - b[0] + b[2] - b[1]) / 2.0
    w, h = float(np.hypot(*u)), float(np.hypot(*v))
    th = math.degrees(math.atan2(u[1], u[0]))
    return float(cx), float(cy), th, w, h


def aabb(box):
    b = np.asarray(box)
    return float(b[:, 0].min()), float(b[:, 1].min()), float(b[:, 0].max()), float(b[:, 1].max())


def rect_corners(cx, cy, theta_deg, w, h):
    t = math.radians(theta_deg)
    u = np.array([math.cos(t), math.sin(t)])
    n = np.array([-math.sin(t), math.cos(t)])
    c = np.array([cx, cy])
    return [c - u * w / 2 - n * h / 2, c + u * w / 2 - n * h / 2, c + u * w / 2 + n * h / 2, c - u * w / 2 + n * h / 2]


def inter_area(a, b):
    ix0, iy0, ix1, iy1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    return max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)


def area(a):
    return max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])


# ------------------------------------------------------------------------------------------------ candidates
def norm_text(t):
    return re.sub(r"[^a-z]", "", t.lower())


def load_ocr(name):
    return json.load(open(os.path.join(MAPLAB_DIR, "ocr", name + ".ocr.json"), encoding="utf-8"))


def candidates(raw, min_letters=3, min_score=0.0):
    """raw OCR list -> list of dict(idx, text, box, score, cx, cy, th, w, h); fragments contained in a longer box dropped."""
    items = []
    for i, r in enumerate(raw):
        t = r["text"].strip()
        if JUNK.search(t) or len(LETTERS.findall(t)) < min_letters or r["score"] < min_score:
            continue
        cx, cy, th, w, h = geom(r["box"])
        items.append(dict(idx=i, text=t, box=r["box"], score=r["score"], cx=cx, cy=cy, th=th, w=w, h=h, bb=aabb(r["box"])))
    # drop a box whose area is mostly inside a larger one that contains its text (fragment / duplicate)
    drop = set()
    for a in items:
        for b in items:
            if a is b or a["idx"] in drop:
                continue
            ov = inter_area(a["bb"], b["bb"])
            if ov <= 0:
                continue
            small, big = (a, b) if area(a["bb"]) <= area(b["bb"]) else (b, a)
            if ov / max(area(small["bb"]), 1) > 0.55:
                ns, nb = norm_text(small["text"]), norm_text(big["text"])
                if ns and (ns in nb or nb in ns or len(ns) <= 3):
                    drop.add(small["idx"])
    return [a for a in items if a["idx"] not in drop]


# ------------------------------------------------------------------------------------------------ colours
def label_colours(arr, box):
    """(ink RGB, background RGB) of an English label: background = median of a ring around its AABB, ink = mean of the
    pixels inside the quad that are farthest from the background."""
    x0, y0, x1, y1 = aabb(box)
    H, W = arr.shape[:2]
    pad = max(6, int(0.5 * (y1 - y0)))
    X0, Y0, X1, Y1 = max(0, int(x0) - pad), max(0, int(y0) - pad), min(W, int(x1) + pad), min(H, int(y1) + pad)
    reg = arr[Y0:Y1, X0:X1, :3].astype(np.float32)
    m = np.zeros(reg.shape[:2], bool)
    m[int(y0) - Y0:int(y1) - Y0 + 1, int(x0) - X0:int(x1) - X0 + 1] = True
    ring = reg[~m]
    bg = np.median(ring, axis=0) if len(ring) else np.array([240, 235, 220], np.float32)
    inside = reg[m]
    if len(inside) == 0:
        return np.array([20, 20, 20], np.float32), bg
    d = np.linalg.norm(inside - bg, axis=1)
    k = max(5, int(0.12 * len(d)))
    sel = inside[np.argsort(-d)[:k]]
    return sel.mean(axis=0), bg


# ------------------------------------------------------------------------------------------------ text drawing
_FONT_CACHE = {}


def _font(size, wght):
    key = (int(size), int(wght))
    f = _FONT_CACHE.get(key)
    if f is None:
        f = ImageFont.truetype(FONT, int(size))
        try:
            f.set_variation_by_axes([wght])
        except Exception:
            pass
        _FONT_CACHE[key] = f
    return f


def text_layer(zh, size, wght=600, track=0.0, ink=(20, 20, 20), halo=(240, 235, 220), halo_w=2, SS=3):
    """(ink alpha, halo alpha) float32 arrays [0..1] of zh drawn horizontally at 1x scale (3x supersampled)."""
    f = _font(size * SS, wght)
    adv = [f.getlength(c) for c in zh]
    total = sum(adv) + track * SS * (len(zh) - 1)
    asc, desc = f.getmetrics()
    pad = (halo_w + 3) * SS
    W = int(total + 2 * pad)
    Hh = int(asc + desc + 2 * pad)
    big = Image.new("L", (W, Hh), 0)
    halo_im = Image.new("L", (W, Hh), 0)
    d = ImageDraw.Draw(big)
    dh = ImageDraw.Draw(halo_im)
    x = pad
    for c, a in zip(zh, adv):
        d.text((x, pad), c, font=f, fill=255)
        dh.text((x, pad), c, font=f, fill=255, stroke_width=halo_w * SS, stroke_fill=255)
        x += a + track * SS
    w1, h1 = max(1, W // SS), max(1, Hh // SS)
    ink_a = np.asarray(big.resize((w1, h1), Image.LANCZOS), np.float32) / 255.0
    halo_a = np.asarray(halo_im.resize((w1, h1), Image.LANCZOS), np.float32) / 255.0
    return ink_a, halo_a


def local_bg(src, X0, Y0, X1, Y1, win):
    """Per-pixel local background estimate (thin lines / text removed) for src[Y0:Y1, X0:X1]: median filter of a
    3x down-sampled crop with a window of ~win px, bilinear up-sampled back.  Returns float32 (Y1-Y0, X1-X0, 3)."""
    from scipy.ndimage import median_filter
    H, W = src.shape[:2]
    pad = int(win)
    a0, b0, a1, b1 = max(0, X0 - pad), max(0, Y0 - pad), min(W, X1 + pad), min(H, Y1 + pad)
    crop = Image.fromarray(np.ascontiguousarray(src[b0:b1, a0:a1, :3]))
    f = 3
    small = crop.resize((max(1, crop.width // f), max(1, crop.height // f)), Image.BOX)
    k = max(3, (int(win) // f) | 1)
    sa = np.asarray(small)
    med = median_filter(sa, size=(k, k, 1), mode="nearest")
    up = Image.fromarray(med).resize(crop.size, Image.BILINEAR)
    return np.asarray(up, np.float32)[Y0 - b0:Y1 - b0, X0 - a0:X1 - a0]


def composite(canvas, ink_a, halo_a, cx, cy, theta, ink, halo, halo_alpha=0.88, bg_src=None, bg_win=21, alpha=None):
    """alpha-blend (halo, then ink) rotated by theta (deg) around (cx, cy) into canvas float32 HxWx3 (in place).
    bg_src (uint8 HxWx3+) -> halo colour is the per-pixel local background of bg_src instead of the constant `halo`.
    alpha (float32 HxWx1, 0..1, in place) -> texture with transparency: the halo is only laid over pixels that already have
    content (scaled by their alpha); the ink is composited with the 'over' operator so text on transparent areas gets its own alpha."""
    h1, w1 = ink_a.shape
    if abs(theta) > 0.3:
        ia = Image.fromarray((ink_a * 255).astype(np.uint8)).rotate(-theta, expand=True, resample=Image.BICUBIC)
        ha = Image.fromarray((halo_a * 255).astype(np.uint8)).rotate(-theta, expand=True, resample=Image.BICUBIC)
        ink_a = np.asarray(ia, np.float32) / 255.0
        halo_a = np.asarray(ha, np.float32) / 255.0
        h1, w1 = ink_a.shape
    x0, y0 = int(round(cx - w1 / 2)), int(round(cy - h1 / 2))
    H, W = canvas.shape[:2]
    X0, Y0, X1, Y1 = max(0, x0), max(0, y0), min(W, x0 + w1), min(H, y0 + h1)
    if X1 <= X0 or Y1 <= Y0:
        return None
    ia = ink_a[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0, None]
    ha = halo_a[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0, None] * halo_alpha
    reg = canvas[Y0:Y1, X0:X1]
    if bg_src is not None:
        hc = local_bg(bg_src, X0, Y0, X1, Y1, bg_win)
    else:
        hc = np.asarray(halo, np.float32)[None, None, :]
    ink_c = np.asarray(ink, np.float32)[None, None, :]
    if alpha is not None:
        ao = alpha[Y0:Y1, X0:X1]                                   # view (h, w, 1)
        hae = ha * ao                                              # halo only over existing content
        a1 = hae + ao * (1 - hae)
        c1 = np.where(a1 > 1e-6, (hc * hae + reg * ao * (1 - hae)) / np.maximum(a1, 1e-6), reg)
        a2 = ia + a1 * (1 - ia)
        c2 = np.where(a2 > 1e-6, (ink_c * ia + c1 * a1 * (1 - ia)) / np.maximum(a2, 1e-6), reg)
        reg[:] = c2
        ao[:] = a2
        return (X0, Y0, X1, Y1)
    reg[:] = reg * (1 - ha) + hc * ha
    reg[:] = reg * (1 - ia) + ink_c * ia
    return (X0, Y0, X1, Y1)


def measure(zh, size, wght=600, track=0.0):
    f = _font(size, wght)
    adv = [f.getlength(c) for c in zh]
    asc, desc = f.getmetrics()
    return sum(adv) + track * (len(zh) - 1), float(size)  # width, nominal glyph height (em)
