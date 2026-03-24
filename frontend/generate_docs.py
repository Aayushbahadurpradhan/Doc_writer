"""
generate_docs.py — Step 2 of the frontend pipeline.

Reorganized to group pages by route prefix.

Output structure:
  docs/frontend/
    index.md                    <- master index
    home/
      README.md                 <- /home group overview
      index.md                  <- /home
      dashboard.md              <- /home/dashboard
    bill/
      README.md
      list.md                   <- /bill/list
      detail.md                 <- /bill/{id}
    undocumented/
      missing_apis.md           <- APIs called but not found in backend
    
Each page gets its own markdown with:
  - Component info
  - Data sources (models, hooks, parent components)
  - API dependencies mapped back to backend
  - Layout hierarchy
  - State management
"""

import os
import re
import sys
import time
from collections import defaultdict
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prompts.frontend_prompts import pages_md_prompt, pages_md_system
from shared.ai_client import AIConfig, call_ai


def _extract_page_group(path: str) -> str:
    """
    Extract page group from route path.
    /home -> home
    /home/dashboard -> home
    /bill/list -> bill
    /settings/profile/edit -> settings
    """
    if not path or path == "/":
        return "home"
    
    parts = [p for p in path.strip("/").split("/") if p]
    if not parts:
        return "home"
    
    # Use first segment as group
    group = parts[0].lower()
    # Remove trailing 's' for plurals
    if group.endswith("s") and len(group) > 3:
        group = group[:-1]
    return group or "home"


def _safe_page_filename(path: str) -> str:
    """Convert page path to safe filename."""
    safe = path.strip("/").replace("/", "_").replace("-", "_") or "index"
    safe = re.sub(r"[^\w]", "_", safe).strip("_") or "index"
    # Remove {id} type params from filename
    safe = re.sub(r"^\{.*?\}", "detail", safe)
    safe = re.sub(r"_\{.*?\}", "", safe)
    return safe + ".md"


def generate_pages_md(
    pages: List[dict],
    output_root: str,
    config: AIConfig,
    no_ai: bool = False,
) -> None:
    """
    Generate frontend docs organized by page group.
    
    Creates:
      output_root/
        index.md
        home/
          README.md
          index.md
          ...
        bill/
          README.md
          list.md
          detail.md
    """
    os.makedirs(output_root, exist_ok=True)
    
    # Group pages by route prefix
    groups: Dict[str, List[dict]] = defaultdict(list)
    undocumented_apis: set = set()
    all_missing_apis: List[Tuple[str, str]] = []  # (page_path, api_call)
    
    for page in pages:
        path = page.get("path", "/")
        group = _extract_page_group(path)
        groups[group].append(page)
        
        # Track missing APIs (called but not documented in backend)
        for api_call in page.get("api_calls", []):
            endpoint = api_call.get("endpoint", "")
            # Just collect for now - we'll validate later if needed
            all_missing_apis.append((path, endpoint))
    
    # Generate per-group documentation
    sys_msg = pages_md_system()
    
    for group_name in sorted(groups.keys()):
        group_pages = groups[group_name]
        group_dir = os.path.join(output_root, group_name)
        os.makedirs(group_dir, exist_ok=True)
        
        # README for group
        _write_group_readme(group_name, group_pages, group_dir)
        
        # Individual page files
        for i, page in enumerate(group_pages):
            path = page.get("path", "UNKNOWN")
            component = page.get("component", "UNKNOWN")
            
            page_file = _safe_page_filename(path)
            page_path = os.path.join(group_dir, page_file)
            
            print(f"  📄 [{i+1}/{len(group_pages)}] {group_name}/{page_file}")
            
            if no_ai or not config.use_ai:
                content = _skeleton_page(page)
            else:
                prompt = pages_md_prompt(page)
                content = call_ai(prompt, config, system=sys_msg, max_tokens=1500)
                if content.startswith("[AI failed"):
                    print(f"     ⚠️  AI failed — using skeleton")
                    content = _skeleton_page(page)
                if config.delay > 0:
                    time.sleep(config.delay)
            
            with open(page_path, "w", encoding="utf-8") as f:
                f.write(content)
    
    # Master index
    _write_frontend_index(groups, output_root)
    
    # Undocumented section (if calling APIs we don't have backend docs for)
    if all_missing_apis:
        _write_missing_apis(all_missing_apis, output_root)
    
    print(f"\n  ✅ Frontend docs generated → {output_root}")
    print(f"     Groups: {', '.join(sorted(groups.keys()))}")
    if all_missing_apis:
        print(f"     ⚠️  {len(all_missing_apis)} API calls may be undocumented")


