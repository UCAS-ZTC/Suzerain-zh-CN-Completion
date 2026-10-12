"""Verify the repainted tutorial-image pack against the pristine game bundles.

usage: python su_verify_img.py PACK_DIR
Checks per bundle: same object set (types, path_ids); every non-Texture2D object byte-identical to the original;
Texture2D: same size, plain DXT1/DXT5, inline image data (no dangling stream reference), decodes to the repainted PNG
(PSNR) and equals the ORIGINAL decode outside the repainted label windows (PSNR); the repainted label windows differ.
Writes work/out/verify_img_report.txt
"""
import sys, os, glob
import numpy as np
from PIL import Image
from lib_su import *
import tut_repaint
import su_stage_img as SI

PACK = sys.argv[1]
base = os.path.join(PACK, AA_REL)
rep = open(os.path.join(WORK, "out", "verify_img_report.txt"), "w", encoding="utf-8")
problems = []


def P(s=""):
    print(s, file=rep)
    rep.flush()


def bad(msg):
    problems.append(msg)
    P("PROBLEM: " + msg)


names = sorted(tut_repaint.LABELS)
files = sorted(f for f in os.listdir(lp(base)) if f.endswith(".bundle"))
P(f"pack bundles: {len(files)} (expected {len(names)})")
if len(files) != len(names):
    bad(f"bundle count {len(files)} != {len(names)}")

for name in names:
    src = SI.game_bundle(name)
    fn = os.path.basename(src)
    if fn not in files:
        bad(f"{name}: bundle {fn} missing")
        continue
    eo = load_env(src)
    en = load_env(os.path.join(base, fn))
    o_objs = {o.path_id: o for o in eo.objects}
    n_objs = {o.path_id: o for o in en.objects}
    if set(o_objs) != set(n_objs) or any(o_objs[k].type.name != n_objs[k].type.name for k in o_objs):
        bad(f"{name}: object set differs")
        continue
    tex_checked = 0
    for pid, o in o_objs.items():
        n = n_objs[pid]
        if o.type.name == "Texture2D":
            t_o, t_n = o.read(), n.read()
            tt = n.read_typetree()
            if (t_n.m_Width, t_n.m_Height) != (t_o.m_Width, t_o.m_Height):
                bad(f"{name}: size changed")
            if int(t_n.m_TextureFormat) not in (10, 12):
                bad(f"{name}: format {int(t_n.m_TextureFormat)} not plain DXT1/DXT5")
            sd = tt.get("m_StreamData") or {}
            if sd.get("size", 0) != 0 or sd.get("path", ""):
                bad(f"{name}: stream data still referenced {sd}")
            if tt.get("m_MipCount") != 1 or tt.get("m_ImageCount") != 1 or tt.get("m_TextureDimension") != 2:
                bad(f"{name}: mip/image/dimension fields changed {tt.get('m_MipCount')}/{tt.get('m_ImageCount')}/{tt.get('m_TextureDimension')}")
            for k in ("m_ColorSpace", "m_IsReadable", "m_LightmapFormat", "m_Name"):
                if tt.get(k) != o.read_typetree().get(k):
                    bad(f"{name}: field {k} changed")
            dec_new = np.asarray(t_n.image.convert("RGB"))
            dec_old = np.asarray(t_o.image.convert("RGB"))
            want = np.asarray(Image.open(os.path.join(tut_repaint.NEW, name + ".png")).convert("RGB"))
            p_want = SI.psnr(dec_new, want)
            # outside every label window (+40 px margin) the picture must equal the original decode
            m = np.ones(dec_new.shape[:2], dtype=bool)
            for lab in tut_repaint.LABELS[name]:
                x0, y0, x1, y1 = lab["win"]
                m[max(0, y0 - 40):y1 + 40, max(0, x0 - 40):x1 + 40] = False
            p_out = SI.psnr(dec_new[m], dec_old[m])
            md = np.abs(dec_new[m].astype(int) - dec_old[m].astype(int))
            # inside the windows the picture must really differ from the original
            mi = ~m
            inner_diff = np.abs(dec_new[mi].astype(int) - dec_old[mi].astype(int)).mean()
            P(f"{name}: {t_n.m_Width}x{t_n.m_Height} fmt {int(t_n.m_TextureFormat)} data {len(t_n.image_data)}B | "
              f"PSNR vs repaint {p_want:.1f} dB | outside labels vs original {p_out:.1f} dB (max abs {md.max()}) | label-area mean diff {inner_diff:.1f}")
            if p_want < 38:
                bad(f"{name}: decode of new texture differs from the repainted PNG (PSNR {p_want:.1f})")
            if p_out < 36:
                bad(f"{name}: picture outside the labels changed too much (PSNR {p_out:.1f})")
            if inner_diff < 3:
                bad(f"{name}: label area looks unchanged (mean diff {inner_diff:.1f})")
            tex_checked += 1
        else:
            if o.get_raw_data() != n.get_raw_data():
                bad(f"{name}: {o.type.name} object {pid} changed")
    if tex_checked != 1:
        bad(f"{name}: {tex_checked} textures checked")
P()
P(f"problems: {len(problems)}")
print(f"problems: {len(problems)}")
