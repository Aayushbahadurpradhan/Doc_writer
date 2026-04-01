"""
_apply_stubs.py
Patches business.md files with the hand-written stub sections.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from _stub_sections import STUBS

DOCS_BASE = os.path.join(ROOT, "doc_output", "nuerabenefits", "docs", "backend")
BACKTICK  = chr(96)

STUB_MARKERS = [
    r"_Run with AI enabled",
    r"\[SERVICE_CALL\]",
    r"\[DB_QUERY\] \?",
    r"\[QUERY_BUILDER\].*UNKNOWN",
    r"Delegates core data operations to",
    r"Run with AI enabled to extract",
]

def is_stub_section(section: str) -> bool:
    return any(re.search(p, section) for p in STUB_MARKERS)


def extract_endpoint_from_section(s: str) -> str:
    pat = BACKTICK + r"([^" + BACKTICK + r"]+)" + BACKTICK
    m = re.search(pat, s)
    return m.group(1).strip() if m else ""


def split_sections(content: str):
    parts = re.split(r"(?m)(?=^## )", content)
    header   = parts[0] if not parts[0].startswith("## ") else ""
    sections = [p for p in parts if p.startswith("## ")]
    return header, sections


def apply_stubs(dry_run: bool = False):
    applied = 0
    skipped = 0

    for domain, endpoint_key, new_section in STUBS:
        biz_path = os.path.join(DOCS_BASE, domain, "business.md")
        if not os.path.isfile(biz_path):
            print(f"  [MISS]   {domain}/business.md not found — skipping {endpoint_key}")
            skipped += 1
            continue

        with open(biz_path, encoding="utf-8") as f:
            content = f.read()

        header, sections = split_sections(content)

        # Find the section whose endpoint == endpoint_key AND is a stub
        target_idx = None
        for i, s in enumerate(sections):
            ep = extract_endpoint_from_section(s)
            if ep == endpoint_key and is_stub_section(s):
                target_idx = i
                break

        if target_idx is None:
            # Check if already patched (endpoint exists but not a stub)
            for s in sections:
                ep = extract_endpoint_from_section(s)
                if ep == endpoint_key and not is_stub_section(s):
                    print(f"  [SKIP]   {domain} | {endpoint_key} — already patched")
                    skipped += 1
                    break
            else:
                print(f"  [WARN]   {domain} | {endpoint_key} — section not found")
                skipped += 1
            continue

        replacement = new_section.strip() + "\n\n"
        sections[target_idx] = replacement

        new_content = header + "".join(sections)

        if not dry_run:
            with open(biz_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"  [OK]     {domain} | {endpoint_key}")
        else:
            print(f"  [DRY]    {domain} | {endpoint_key}")

        applied += 1

    print(f"\nApplied: {applied}  |  Skipped/Not found: {skipped}")
    return applied


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    apply_stubs(dry_run=args.dry_run)
