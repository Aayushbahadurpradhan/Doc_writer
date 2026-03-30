import os
import re
import sys

func_name = sys.argv[1] if len(sys.argv) > 1 else "sendWebhookResponse"
search_root = sys.argv[2] if len(sys.argv) > 2 else r"D:\CloudTech_main\nuerabenefits\app"

def extract_body(content, func):
    pat = re.compile(r"\bfunction\s+" + re.escape(func) + r"\s*\(", re.IGNORECASE)
    m = pat.search(content)
    if not m:
        return ""
    n = len(content)
    pos = m.end() - 1
    paren_depth = 0
    while pos < n:
        c = content[pos]
        if c == "(":
            paren_depth += 1
        elif c == ")":
            paren_depth -= 1
            if paren_depth == 0:
                pos += 1
                break
        pos += 1
    window = content[pos : pos + 500]
    bi = window.find("{")
    if bi == -1:
        return ""
    si = window.find(";")
    if si != -1 and si < bi:
        return ""
    start = pos + bi + 1
    depth = 1
    pos2 = start
    while pos2 < n and depth > 0:
        if content[pos2] == "{":
            depth += 1
        elif content[pos2] == "}":
            depth -= 1
        pos2 += 1
    return content[start : pos2 - 1].strip()

for root, dirs, files in os.walk(search_root):
    dirs[:] = [d for d in dirs if d not in ("vendor", "node_modules")]
    for fn in files:
        if not fn.endswith(".php"):
            continue
        fp = os.path.join(root, fn)
        try:
            with open(fp, encoding="utf-8", errors="ignore") as f:
                c = f.read()
            if func_name.lower() in c.lower():
                print("Found in:", fp)
                body = extract_body(c, func_name)
                print(body[:800] if body else "-- body not extractable")
                print()
        except Exception:
            pass
