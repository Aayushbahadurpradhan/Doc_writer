"""
Migrate documentation after domain-detection fixes.

1. Regenerate all api.md files (fast, no AI) with new domain groupings
2. Move business.md/responses.md/legacy_query.sql content from old bad
   folders into the correct new domain folders where possible
3. Remove old bad domain folders
4. Remove progress.json entries for routes that moved, so they get
   re-documented in their correct new folder on next pipeline run
"""
import json
import os
import re
import shutil
import sys

sys.path.insert(0, r'd:\CloudTech_main\Doc_writer')

from collections import defaultdict

from backend.generate_docs import _write_api_md, detect_domain

ROUTES_FILE = r'd:\CloudTech_main\Doc_writer\doc_output\nuerabenefits\.docwriter\routes.json'
PROGRESS_FILE = r'd:\CloudTech_main\Doc_writer\doc_output\nuerabenefits\.docwriter\progress.json'
BE_DIR = r'd:\CloudTech_main\Doc_writer\doc_output\nuerabenefits\docs\backend'

# ── Load routes & build new domain map ────────────────────────────────────────
with open(ROUTES_FILE) as f:
    routes = json.load(f)

new_domain_map = defaultdict(list)
for r in routes:
    d = detect_domain(
        r.get('method', 'GET'),
        r.get('full_path', r.get('path', '/')),
        r.get('controller', ''),
    )
    safe = re.sub(r'[^\w-]', '_', d.strip()).strip('_') or 'general'
    new_domain_map[safe].append(r)

# ── Build old domain map (from existing api.md files) ─────────────────────────
old_domain_map = defaultdict(list)  # old_domain -> [route_keys]
for old_domain in os.listdir(BE_DIR):
    api_md = os.path.join(BE_DIR, old_domain, 'api.md')
    if not os.path.exists(api_md):
        continue
    content = open(api_md, encoding='utf-8').read()
    endpoints = re.findall(r"Endpoint\s*\*\*\s*:\s*`([A-Z]+)\s+([^`]+)`", content)
    for method, path in endpoints:
        old_domain_map[old_domain].append(method.strip() + ' ' + path.strip())

# ── Identify domains that changed ─────────────────────────────────────────────
old_domains = set(d for d in os.listdir(BE_DIR) if os.path.isdir(os.path.join(BE_DIR, d)))
new_domains = set(new_domain_map.keys())
bad_domains = old_domains - new_domains

print(f"Old domains: {len(old_domains)}  ->  New domains: {len(new_domains)}")
print(f"Bad folders to remove: {sorted(bad_domains)}")
print(f"New folders to create: {sorted(new_domains - old_domains)}")
print()

# ── Step 1: Re-create all api.md files with new domain groupings ───────────────
regen = 0
for domain, droutes in sorted(new_domain_map.items()):
    ddir = os.path.join(BE_DIR, domain)
    os.makedirs(ddir, exist_ok=True)
    _write_api_md(droutes, os.path.join(ddir, 'api.md'))
    regen += 1
print(f"Regenerated {regen} api.md files.")

# ── Step 2: For bad domains, try to migrate business.md/responses.md/sql ──────
# Build a reverse map: route_key -> new_domain
route_to_new_domain = {}
for nd, droutes in new_domain_map.items():
    for r in droutes:
        key = r.get('method', '') + ' ' + r.get('full_path', r.get('path', ''))
        route_to_new_domain[key] = nd

migrated_routes = set()  # route keys that were successfully migrated

