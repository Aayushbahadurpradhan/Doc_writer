"""Parse all routes from commission_billing route files and output domain groups."""
import json
import os
import re

PROJECT = "D:/CloudTech_main/commission_billing"
OUTPUT_BASE = "D:/CloudTech_main/Doc_writer/doc_output/commission_billing"

ROUTE_FILES = [
    (f"{PROJECT}/routes/api.php", "v1", ""),
    (f"{PROJECT}/routes/api-commission.php", "v1", ""),
    (f"{PROJECT}/routes/api_v2.php", "v2", ""),
    (f"{PROJECT}/routes/api_v5.php", "v5", ""),
]

# Stopwords to strip from domain detection
STOPWORDS = set("""get set add create update delete remove upload download send view edit list manage check
fetch generate process approve reject import export restore change reset save validate verify mark toggle
submit bulk total show find search filter load build activate deactivate enable disable calculate store
define retrieve preview sync onboard migrate switch resend reprocess refund new latest recent active
all and or any the of by old own my true false yes no""".split())

ENTITY_WORDS = set("""agent group policy member plan payment invoice contract commission enrollment
dependent beneficiary carrier template email bank billing claim document report license medical platform
feature note term rider address question text tier waive fee acm prudential website homepage downline
upline referral webhook notification queue lead script analytic statistic progress rate price renewal
receipt tax eft ach census credit routing client user admin resource activity log audit setting option
type status level info detail summary history request approval sub""".split())

def normalize_plural(word):
    if len(word) > 4:
        if word.endswith('ies'):
            return word[:-3] + 'y'
        if word.endswith('ses') and len(word) > 5:
            return word[:-1]
        if word.endswith('s') and not word.endswith('ss'):
            return word[:-1]
    return word

def camel_to_words(s):
    """Split camelCase into individual words."""
    # Insert underscore before uppercase letters
    s2 = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', s)
    s2 = re.sub(r'([a-z\d])([A-Z])', r'\1_\2', s2)
    return s2.lower().split('_')

def segment_to_words(seg):
    """Split a path segment (may be kebab, snake, camelCase) into words."""
    # First split on hyphens and underscores
    parts = re.split(r'[-_]', seg)
    words = []
    for part in parts:
        words.extend(camel_to_words(part))
    return [w for w in words if w]

def detect_domain(path):
    # Strip leading /
    path = path.lstrip('/')
    # Strip version/api prefixes
    for prefix in ['api/v1/', 'api/v2/', 'api/v3/', 'api/v5/', 
                   'api/', 'v1/', 'v2/', 'v3/', 'v5/', 'api.access/', 'access/']:
        if path.startswith(prefix):
            path = path[len(prefix):]
            break
    if not path:
        return 'general'
    
    segments = path.split('/')
    for seg in segments[:3]:
        # Skip param segments
        if seg.startswith('{') or seg.startswith(':') or seg == '':
            continue
        words = segment_to_words(seg)
        # Filter stopwords
        nouns = [w for w in words if w and w not in STOPWORDS and len(w) >= 3]
        # Prefer entity words
        entity_nouns = [w for w in nouns if w in ENTITY_WORDS]
        candidate = entity_nouns[0] if entity_nouns else (nouns[0] if nouns else None)
        if candidate and len(candidate) >= 3:
            return normalize_plural(candidate)
    
    # fallback: use last word of first segment
    first_seg = segments[0] if segments else 'general'
    words = segment_to_words(first_seg)
    # filter stopwords for fallback too
    nouns = [w for w in words if w and w not in STOPWORDS and len(w) >= 2]
    fallback = nouns[-1] if nouns else (words[-1] if words else 'general')
    return normalize_plural(fallback) if fallback else 'general'

def extract_ns_and_handlers(content):
    """Parse routes from content, returning list of (method, path, handler, middleware) tuples."""
    routes = []
    
    # Simple extraction using regex
    pattern = re.compile(
        r"Route::(get|post|put|patch|delete|options|any)\s*\(\s*'([^']+)'\s*,\s*'([^']+)'",
        re.IGNORECASE
    )
    
    for m in pattern.finditer(content):
        method = m.group(1).upper()
        path = m.group(2)
        handler = m.group(3)
        routes.append((method, path, handler, []))
    
    # Also find Route::resource patterns
    resource_pattern = re.compile(
        r"Route::resource\s*\(\s*'([^']+)'\s*,\s*'([^']+)'",
        re.IGNORECASE
    )
    for m in resource_pattern.finditer(content):
        res_path = m.group(1)
        ctrl = m.group(2)
        routes.append(('GET', res_path, f"{ctrl}@index", []))
        routes.append(('POST', res_path, f"{ctrl}@store", []))
        routes.append(('GET', f"{res_path}/{{id}}", f"{ctrl}@show", []))
        routes.append(('PUT', f"{res_path}/{{id}}", f"{ctrl}@update", []))
        routes.append(('DELETE', f"{res_path}/{{id}}", f"{ctrl}@destroy", []))
    
    return routes

