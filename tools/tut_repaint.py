"""Repaint the English labels baked into the war-tutorial screenshots with Chinese labels.

Input : work/cache/tut/orig/<name>.png   (decoded from the pristine game bundles; created on demand by ensure_orig)
Output: work/cache/tut/new/<name>.png    (repainted RGB, same size)  +  work/cache/tut/qa/<name>_<k>.png (before|after crops)

Per label:  find the text pixels inside a hand-set search window (they are the only bright pixels in the dark label body),
            erase them by row-wise interpolation across the glyph runs (keeps the label's own gradient),
            draw the Chinese text (Noto Serif SC, same colour, centred where the English text was).
usage: python tut_repaint.py [name ...]    (default: all configured images)
"""
import os, sys, json, re
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from lib_su import *

ORIG = os.path.join(WORK, "cache", "tut", "orig")
NEW = os.path.join(WORK, "cache", "tut", "new")
QA = os.path.join(WORK, "cache", "tut", "qa")
os.makedirs(NEW, exist_ok=True)
os.makedirs(QA, exist_ok=True)

# win = (x0, y0, x1, y1) search window inside the label body (full-res px); thr = luma threshold of text pixels vs. label fill
# size = font size in px; wght = variable-font weight; track = extra letter spacing in px
BUBBLE = dict(thr=110, size=40, wght=500, track=3)
LABELS = {
    "tutorial_war_attack": [dict(en="Attack", zh="攻击", win=(1440, 456, 1676, 512), **BUBBLE)],
    "tutorial_war_bombing": [dict(en="Bomb", zh="轰炸", win=(1078, 492, 1262, 536), **BUBBLE)],
    "tutorial_war_fortify": [dict(en="Fortify", zh="固守", win=(948, 400, 1158, 452), **BUBBLE)],
    "tutorial_war_movement": [dict(en="Move", zh="移动", win=(900, 158, 1060, 198), **BUBBLE)],
    "tutorial_war_navalbattle": [dict(en="Support", zh="支援", win=(662, 372, 838, 414), **BUBBLE)],
    "tutorial_war_navalinvasion": [dict(en="Deploy Marine", zh="部署海军陆战队", win=(800, 96, 1245, 160), **BUBBLE)],
    "tutorial_war_navallandsupport": [dict(en="Support", zh="支援", win=(698, 258, 892, 298), **BUBBLE)],
    "tutorial_war_navalmove": [dict(en="Move", zh="移动", win=(1698, 230, 1872, 274), **BUBBLE)],
    "tutorial_war_support": [dict(en="Support", zh="支援", win=(948, 504, 1120, 540), **BUBBLE)],
    "tutorial_war_actionpoints": [
        dict(en="Action Points", zh="行动点", win=(1440, 750, 1730, 814), thr=80, size=40, wght=500, track=3),
        dict(en="End Turn", zh="结束回合", win=(1740, 910, 1950, 970), thr=120, size=40, wght=500, track=3),
    ],
}


def _deploy_panel():
    """the unit-deployment panel screenshot: header, 9 list rows (name + sub line, left aligned), 2 buttons, 2 banners"""
    NAME = dict(thr=100, size=22, wght=500, track=1, align="left", vmode="cap")
    SUB = dict(thr=90, size=15, wght=500, track=0, align="left", vmode="cap")
    NAME_SEL = dict(NAME, ink="dark", thr=150)
    SUB_SEL = dict(SUB, ink="dark", thr=150)
    # windows are set from the measured text bands (tut_bands.py): name window y0,y1 / sub window y0,y1 with >= 2 blank rows in between
    rows = [  # (name en, name zh, name window y0,y1, sub en, sub zh, sub window y0,y1, selected)
        ("Infantry", "步兵", 124, 156, "Rizian Army", "里齐亚陆军", 156, 177, False),
        ("Support", "支援", 208, 237, "Rizian Army", "里齐亚陆军", 238, 259, True),
        ("Tank", "坦克", 289, 317, "Rizian Army", "里齐亚陆军", 318, 343, False),
        ("Mountaineer", "山地师", 372, 399, "Rizian Army", "里齐亚陆军", 401, 424, False),
        ("Military ship", "军舰", 454, 486, "Rizian Army", "里齐亚陆军", 486, 508, False),
        ("Submarine", "潜艇", 537, 564, "Rizian Army", "里齐亚陆军", 566, 591, False),
        ("Invasion ship", "登陆舰", 620, 650, "Rizian Army", "里齐亚陆军", 651, 673, False),
        ("Azaro Elites", "阿扎罗精锐", 702, 731, "House Azaro", "阿扎罗家族", 732, 752, False),
    ]
    out = [
        dict(en="Units", zh="单位", win=(40, 34, 150, 67), thr=80, size=30, wght=600, track=4, align="left", vmode="cap"),
        dict(en="Select to Deploy", zh="选择以部署", win=(40, 68, 230, 96), thr=80, size=22, wght=500, track=2, align="left", vmode="cap"),
    ]
    for en, zh, ny0, ny1, sen, szh, sy0, sy1, sel in rows:
        out.append(dict(en=en, zh=zh, win=(136, ny0, 330, ny1), **(NAME_SEL if sel else NAME)))
        out.append(dict(en=sen, zh=szh, win=(136, sy0, 300, sy1), **(SUB_SEL if sel else SUB)))
    # last list row is scrolled under the panel edge: only the top ~11 px of the text (y 791..801) are visible.
    # cy = vertical centre of a full-height name line (same pitch as the rows above: cap top 791 + 17/2)
    out.append(dict(en="Sazon Levies", zh="萨宗征召兵", win=(136, 785, 330, 802), clip_y=802, cy=799.5, touch_ok=True, **NAME))
    out += [
        dict(en="Azaro's Deployment Plan", zh="阿扎罗的部署方案", win=(90, 834, 366, 867), thr=130, size=24, wght=500, track=3, vmode="cap"),
        dict(en="Reset Deployment", zh="重置部署", win=(120, 922, 336, 956), thr=130, size=24, wght=500, track=4, vmode="cap"),
        dict(en="OPERATION START", zh="行动开始", win=(930, 0, 1160, 19), thr=100, size=15, wght=500, track=14),
        dict(en="All land border tiles must have a unit.", zh="所有陆地边境地块都必须部署单位。", win=(1600, 14, 2035, 52), thr=80, size=24, wght=500, track=1),
    ]
    return out


