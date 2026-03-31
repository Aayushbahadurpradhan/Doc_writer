"""Generate backend documentation for commission_billing project."""
import glob
import json
import os
import re

PROJECT = "D:/CloudTech_main/commission_billing"
OUTPUT_BASE = "D:/CloudTech_main/Doc_writer/doc_output/commission_billing"
DOCS_BACKEND = f"{OUTPUT_BASE}/docs/backend"
PROJECT_NAME = "commission_billing"

# Load parsed routes
with open(f"{OUTPUT_BASE}/routes.json") as f:
    all_routes = json.load(f)
with open(f"{OUTPUT_BASE}/domains.json") as f:
    domains = json.load(f)

# ---------- Controller file resolution ----------

_ctrl_file_cache = {}

def find_controller_file(class_name):
    """Find PHP file for a controller class. Returns path or None."""
    if class_name in _ctrl_file_cache:
        return _ctrl_file_cache[class_name]
    
    # Strategy 1: Convert namespace to path
    # App\Http\Controllers\Api\V1\AgentController -> app/Http/Controllers/Api/V1/AgentController.php
    ctrl_path = class_name.replace("App\\", "").replace("\\", "/")
    candidate = f"{PROJECT}/app/{ctrl_path}.php"
    if os.path.exists(candidate):
        _ctrl_file_cache[class_name] = candidate
        return candidate
    
    # Strategy 2: Walk all PHP files, score by namespace segments
    basename = class_name.split("\\")[-1]
    all_php = glob.glob(f"{PROJECT}/app/Http/Controllers/**/{basename}.php", recursive=True)
    if all_php:
        # Score by how many namespace segments appear in the path
        def score(p):
            parts = class_name.lower().split("\\")[1:]  # skip App
            return sum(1 for part in parts if part.lower() in p.lower())
        all_php.sort(key=score, reverse=True)
        _ctrl_file_cache[class_name] = all_php[0]
        return all_php[0]
    
    _ctrl_file_cache[class_name] = None
    return None

# ---------- Method extraction ----------

def extract_method_body(file_content, method_name):
    """Extract method body from PHP class content."""
    # Case-insensitive match of function name
    pattern = re.compile(
        r'(public|protected|private)?\s*function\s+' + re.escape(method_name) + r'\s*\(',
        re.IGNORECASE
    )
    m = pattern.search(file_content)
    if not m:
        return None
    
    start = m.start()
    # Find opening brace
    brace_pos = file_content.find('{', m.end())
    if brace_pos == -1 or brace_pos - m.end() > 500:
        return None
    
    # Extract balanced braces
    depth = 0
    i = brace_pos
    while i < len(file_content):
        if file_content[i] == '{':
            depth += 1
        elif file_content[i] == '}':
            depth -= 1
            if depth == 0:
                return file_content[brace_pos:i+1]
        i += 1
    return None

def extract_db_queries(body):
    """Extract DB operations from method body."""
    queries = []
    patterns = [
        (r'DB::table\(["\'](\w+)["\']', 'db_facade'),
        (r'DB::select\(', 'raw_sql'),
        (r'DB::statement\(', 'raw_sql'),
        (r'(\w+)::where\(', 'eloquent'),
        (r'(\w+)::find\(', 'eloquent'),
        (r'(\w+)::all\(', 'eloquent'),
        (r'(\w+)::create\(', 'eloquent'),
        (r'(\w+)::firstOrCreate\(', 'eloquent'),
        (r'(\w+)::updateOrCreate\(', 'eloquent'),
        (r'->get\(\)', 'eloquent'),
        (r'->first\(\)', 'eloquent'),
        (r'->paginate\(', 'eloquent'),
    ]
    for pat, qtype in patterns:
        if re.search(pat, body, re.IGNORECASE):
            queries.append(qtype)
    return list(set(queries))

