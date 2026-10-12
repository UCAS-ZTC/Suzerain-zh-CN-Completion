"""Annotate one map: OCR candidates + curated patch + glossary -> annotated PNG.

usage: python map_run.py NAME [NAME ...]
reads   cache\\map\\NAME.png, cache\\map\\NAME.ocr.json, maplab\\patch_NAME.py (optional: PATCH = dict(drop, fix, merge, add, skip, style))
writes  cache\\map\\out\\NAME.png (RGBA, same size), cache\\map\\out\\NAME.labels.json
prints  labels without a Chinese rendering (map_names.lookup) and placement statistics
"""
import sys
import os
import json
import time
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import map_lab as ML
import map_names
import map_render as MR

OUT = os.path.join(ML.MAPDIR, "out")
os.makedirs(OUT, exist_ok=True)


def load_patch(name):
    p = os.path.join(ML.MAPLAB_DIR, f"patch_{name}.py")
    if not os.path.exists(p):
        return {}
    ns = {}
    exec(compile(open(p, encoding="utf-8").read(), p, "exec"), ns)
    return ns.get("PATCH", {})


SUFFIX_WORDS = {"bay", "gulf", "lake", "island", "isles", "islands", "sea", "strait"}


def auto_suffix_merge(labels):
    """'Torreic' + 'Bay' (stacked or on one line) -> 'Torreic Bay' when the combined name has a Chinese rendering."""
    used, merged = set(), []
    for i, L in enumerate(labels):
        if map_names.key(L["text"]) not in SUFFIX_WORDS or i in used:
            continue
        cx, cy, th, w, h = ML.geom(L["box"])
        best = None
        for j, B in enumerate(labels):
            if i == j or j in used or map_names.key(B["text"]) in SUFFIX_WORDS:
                continue
            bx, by, bth, bw, bh = ML.geom(B["box"])
            if abs(((th - bth + 90) % 180) - 90) > 12:
                continue
            t = np.radians(bth)
            u, n = np.array([np.cos(t), np.sin(t)]), np.array([-np.sin(t), np.cos(t)])
            d = np.array([cx - bx, cy - by])
            du, dn = float(d @ u), float(d @ n)
            hh = max(h, bh)
            stacked = 0.6 * hh <= dn <= 2.6 * hh and abs(du) <= 0.6 * (w + bw)
            inline = abs(dn) <= 0.7 * hh and 0.5 * (bw + w) * 0.8 <= du <= 0.5 * (bw + w) + 1.6 * hh
            if not (stacked or inline):
                continue
            dist = float(np.hypot(du, dn))
            if best is None or dist < best[0]:
                best = (dist, j, bth)
        if best is None:
            continue
        j = best[1]
        B = labels[j]
        text = f"{B['text']} {L['text']}"
        zh = map_names.lookup(text)
        if not zh:
            continue
        quad, th2 = MR.union_quad([B["box"], L["box"]], theta=best[2])
        lab = dict(idx=B["idx"], text=text, box=quad, zh=zh, theta=th2,
                   h_ref=float(np.median([ML.geom(B["box"])[4], h])))
        for k in ("kind", "side", "size", "wght", "track", "scale", "dx", "dy", "ink", "halo"):
            if k in B:
                lab[k] = B[k]
        used |= {i, j}
        merged.append(lab)
    return [l for k, l in enumerate(labels) if k not in used] + merged


