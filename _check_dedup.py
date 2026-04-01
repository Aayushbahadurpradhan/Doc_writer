"""Check dedup safety - verify duplicate sections have same endpoint."""
import os
import re

base = r'd:\CloudTech_main\Doc_writer\doc_output\nuerabenefits\docs\backend'

BACKTICK = '`'

def extract_endpoint(s):
    pattern = r'\*\*Endpoint\*\*\s*\|\s*' + BACKTICK + r'([^' + BACKTICK + r']+)' + BACKTICK
    m = re.search(pattern, s)
    return m.group(1).strip() if m else ''

PLACEHOLDER_PATTERNS = [
    r'_Run with AI enabled',
    r'\[SERVICE_CALL\]',
    r'\[DB_QUERY\] \?',
    r'\[QUERY_BUILDER\].*UNKNOWN',
]

def is_placeholder_section(section):
    for p in PLACEHOLDER_PATTERNS:
        if re.search(p, section):
            return True
    return False


for domain in sorted(os.listdir(base)):
    fpath = os.path.join(base, domain, 'business.md')
    if not os.path.isfile(fpath):
        continue
    with open(fpath, encoding='utf-8') as f:
        content = f.read()
    parts = re.split(r'(?m)(?=^## )', content)
    sections = [p for p in parts if p.startswith('## ')]

    by_title = {}
    for s in sections:
        t = s.split('\n')[0].strip()
        ep = extract_endpoint(s)
        is_ph = is_placeholder_section(s)
        by_title.setdefault(t, []).append((ep, is_ph, s))

    for t, versions in by_title.items():
        if len(versions) < 2:
            continue
        # Check if any duplicates have DIFFERENT endpoints
        eps = set(ep for ep, _, _ in versions)
        if len(eps) > 1:
            print(f'  DIFFERENT-ENDPOINT DUPS: {domain}/{t}')
            for ep, is_ph, _ in versions:
                print(f'    endpoint={ep}  placeholder={is_ph}')
        # Also check if all duplicates are skeletons (no good version)
        good = [(ep, s) for ep, is_ph, s in versions if not is_ph]
        bad = [(ep, s) for ep, is_ph, s in versions if is_ph]
        if bad and not good:
            print(f'  SKELETON-ONLY DUP: {domain}/{t}  ({len(bad)} copies, all placeholders)')
            for ep, _ in bad:
                print(f'    endpoint={ep}')
