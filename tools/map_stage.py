"""Stage: annotated map textures -> replacement bundles.

For every bundle that holds a configured map texture:
  base bundle  = the Plus main pack's copy if the Plus pack already patches this file, otherwise the pristine game file
  Texture2D(name) replaced by the annotated image, all other objects untouched.
Encoding keeps the shipped DXT data wherever the annotation did not touch a 4x4 block (block-preserving), and handles
DXT1 / DXT5 (alpha-aware) / Crunched originals and mip chains.
"""
import os
import json
import time
import numpy as np
from PIL import Image
import texture2ddecoder
import etcpak
from UnityPy.enums import TextureFormat as TF
from lib_su import *

PLUS_DIR = os.path.join(ROOT, "Suzerain_CN_Plus_SteamWin_2026-10-10")
BPB = {int(TF.DXT1): 8, int(TF.DXT1Crunched): 8, int(TF.DXT5): 16, int(TF.DXT5Crunched): 16}
CRUNCHED = (int(TF.DXT1Crunched), int(TF.DXT5Crunched))


def load_manifest(pack_dir):
    return json.load(open(os.path.join(pack_dir, "patch_manifest.json"), encoding="utf-8-sig"))


_PLUS = None


def plus_entry(file_name):
    """manifest entry of the Plus pack for this bundle file name, or None"""
    global _PLUS
    if _PLUS is None:
        _PLUS = {f["file_name"]: f for f in load_manifest(PLUS_DIR)["files"]}
    return _PLUS.get(file_name)


def tex_index():
    rows = json.load(open(os.path.join(MAPLAB_DIR, "tex_locator.json"), encoding="utf-8"))
    idx = {}
    for r in rows:
        if r["t"] == "Texture2D":
            idx.setdefault(r["n"], [])
            if r["f"] not in idx[r["n"]]:
                idx[r["n"]].append(r["f"])
    return idx


def base_path(file_name):
    """(path of the bundle to start from, original_sha256 the installer must find in the game dir, source label)"""
    pe = plus_entry(file_name)
    if pe is not None:
        p = os.path.join(PLUS_DIR, pe["relative_path"])
        return p, pe["patched_sha256"], "plus"
    p = os.path.join(AA_GAME, file_name)
    return p, sha256_file(p), "pristine"


