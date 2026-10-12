"""Read-only provenance check: how much of this repo's Chinese translation data equals or resembles the Chinese text
of the base patch (the old stable pack)?

    set SUZERAIN_BASE=<unpacked base patch folder>      (build.py fetch puts it in <work>\\base\\...)
    python tools/provenance_scan.py

Method
  1. Collect every Chinese line of the base patch: all MonoBehaviour / TextAsset strings of its 30 bundles, split at line
     breaks (about 115,000 distinct lines).
  2. Collect every Chinese line of data/tm/*.json, split the same way.
  3. For lines with >= 10 Chinese characters: exact match against (1); otherwise the best Jaccard similarity of 4-character
     shingles against the long lines of (1).  Lines with 2-9 Chinese characters (names, titles, short UI terms) are only
     counted for exact matches - short strings coincide by nature.
This is a measurement, not a legal test: a high similarity says "look at this line", a low one says the wording is independent.
"""
import glob, json, os, re, sys, time
from collections import Counter, defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
from lib_su import AA_OLD, load_env  # noqa: E402  (needs SUZERAIN_BASE; SUZERAIN_GAME is not used here)

CJK = re.compile(r"[\u4e00-\u9fff]")
LONG, G = 10, 4


def cjk_n(s):
    return len(CJK.findall(s))


def strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from strings(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from strings(v)


def lines(s):
    for p in re.split(r"[\r\n]+", s):
        p = p.strip()
        if CJK.search(p):
            yield p


def grams(s):
    s = re.sub(r"\s+", "", s)
    return {s[i:i + G] for i in range(max(1, len(s) - G + 1))}


def load_old():
    old, nb = set(), 0
    for f in sorted(glob.glob(os.path.join(AA_OLD, "*.bundle"))):
        env = load_env(f)
        nb += 1
        for obj in env.objects:
            try:
                if obj.type.name == "MonoBehaviour":
                    for s in strings(obj.read_typetree()):
                        old.update(lines(s))
                elif obj.type.name == "TextAsset":
                    d = obj.read()
                    s = d.m_Script if isinstance(d.m_Script, str) else bytes(d.m_Script).decode("utf-8", "ignore")
                    old.update(lines(s))
            except Exception:  # noqa: BLE001  (objects without a readable payload are irrelevant here)
                pass
    return old, nb


def main():
    t0 = time.time()
    old, nb = load_old()
    old_long = sorted(p for p in old if cjk_n(p) >= LONG)
    og, idx = [], defaultdict(list)
    for i, p in enumerate(old_long):
        g = grams(p)
        og.append(g)
        for x in g:
            idx[x].append(i)
    print("base patch: %d bundles, %d distinct Chinese lines (%d long)" % (nb, len(old), len(old_long)))

    def best(p):
        # Jaccard = n / (|A| + |B| - n) <= n / |A|, so a line can only reach 0.6 when it shares n >= 0.6*|A| shingles:
        # every candidate with n >= 0.5*|A| is scored exactly (a superset), which makes the result independent of any ordering.
        g, c = grams(p), Counter()
        for x in g:
            for i in idx.get(x, ()):
                c[i] += 1
        return max((n / (len(g) + len(og[i]) - n) for i, n in c.items() if 2 * n >= len(g)), default=0.0)

    tot, near, exact_long = Counter(), [], []
    print("\n%-36s %5s %6s %6s %7s %6s %6s | short exact / short" % ("file", "long", "exact", ">=.95", ".8-.95", ".6-.8", "<.6"))
    for f in sorted(glob.glob(os.path.join(REPO, "data", "tm", "*.json"))):
        with open(f, encoding="utf-8") as fh:
            o = json.load(fh)
        seen = {p for s in strings(o) for p in lines(s)}
        longp = sorted(p for p in seen if cjk_n(p) >= LONG)
        shortp = [p for p in seen if 2 <= cjk_n(p) < LONG]
        h = Counter()
        for p in longp:
            if p in old:
                h["exact"] += 1
                exact_long.append((os.path.basename(f), p))
                continue
            s = best(p)
            h["a" if s >= .95 else "b" if s >= .8 else "c" if s >= .6 else "d"] += 1
            if s >= .6:
                near.append((s, os.path.basename(f), p))
        sx = sum(1 for p in shortp if p in old)
        print("%-36s %5d %6d %6d %7d %6d %6d | %d / %d" % (os.path.basename(f), len(longp), h["exact"], h["a"], h["b"], h["c"], h["d"], sx, len(shortp)))
        for k, v in (("long", len(longp)), ("exact", h["exact"]), ("a", h["a"]), ("b", h["b"]), ("c", h["c"]), ("d", h["d"]), ("sx", sx), ("st", len(shortp))):
            tot[k] += v
    print("%-36s %5d %6d %6d %7d %6d %6d | %d / %d" % ("TOTAL", tot["long"], tot["exact"], tot["a"], tot["b"], tot["c"], tot["d"], tot["sx"], tot["st"]))
    print("share of long lines with similarity < 0.6: %.1f%%" % (100.0 * tot["d"] / max(1, tot["long"])))
    print("\nlong lines that equal a base-patch line exactly (%d):" % len(exact_long))
    for fn, p in exact_long:
        print("  %-22s %s" % (fn, p[:70]))
    print("\nlong lines with similarity >= 0.6 (%d):" % len(near))
    for s, fn, p in sorted(near, reverse=True):
        print("  %.2f  %-30s %s" % (s, fn, p[:60]))
    print("\ndone in %.0f s" % (time.time() - t0))


if __name__ == "__main__":
    main()
