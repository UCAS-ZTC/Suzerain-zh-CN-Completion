"""Minimal Lua-ish literal scanner for Pixel Crushers dialogue scripts and the entity-JSON instruction DSL.

scan(code) -> list of literal dicts:
  start,end   : span of the literal CONTENT (between the quotes) in `code`
  quote       : quote char
  val         : decoded string value
  fn,arg      : innermost enclosing call name and argument index (or None)
  assign      : variable name if literal is the ENTIRE RHS of an assignment  (Variable["X"] = "..."  or  X.Y = "...")
  cmp         : variable name if literal is the right operand of  ==, ~=, !=  against a variable
  idx         : True if literal is directly inside [...] (an index/key such as Variable["X"]), never display text
"""
import re

ESC = {"n": "\n", "r": "\r", "t": "\t", "\\": "\\", '"': '"', "'": "'", "0": "\0"}
ASSIGN_VAR = re.compile(r"""^\s*Variable\s*\[\s*(["'])([^"']+)\1\s*\]\s*=\s*$""")
ASSIGN_DIRECT = re.compile(r"""^\s*([A-Za-z_][A-Za-z0-9_\.]*)\s*=\s*$""")
CMP_VAR = re.compile(r"""[\s(]*Variable\s*\[\s*(["'])([^"']+)\1\s*\]\s*(?:==|~=|!=)\s*$""")
CMP_DIRECT = re.compile(r"""[\s(]*([A-Za-z_][A-Za-z0-9_\.]*)\s*(?:==|~=|!=)\s*$""")


def decode(raw):
    out = []
    i = 0
    while i < len(raw):
        c = raw[i]
        if c == "\\" and i + 1 < len(raw):
            n = raw[i + 1]
            out.append(ESC.get(n, "\\" + n))
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def encode(val, quote):
    s = val.replace("\\", "\\\\").replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
    s = s.replace(quote, "\\" + quote)
    return s


def scan(code):
    res = []
    n = len(code)
    i = 0
    stack = []          # frames: [fn, argidx, kind]  kind '(' or '['
    stmt_start = 0
    last_ident = None
    last_ident_end = -1
    while i < n:
        c = code[i]
        if c == "-" and code.startswith("--", i):
            if code.startswith("--[[", i):
                j = code.find("]]", i + 4)
                i = n if j < 0 else j + 2
            else:
                j = code.find("\n", i)
                i = n if j < 0 else j
            continue
        if c in "\"'":
            q = c
            j = i + 1
            while j < n:
                if code[j] == "\\":
                    j += 2
                    continue
                if code[j] == q:
                    break
                j += 1
            raw = code[i + 1:j]
            head = code[stmt_start:i]
            assign = None
            cmpv = None
            if not stack:
                m = ASSIGN_VAR.match(head)
                if m:
                    assign = m.group(2)
                else:
                    m = ASSIGN_DIRECT.match(head)
                    if m:
                        assign = m.group(1)
            m = CMP_VAR.match(code[stmt_start:i]) or CMP_DIRECT.match(code[max(stmt_start, 0):i]) if not assign else None
            if m:
                cmpv = m.group(2) if m.re is CMP_VAR else m.group(1)
            fn = arg = None
            for fr in reversed(stack):
                if fr[2] == "(":
                    fn, arg = fr[0], fr[1]
                    break
            idx = bool(stack) and stack[-1][2] == "["
            res.append(dict(start=i + 1, end=j, quote=q, raw=raw, val=decode(raw), fn=fn, arg=arg, assign=assign, cmp=cmpv, idx=idx))
            i = j + 1
            continue
        if c.isalpha() or c == "_":
            j = i + 1
            while j < n and (code[j].isalnum() or code[j] in "_."):
                j += 1
            last_ident = code[i:j]
            last_ident_end = j
            i = j
            continue
        if c == "(":
            fn = last_ident if (last_ident and code[last_ident_end:i].strip() == "") else None
            stack.append([fn, 0, "("])
        elif c == "[":
            stack.append([None, 0, "["])
        elif c in ")]":
            if stack:
                stack.pop()
        elif c == ",":
            if stack:
                stack[-1][1] += 1
        elif c in ";\n" and not stack:
            stmt_start = i + 1
        i += 1
    return res


def replace_literals(code, repl):
    """repl: dict {(start,end): new_value}  -> new code string (new_value is a DECODED string; re-encoded with the original quote)."""
    out = []
    pos = 0
    lits = {(l["start"], l["end"]): l for l in scan(code)}
    for (s, e), newval in sorted(repl.items()):
        l = lits[(s, e)]
        out.append(code[pos:s])
        out.append(encode(newval, l["quote"]))
        pos = e
    out.append(code[pos:])
    return "".join(out)


if __name__ == "__main__":
    t = ('Variable["RiziaDLCText.X"]="He said \\"hi\\"" ; UpdateCharacterTitle("Gloria Tory", \'Vice President\'); '
         'Variable["A"]=Concat(Variable["B"], " and Vina");\nRiziaDLCText.RoyalJet = "The Princess Lena";\n'
         '(Variable["RiziaDLCText.SaltanaToPlayer"] =="Your Majesty") == false\nSomeVar.Name == \'zzz\'')
    for l in scan(t):
        print(repr(l["val"]), "| fn", l["fn"], "arg", l["arg"], "| assign", l["assign"], "| cmp", l["cmp"], "| idx", l["idx"])
    print("roundtrip:", replace_literals(t, {(l["start"], l["end"]): l["val"] for l in scan(t)}) == t)