def down(img):
    h, w = img.shape[:2]
    a = img.astype(np.float32).reshape(h // 2, 2, w // 2, 2, 4).mean(axis=(1, 3))
    return np.clip(a + 0.5, 0, 255).astype(np.uint8)


def compress(rgba, bpb):
    h, w = rgba.shape[:2]
    data = np.ascontiguousarray(rgba).tobytes()
    return etcpak.compress_bc1(data, w, h) if bpb == 8 else etcpak.compress_bc3(data, w, h)


def encode_map(tex, new_rgba):
    """plain-DXT data (all mip levels) of new_rgba (top-down HxWx4 uint8); untouched 4x4 blocks keep the original bytes.
    returns (data, plain_format, changed_blocks_total, blocks_total)"""
    w, h = int(tex.m_Width), int(tex.m_Height)
    fmt = int(tex.m_TextureFormat)
    bpb = BPB[fmt]
    plain = TF.DXT1 if bpb == 8 else TF.DXT5
    mips = max(1, int(tex.m_MipCount))
    raw = bytes(tex.get_image_data())
    if fmt in CRUNCHED:
        raw = texture2ddecoder.unpack_unity_crunch(raw)
    dims = [(max(1, w >> k), max(1, h >> k)) for k in range(mips)]
    sizes = [((wk + 3) // 4) * ((hk + 3) // 4) * bpb for wk, hk in dims]
    assert len(raw) == sum(sizes), (tex.m_Name, len(raw), sum(sizes), mips)
    old = np.ascontiguousarray(np.asarray(tex.image.convert("RGBA").transpose(Image.Transpose.FLIP_TOP_BOTTOM)))
    new = np.ascontiguousarray(new_rgba[::-1])
    assert old.shape == new.shape, (old.shape, new.shape)
    out, off = [], 0
    n_changed = n_total = 0
    for k in range(mips):
        wk, hk = dims[k]
        blob = raw[off:off + sizes[k]]
        off += sizes[k]
        if k > 0:
            if min(wk, hk) < 4 or old.shape[0] % 2 or old.shape[1] % 2:
                out.append(blob)
                continue
            old, new = down(old), down(new)
        if min(wk, hk) < 4:
            out.append(blob)
            continue
        blocks = np.frombuffer(blob, np.uint8).reshape(hk // 4, wk // 4, bpb).copy()
        changed = (old != new).any(axis=2).reshape(hk // 4, 4, wk // 4, 4).any(axis=(1, 3))
        if changed.any():
            enc = np.frombuffer(compress(new, bpb), np.uint8).reshape(hk // 4, wk // 4, bpb)
            blocks[changed] = enc[changed]
        out.append(blocks.tobytes())
        n_changed += int(changed.sum())
        n_total += changed.size
    return b"".join(out), plain, n_changed, n_total


def set_texture(tex, data, plain):
    """store the texture data inline in the serialized file (no .resS reference)"""
    tex.image_data = data
    tex.m_CompleteImageSize = len(data)
    tex.m_TextureFormat = plain
    tex.m_StreamData.path = ""
    tex.m_StreamData.offset = 0
    tex.m_StreamData.size = 0
    tex.save()


def build_bundle(file_name, images, out_dir, log):
    """images: {texture name: annotated PNG path}.  returns dict(file, base_label, original_sha256, textures:[...])

    Streamed textures (data lives in the bundle's .resS) whose new data has exactly the old size are patched IN PLACE in the
    .resS: the serialized file stays byte-identical and the bundle keeps its size.  Anything else (crunched originals, size change)
    is stored inline and the old .resS region is zero-filled (so it compresses to nothing)."""
    from UnityPy.streams.EndianBinaryReader import EndianBinaryReader_Memoryview as RM
    src, orig_sha, label = base_path(file_name)
    t0 = time.time()
    env = load_env(src)
    bf = env.file
    res_buf, res_old = {}, {}
    done = []

    def res_of(sd):
        name = sd.path.split("/")[-1]
        if name not in res_buf:
            res_old[name] = bf.files[name]
            res_buf[name] = bytearray(res_old[name].bytes)
        return res_buf[name]

    for o in env.objects:
        if o.type.name != "Texture2D":
            continue
        tex = o.read()
        if tex.m_Name not in images:
            continue
        new = np.asarray(Image.open(images[tex.m_Name]).convert("RGBA"))
        old_fmt = int(tex.m_TextureFormat)
        sd = tex.m_StreamData
        streamed = bool(sd.path) and int(sd.size) > 0
        data, plain, nc, nt = encode_map(tex, new)
        if streamed and len(data) == int(sd.size) and int(plain) == old_fmt:
            buf = res_of(sd)
            buf[int(sd.offset):int(sd.offset) + int(sd.size)] = data
            mode = "in-place"
        else:
            if streamed:
                buf = res_of(sd)
                buf[int(sd.offset):int(sd.offset) + int(sd.size)] = bytes(int(sd.size))
            set_texture(tex, data, plain)
            mode = "inline"
        done.append((tex.m_Name, nc, nt, mode))
    missing = set(images) - {d[0] for d in done}
    assert not missing, (file_name, missing)
    for name, buf in res_buf.items():
        old = res_old[name]
        newr = RM(bytes(buf))
        for attr in ("flags", "name", "path"):
            if hasattr(old, attr):
                try:
                    setattr(newr, attr, getattr(old, attr))
                except Exception:
                    pass
        bf.files[name] = newr
    dst = os.path.join(out_dir, AA_REL, file_name)
    os.makedirs(lp(os.path.dirname(dst)), exist_ok=True)
    size = save_bundle(env, dst)
    log(f"  {file_name[:60]}: base={label}, {os.path.getsize(lp(src))} -> {size} bytes; "
        + ", ".join(f"{n}: {c}/{t} blocks {m}" for n, c, t, m in done) + f" [{time.time() - t0:.0f}s]")
    return dict(file=file_name, base=label, original_sha256=orig_sha, textures=[d[0] for d in done])