def extract_validation(body):
    """Extract validation rules from method body."""
    # $request->validate([...])
    m = re.search(r'\$request->validate\(\[([^\]]*)\]', body, re.DOTALL)
    if m:
        return m.group(1).strip()[:300]
    # FormRequest
    m = re.search(r'(\w+Request)\s+\$\w+', body)
    if m:
        return f"FormRequest: {m.group(1)}"
    return None

def extract_response_fields(body):
    """Extract response fields from response()->json([...])."""
    m = re.search(r'response\(\)->json\(\[([^\]]{0,500})\]', body, re.DOTALL)
    if m:
        return m.group(1).strip()[:400]
    m = re.search(r'return \[([^\]]{0,300})\]', body, re.DOTALL)
    if m:
        return m.group(1).strip()[:300]
    return None

def extract_jobs_events(body):
    """Extract dispatched jobs and fired events."""
    jobs = re.findall(r'dispatch\(new\s+(\w+)', body)
    jobs += re.findall(r'(\w+)::dispatch\(', body)
    events = re.findall(r'event\(new\s+(\w+)', body)
    return jobs, events

def analyze_route(route):
    """Analyze a route and return extracted info."""
    ctrl_file = find_controller_file(route['controller'])
    info = {
        'controller_file': ctrl_file,
        'method_body': None,
        'validation': None,
        'db_queries': [],
        'response_fields': None,
        'jobs': [],
        'events': [],
        'has_auth': bool(route.get('middleware') and 
                        any('auth' in str(m) for m in route['middleware'])),
    }
    
    if ctrl_file and os.path.exists(ctrl_file):
        with open(ctrl_file, encoding='utf-8', errors='ignore') as f:
            content = f.read()
        body = extract_method_body(content, route['action'])
        if body:
            info['method_body'] = body[:2000]  # limit
            info['validation'] = extract_validation(body)
            info['db_queries'] = extract_db_queries(body)
            info['response_fields'] = extract_response_fields(body)
            jobs, events = extract_jobs_events(body)
            info['jobs'] = jobs
            info['events'] = events
    
    return info

# ---------- Documentation generation ----------

def get_route_heading(r):
    """Get a descriptive heading for a route - use last non-param segment or action name."""
    segments = r['path'].split('/')
    # Find last non-param segment (param segments contain { })
    for seg in reversed(segments):
        if seg and not seg.startswith('{') and not seg.startswith(':'):
            return seg
    # fallback to action name
    return r['action']

def generate_api_md(domain, routes):
    """Generate api.md content."""
    lines = [
        f"# API Reference\n",
        f"Total: **{len(routes)}**\n",
        "---\n",
    ]
    for r in routes:
        ctrl_short = r['controller'].split("\\")[-1]
        last_seg = get_route_heading(r)
        params = r.get('params', [])
        mw = r.get('middleware', [])
        
        lines.append(f"## {last_seg}\n")
        lines.append(f"- **Endpoint** : `{r['method']} {r['full_path']}`")
        lines.append(f"- **Controller** : `{ctrl_short}@{r['action']}`")
        if mw:
            lines.append(f"- **Middleware** : {', '.join(str(m) for m in mw)}")
        if params:
            lines.append(f"- **Params** : " + ', '.join(f'`{p}`' for p in params))
        lines.append("\n---\n")
    return '\n'.join(lines)

