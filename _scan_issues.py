"""
Scan all nuerabenefits backend docs for unresolved placeholders and issues.
"""
import os
import re
from collections import defaultdict

base = r'd:\CloudTech_main\Doc_writer\doc_output\nuerabenefits\docs\backend'

# ---- Collect SERVICE_CALL issues ----
service_call_issues = []
run_ai_issues = []
db_query_issues = []
qb_unknown_issues = []

for root, dirs, files in os.walk(base):
    for fname in files:
        if not fname.endswith('.md'):
            continue
        domain = os.path.basename(root)
        fpath = os.path.join(root, fname)
        with open(fpath, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        current_endpoint = 'unknown'
        for i, line in enumerate(lines):
            m = re.match(r'^## (.+)', line.strip())
            if m:
                current_endpoint = m.group(1).strip()

            if '[SERVICE_CALL]' in line:
                svc = re.sub(r'.*\[SERVICE_CALL\]\s*', '', line).strip()
                service_call_issues.append((domain, fname, current_endpoint, svc, i + 1))

            if '_Run with AI enabled' in line:
                run_ai_issues.append((domain, fname, current_endpoint, i + 1))

            if '[DB_QUERY] ?' in line:
                db_query_issues.append((domain, fname, current_endpoint, i + 1))

            if re.search(r'\[QUERY_BUILDER\].*UNKNOWN', line):
                qb_unknown_issues.append((domain, fname, current_endpoint, i + 1))

# ---- Missing files ----
missing_files = []
for domain_dir in os.listdir(base):
    full_path = os.path.join(base, domain_dir)
    if not os.path.isdir(full_path):
        continue
    for expected in ['api.md', 'business.md', 'responses.md']:
        fpath = os.path.join(full_path, expected)
        if not os.path.exists(fpath):
            missing_files.append((domain_dir, expected))

# ---- Print Report ----
print("=" * 100)
print("NUERABENEFITS BACKEND DOCS - BUG & PLACEHOLDER REPORT")
print("=" * 100)

print("\n" + "=" * 100)
print("BUG TYPE 1: [SERVICE_CALL] — Unresolved service/repository/model call placeholders")
print("  These endpoints have a service call dependency detected but AI did NOT expand them.")
print("  Total:", len(service_call_issues))
print("-" * 100)
by_domain = defaultdict(list)
for d, f, ep, svc, ln in service_call_issues:
    by_domain[d].append((ep, svc, ln))
for domain in sorted(by_domain.keys()):
    items = by_domain[domain]
    print(f"\n  [{domain}] — {len(items)} issue(s)")
    for ep, svc, ln in items:
        print(f"    Line {ln:>4} | Endpoint: {ep:<50} | Calls: {svc}")

print("\n" + "=" * 100)
print("BUG TYPE 2: Purpose not filled ('_Run with AI enabled for full description._')")
print("  These endpoints have NO purpose text — AI was never run or response was not saved.")
print("  Total:", len(run_ai_issues))
print("-" * 100)
by_domain2 = defaultdict(list)
for d, f, ep, ln in run_ai_issues:
    by_domain2[d].append((ep, f, ln))
for domain in sorted(by_domain2.keys()):
    items = by_domain2[domain]
    print(f"\n  [{domain}] — {len(items)} endpoint(s) missing purpose")
    for ep, f, ln in items:
        print(f"    Line {ln:>4} | {f} | Endpoint: {ep}")

print("\n" + "=" * 100)
print("BUG TYPE 3: [DB_QUERY] ? — Unknown/unresolved database queries")
print("  Total:", len(db_query_issues))
print("-" * 100)
by_domain3 = defaultdict(list)
for d, f, ep, ln in db_query_issues:
    by_domain3[d].append((ep, f, ln))
for domain in sorted(by_domain3.keys()):
    items = by_domain3[domain]
    print(f"\n  [{domain}] — {len(items)} unknown query/queries")
    for ep, f, ln in items:
        print(f"    Line {ln:>4} | {f} | Endpoint: {ep}")

print("\n" + "=" * 100)
print("BUG TYPE 4: [QUERY_BUILDER] UNKNOWN — Query builder logic not analyzed")
print("  Total:", len(qb_unknown_issues))
print("-" * 100)
by_domain4 = defaultdict(list)
for d, f, ep, ln in qb_unknown_issues:
    by_domain4[d].append((ep, f, ln))
for domain in sorted(by_domain4.keys()):
    items = by_domain4[domain]
    print(f"\n  [{domain}] — {len(items)} unknown query builder(s)")
    for ep, f, ln in items:
        print(f"    Line {ln:>4} | {f} | Endpoint: {ep}")

print("\n" + "=" * 100)
print("BUG TYPE 5: MISSING FILES — Expected documentation files not generated")
print("  Total:", len(missing_files))
print("-" * 100)
for domain, fname in sorted(missing_files):
    print(f"  [{domain}] missing: {fname}")

# Unique service call targets
print("\n" + "=" * 100)
print("SUMMARY: Unique unresolved SERVICE_CALL targets (what is being called but not documented)")
print("-" * 100)
svc_counts = defaultdict(int)
for d, f, ep, svc, ln in service_call_issues:
    svc_counts[svc] += 1
for svc, count in sorted(svc_counts.items(), key=lambda x: -x[1]):
    print(f"  {svc:<35} — {count} endpoint(s) use this without documentation")

print("\n" + "=" * 100)
print("GRAND TOTAL ISSUES:")
print(f"  [SERVICE_CALL] unresolved     : {len(service_call_issues)}")
print(f"  Purpose not filled (Run AI)   : {len(run_ai_issues)}")
print(f"  [DB_QUERY] unknown            : {len(db_query_issues)}")
print(f"  [QUERY_BUILDER] UNKNOWN       : {len(qb_unknown_issues)}")
print(f"  Missing expected files        : {len(missing_files)}")
total = len(service_call_issues) + len(run_ai_issues) + len(db_query_issues) + len(qb_unknown_issues) + len(missing_files)
print(f"  TOTAL                        : {total}")
print("=" * 100)
