# -*- coding: utf-8 -*-
"""Verify the map-label add-on pack against the bundles it was built from (pristine game file, or the Plus main pack's copy).

usage: python su_verify_map.py PACK_DIR
Per bundle (work/out/map_build_info.json lists bundle -> patched textures):
  1. same object set (path_ids / types) as the base bundle
  2. every object that is not a patched Texture2D is byte-identical (serialized data)
  3. streamed data (.resS): differs from the base ONLY inside the patched textures' own ranges
  4. patched textures: same size / mip count, plain DXT1/DXT5, decode == annotated PNG (PSNR), and the decode equals the BASE decode
     in every 4x4 block the annotation did not touch (mip 0 and all lower mips)
  5. manifest: file list == bundles in the pack, patched_sha256 matches, original_sha256 == hash of the base file
Writes work/out/verify_map_report.txt
"""
import sys, os, json, time
import numpy as np
from PIL import Image
import texture2ddecoder
from UnityPy.enums import TextureFormat as TF
from lib_su import *
import map_stage as MS

PACK = sys.argv[1]
MAPOUT = os.path.join(CACHE, "map", "out")
rep = open(os.path.join(WORK, "out", "verify_map_report.txt"), "w", encoding="utf-8")
problems = []


def P(s=""):
    print(s, file=rep)
    rep.flush()


def bad(msg):
    problems.append(msg)
    P("PROBLEM: " + msg)


def psnr(a, b):
    mse = np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2)
    return 99.0 if mse == 0 else 10 * np.log10(255.0 ** 2 / mse)


