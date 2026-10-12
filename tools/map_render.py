"""Render Chinese annotations next to the English labels of one map texture.

labels: list of dict
   text   English text (for logs)         zh     Chinese annotation
   box    4x2 quad of the English label    kind   'line' (default) | 'chain' (spaced letters along a curve)
 optional: side ('below'|'above'|'right'|'left' or list = preference order), size (px), wght, track (px), scale, dx, dy (px, in
 the label's own frame: dx along the text, dy along its normal), theta (override angle), ink / halo (RGB overrides)
"""
import math
import numpy as np
from PIL import Image
import map_lab as ML

SIDES = ("below", "above", "right", "left")


def union_quad(boxes, theta=None, chain=False):
    pts = np.concatenate([np.asarray(b, np.float64) for b in boxes], axis=0)
    if theta is None:
        if chain and len(boxes) >= 2:
            cs = np.array([np.asarray(b).mean(axis=0) for b in boxes])
            c0 = cs - cs.mean(axis=0)
            _, _, vt = np.linalg.svd(c0, full_matrices=False)
            d = vt[0]
            theta = math.degrees(math.atan2(d[1], d[0]))
            if theta > 90:
                theta -= 180
            if theta <= -90:
                theta += 180
        else:
            theta = ML.geom(boxes[0])[2]
    t = math.radians(theta)
    u = np.array([math.cos(t), math.sin(t)])
    n = np.array([-math.sin(t), math.cos(t)])
    pu, pn = pts @ u, pts @ n
    u0, u1, n0, n1 = pu.min(), pu.max(), pn.min(), pn.max()
    quad = [u0 * u + n0 * n, u1 * u + n0 * n, u1 * u + n1 * n, u0 * u + n1 * n]
    return [[float(p[0]), float(p[1])] for p in quad], theta


class Edge:
    """edge-density lookup (summed-area table of |grad| > thr)"""

    def __init__(self, rgb):
        g = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
        gy, gx = np.gradient(g.astype(np.float32))
        e = (np.hypot(gx, gy) > 22).astype(np.float32)
        self.sat = np.pad(np.cumsum(np.cumsum(e, 0), 1), ((1, 0), (1, 0)))
        self.H, self.W = e.shape

    def density(self, bb):
        x0, y0, x1, y1 = [int(round(v)) for v in bb]
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(self.W, x1), min(self.H, y1)
        if x1 <= x0 or y1 <= y0:
            return 1.0
        s = self.sat[y1, x1] - self.sat[y0, x1] - self.sat[y1, x0] + self.sat[y0, x0]
        return float(s) / ((x1 - x0) * (y1 - y0))


def rot_aabb(cx, cy, w, h, theta):
    q = np.array(ML.rect_corners(cx, cy, theta, w, h))
    return (q[:, 0].min(), q[:, 1].min(), q[:, 0].max(), q[:, 1].max())


def rot_slices(cx, cy, w, h, theta):
    """a rotated rectangle as a list of axis-aligned boxes (slices of about square shape along its length)"""
    k = max(1, int(math.ceil(w / max(h, 1.0))))
    if abs(math.sin(math.radians(theta))) < 0.05 or k == 1:
        return [rot_aabb(cx, cy, w, h, theta)]
    t = math.radians(theta)
    u = np.array([math.cos(t), math.sin(t)])
    out = []
    for i in range(k):
        off = ((i + 0.5) / k - 0.5) * w
        out.append(rot_aabb(cx + u[0] * off, cy + u[1] * off, w / k, h, theta))
    return out


