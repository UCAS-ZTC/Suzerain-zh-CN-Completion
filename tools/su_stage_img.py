"""Stage: repainted war-tutorial screenshots (Chinese labels) -> replacement texture bundles.

For every image configured in tut_repaint.LABELS:
  pristine game bundle (Texture2D + Sprite + AssetBundle)  --UnityPy-->  same bundle, Texture2D replaced by the repainted image.

The original texture is Crunch-compressed DXT1 and no Crunch encoder is available, so the new one is stored as plain DXT1.
To keep the rest of the picture exactly as shipped, the original Crunch stream is unpacked to its DXT1 blocks and every
4x4 block that the repaint did not touch keeps its ORIGINAL block bytes; only the blocks that contain repainted pixels are
re-encoded (etcpak BC1).  Result: outside the labels the decoded picture is bit-identical to the original.
"""
import os, time
import numpy as np
from PIL import Image
import UnityPy
import texture2ddecoder
import etcpak
from UnityPy.enums import TextureFormat as TF
from UnityPy.export import Texture2DConverter as T2C
from lib_su import *
import tut_repaint

PREFIX = "tutorial_assets_assets_addressableassets_tutorial_{name}.png_"
BYTES_PER_BLOCK = {int(TF.DXT1): 8, int(TF.DXT1Crunched): 8, int(TF.DXT5): 16, int(TF.DXT5Crunched): 16}


def game_bundle(name):
    return find_bundle(PREFIX.format(name=name), AA_GAME)


def psnr(a, b):
    mse = np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2)
    return 99.0 if mse == 0 else 10 * np.log10(255.0 ** 2 / mse)


def unpack_blocks(tex):
    """original texture data as plain DXT blocks, in the texture's native (bottom-up) row order"""
    raw = bytes(tex.get_image_data())
    fmt = int(tex.m_TextureFormat)
    if fmt in (int(TF.DXT1Crunched), int(TF.DXT5Crunched)):
        raw = texture2ddecoder.unpack_unity_crunch(raw)
    return raw


def encode_preserving(tex, new_rgb):
    """plain-DXT data of new_rgb (top-down HxWx3 uint8); untouched 4x4 blocks keep the original block bytes"""
    w, h = int(tex.m_Width), int(tex.m_Height)
    assert w % 4 == 0 and h % 4 == 0
    fmt = int(tex.m_TextureFormat)
    bpb = BYTES_PER_BLOCK[fmt]
    plain_fmt = TF.DXT1 if bpb == 8 else TF.DXT5
    orig_blocks = unpack_blocks(tex)
    assert len(orig_blocks) == w * h // 16 * bpb, (len(orig_blocks), w, h, bpb)
    # native orientation = vertically flipped relative to the PNG
    orig_native = np.asarray(tex.image.convert("RGB").transpose(Image.Transpose.FLIP_TOP_BOTTOM))
    new_native = np.ascontiguousarray(new_rgb[::-1])
    changed_px = (orig_native != new_native).any(axis=2)
    changed = changed_px.reshape(h // 4, 4, w // 4, 4).any(axis=(1, 3))
    rgba = np.dstack([new_native, np.full((h, w), 255, np.uint8)])
    if bpb == 8:
        enc = etcpak.compress_bc1(rgba.tobytes(), w, h)
    else:
        enc = etcpak.compress_bc3(rgba.tobytes(), w, h)
    out = np.frombuffer(orig_blocks, dtype=np.uint8).reshape(h // 4, w // 4, bpb).copy()
    new = np.frombuffer(enc, dtype=np.uint8).reshape(h // 4, w // 4, bpb)
    out[changed] = new[changed]
    return out.tobytes(), plain_fmt, int(changed.sum()), changed.size


def build_one(name, out_dir, log):
    src = game_bundle(name)
    env = load_env(src)
    img = np.asarray(Image.open(os.path.join(tut_repaint.NEW, name + ".png")).convert("RGB"))
    n_tex = 0
    for o in env.objects:
        if o.type.name != "Texture2D":
            continue
        tex = o.read()
        assert img.shape[:2] == (tex.m_Height, tex.m_Width), (name, img.shape, tex.m_Width, tex.m_Height)
        data, plain_fmt, n_changed, n_blocks = encode_preserving(tex, img)
        tex.image_data = data
        tex.m_CompleteImageSize = len(data)
        tex.m_TextureFormat = plain_fmt
        tex.m_StreamData.path = ""
        tex.m_StreamData.offset = 0
        tex.m_StreamData.size = 0
        tex.save()
        n_tex += 1
    assert n_tex == 1, (name, n_tex)
    dst = os.path.join(out_dir, AA_REL, os.path.basename(src))
    size = save_bundle(env, dst)
    log(f"  {name}: {os.path.getsize(src)} -> {size} bytes; re-encoded {n_changed}/{n_blocks} DXT blocks")
    return dst


def build(out_dir, log):
    os.makedirs(lp(os.path.join(out_dir, AA_REL)), exist_ok=True)
    t0 = time.time()
    outs = []
    for name in tut_repaint.LABELS:
        outs.append(build_one(name, out_dir, log))
    log(f"stage img: {len(outs)} texture bundles written [{time.time() - t0:.0f}s]")
    return outs