def decode_mips(raw, w, h, mips, bpb):
    """list of top-down RGBA uint8 arrays, one per mip level, from plain DXT data"""
    out, off = [], 0
    for k in range(mips):
        wk, hk = max(1, w >> k), max(1, h >> k)
        n = ((wk + 3) // 4) * ((hk + 3) // 4) * bpb
        blob = raw[off:off + n]
        off += n
        bgra = texture2ddecoder.decode_bc1(blob, wk, hk) if bpb == 8 else texture2ddecoder.decode_bc3(blob, wk, hk)
        a = np.frombuffer(bgra, np.uint8).reshape(hk, wk, 4)[..., [2, 1, 0, 3]]
        out.append(a[::-1].copy())            # native data is bottom-up
    assert off == len(raw), (off, len(raw))
    return out


def touched_mask(old_rgba, new_rgba):
    H, W = old_rgba.shape[:2]
    ch = (old_rgba != new_rgba).any(axis=2)
    blk = ch.reshape(H // 4, 4, W // 4, 4).any(axis=(1, 3))
    return np.repeat(np.repeat(blk, 4, axis=0), 4, axis=1)


infos = json.load(open(os.path.join(WORK, "out", "map_build_info.json"), encoding="utf-8"))
base_dir = os.path.join(PACK, AA_REL)
files = sorted(f for f in os.listdir(lp(base_dir)) if f.endswith(".bundle"))
P(f"pack bundles: {len(files)} (expected {len(infos)})")
if sorted(i["file"] for i in infos) != files:
    bad("bundle list differs from the build info")

man = json.load(open(os.path.join(PACK, "patch_manifest.json"), encoding="utf-8-sig"))
mf = {f["file_name"]: f for f in man["files"]}
if sorted(mf) != files:
    bad("manifest file list != bundles in the pack")

t_all = time.time()
n_tex = 0
for inf in infos:
    fn = inf["file"]
    if fn not in files:
        bad(f"{fn}: missing")
        continue
    t0 = time.time()
    src, orig_sha, label = MS.base_path(fn)
    newp = os.path.join(base_dir, fn)
    if fn in mf:
        if mf[fn]["original_sha256"] != orig_sha:
            bad(f"{fn}: manifest original_sha256 != base hash")
        if mf[fn]["patched_sha256"] != sha256_file(newp):
            bad(f"{fn}: manifest patched_sha256 mismatch")
        if label == "plus" and mf[fn].get("requires_pack") is None:
            bad(f"{fn}: built on the main pack but manifest has no requires_pack")
    eo, en = load_env(src), load_env(newp)
    o_objs = {o.path_id: o for o in eo.objects}
    n_objs = {o.path_id: o for o in en.objects}
    if set(o_objs) != set(n_objs) or any(o_objs[k].type.name != n_objs[k].type.name for k in o_objs):
        bad(f"{fn}: object set differs")
        continue
    patched_names = set(inf["textures"])
    patched_ranges = {}          # resS name -> [(offset, size)] in the BASE bundle
    pairs = []
    for pid, o in o_objs.items():
        n = n_objs[pid]
        if o.type.name == "Texture2D":
            t_o = o.read()
            if t_o.m_Name in patched_names:
                sd = t_o.m_StreamData
                if sd.path and int(sd.size) > 0:
                    patched_ranges.setdefault(sd.path.split("/")[-1], []).append((int(sd.offset), int(sd.size)))
                pairs.append((t_o.m_Name, o, n))
                continue
        if o.get_raw_data() != n.get_raw_data():
            bad(f"{fn}: {o.type.name} object {pid} changed (not a patched texture)")
    got = {p[0] for p in pairs}
    if got != patched_names:
        bad(f"{fn}: patched textures {sorted(patched_names - got)} not found")
    # 3. resS
    for name, f_o in eo.file.files.items():
        if not name.endswith(".resS"):
            continue
        f_n = en.file.files.get(name)
        if f_n is None:
            bad(f"{fn}: {name} missing in the new bundle")
            continue
        a, b = np.frombuffer(bytes(f_o.bytes), np.uint8), np.frombuffer(bytes(f_n.bytes), np.uint8)
        if a.shape != b.shape:
            bad(f"{fn}: {name} size {a.size} -> {b.size}")
            continue
        diff = a != b
        allowed = np.zeros(a.shape, bool)
        for off, size in patched_ranges.get(name, []):
            allowed[off:off + size] = True
        outside = int((diff & ~allowed).sum())
        P(f"  {name}: {a.size} B, changed {int(diff.sum())} B, outside patched ranges {outside} B")
        if outside:
            bad(f"{fn}: {name} changed outside the patched textures ({outside} B)")
    # 4. textures
    for name, o, n in pairs:
        t_o, t_n = o.read(), n.read()
        ann = np.asarray(Image.open(os.path.join(MAPOUT, name + ".png")).convert("RGBA"))
        w, h = int(t_n.m_Width), int(t_n.m_Height)
        if (w, h) != (int(t_o.m_Width), int(t_o.m_Height)) or ann.shape[:2] != (h, w):
            bad(f"{fn}/{name}: size {w}x{h} vs {t_o.m_Width}x{t_o.m_Height} / png {ann.shape[1]}x{ann.shape[0]}")
            continue
        mips = int(t_n.m_MipCount)
        if mips != int(t_o.m_MipCount):
            bad(f"{fn}/{name}: mip count {t_o.m_MipCount} -> {mips}")
        fmt = int(t_n.m_TextureFormat)
        if fmt not in (int(TF.DXT1), int(TF.DXT5)):
            bad(f"{fn}/{name}: format {fmt} is not plain DXT1/DXT5")
            continue
        bpb = 8 if fmt == int(TF.DXT1) else 16
        raw_n = bytes(t_n.get_image_data())
        raw_o = bytes(t_o.get_image_data())
        if int(t_o.m_TextureFormat) in (int(TF.DXT1Crunched), int(TF.DXT5Crunched)):
            raw_o = texture2ddecoder.unpack_unity_crunch(raw_o)
        tt = n.read_typetree()
        sd = tt.get("m_StreamData") or {}
        streamed_new = bool(sd.get("path")) and int(sd.get("size", 0)) > 0
        if len(raw_n) != len(raw_o):
            bad(f"{fn}/{name}: data length {len(raw_o)} -> {len(raw_n)}")
            continue
        dn = decode_mips(raw_n, w, h, mips, bpb)
        do = decode_mips(raw_o, w, h, mips, bpb)
        cur, old_k = ann, do[0]                   # annotated / original level-0 image, box-downsampled together (same as the encoder)
        worst_out, min_psnr, n_touch = 0, 99.0, 0
        for k in range(mips):
            if k > 0:
                if min(dn[k].shape[:2]) < 4:
                    break
                cur, old_k = MS.down(cur), MS.down(old_k)
            msk = touched_mask(old_k, cur)        # blocks the encoder re-encoded at this level
            out_diff = int((dn[k] != do[k]).any(axis=2)[~msk].sum())      # everything else must still be the ORIGINAL data
            ch = slice(0, 3) if bpb == 8 else slice(0, 4)
            ps = psnr(dn[k][msk][:, ch], cur[msk][:, ch]) if msk.any() else 99.0   # re-encoded blocks vs the annotated image
            min_psnr = min(min_psnr, ps)
            worst_out = max(worst_out, out_diff)
            if k == 0:
                n_touch = int(msk.sum() // 16)
                share = float(msk.mean())
        P(f"  {name}: {w}x{h} fmt {fmt} mips {mips} {'streamed' if streamed_new else 'inline'} | touched blocks {n_touch} ({100 * share:.2f}% of area) | "
          f"re-encoded blocks vs annotated: min PSNR {min_psnr:.1f} dB | px differing from base outside touched blocks: {worst_out}")
        if worst_out:
            bad(f"{fn}/{name}: {worst_out} px changed outside the annotated blocks")
        # 4x4-block DXT cannot reproduce hard text edges exactly: ~28-33 dB inside the re-encoded blocks is normal; < 26 would mean wrong data
        if min_psnr < 26:
            bad(f"{fn}/{name}: decoded texture differs from the annotated PNG (min PSNR {min_psnr:.1f} dB inside the re-encoded blocks)")
        if n_touch == 0:
            bad(f"{fn}/{name}: nothing changed")
        n_tex += 1
    P(f"{fn[:70]}: base={label}, {len(pairs)} texture(s) [{time.time() - t0:.0f}s]")
P()
P(f"textures checked: {n_tex}; problems: {len(problems)} [{time.time() - t_all:.0f}s]")
print(f"textures checked: {n_tex}; problems: {len(problems)}")