def parse_file(filepath, version_prefix):
    """Parse a route file and return route info with version prefix."""
    with open(filepath, encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # Remove comments
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    content = re.sub(r'//.*', '', content)
    
    routes_raw = extract_ns_and_handlers(content)
    
    # Now we need to associate namespace context. Simple approach: extract namespace from context
    # Look for namespace => 'Api\V1' or 'Api\V2' etc patterns
    ns_v1 = "App\\Http\\Controllers\\Api\\V1"
    ns_v2 = "App\\Http\\Controllers\\Api\\V2"
    ns_commission = "App\\Http\\Controllers\\Api\\V1\\commission"
    ns_enrollment = "App\\Http\\Controllers\\Api\\V1\\enrollment"
    ns_policy = "App\\Http\\Controllers\\Api\\V1\\policy"
    ns_invoice_dist = "App\\Http\\Controllers\\Api\\V1\\InvoiceDistribution"
    
    results = []
    for method, path, handler, mw in routes_raw:
        # Determine controller class from handler
        if '@' in handler:
            ctrl_short, action = handler.rsplit('@', 1)
        else:
            ctrl_short = handler
            action = '__invoke'
        
        # Determine namespace
        if '\\' in ctrl_short or '/' in ctrl_short:
            # Has namespace fragments
            ctrl_short_normalized = ctrl_short.replace('/', '\\')
            if ctrl_short_normalized.startswith('commission\\'):
                ns = ns_commission
                ctrl_class = f"App\\Http\\Controllers\\Api\\V1\\{ctrl_short_normalized}"
            elif ctrl_short_normalized.startswith('enrollment\\'):
                ns = ns_enrollment
                ctrl_class = f"App\\Http\\Controllers\\Api\\V1\\{ctrl_short_normalized}"
            elif ctrl_short_normalized.startswith('policy\\'):
                ns = ns_policy
                ctrl_class = f"App\\Http\\Controllers\\Api\\V1\\{ctrl_short_normalized}"
            elif ctrl_short_normalized.startswith('InvoiceDistribution\\'):
                ns = ns_invoice_dist
                ctrl_class = f"App\\Http\\Controllers\\Api\\V1\\{ctrl_short_normalized}"
            else:
                ctrl_class = f"App\\Http\\Controllers\\{ctrl_short_normalized}"
        else:
            # Use v2 namespace for v2/v5 file, v1 for others
            if 'v2' in filepath or 'v5' in filepath:
                ctrl_class = f"{ns_v1}\\{ctrl_short}"  # Most in api_v2.php use V1 namespace
            else:
                ctrl_class = f"{ns_v1}\\{ctrl_short}"
        
        # Build full path - prepend version
        full_path = f"/api/{version_prefix}/{path.lstrip('/')}"
        
        # Get domain
        domain = detect_domain(full_path)
        
        results.append({
            'method': method,
            'path': path.lstrip('/'),
            'full_path': full_path,
            'controller': ctrl_class,
            'action': action,
            'middleware': mw,
            'params': re.findall(r'\{(\w+)\}', path),
            'domain': domain,
        })
    
    return results

# Parse all files
all_routes = []
version_map = {
    'api.php': 'v1',
    'api-commission.php': 'v1',
    'api_v2.php': 'v2',
    'api_v5.php': 'v5',
}

for filepath, ver, _ in ROUTE_FILES:
    fname = os.path.basename(filepath)
    v = version_map.get(fname, 'v1')
    routes = parse_file(filepath, v)
    all_routes.extend(routes)
    print(f"  {fname}: {len(routes)} routes")

print(f"\nTotal routes: {len(all_routes)}")

# Deduplicate (same method+path)
seen = set()
unique_routes = []
for r in all_routes:
    key = (r['method'], r['full_path'])
    if key not in seen:
        seen.add(key)
        unique_routes.append(r)

print(f"Unique routes: {len(unique_routes)}")

# Group by domain
domains = {}
for r in unique_routes:
    d = r['domain']
    if d not in domains:
        domains[d] = []
    domains[d].append(r)

print(f"\nDomains ({len(domains)}):")
sorted_domains = sorted(domains.items(), key=lambda x: x[0])
for domain, routes in sorted_domains:
    print(f"  {domain:40s} {len(routes):3d} routes")

# Save to JSON for further processing
os.makedirs(OUTPUT_BASE, exist_ok=True)
with open(f"{OUTPUT_BASE}/routes.json", 'w') as f:
    json.dump(unique_routes, f, indent=2)
with open(f"{OUTPUT_BASE}/domains.json", 'w') as f:
    json.dump({k: v for k, v in sorted_domains}, f, indent=2)

print("\nSaved routes.json and domains.json")
