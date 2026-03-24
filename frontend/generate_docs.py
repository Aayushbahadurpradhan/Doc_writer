"""
generate_docs.py — Step 2 of the frontend pipeline.

Generates frontend documentation organized by route group.

Output structure:
  docs/frontend/
    index.md                         <- master index
    admin/
      README.md                      <- /admin group overview
      admin_dashboard.md             <- /admin
      admin_users.md                 <- /admin/users
    bill/
      README.md
      bill_list.md
      bill_detail.md
    undocumented/
      README.md                      <- components with no route or file
      missing_apis.md                <- APIs called but not in backend docs

Each page .md includes:
  - Route / component / source file
  - Layout
  - Child components (imported locally)
  - Composables used
  - API dependencies (endpoint + method + caller + route)
  - State management
  - Unknowns / warnings
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


def _extract_page_group(page: dict) -> str:
    """
    Determine the documentation folder group for a page.

    - Pages with path=UNKNOWN or missing component file → 'undocumented'
    - /admin/*   → 'admin'
    - /bill/list → 'bill'
    - /          → 'home'
    - /:id       → 'detail'
    """
    # Undocumented: no route recorded OR component file not found
    path = page.get("path", "UNKNOWN")
    has_no_file = any("Component file not found" in u for u in page.get("unknowns", []))
    if path == "UNKNOWN" or has_no_file:
        return "undocumented"

    if not path or path == "/":
        return "home"

    parts = [p for p in path.strip("/").split("/") if p and not p.startswith(":")]
    if not parts:
        return "detail"

    group = parts[0].lower()
    # Keep plural as-is (admin, bills, agents all make sense as groups)
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
    Generate frontend docs organized by route group.
    Pages without a route or whose component file is missing go to undocumented/.
    """
    output_root = os.path.abspath(output_root)
    os.makedirs(output_root, exist_ok=True)

    # ── Group pages ───────────────────────────────────────────────────────────
    groups: Dict[str, List[dict]] = defaultdict(list)
    all_missing_apis: List[Tuple[str, str]] = []

    for page in pages:
        group = _extract_page_group(page)
        groups[group].append(page)

        for api_call in page.get("api_calls", []):
            endpoint = api_call.get("endpoint", "")
            if endpoint and endpoint != "UNKNOWN":
                all_missing_apis.append((page.get("path", "UNKNOWN"), endpoint))

    # ── Generate per-group documentation ─────────────────────────────────────
    sys_msg = pages_md_system()

    for group_name in sorted(groups.keys()):
        group_pages = groups[group_name]
        group_dir   = os.path.normpath(os.path.join(output_root, group_name))
        os.makedirs(group_dir, exist_ok=True)

        _write_group_readme(group_name, group_pages, group_dir)

        for i, page in enumerate(group_pages):
            path       = page.get("path", "UNKNOWN")
            page_file  = _safe_page_filename(path)
            page_path  = os.path.join(group_dir, page_file)

            print(f"  [PAGE {i+1}/{len(group_pages)}] {group_name}/{page_file}")

            if no_ai or not config.use_ai:
                content = _skeleton_page(page)
            else:
                prompt = pages_md_prompt(page)
                try:
                    content = call_ai(prompt, config, system=sys_msg, max_tokens=1500)
                except Exception as e:
                    content = "[AI failed: {}]".format(str(e)[:80])
                if not content or content.startswith("[AI failed"):
                    print(f"     [WARN] AI failed - using skeleton")
                    content = _skeleton_page(page)
                if config.delay > 0:
                    time.sleep(config.delay)

            os.makedirs(os.path.dirname(page_path), exist_ok=True)
            with open(page_path, "w", encoding="utf-8") as f:
                f.write(content)

    # ── Master index ──────────────────────────────────────────────────────────
    _write_frontend_index(groups, output_root)

    # ── Undocumented APIs ─────────────────────────────────────────────────────
    _write_missing_apis(all_missing_apis, output_root)

    documented   = sum(len(v) for k, v in groups.items() if k != "undocumented")
    undocumented = len(groups.get("undocumented", []))
    print(f"\n  [OK] Frontend docs -> {output_root}")
    print(f"     Groups   : {', '.join(k for k in sorted(groups.keys()) if k != 'undocumented')}")
    print(f"     Documented   : {documented} pages")
    if undocumented:
        print(f"     Undocumented : {undocumented} components (no route or file)")


def _write_group_readme(group: str, pages: List[dict], group_dir: str) -> None:
    """Write README.md for each page group with rich detail."""
    readme_path = os.path.join(group_dir, "README.md")

    is_undoc = group == "undocumented"

    with open(readme_path, "w", encoding="utf-8") as f:
        if is_undoc:
            f.write("# Undocumented Components\n\n")
            f.write(
                "These components were detected but either have no route mapping "
                "or their source file could not be located.\n\n"
            )
        else:
            f.write(f"# /{group} Pages\n\n")
            f.write(f"Route prefix: **`/{group}`**\n\n")

        f.write(f"## Summary\n\n")
        f.write(f"| Route | Component | Layout | Children | APIs | State | Example URL |\n")
        f.write(f"|-------|-----------|--------|----------|------|-------|-------------|\n")

        for page in pages:
            path                = page.get("path", "UNKNOWN")
            component           = page.get("component", "UNKNOWN")
            layout              = page.get("layout", "UNKNOWN")
            children            = page.get("children", [])
            template_components = page.get("template_components", [])
            api_calls           = page.get("api_calls", [])
            state_mgmt          = page.get("state_management", [])
            example_url         = page.get("example_url", "N/A")

            page_file    = _safe_page_filename(path)
            child_count  = len(children) or len(template_components)
            state_short  = ", ".join(
                dict.fromkeys(s.split(":")[0] for s in state_mgmt)
            ) if state_mgmt else "—"
            layout_short = layout if layout != "UNKNOWN" else "—"

            f.write(
                f"| [{path}]({page_file}) "
                f"| `{component}` "
                f"| {layout_short} "
                f"| {child_count} "
                f"| {len(api_calls)} "
                f"| {state_short} "
                f"| `{example_url}` |\n"
            )

        f.write("\n---\n")


def _write_frontend_index(groups: Dict[str, List[dict]], output_root: str) -> None:
    """Write master index for all frontend pages."""
    index_path = os.path.join(output_root, "index.md")

    # Separate documented from undocumented
    doc_groups   = {k: v for k, v in groups.items() if k != "undocumented"}
    undoc_pages  = groups.get("undocumented", [])

    total_pages  = sum(len(v) for v in doc_groups.values())
    total_apis   = sum(
        len(p.get("api_calls", [])) for pages in doc_groups.values() for p in pages
    )

    with open(index_path, "w", encoding="utf-8") as f:
        f.write("# Frontend Documentation\n\n")
        f.write(f"**Documented pages**: {total_pages} | **API dependencies**: {total_apis}")
        if undoc_pages:
            f.write(f" | **Undocumented**: {len(undoc_pages)}")
        f.write("\n\n")

        f.write("## Page Groups\n\n")
        f.write("| Group | Route Prefix | Pages | APIs |\n")
        f.write("|-------|-------------|-------|------|\n")

        for group_name in sorted(doc_groups.keys()):
            gp       = doc_groups[group_name]
            api_cnt  = sum(len(p.get("api_calls", [])) for p in gp)
            f.write(
                f"| [{group_name}](./{group_name}/README.md) "
                f"| `/{group_name}` "
                f"| {len(gp)} "
                f"| {api_cnt} |\n"
            )

        if undoc_pages:
            f.write(
                f"| [undocumented](./undocumented/README.md) "
                f"| — "
                f"| {len(undoc_pages)} "
                f"| — |\n"
            )

        f.write("\n---\n")
        f.write("_Generated by doc_writer_\n")


def _write_missing_apis(api_list: List[Tuple[str, str]], output_root: str) -> None:
    """Write undocumented APIs called by frontend pages into undocumented/missing_apis.md."""
    undoc_dir = os.path.join(output_root, "undocumented")
    os.makedirs(undoc_dir, exist_ok=True)

    # Filter out UNKNOWN endpoints
    real_apis = [(page, ep) for page, ep in api_list if ep and ep != "UNKNOWN"]
    if not real_apis:
        return

    missing_path = os.path.join(undoc_dir, "missing_apis.md")

    # Group by endpoint
    api_map: Dict[str, List[str]] = defaultdict(list)
    for page_path, endpoint in real_apis:
        api_map[endpoint].append(page_path)

    with open(missing_path, "w", encoding="utf-8") as f:
        f.write("# Missing Backend Documentation\n\n")
        f.write(
            "These API endpoints are called by frontend pages but do not have "
            "corresponding backend documentation.\n\n"
        )
        f.write(f"**Total**: {len(api_map)} endpoints\n\n")

        for endpoint in sorted(api_map.keys()):
            pages = sorted(set(api_map[endpoint]))
            f.write(f"## `{endpoint}`\n\n")
            f.write(f"Called from {len(pages)} page(s):\n\n")
            for page in pages:
                f.write(f"- `{page}`\n")
            f.write("\n")

        f.write("---\n")


def _skeleton_page(page: dict) -> str:
    """No-AI fallback: produce structured markdown from extracted page data."""
    path                = page.get("path", "UNKNOWN")
    component           = page.get("component", "UNKNOWN")
    comp_file           = page.get("component_file") or "not found"
    example_url         = page.get("example_url", "N/A")
    layout              = page.get("layout", "UNKNOWN")
    children            = page.get("children", [])            # local imports
    template_components = page.get("template_components", []) # template scan
    composables         = page.get("composables", [])
    api_calls           = page.get("api_calls", [])
    state_mgmt          = page.get("state_management", [])
    unknowns            = page.get("unknowns", [])

    # ── Child components ──────────────────────────────────────────────────────
    if children:
        children_md = "\n".join(f"- `{c}` _(imported)_" for c in children)
    elif template_components:
        children_md = "\n".join(f"- `{c}`" for c in template_components)
    else:
        children_md = "_None detected_"

    # ── Composables ───────────────────────────────────────────────────────────
    composables_md = (
        "\n".join(f"- `{c}()`" for c in composables)
        if composables else "_None detected_"
    )

    # ── State management ──────────────────────────────────────────────────────
    if state_mgmt:
        by_type: Dict[str, List[str]] = defaultdict(list)
        for s in state_mgmt:
            parts = s.split(":", 1)
            by_type[parts[0]].append(parts[1] if len(parts) > 1 else parts[0])
        state_lines = []
        for stype, names in by_type.items():
            state_lines.append(f"**{stype}**: {', '.join(f'`{n}`' for n in names)}")
        state_md = "\n".join(state_lines)
    else:
        state_md = "_None detected_"

    # ── API calls ─────────────────────────────────────────────────────────────
    api_lines = []
    for call in api_calls:
        method      = call.get("method", "?").upper()
        endpoint    = call.get("endpoint", "UNKNOWN")
        called_from = call.get("called_from", "?")
        composable  = call.get("composable")
        via         = call.get("via", "direct")
        source_note = f"via `{composable}()`" if composable else f"in `{called_from}`"
        api_lines.append(f"| `{method}` | `{endpoint}` | {source_note} | {via} |")

    if api_lines:
        api_md = (
            "| Method | Endpoint | Source | Transport |\n"
            "|--------|----------|--------|-----------|\n"
            + "\n".join(api_lines)
        )
    else:
        api_md = "_None detected_"

    # ── Unknowns / warnings ───────────────────────────────────────────────────
    unknowns_md = (
        "\n".join(f"- {u}" for u in unknowns)
        if unknowns else "_None_"
    )

    return (
        f"# `{path}`\n\n"
        f"| Field | Value |\n"
        f"|-------|-------|\n"
        f"| **Component** | `{component}` |\n"
        f"| **Source file** | `{comp_file}` |\n"
        f"| **Layout** | {layout} |\n"
        f"| **Example URL** | `{example_url}` |\n\n"
        f"> To verify this page open: **[{example_url}]({example_url})**\n\n"
        f"## Child Components\n\n"
        f"{children_md}\n\n"
        f"## Composables Used\n\n"
        f"{composables_md}\n\n"
        f"## Backend API Dependencies\n\n"
        f"{api_md}\n\n"
        f"## State Management\n\n"
        f"{state_md}\n\n"
        f"## Warnings\n\n"
        f"{unknowns_md}\n\n"
        f"---"
    )