for bad in sorted(bad_domains):
    bad_dir = os.path.join(BE_DIR, bad)
    if not os.path.isdir(bad_dir):
        continue

    route_keys_in_bad = old_domain_map.get(bad, [])
    print(f"\nMigrating '{bad}' ({len(route_keys_in_bad)} routes) ->", end=' ')

    # Find which new domains these routes went to
    target_domains = set()
    for rk in route_keys_in_bad:
        nd = route_to_new_domain.get(rk)
        if nd:
            target_domains.add(nd)
    print(', '.join(sorted(target_domains)) if target_domains else 'UNMAPPED')

    for file_name in ('business.md', 'responses.md', 'legacy_query.sql'):
        src = os.path.join(bad_dir, file_name)
        if not os.path.exists(src):
            continue
        src_content = open(src, encoding='utf-8').read()

        # Only move when ALL routes map to a single new domain (clean migration)
        if len(target_domains) == 1:
            nd = next(iter(target_domains))
            dst = os.path.join(BE_DIR, nd, file_name)
            if os.path.exists(dst):
                # Append to existing file (skip header if already has one)
                existing = open(dst, encoding='utf-8').read()
                # Strip duplicate headers
                body = re.sub(r'^#[^\n]+\n', '', src_content, count=1).strip()
                if body:
                    with open(dst, 'a', encoding='utf-8') as f:
                        f.write('\n\n---\n\n' + body)
                    print(f"  Appended {file_name} -> {nd}/")
            else:
                shutil.copy2(src, dst)
                print(f"  Moved {file_name} -> {nd}/")
            for rk in route_keys_in_bad:
                migrated_routes.add(rk)
        else:
            print(f"  Skipped {file_name} (routes split across multiple domains — needs re-doc)")

# ── Step 3: Remove bad domain folders ─────────────────────────────────────────
print()
removed_count = 0
for bad in sorted(bad_domains):
    bad_dir = os.path.join(BE_DIR, bad)
    if os.path.isdir(bad_dir):
        shutil.rmtree(bad_dir)
        removed_count += 1
        print(f"Removed: {bad}/")
print(f"\nRemoved {removed_count} old domain folders.")

# ── Step 4: Clear progress.json entries for routes in multi-split bad domains ──
# Routes that could NOT be cleanly migrated need to be re-documented
with open(PROGRESS_FILE) as f:
    prog = json.load(f)

all_route_keys_in_bad = set()
for bad in sorted(bad_domains):
    for rk in old_domain_map.get(bad, []):
        if rk not in migrated_routes:
            all_route_keys_in_bad.add(rk)

if all_route_keys_in_bad:
    print(f"\nRoutes needing re-documentation (split across domains): {len(all_route_keys_in_bad)}")
    for rk in sorted(all_route_keys_in_bad):
        print(f"  {rk}")
        for key in ('apis', 'ai_apis', 'sql_apis', 'sql_ai_apis'):
            if rk in prog.get(key, []):
                prog[key].remove(rk)

    with open(PROGRESS_FILE, 'w') as f:
        json.dump(prog, f, indent=2)
    print(f"Cleared {len(all_route_keys_in_bad)} routes from progress.json -> will be re-documented on next run.")
else:
    print("\nAll routes successfully migrated — no progress.json changes needed.")

# ── Step 5: Regenerate backend index.md ───────────────────────────────────────
total_routes = len(routes)
total_domains = len(new_domain_map)
lines = [
    '# Backend API Index', '',
    f'Total routes: **{total_routes}** | Domains: **{total_domains}**', '',
    '## Domains', '',
    '| Domain | Routes | Files |',
    '|--------|--------|-------|',
]
for domain in sorted(new_domain_map.keys()):
    cnt = len(new_domain_map[domain])
    safe = re.sub(r'[^\w-]', '_', domain.strip()).strip('_') or 'general'
    lines.append(
        f'| {domain} | {cnt} | [api.md](./{safe}/api.md) · '
        f'[business.md](./{safe}/business.md) · '
        f'[responses.md](./{safe}/responses.md) · '
        f'[legacy_query.sql](./{safe}/legacy_query.sql) |'
    )
with open(os.path.join(BE_DIR, 'index.md'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines) + '\n')
print(f"\nRegenerated index.md: {total_domains} domains, {total_routes} routes.")
print("\nDone! Run the pipeline again to re-document any routes that needed migration.")
