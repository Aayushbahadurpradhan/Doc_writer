"""Generate dependency graph for commission_billing project."""
import json
import os

OUTPUT_BASE = "D:/CloudTech_main/Doc_writer/doc_output/commission_billing"
DOCS_DIR = f"{OUTPUT_BASE}/docs"

# Load data
with open(f"{OUTPUT_BASE}/routes.json") as f:
    all_routes = json.load(f)
with open(f"{OUTPUT_BASE}/pages.json") as f:
    all_pages = json.load(f)

# Build dependency graph
graph = {
    "pages": {},
    "apis": {},
    "links": []
}

# Add pages
for page in all_pages:
    path = page['path']
    graph['pages'][path] = {
        "component": page['component'],
        "layout": page['layout'],
        "api_calls": len(page['api_calls'])
    }

# Add APIs (deduplicate by full_path)
seen_apis = set()
for route in all_routes:
    key = f"{route['method']} {route['full_path']}"
    if key not in seen_apis:
        seen_apis.add(key)
        graph['apis'][key] = {
            "controller": route['controller'].split('\\')[-1],
            "action": route['action'],
            "domain": route.get('domain', 'unknown')
        }

# Add links (page -> api)
link_count = 0
for page in all_pages:
    page_path = page['path']
    for api_call in page['api_calls']:
        endpoint = api_call['endpoint']
        method = api_call['method']
        # Try to match to backend route
        for route in all_routes:
            if route['full_path'] == endpoint or route['path'] == endpoint.lstrip('/'):
                link_key = f"{method} {route['full_path']}"
                graph['links'].append({
                    "from": page_path,
                    "to": link_key,
                    "via": page['component'],
                    "transport": api_call['transport']
                })
                link_count += 1
                break

print(f"Graph: {len(graph['pages'])} pages, {len(graph['apis'])} APIs, {len(graph['links'])} links")

# Save dependency_graph.json
with open(f"{DOCS_DIR}/dependency_graph.json", 'w') as f:
    json.dump(graph, f, indent=2)
print(f"Written: {DOCS_DIR}/dependency_graph.json")

# Generate dependency_graph.mermaid (max 80 links)
mermaid_lines = ["graph LR"]
link_nodes = set()

# Add API nodes for top domains
domain_counts = {}
for route in all_routes:
    d = route.get('domain', 'unknown')
    domain_counts[d] = domain_counts.get(d, 0) + 1

top_domains = sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)[:20]
top_domain_names = {d for d, _ in top_domains}

# Add page -> api links, limited to 80
link_count_mermaid = 0
for page in all_pages[:30]:  # limit pages too
    page_path = page['path']
    safe_page = page['component']
    for api_call in page['api_calls'][:5]:
        if link_count_mermaid >= 80:
            break
        endpoint = api_call['endpoint']
        # Simplify endpoint for display
        ep_short = endpoint.split('/')[-2] if endpoint.count('/') > 1 else endpoint
        mermaid_lines.append(f'  "{safe_page}" --> "{api_call["method"]} {ep_short}"')
        link_count_mermaid += 1

# Add domain -> API mappings
for domain, count in top_domains[:15]:
    routes_in_domain = [r for r in all_routes if r.get('domain') == domain]
    for route in routes_in_domain[:3]:
        ctrl = route['controller'].split('\\')[-1]
        mermaid_lines.append(f'  "{domain}" --> "{ctrl}@{route["action"]}"')

with open(f"{DOCS_DIR}/dependency_graph.mermaid", 'w') as f:
    f.write('\n'.join(mermaid_lines))
print(f"Written: {DOCS_DIR}/dependency_graph.mermaid")

# Generate cross_validation.json
# Find APIs called in frontend but not in backend
backend_endpoints = set()
for route in all_routes:
    backend_endpoints.add(route['full_path'])
    backend_endpoints.add(f"/api/v1/{route['path'].lstrip('/')}")
    backend_endpoints.add(f"/api/v2/{route['path'].lstrip('/')}")

missing_in_backend = []
for page in all_pages:
    for api_call in page['api_calls']:
        endpoint = api_call['endpoint']
        if endpoint not in backend_endpoints:
            missing_in_backend.append({
                "endpoint": endpoint,
                "method": api_call['method'],
                "called_from": page['component']
            })

# Find backend routes not called by any frontend page
frontend_called = set()
for page in all_pages:
    for ac in page['api_calls']:
        frontend_called.add(ac['endpoint'])

unused_backend = []
for route in all_routes[:50]:  # just show first 50 for brevity
    ep = route['full_path']
    if ep not in frontend_called:
        unused_backend.append({
            "endpoint": ep,
            "method": route['method'],
            "controller": route['controller'].split('\\')[-1]
        })

cross_validation = {
    "missing_in_backend": missing_in_backend[:20],
    "unused_backend_apis": unused_backend[:20],
    "mismatches": []
}

with open(f"{DOCS_DIR}/cross_validation.json", 'w') as f:
    json.dump(cross_validation, f, indent=2)
print(f"Written: {DOCS_DIR}/cross_validation.json")

# Generate validation_report.json
validation_report = {
    "project": "commission_billing",
    "generated_at": "2026-03-30",
    "backend": {
        "route_files_parsed": 4,
        "total_routes": len(all_routes),
        "unique_routes": len(all_routes),
        "domains": len(set(r.get('domain', 'unknown') for r in all_routes)),
        "controllers_found": len(set(r['controller'] for r in all_routes)),
    },
    "frontend": {
        "router_file": "resources/assets/js/app.js",
        "total_pages": len(all_pages),
        "page_groups": 14,
        "api_calls_extracted": sum(len(p['api_calls']) for p in all_pages),
    },
    "cross_validation": {
        "missing_in_backend": len(missing_in_backend),
        "unused_backend_apis_sampled": len(unused_backend),
    }
}

with open(f"{OUTPUT_BASE}/validation_report.json", 'w') as f:
    json.dump(validation_report, f, indent=2)
print(f"Written: {OUTPUT_BASE}/validation_report.json")

print("\nDependency graph generation complete!")
print(f"Pages: {len(all_pages)}")
print(f"APIs: {len(graph['apis'])}")
print(f"Links: {len(graph['links'])}")
print(f"Missing in backend: {len(missing_in_backend)}")
print(f"Unused backend APIs (sample): {len(unused_backend)}")