def build_labels(name):
    raw = ML.load_ocr(name)
    patch = load_patch(name)
    drop = set(patch.get("drop", []))
    fix = patch.get("fix", {})
    skip = {map_names.key(s) for s in patch.get("skip", [])}
    merged_idx = set()
    for m in patch.get("merge", []):
        merged_idx |= set(m["idx"])
    cands = ML.candidates(raw)
    labels = []
    for a in cands:
        if a["idx"] in drop or a["idx"] in merged_idx:
            continue
        text = fix.get(a["idx"], a["text"])
        if map_names.key(text) in skip:
            continue
        labels.append(dict(idx=a["idx"], text=text, box=a["box"], zh=map_names.lookup(text)))
    for i, t in fix.items():                       # fixes may revive a box that candidates() filtered out
        if i not in {l["idx"] for l in labels} and i not in drop and i not in merged_idx:
            r = raw[i]
            labels.append(dict(idx=i, text=t, box=r["box"], zh=map_names.lookup(t)))
    if not patch.get("nomerge"):
        labels = auto_suffix_merge(labels)
    for m in patch.get("merge", []):
        boxes = [raw[i]["box"] for i in m["idx"]]
        chain = m.get("kind") == "chain"
        quad, th = MR.union_quad(boxes, theta=m.get("theta"), chain=chain)
        lab = dict(idx=m["idx"][0], text=m["text"], box=quad, zh=m.get("zh") or map_names.lookup(m["text"]),
                   kind=m.get("kind", "line"), theta=th)
        lab["h_ref"] = float(np.median([ML.geom(b)[4] for b in boxes]))   # size follows ONE text line, not the whole block
        for k in ("side", "size", "wght", "track", "scale", "dx", "dy", "ink", "halo", "span"):
            if k in m:
                lab[k] = m[k]
        labels.append(lab)
    for m in patch.get("add", []):
        if "pts" in m:                                  # curved letter chain: one Chinese char per slot along the polyline
            pts = np.array(m["pts"], float)
            if pts[0][0] > pts[-1][0]:
                pts = pts[::-1]
            seg = np.hypot(*np.diff(pts, axis=0).T)
            cum = np.r_[0.0, np.cumsum(seg)]
            tot = float(cum[-1])
            zh = m.get("zh") or map_names.lookup(m["text"])
            if not zh:
                labels.append(dict(idx=-1, text=m["text"], box=ML.rect_corners(float(pts[0][0]), float(pts[0][1]), 0, 10, 10), zh=None))
                continue
            n = len(zh)
            fr = [0.5] if n == 1 else [0.5 + (i / (n - 1) - 0.5) * m.get("span", 0.6) for i in range(n)]
            size = int(m["size"])
            for ch, f in zip(zh, fr):
                s = f * tot
                k = int(min(max(np.searchsorted(cum, s, side="right") - 1, 0), len(seg) - 1))
                tt = (s - cum[k]) / max(seg[k], 1e-6)
                p = pts[k] + (pts[k + 1] - pts[k]) * tt
                tang = pts[k + 1] - pts[k]
                th = float(np.degrees(np.arctan2(tang[1], tang[0])))
                th = ((th + 90) % 180) - 90
                nv = np.array([-np.sin(np.radians(th)), np.cos(np.radians(th))])
                c = p + nv * m.get("off", 0.0)
                if m.get("upright"):
                    th = 0.0
                quad = ML.rect_corners(float(c[0]), float(c[1]), th, float(size), float(size))
                lab = dict(idx=-1, text=m["text"], box=[[float(q[0]), float(q[1])] for q in quad], zh=ch, kind="line", theta=th,
                           h_ref=float(size), size=size, side="center", wght=m.get("wght", 700))
                for k2 in ("ink", "halo", "dx", "dy"):
                    if k2 in m:
                        lab[k2] = m[k2]
                labels.append(lab)
            continue
        if "p0" in m:                                   # letter chain given by the centres of its first / last letter
            (x0, y0), (x1, y1) = m["p0"], m["p1"]
            th = float(np.degrees(np.arctan2(y1 - y0, x1 - x0)))
            if th > 90:
                th -= 180
            if th <= -90:
                th += 180
            span = float(np.hypot(x1 - x0, y1 - y0)) + m["h"]
            cx, cy, w, h, kind = (x0 + x1) / 2, (y0 + y1) / 2, span, float(m["h"]), "chain"
        else:
            cx, cy, th, w, h, kind = m["cx"], m["cy"], m.get("theta", 0.0), m["w"], m["h"], m.get("kind", "line")
        quad = ML.rect_corners(cx, cy, th, w, h)
        lab = dict(idx=-1, text=m["text"], box=[[float(p[0]), float(p[1])] for p in quad], zh=m.get("zh") or map_names.lookup(m["text"]),
                   kind=kind, theta=th, h_ref=h if kind == "chain" else h)
        for k in ("side", "size", "wght", "track", "scale", "dx", "dy", "ink", "halo", "span"):
            if k in m:
                lab[k] = m[k]
        labels.append(lab)
    # per-label style overrides by raw idx
    for i, st in patch.get("style", {}).items():
        for l in labels:
            if l["idx"] == i:
                l.update(st)
    return raw, labels, patch


def run(name):
    t0 = time.time()
    orig = np.array(Image.open(os.path.join(ML.MAPDIR, name + ".png")).convert("RGBA"))
    patch0 = load_patch(name)
    if callable(patch0.get("pre")):                 # optional pixel-level preparation (e.g. shrink a sprite to make room)
        orig = patch0["pre"](orig)
    arr, orig_arg = orig, None
    if orig[..., 3].min() < 250:                    # real transparency: analyse on a flattened copy, composite alpha-aware
        bg = tuple(patch0.get("flat", (255, 255, 255)))
        a = orig[..., 3:4].astype(np.float32) / 255.0
        flat = orig[..., :3].astype(np.float32) * a + np.asarray(bg, np.float32)[None, None, :] * (1 - a)
        arr = np.dstack([np.clip(flat + 0.5, 0, 255).astype(np.uint8), np.full(orig.shape[:2], 255, np.uint8)])
        orig_arg = orig
    raw, labels, patch = build_labels(name)
    others = [ML.aabb(r["box"]) for r in raw]
    if not patch.get("nomarkers"):
        others = others + MR.find_markers(arr, others)
    frame = patch.get("frame")
    if frame is None and orig_arg is not None and name.startswith("c_"):      # codex crops: keep inside the opaque map area
        ys, xs = np.nonzero(orig_arg[..., 3] > 8)
        frame = (float(xs.min()), float(ys.min()), float(xs.max() + 1), float(ys.max() + 1))
    out, placed = MR.render(arr, labels, others=others, frame=frame, orig=orig_arg)
    Image.fromarray(out, "RGBA").save(os.path.join(OUT, name + ".png"))
    json.dump(dict(placed=placed, missing=[l["text"] for l in labels if not l.get("zh")]),
              open(os.path.join(OUT, name + ".labels.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    miss = sorted({l["text"] for l in labels if not l.get("zh")})
    sides = {}
    for p in placed:
        sides[p["side"]] = sides.get(p["side"], 0) + 1
    bad = [p for p in placed if p["pen"] > 3]
    print(f"{name}: labels {len(labels)}, annotated {len(placed)}, sides {sides}, high-penalty {len(bad)}, missing zh {len(miss)} [{time.time() - t0:.0f}s]")
    if miss:
        print("   MISSING:", " | ".join(miss))
    if bad:
        print("   HIGH-PEN:", " | ".join(f"{p['text']}({p['pen']})" for p in bad[:20]))


if __name__ == "__main__":
    for n in sys.argv[1:]:
        run(n)