def find_markers(arr, ocr_boxes, max_side=90, min_side=7):
    """AABBs of compact dark blobs (city dots, capital stars, small icons) that are not OCR text: the Chinese must not cover them."""
    from scipy import ndimage as ndi
    rgb = arr[..., :3].astype(np.float32)
    lum = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
    er = ndi.binary_erosion(lum < 80, structure=np.ones((3, 3), bool))          # thin lines / small text vanish
    lab, n = ndi.label(er)
    if n == 0:
        return []
    objs = ndi.find_objects(lab)
    areas = ndi.sum(er, lab, index=np.arange(1, n + 1))
    ob = np.array(ocr_boxes, np.float32).reshape(-1, 4) if len(ocr_boxes) else np.zeros((0, 4), np.float32)
    out = []
    for k, sl in enumerate(objs):
        if sl is None:
            continue
        y0, y1, x0, x1 = sl[0].start, sl[0].stop, sl[1].start, sl[1].stop
        w, h = x1 - x0, y1 - y0
        if w < min_side or h < min_side or w > max_side or h > max_side or areas[k] < 0.18 * w * h or areas[k] < 30:
            continue
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if len(ob) and np.any((ob[:, 0] <= cx) & (cx <= ob[:, 2]) & (ob[:, 1] <= cy) & (cy <= ob[:, 3])):
            continue                                                         # part of a text label (already an obstacle)
        out.append((x0 - 3.0, y0 - 3.0, x1 + 3.0, y1 + 3.0))
    return out