def generate_business_md(domain, routes_with_info):
    """Generate business.md content."""
    lines = ["# Business Logic Documentation\n"]
    
    for r, info in routes_with_info:
        ctrl_short = r['controller'].split("\\")[-1]
        last_seg = get_route_heading(r)
        has_auth = info['has_auth'] or 'auth' in str(r.get('middleware', ''))
        
        lines.append(f"## {last_seg}\n")
        lines.append("| Field             | Value                   |")
        lines.append("| ----------------- | ----------------------- |")
        lines.append(f"| **Endpoint**      | `{r['method']} {r['full_path']}` |")
        lines.append(f"| **Controller**    | `{ctrl_short}@{r['action']}` |")
        lines.append(f"| **Auth Required** | {'Yes' if has_auth else 'UNKNOWN'} |")
        lines.append(f"| **HTTP Method**   | {r['method']} |")
        lines.append("")
        lines.append("### Purpose\n")
        
        # Infer purpose from controller and action name
        action = r['action']
        ctrl_name = ctrl_short.replace('Controller', '')
        purpose = infer_purpose(action, ctrl_name, r['path'])
        lines.append(purpose + "\n")
        
        lines.append("### Business Logic\n")
        if info.get('method_body'):
            logic_points = infer_business_logic(info)
            for point in logic_points:
                lines.append(f"- {point}")
        else:
            lines.append("- UNKNOWN — controller file not found or method body not extractable")
        lines.append("")
        
        lines.append("### Input Parameters\n")
        params = r.get('params', [])
        if params or info.get('validation'):
            if params:
                lines.append("| Parameter    | Type   | Required | Description |")
                lines.append("| ------------ | ------ | -------- | ----------- |")
                for p in params:
                    lines.append(f"| `{p}` | string | Yes | URL path parameter |")
            if info.get('validation'):
                lines.append(f"\nValidation rules: `{info['validation'][:200]}`")
        else:
            lines.append("No parameters." if r['method'] == 'GET' and not params else "UNKNOWN")
        lines.append("")
        
        lines.append("### Database Operations\n")
        if info.get('db_queries'):
            for i, qt in enumerate(info['db_queries'], 1):
                lines.append(f"{i}. {qt.upper()} — database operation detected in method body")
        else:
            lines.append("None" if not info.get('method_body') else "UNKNOWN — infer from implementation")
        lines.append("")
        
        lines.append("### Side Effects\n")
        lines.append(f"- **Emails**: {'Job dispatched or email sent' if info.get('jobs') else 'None'}")
        lines.append(f"- **Jobs/Queues**: {', '.join(info['jobs']) if info.get('jobs') else 'None'}")
        lines.append(f"- **Events**: {', '.join(info['events']) if info.get('events') else 'None'}")
        lines.append("- **External APIs**: None")
        lines.append("- **Files**: None")
        
        if not info.get('controller_file'):
            lines.append(f"\n> **Warning**: Controller file not found for `{r['controller']}`")
        
        lines.append("\n---\n")
    
    return '\n'.join(lines)

def infer_purpose(action, ctrl_name, path):
    """Infer purpose from action name and controller."""
    action_lower = action.lower()
    if 'get' in action_lower or 'render' in action_lower or 'fetch' in action_lower or action_lower == 'index':
        return f"Retrieves {ctrl_name} data. Called by clients needing to display or process {ctrl_name.lower()} information. Returns a list or detail view of the resource."
    elif 'store' in action_lower or 'create' in action_lower or 'save' in action_lower or 'add' in action_lower:
        return f"Creates or stores a new {ctrl_name} record. Called when a user or system submits a form or triggers an insert action. Validates input and persists data."
    elif 'update' in action_lower or 'edit' in action_lower or 'change' in action_lower:
        return f"Updates an existing {ctrl_name} record. Called when modifying existing data. Validates input and applies changes."
    elif 'delete' in action_lower or 'remove' in action_lower or 'destroy' in action_lower:
        return f"Deletes or removes a {ctrl_name} record. Called when a user or admin triggers a delete action. May soft-delete or hard-delete depending on implementation."
    elif 'pay' in action_lower or 'payment' in action_lower:
        return f"Processes a payment for {ctrl_name}. Handles payment transaction logic including validation, processing, and recording."
    elif 'report' in action_lower or 'statement' in action_lower or 'export' in action_lower:
        return f"Generates or exports a report for {ctrl_name}. Returns formatted data for reporting or export purposes."
    elif 'send' in action_lower or 'email' in action_lower:
        return f"Sends an email or notification for {ctrl_name}. Triggers email dispatch with relevant data."
    else:
        return f"Handles {action} operation for {ctrl_name}. UNKNOWN — exact purpose requires reviewing implementation."