LABELS["tutorial_war_placingunit"] = _deploy_panel()


def luma(a):
    return 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]


def dilate(m, r):
    """square dilation by r px (the search windows keep a margin to the window edge, so np.roll wrap-around is harmless)"""
    out = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out |= np.roll(np.roll(m, dy, axis=0), dx, axis=1)
    return out


def boxblur(a, k):
    pad = k // 2
    p = np.pad(a, ((pad, pad), (pad, pad), (0, 0)), mode="edge")
    c = np.cumsum(np.cumsum(p, axis=0), axis=1)
    c = np.pad(c, ((1, 0), (1, 0), (0, 0)))
    s = c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]
    return s / (k * k)


def erase(img, win, thr, ink="light"):
    """img float32 HxWx3 (modified in place). ink 'light' = text brighter than its label fill (pixels with luma > thr),
    'dark' = text darker than the fill (luma < thr).  returns (text bbox (x0,y0,x1,y1) full-res, text colour, touches window edge)"""
    x0, y0, x1, y1 = win
    reg = img[y0:y1, x0:x1]
    L = luma(reg)
    raw = (L > thr) if ink == "light" else (L < thr)
    ys, xs = np.where(raw)
    if len(xs) == 0:
        raise RuntimeError(f"no text pixels found in window {win}")
    bx0, bx1, by0, by1 = xs.min(), xs.max(), ys.min(), ys.max()
    touches = bx0 <= 1 or by0 <= 1 or bx1 >= reg.shape[1] - 2 or by1 >= reg.shape[0] - 2
    mask = dilate(raw, 3)
    # colour of the English text = mean of its most extreme (brightest / darkest) pixels
    top = L[raw]
    sel = raw & ((L >= np.percentile(top, 80)) if ink == "light" else (L <= np.percentile(top, 20)))
    colour = reg[sel].mean(axis=0)
    work = reg.copy()
    H, W = mask.shape
    for yy in range(H):
        row = mask[yy]
        if not row.any():
            continue
        xs_m = np.where(row)[0]
        # runs of masked pixels
        starts = [xs_m[0]]
        ends = []
        for a, b in zip(xs_m[:-1], xs_m[1:]):
            if b != a + 1:
                ends.append(a)
                starts.append(b)
        ends.append(xs_m[-1])
        for a, b in zip(starts, ends):
            la = max(0, a - 6)
            lb = min(W, b + 7)
            left = reg[yy, la:a].mean(axis=0) if a - la > 0 and not mask[yy, la:a].any() else None
            right = reg[yy, b + 1:lb].mean(axis=0) if lb - (b + 1) > 0 and not mask[yy, b + 1:lb].any() else None
            if left is None and right is None:
                left = right = reg[yy, ~row].mean(axis=0)
            elif left is None:
                left = right
            elif right is None:
                right = left
            n = b - a + 1
            t = (np.arange(n) + 0.5) / n
            work[yy, a:b + 1] = left[None, :] * (1 - t[:, None]) + right[None, :] * t[:, None]
    sm = boxblur(work, 5)
    m3 = mask[..., None]
    work = np.where(m3, sm, work)
    img[y0:y1, x0:x1] = work
    return (x0 + int(bx0), y0 + int(by0), x0 + int(bx1) + 1, y0 + int(by1) + 1), colour, touches