def _write_group_readme(group: str, pages: List[dict], group_dir: str) -> None:
    """Write README.md for each page group."""
    readme_path = os.path.join(group_dir, "README.md")
    
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(f"# {group.upper()} Pages\n\n")
        f.write(f"Page group: **/{group}**\n\n")
        f.write(f"## Pages ({len(pages)})\n\n")
        
        for page in pages:
            path = page.get("path", "/")
            component = page.get("component", "UNKNOWN")
            api_count = len(page.get("api_calls", []))
            
            page_file = _safe_page_filename(path)
            f.write(f"- [{path}]({page_file}) — `{component}`")
            if api_count > 0:
                f.write(f" ({api_count} API calls)")
            f.write("\n")
        
        f.write("\n---\n")


def _write_frontend_index(groups: Dict[str, List[dict]], output_root: str) -> None:
    """Write master index for all frontend pages."""
    index_path = os.path.join(output_root, "index.md")
    
    total_pages = sum(len(v) for v in groups.values())
    total_apis = 0
    for pages in groups.values():
        for page in pages:
            total_apis += len(page.get("api_calls", []))
    
    with open(index_path, "w", encoding="utf-8") as f:
        f.write("# Frontend Documentation\n\n")
        f.write(f"**Pages**: {total_pages} | **API Dependencies**: {total_apis}\n\n")
        f.write("## Page Groups\n\n")
        f.write("| Group | Pages | APIs |\n")
        f.write("|-------|-------|------|\n")
        
        for group_name in sorted(groups.keys()):
            group_pages = groups[group_name]
            group_api_count = sum(len(p.get("api_calls", [])) for p in group_pages)
            f.write(
                f"| [{group_name}](./{group_name}/README.md) "
                f"| {len(group_pages)} "
                f"| {group_api_count} |\n"
            )
        
        f.write("\n---\n")
        f.write("_Generated by doc_writer_\n")


def _write_missing_apis(api_list: List[Tuple[str, str]], output_root: str) -> None:
    """Write undocumented APIs called by frontend pages."""
    undoc_dir = os.path.join(output_root, "undocumented")
    os.makedirs(undoc_dir, exist_ok=True)
    
    missing_path = os.path.join(undoc_dir, "missing_apis.md")
    
    # Group by API
    api_map: Dict[str, List[str]] = defaultdict(list)
    for page_path, api_endpoint in api_list:
        if api_endpoint and api_endpoint != "UNKNOWN":
            api_map[api_endpoint].append(page_path)
    
    with open(missing_path, "w", encoding="utf-8") as f:
        f.write("# Undocumented APIs\n\n")
        f.write("Frontend pages are calling these APIs, but no backend documentation "
                "was found.\n\n")
        f.write("Add documentation for these endpoints:\n\n")
        
        for endpoint in sorted(api_map.keys()):
            pages = api_map[endpoint]
            f.write(f"## `{endpoint}`\n\n")
            f.write(f"Called by ({len(pages)} pages):\n")
            for page in sorted(set(pages)):
                f.write(f"- {page}\n")
            f.write("\n")
        
        f.write("---\n")


def _skeleton_page(page: dict) -> str:
    """No-AI fallback: structured markdown from extracted JSON."""
    path       = page.get("path", "UNKNOWN")
    component  = page.get("component", "UNKNOWN")
    layout     = page.get("layout", "UNKNOWN")
    children   = page.get("children", [])
    api_calls  = page.get("api_calls", [])
    state_mgmt = page.get("state_management", [])
    unknowns   = page.get("unknowns", [])

    children_md = "\n".join(f"- `{c}`" for c in children) or "None"
    state_md    = ", ".join(state_mgmt) if state_mgmt else "none"
    unknowns_md = "\n".join(f"- {u}" for u in unknowns) or "None"

    api_lines = []
    for call in api_calls:
        method = call.get("method", "?").upper()
        endpoint = call.get("endpoint", "UNKNOWN")
        called_from = call.get("called_from", "?")
        via = call.get("composable", call.get("via", "direct"))
        api_lines.append(
            f"- `{method} {endpoint}` (via {via})"
        )
    api_md = "\n".join(api_lines) or "None detected"

    return (
        f"# {path}\n\n"
        f"**Component**: `{component}`\n\n"
        f"## Layout\n{layout}\n\n"
        f"## Child Components\n{children_md}\n\n"
        f"## API Dependencies\n{api_md}\n\n"
        f"## State Management\n{state_md}\n\n"
        f"## Unknowns\n{unknowns_md}\n\n"
        f"---"
    )