def render(arr, labels, others=(), log=print, frame=None, orig=None):
    """arr: HxWx4 uint8 original.  labels: see module doc.  others: AABBs of text that must not be covered (all English labels).
    frame: optional AABB the annotations must stay inside.  returns (new HxWx4 uint8, placed list)
    orig: for textures with transparency -- the true RGBA original; `arr` is then the same image flattened over an opaque
    background (used for colour / edge / placement analysis) and the output keeps `orig`'s RGB and alpha wherever nothing was drawn."""
    H, W = arr.shape[:2]
    src_img = orig if orig is not None else arr
    canvas = src_img[..., :3].astype(np.float32).copy()
    alpha_c = None if orig is None else orig[..., 3:4].astype(np.float32) / 255.0
    edge = Edge(arr[..., :3].astype(np.float32))
    occ = [tuple(o) for o in others]
    placed = []
    order = sorted(range(len(labels)), key=lambda i: (ML.geom(labels[i]["box"])[1], ML.geom(labels[i]["box"])[0]))
    for i in order:
        L = labels[i]
        zh = L.get("zh")
        if not zh:
            continue
        cx, cy, th, w, h = ML.geom(L["box"])
        if L.get("theta") is not None:
            th = L["theta"]
        th = ((th + 90) % 180) - 90                      # keep text upright
        chain = L.get("kind") == "chain"
        h_ref = L.get("h_ref", h)
        lower = any(c.islower() for c in L["text"])
        # steep chains: the Chinese stays upright (horizontal) beside the chain and may slide along it
        upright = bool(L.get("upright", chain and abs(th) > 38))
        th_txt = 0.0 if upright else th
        size = L.get("size") or max(20, int(round(h_ref * (0.80 if (lower or upright) else 0.62 if chain else 0.78) * L.get("scale", 1.0))))
        wght = L.get("wght", 700 if (chain or not lower) else 600)
        track = L.get("track", 0.0)
        if chain and "track" not in L and len(zh) > 1:       # spread the Chinese along the letter chain
            nat0, _ = ML.measure(zh, size, wght, 0.0)
            if upright:
                track = 0.12 * size
            else:
                track = float(min(max(0.0, (L.get("span", 0.6) * w - nat0) / (len(zh) - 1)), 1.6 * size))
        nat_w, _ = ML.measure(zh, size, wght, track)
        if not L.get("size") and nat_w > 1.9 * w and size > 18:
            size = max(18, int(size * 1.9 * w / nat_w))
            nat_w, _ = ML.measure(zh, size, wght, track)
        ink, bg = ML.label_colours(arr, L["box"])
        if chain and "ink" not in L:                         # hollow / spaced letters: darkest pixels of the chain's area
            x0_, y0_, x1_, y1_ = [int(v) for v in ML.aabb(L["box"])]
            reg = arr[max(0, y0_):max(1, y1_), max(0, x0_):max(1, x1_), :3].reshape(-1, 3).astype(np.float32)
            if len(reg) > 100:
                lum = reg @ np.array([0.299, 0.587, 0.114], np.float32)
                k = max(60, int(0.015 * len(lum)))
                ink = reg[np.argsort(lum)[:k]].mean(axis=0)
        ink = np.array(L.get("ink", ink), np.float32)
        halo = np.array(L.get("halo", bg), np.float32)
        halo_w = max(2, int(round(size * 0.11)))
        ia, ha = ML.text_layer(zh, size, wght, track, halo_w=halo_w)
        # tight crop to the halo footprint -> layer centre == ink centre
        ys, xs = np.where(ha > 0.02)
        if len(xs) == 0:
            continue
        ia = ia[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        ha = ha[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        lh, lw = ia.shape
        u = np.array([math.cos(math.radians(th)), math.sin(math.radians(th))])
        n = np.array([-math.sin(math.radians(th)), math.cos(math.radians(th))])
        gap = max(4.0, (0.35 if chain else 0.10) * (h_ref if chain else h))
        prefs = L.get("side", ("below", "above") if chain else SIDES)
        if isinstance(prefs, str):
            prefs = (prefs,) + tuple(s for s in (("below", "above") if chain else SIDES) if s != prefs)
        # text boxes lying inside this label's own quad (its letters / fragments) are not obstacles for it
        qc = np.array([cx, cy])
        own = []
        for o in occ:
            oc = np.array([(o[0] + o[2]) / 2, (o[1] + o[3]) / 2])
            d = oc - qc
            if abs(d @ u) <= w / 2 + 0.1 * h and abs(d @ n) <= h / 2 + 0.1 * h:
                own.append(o)
        others_now = [o for o in occ if o not in own]
        best = None
        ext = (lw / 2) * abs(n[0]) + (lh / 2) * abs(n[1]) if upright else lh / 2     # half extent of the text block along n
        fr_list = (0.5, 0.3, 0.7, 0.15, 0.85) if L.get("slide", upright) else (0.5,)
        gap_mults = (1.0, 2.2) if chain else (1.0,)
        for rank, side in enumerate(prefs):
            for fr in fr_list:
                for gi, gm in enumerate(gap_mults):
                    base = np.array([cx, cy]) + u * (fr - 0.5) * w
                    if side == "below":
                        c = base + n * (h / 2 + gap * gm + ext)
                    elif side == "above":
                        c = base - n * (h / 2 + gap * gm + ext)
                    elif side == "center":
                        c = base
                    elif side == "right":
                        c = base + u * (w / 2 + gap + lw / 2)
                    else:
                        c = base - u * (w / 2 + gap + lw / 2)
                    c = c + u * L.get("dx", 0) + n * L.get("dy", 0)
                    bb = rot_aabb(c[0], c[1], lw, lh, th_txt)
                    sl = rot_slices(c[0], c[1], lw, lh, th_txt)
                    a_bb = max(sum(ML.area(s) for s in sl), 1.0)
                    pen = 0.0
                    for o in others_now:
                        pen += 4.0 * sum(ML.inter_area(s, o) for s in sl) / a_bb
                    pen += 2.0 * float(np.mean([edge.density(s) for s in sl]))
                    if bb[0] < 0 or bb[1] < 0 or bb[2] > W or bb[3] > H:
                        pen += 50.0
                    if frame and (bb[0] < frame[0] or bb[1] < frame[1] or bb[2] > frame[2] or bb[3] > frame[3]):
                        pen += 20.0
                    pen += 0.12 * rank + 0.5 * abs(fr - 0.5) + 0.25 * gi
                    if best is None or pen < best[0]:
                        best = (pen, side, c, bb)
        pen, side, c, bb = best
        rect = ML.composite(canvas, ia, ha, c[0], c[1], th_txt, ink, halo,
                            bg_src=None if "halo" in L else arr, bg_win=max(21, int(round(0.45 * size))), alpha=alpha_c)
        if rect is None:
            continue
        occ.extend(rot_slices(c[0], c[1], lw, lh, th_txt))
        placed.append(dict(text=L["text"], zh=zh, side=side, pen=round(pen, 2), center=[round(float(c[0]), 1), round(float(c[1]), 1)],
                           size=size, theta=round(th_txt, 1), rect=[int(v) for v in rect]))
    out = src_img.copy()
    out[..., :3] = np.clip(canvas + 0.5, 0, 255).astype(np.uint8)
    if alpha_c is not None:
        out[..., 3] = np.clip(alpha_c[..., 0] * 255 + 0.5, 0, 255).astype(np.uint8)
    return out, placed