def draw_text(img, zh, ax, cy, size, wght, track, colour, align="center", clip_y=None):
    """Alpha-composite zh into img float HxWx3 (4x supersampling): ink box centred on (ax, cy), or - with align='left' - its left edge
    at ax and its vertical centre at cy.  clip_y: rows >= clip_y are not drawn (list items scrolled under a panel edge)."""
    SS = 4
    f = ImageFont.truetype(FONT, size * SS)
    f.set_variation_by_axes([wght])
    # lay out char by char with tracking
    adv = [f.getlength(c) for c in zh]
    total = sum(adv) + track * SS * (len(zh) - 1)
    bb = [f.getbbox(c) for c in zh]
    top = min(b[1] for b in bb)
    bot = max(b[3] for b in bb)
    wpx = int(total) + 8 * SS
    hpx = (bot - top) + 8 * SS
    layer = Image.new("L", (wpx, hpx), 0)
    d = ImageDraw.Draw(layer)
    x = 4 * SS
    for c, a, b in zip(zh, adv, bb):
        d.text((x, 4 * SS - top), c, font=f, fill=255)
        x += a + track * SS
    # ink bbox of the layer
    ib = layer.getbbox()
    layer = layer.crop(ib)
    lw, lh = layer.size
    # downsample to 1x with high-quality filter
    sw, sh = max(1, round(lw / SS)), max(1, round(lh / SS))
    a1 = np.asarray(layer.resize((sw, sh), Image.LANCZOS), dtype=np.float32) / 255.0
    px0 = int(round(ax - sw / 2)) if align == "center" else int(round(ax))
    py0 = int(round(cy - sh / 2))
    if clip_y is not None and py0 + sh > clip_y:
        keep = max(0, clip_y - py0)
        a1 = a1[:keep]
        sh = keep
    reg = img[py0:py0 + sh, px0:px0 + sw]
    img[py0:py0 + sh, px0:px0 + sw] = reg * (1 - a1[..., None]) + np.asarray(colour, dtype=np.float32)[None, None, :] * a1[..., None]
    return (px0, py0, px0 + sw, py0 + sh)


def ensure_orig(name):
    """decoded pristine screenshot (RGB PNG cache); decoded from the game's bundle when the cache file is missing"""
    p = os.path.join(ORIG, name + ".png")
    if not os.path.exists(p):
        os.makedirs(ORIG, exist_ok=True)
        src = find_bundle(f"tutorial_assets_assets_addressableassets_tutorial_{name}.png_", AA_GAME)
        env = load_env(src)
        for o in env.objects:
            if o.type.name == "Texture2D":
                o.read().image.convert("RGB").save(p)
    return p


def process(name):
    src = Image.open(ensure_orig(name)).convert("RGB")
    img = np.asarray(src, dtype=np.float32).copy()
    info = []
    for k, lab in enumerate(LABELS[name]):
        before = src.copy()
        bbox, colour, touches = erase(img, lab["win"], lab["thr"], lab.get("ink", "light"))
        align = lab.get("align", "center")
        ax = (bbox[0] + bbox[2]) / 2 if align == "center" else bbox[0]
        if lab.get("vmode", "bbox") == "cap":
            # baseline-aligned list text: the English bbox includes descenders (g j p q y), the Chinese is centred on the cap-height band
            hh = bbox[3] - bbox[1]
            cap = hh * (0.78 if re.search("[gjpqy]", lab["en"]) else 1.0)
            cy = bbox[1] + cap / 2
        else:
            cy = (bbox[1] + bbox[3]) / 2
        if "cy" in lab:
            cy = lab["cy"]
        if "color" in lab:
            colour = np.asarray(lab["color"], dtype=np.float32)
        nb = draw_text(img, lab["zh"], ax, cy, lab["size"], lab["wght"], lab["track"], colour, align, lab.get("clip_y"))
        info.append(dict(name=name, en=lab["en"], zh=lab["zh"], en_bbox=bbox, zh_bbox=nb, colour=[round(float(c)) for c in colour], touches_window=bool(touches and not lab.get("touch_ok"))))
        # QA crop: before | after, around the window
        wx0, wy0, wx1, wy1 = lab["win"]
        pad = 40
        box = (max(0, wx0 - pad), max(0, wy0 - pad), min(2048, wx1 + pad), min(1024, wy1 + pad))
        cur = Image.fromarray(np.clip(img + 0.5, 0, 255).astype(np.uint8))
        a = before.crop(box)
        b = cur.crop(box)
        sheet = Image.new("RGB", (a.width, a.height * 2 + 6), (255, 0, 255))
        sheet.paste(a, (0, 0))
        sheet.paste(b, (0, a.height + 6))
        sheet.save(os.path.join(QA, f"{name}_{k}.png"))
    out = Image.fromarray(np.clip(img + 0.5, 0, 255).astype(np.uint8))
    out.save(os.path.join(NEW, name + ".png"))
    return info


if __name__ == "__main__":
    names = sys.argv[1:] or list(LABELS)
    allinfo = []
    for n in names:
        allinfo += process(n)
    for i in allinfo:
        print(json.dumps(i, ensure_ascii=False))