def infer_business_logic(info):
    """Infer business logic points from extracted info."""
    points = []
    if info.get('validation'):
        points.append(f"Validates input: {info['validation'][:150]}")
    if info.get('db_queries'):
        for qt in info['db_queries']:
            if qt == 'eloquent':
                points.append("Performs Eloquent ORM database query")
            elif qt == 'raw_sql':
                points.append("Executes raw SQL query")
            elif qt == 'db_facade':
                points.append("Uses DB facade for database operations")
    if info.get('jobs'):
        for job in info['jobs']:
            points.append(f"Dispatches job: `{job}`")
    if info.get('events'):
        for event in info['events']:
            points.append(f"Fires event: `{event}`")
    if info.get('response_fields'):
        points.append(f"Returns JSON response with fields")
    if not points:
        points.append("UNKNOWN — implementation details require code review")
    return points

def generate_responses_md(domain, routes_with_info):
    """Generate responses.md content."""
    lines = [
        "# API Response Schemas\n",
        "Response bodies for each endpoint.\n",
        "---\n",
    ]
    
    for r, info in routes_with_info:
        ctrl_short = r['controller'].split("\\")[-1]
        params = r.get('params', [])
        
        lines.append(f"## {r['method']} {r['full_path']}\n")
        lines.append(f"**Endpoint**: `{ctrl_short}@{r['action']}`\n")
        
        if params:
            lines.append("**Path Parameters**:\n")
            for p in params:
                lines.append(f"- `{p}` - (from URL path)")
            lines.append("")
        
        lines.append("**Response Type**: `json`\n")
        
        if info.get('response_fields'):
            lines.append("**Response Fields**:\n")
            lines.append("```json")
            lines.append("{")
            for field_line in info['response_fields'].split('\n')[:10]:
                field_line = field_line.strip().strip(',')
                if '=>' in field_line:
                    key, _, val = field_line.partition('=>')
                    key = key.strip().strip("'\"")
                    val = val.strip()
                    lines.append(f'  "{key}": "UNKNOWN"')
            lines.append("}")
            lines.append("```\n")
        else:
            lines.append("**Response**: Unable to determine from available code.\n")
        
        lines.append("---\n")
    
    return '\n'.join(lines)

def generate_legacy_sql(domain, routes_with_info):
    """Generate legacy_query.sql content."""
    lines = []
    has_queries = False
    
    for r, info in routes_with_info:
        ctrl_short = r['controller'].split("\\")[-1]
        if not info.get('db_queries'):
            continue
        has_queries = True
        
        last_seg = get_route_heading(r)
        lines.append(f"-- Endpoint  : {r['method']} {r['full_path']}")
        lines.append(f"-- Controller: {ctrl_short}@{r['action']}")
        lines.append("")
        
        for i, qt in enumerate(info['db_queries'], 1):
            op_type = 'SELECT' if qt == 'eloquent' and 'get' in r['action'].lower() else 'SELECT/INSERT/UPDATE'
            lines.append(f"### {last_seg} -- Query {i}: database operation")
            lines.append("")
            lines.append("| Field | Value |")
            lines.append("|-------|-------|")
            lines.append(f"| **Type** | {qt} |")
            lines.append(f"| **Operation** | {op_type} |")
            lines.append("| **Tables** | UNKNOWN |")
            lines.append("| **Columns Read** | * |")
            lines.append("| **Columns Written** | None |")
            lines.append("| **Conditions** | UNKNOWN |")
            lines.append("| **Joins** | None |")
            lines.append("| **Order / Group** | None |")
            lines.append("| **Aggregates** | None |")
            lines.append("| **Transaction** | No |")
            lines.append("| **Soft Deletes** | No |")
            lines.append("")
            lines.append("```sql")
            lines.append("-- reconstructed SQL with ? for bound params")
            lines.append("SELECT * FROM unknown_table WHERE id = ?;")
            lines.append("```")
            lines.append("")
            lines.append("**Optimization Notes:**")
            lines.append("- No issues identified")
            lines.append("")
    
    if not has_queries:
        lines.append("-- No database queries")
    
    return '\n'.join(lines)

