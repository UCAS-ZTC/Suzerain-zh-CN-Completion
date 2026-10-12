"""Byte-faithful JSON string-literal scanner / splicer.

The entity text assets store JSON as one big string field.  Re-serialising it with
json.dumps would change whitespace / newline style / escape style of *untouched* data,
so edits are applied by replacing the exact character span of the string literal.

scan_strings(text) -> [(path, start, end, value)]
    path  : tuple of dict keys (str) / list indices (int); for dict *values* only (keys are not listed)
    start : index of opening quote, end : index just after closing quote  (text[start:end] is the raw literal)
encode_literal(value, escape_nonascii) -> raw JSON string literal
splice(text, {(start, end): raw_literal}) -> new text
"""
import re
from json.decoder import scanstring

_WS = " \t\r\n"
_NUM = re.compile(r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?")


def scan_strings(text):
    out = []
    n = len(text)

    def skip(i):
        while i < n and text[i] in _WS:
            i += 1
        return i

    def value(i, path):
        c = text[i]
        if c == '"':
            val, end = scanstring(text, i + 1, False)
            out.append((path, i, end, val))
            return end
        if c == "{":
            i = skip(i + 1)
            if text[i] == "}":
                return i + 1
            while True:
                if text[i] != '"':
                    raise ValueError(f"expected key at {i}: {text[i:i+30]!r}")
                key, kend = scanstring(text, i + 1, False)
                i = skip(kend)
                if text[i] != ":":
                    raise ValueError(f"expected ':' at {i}")
                i = skip(i + 1)
                i = value(i, path + (key,))
                i = skip(i)
                if text[i] == ",":
                    i = skip(i + 1)
                    continue
                if text[i] == "}":
                    return i + 1
                raise ValueError(f"expected ',' or '}}' at {i}: {text[i:i+30]!r}")
        if c == "[":
            i = skip(i + 1)
            if text[i] == "]":
                return i + 1
            idx = 0
            while True:
                i = value(i, path + (idx,))
                idx += 1
                i = skip(i)
                if text[i] == ",":
                    i = skip(i + 1)
                    continue
                if text[i] == "]":
                    return i + 1
                raise ValueError(f"expected ',' or ']' at {i}: {text[i:i+30]!r}")
        for lit in ("true", "false", "null"):
            if text.startswith(lit, i):
                return i + len(lit)
        m = _NUM.match(text, i)
        if not m:
            raise ValueError(f"bad token at {i}: {text[i:i+30]!r}")
        return m.end()

    i = skip(0)
    end = value(i, ())
    if skip(end) != n:
        raise ValueError(f"trailing data at {end}")
    return out


_ESC = {'"': '\\"', "\\": "\\\\", "\n": "\\n", "\r": "\\r", "\t": "\\t", "\b": "\\b", "\f": "\\f"}


def encode_literal(value, escape_nonascii=False):
    parts = ['"']
    for ch in value:
        e = _ESC.get(ch)
        if e is not None:
            parts.append(e)
        elif ord(ch) < 0x20:
            parts.append("\\u%04x" % ord(ch))
        elif escape_nonascii and ord(ch) > 0x7E:
            o = ord(ch)
            if o > 0xFFFF:
                o -= 0x10000
                parts.append("\\u%04x\\u%04x" % (0xD800 + (o >> 10), 0xDC00 + (o & 0x3FF)))
            else:
                parts.append("\\u%04x" % o)
        else:
            parts.append(ch)
    parts.append('"')
    return "".join(parts)


def detect_escape_style(text):
    """True if the document escapes non-ASCII characters as \\uXXXX (and has no raw non-ASCII)."""
    has_raw = any(ord(c) > 0x7E for c in text)
    has_u = re.search(r"\\u[0-9a-fA-F]{4}", text) is not None
    return has_u and not has_raw


def splice(text, edits):
    """edits: {(start, end): replacement_raw}; spans must not overlap."""
    if not edits:
        return text
    items = sorted(edits.items())
    out = []
    pos = 0
    for (s, e), rep in items:
        if s < pos:
            raise ValueError("overlapping edits")
        out.append(text[pos:s])
        out.append(rep)
        pos = e
    out.append(text[pos:])
    return "".join(out)
