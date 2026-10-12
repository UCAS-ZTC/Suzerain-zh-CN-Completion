"""Size-preserving rewrite of IL2CPP string literals in global-metadata.dat (v39, see meta_lib.py for the layout).

Design (everything except the literal bytes stays byte-identical):
  * the file keeps its exact size, the 380-byte header, every section offset / size / count and everything after the literal data blob;
  * the literal COUNT and ORDER never change (compiled code addresses literals by index);
  * each translated literal is replaced by its Chinese UTF-8 bytes;
  * the bytes saved by shorter literals (delta >= 0) are absorbed by appending trailing ASCII spaces to ONE inert library message
    (SINK_TEXT, a Unity.Collections exception message that sits right after the last translated literal), so the blob keeps its
    original size and IL2CPP's section-contiguity assumptions (blob end == start of the next section) still hold;
  * the offset table is rebuilt cumulatively: offs[0] = 0, offs[i+1] = offs[i] + len(literal i), offs[N] = blob size.
"""
import re, struct, collections
import meta_lib

PH = re.compile(r"\{\d+\}")
TAG = re.compile(r"<[^<>]*>")
CJKRX = re.compile(r"[\u4e00-\u9fff]")

SINK_TEXT = "{0} used in NativeArray<{1}> must be unmanaged (contain no managed types)."


def check_pair(en, zh):
    """problems with a (english, chinese) pair; [] when the Chinese keeps every placeholder / tag / line break"""
    p = []
    if collections.Counter(PH.findall(en)) != collections.Counter(PH.findall(zh)):
        p.append("placeholders differ")
    if collections.Counter(TAG.findall(en)) != collections.Counter(TAG.findall(zh)):
        p.append("rich-text tags differ")
    for ch, nm in (("\r", "CR"), ("\n", "LF")):
        if en.count(ch) != zh.count(ch):
            p.append(f"{nm} count differs")
    if en.startswith(("\r", "\n")) != zh.startswith(("\r", "\n")):
        p.append("leading line break differs")
    if en.endswith(("\r", "\n")) != zh.endswith(("\r", "\n")):
        p.append("trailing line break differs")
    if CJKRX.search(en):
        p.append("english side contains CJK")
    if not CJKRX.search(zh):
        p.append("chinese side has no CJK character")
    if en == zh:
        p.append("unchanged")
    return p


def apply(b, pairs, sink_text=SINK_TEXT):
    """b = original file bytes, pairs = [(group, english, chinese)].  Returns (new_bytes, info)."""
    m = meta_lib.Meta(b)
    lits = list(m.lits)
    where = collections.defaultdict(list)
    for i, l in enumerate(lits):
        where[l].append(i)
    problems = []
    seen = set()
    changes = []                                   # (index, group, english, chinese)
    for g, en, zh in pairs:
        if en in seen:
            problems.append(f"duplicate pair: {en!r}")
            continue
        seen.add(en)
        for pr in check_pair(en, zh):
            problems.append(f"{pr}: {en!r}")
        ids = where.get(en.encode("utf-8"), [])
        if len(ids) != 1:
            problems.append(f"english literal found {len(ids)} times (need exactly 1): {en!r}")
            continue
        changes.append((ids[0], g, en, zh))
    sink_ids = where.get(sink_text.encode("utf-8"), [])
    if len(sink_ids) != 1:
        problems.append(f"sink literal found {len(sink_ids)} times: {sink_text!r}")
    if problems:
        raise ValueError("pair problems:\n  " + "\n  ".join(problems))
    sink = sink_ids[0]
    changes.sort()
    idx_changed = [c[0] for c in changes]
    if sink in idx_changed:
        raise ValueError("sink literal is itself translated")
    if sink < max(idx_changed):
        raise ValueError(f"sink {sink} lies before the last translated literal {max(idx_changed)}")
    new = list(lits)
    for i, g, en, zh in changes:
        new[i] = zh.encode("utf-8")
    delta = sum(len(lits[i]) - len(new[i]) for i, *_ in changes)
    if delta < 0:
        raise ValueError(f"Chinese is {-delta} bytes longer in total than the English; nothing to absorb it (drop strings)")
    new[sink] = lits[sink] + b" " * delta
    blob = b"".join(new)
    assert len(blob) == m.data_size, (len(blob), m.data_size)
    offs = [0]
    for l in new:
        offs.append(offs[-1] + len(l))
    assert offs[-1] == m.data_size
    tab = struct.pack("<%dI" % len(offs), *offs)
    assert len(tab) == m.trip[0][1]
    out = b[:m.off_tab] + tab + blob + b[m.data_off + m.data_size:]
    assert len(out) == len(b)
    info = {"changes": changes, "delta": delta, "sink": sink, "sink_text": sink_text, "n_lit": m.n_lit,
            "first": min(idx_changed), "last": max(idx_changed),
            "offsets_changed": sum(1 for a, c in zip(m.offs, offs) if a != c)}
    return out, info