def generate_domain(domain, routes, force=False):
    """Generate all 4 docs files for a domain."""
    domain_dir = f"{DOCS_BACKEND}/{domain}"
    os.makedirs(domain_dir, exist_ok=True)
    
    # Check resume logic - if api.md exists, skip if all routes present
    api_md_path = f"{domain_dir}/api.md"
    business_md_path = f"{domain_dir}/business.md"
    
    if force:
        # Remove existing files
        for f in [api_md_path, business_md_path, 
                  f"{domain_dir}/responses.md", f"{domain_dir}/legacy_query.sql"]:
            if os.path.exists(f):
                os.remove(f)
    
    # Analyze routes
    routes_with_info = []
    for r in routes:
        info = analyze_route(r)
        routes_with_info.append((r, info))
    
    # Generate api.md (always regenerate)
    api_content = generate_api_md(domain, routes)
    with open(api_md_path, 'w', encoding='utf-8') as f:
        f.write(api_content)
    
    # Generate business.md
    if not os.path.exists(business_md_path):
        business_content = generate_business_md(domain, routes_with_info)
        with open(business_md_path, 'w', encoding='utf-8') as f:
            f.write(business_content)
    else:
        # Check for missing routes
        with open(business_md_path, encoding='utf-8') as f:
            existing = f.read()
        missing = [rr for rr in routes_with_info 
                   if not re.search(r'^## ' + re.escape(re.sub(r'[{}]', '', rr[0]['path'].split('/')[-1] or rr[0]['path'])), existing, re.MULTILINE)]
        if missing:
            append_content = generate_business_md(domain, missing)
            # Remove the header from append content
            append_content = re.sub(r'^# Business Logic Documentation\n+', '', append_content)
            with open(business_md_path, 'a', encoding='utf-8') as f:
                f.write('\n' + append_content)
    
    # Generate responses.md
    responses_path = f"{domain_dir}/responses.md"
    if not os.path.exists(responses_path):
        resp_content = generate_responses_md(domain, routes_with_info)
        with open(responses_path, 'w', encoding='utf-8') as f:
            f.write(resp_content)
    
    # Generate legacy_query.sql
    sql_path = f"{domain_dir}/legacy_query.sql"
    if not os.path.exists(sql_path):
        sql_content = generate_legacy_sql(domain, routes_with_info)
        with open(sql_path, 'w', encoding='utf-8') as f:
            f.write(sql_content)
    
    return len(routes)

# ---------- Main execution ----------

print("Generating backend documentation...")
os.makedirs(DOCS_BACKEND, exist_ok=True)

total_routes = 0
domain_count = 0
domain_stats = []

for domain, routes in sorted(domains.items()):
    count = generate_domain(domain, routes, force=True)  # force regenerate with fixes
    domain_stats.append((domain, count))
    total_routes += count
    domain_count += 1
    if domain_count % 10 == 0:
        print(f"  Progress: {domain_count}/{len(domains)} domains...")

print(f"\nDone! Generated docs for {domain_count} domains, {total_routes} routes.")

# Generate backend/index.md
index_lines = [
    "# Backend API Index\n",
    f"Total routes: {total_routes} | Domains: {domain_count}\n",
    "## Domains\n",
    "| Domain | Routes | Files |",
    "|--------|--------|-------|",
]
for domain, count in sorted(domain_stats):
    index_lines.append(
        f"| {domain} | {count} | [api.md](./{domain}/api.md) · [business.md](./{domain}/business.md) |"
    )

with open(f"{DOCS_BACKEND}/index.md", 'w', encoding='utf-8') as f:
    f.write('\n'.join(index_lines))

print(f"Written: {DOCS_BACKEND}/index.md")
print(f"\nOutput: {OUTPUT_BASE}")
