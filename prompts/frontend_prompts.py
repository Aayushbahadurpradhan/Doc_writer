"""
All AI prompts for frontend (Vue/React) analysis.
"""

from typing import List


def pages_md_system() -> str:
    return (
        "You are a frontend documentation generator.\n\n"
        "STRICT RULES:\n"
        "- DO NOT invent component structure not in the JSON\n"
        "- If something is unknown → write 'UNKNOWN'\n"
        "- Focus on API dependencies as the primary concern\n"
        "- Only document what is statically visible in the data\n"
    )


def pages_md_prompt(json_data: dict) -> str:
    import json

    from frontend.detect_pages import _build_example_url

    page                = json_data
    path                = page.get("path", "UNKNOWN")
    component           = page.get("component", "UNKNOWN")
    comp_file           = page.get("component_file") or page.get("file") or "not found"
    layout              = page.get("layout", "UNKNOWN")
    children            = page.get("children", [])
    template_components = page.get("template_components", [])
    composables         = page.get("composables", [])
    api_calls           = page.get("api_calls", [])
    state_mgmt          = page.get("state_management", [])
    unknowns            = page.get("unknowns", [])
    code_snippet        = page.get("code_snippet", "")

    # Recompute example_url when cached as None / "N/A" / null
    _cached_url = page.get("example_url")
    if not _cached_url or str(_cached_url).strip() in ("N/A", "None", "null", ""):
        example_url = _build_example_url(path) or "N/A"
    else:
        example_url = str(_cached_url)

    # Verify link: only shown when a real URL is available
    if example_url and example_url != "N/A":
        verify_block = f"> To verify this page open: **[{example_url}]({example_url})**\n\n"
    else:
        verify_block = "> Route has no URL mapping — component may be a modal or child view.\n\n"

    # Merge children + template_components for display
    all_children = children or template_components
    children_md    = "\n".join(f"- {c}" for c in all_children) or "None"
    composables_md = "\n".join(f"- {c}()" for c in composables) or "None"
    state_md       = ", ".join(state_mgmt) if state_mgmt else "none"
    unknowns_md    = "\n".join(f"- {u}" for u in unknowns) or "None"

    api_md_lines = []
    for i, call in enumerate(api_calls, 1):
        composable   = call.get("composable")
        via          = call.get("via", "direct")
        via_child    = call.get("via_child")
        source       = f"via `{composable}()`" if composable else f"`{call.get('called_from', 'UNKNOWN')}`"
        if via_child:
            source += f" (child: `{via_child}`)"
        purpose      = call.get("purpose", "")
        trigger      = call.get("trigger", "")
        trigger_name = call.get("trigger_name", "")
        comment      = call.get("comment", "")
        fn_name      = call.get("function_name", "")
        dynamic      = call.get("dynamic", False)

        trigger_str  = ""
        if trigger_name:
            trigger_str = f"  - Trigger: `{trigger_name}` ({trigger})"
        elif trigger and trigger != "unknown":
            trigger_str = f"  - Trigger: {trigger}"

        purpose_str  = f"  - Purpose: {purpose}" if purpose and purpose != "inline call" else ""
        comment_str  = f"  - Code comment: `{comment}`" if comment else ""
        fn_str       = f"  - In function: `{fn_name}()`" if fn_name else ""
        dynamic_flag = "  - **DYNAMIC URL** — exact path resolved at runtime" if dynamic else ""

        parts = [
            f"### API Call {i}: `{call.get('endpoint', 'UNKNOWN')}`",
            f"  - Method: `{call.get('method', 'UNKNOWN')}`",
            f"  - Source: {source}",
            f"  - Transport: `{via}`",
        ]
        for detail in (trigger_str, fn_str, purpose_str, comment_str, dynamic_flag):
            if detail:
                parts.append(detail)
        api_md_lines.append("\n".join(parts))
    api_md = "\n\n".join(api_md_lines) or "None detected"

    # Seed EXCEL_DATA — one object per API call (AI fills in the <<fill>> placeholders)
    excel_seed = []
    screen_name = (
        component
        .replace(".vue", "").replace(".jsx", "").replace(".tsx", "")
        .replace("_", " ").replace("-", " ")
    )
    effective_calls = api_calls or [{}]
    for call in effective_calls:
        excel_seed.append({
            "screen_name": screen_name,
            "route": path,
            "component_path": comp_file if comp_file != "not found" else "",
            "api_endpoint": call.get("endpoint", ""),
            "http_method": call.get("method", ""),
            "request_payload": "<<fill: list all query params / body fields with type and required status>>",
            "conditional_logic": "<<fill: describe conditional UI rendering, field visibility rules, business conditions>>",
            "validation_rules": "<<fill: list all form/input validation rules in this component>>",
        })

    return (
        f"Generate markdown documentation for the following frontend page.\n"
        f"Output ONLY the markdown followed by an EXCEL_DATA JSON block. No intro text.\n\n"
        f"Analyze the COMPONENT SOURCE CODE below to fill in:\n"
        f"  - Request Payload / Query Parameters: all API call params/body fields\n"
        f"  - Conditional Logic: field visibility rules, business conditions, show/hide logic\n"
        f"  - Validation Rules: all form/input validation rules\n"
        f"  - For EACH API call: describe its specific business purpose based on when/where it fires\n\n"
        f"IMPORTANT — API calls:\n"
        f"  - Every call listed under 'Backend API Dependencies' is a REAL occurrence — document all of them\n"
        f"  - Multiple calls to the same endpoint with different triggers (e.g. load vs. save) "
        f"    represent DIFFERENT business operations — treat them separately\n"
        f"  - For DYNAMIC urls, note they are computed at runtime and describe what they likely contain\n\n"
        f"INPUT JSON:\n{json.dumps(page, indent=2)}\n\n"
        f"COMPONENT SOURCE CODE (analyze for payload fields, validation, conditional logic):\n"
        f"```\n{code_snippet[:3000]}\n```\n\n"
        f"─────────────────────────────────────────────────────────\n\n"
        f"# Page: `{path}`\n\n"
        f"| Field | Value |\n"
        f"|-------|-------|\n"
        f"| **Component** | `{component}` |\n"
        f"| **Source file** | `{comp_file}` |\n"
        f"| **Layout** | {layout} |\n"
        f"| **Example URL** | `{example_url}` |\n\n"
        f"{verify_block}"
        f"## Child Components\n{children_md}\n\n"
        f"## Composables Used\n{composables_md}\n\n"
        f"## Backend API Dependencies\n\n{api_md}\n\n"
        f"## Request Payload / Query Parameters\n"
        f"_For each API call above, list all query parameters or request body fields "
        f"with name, type, required/optional, and description. "
        f"Group by API call number if there are multiple calls._\n\n"
        f"## Business Logic per API Call\n"
        f"_For each API call above: describe what business operation it performs, "
        f"when it fires (lifecycle, user action, etc.), what data it returns/sends, "
        f"and how the UI reacts to the response (loading state, error handling, redirect, etc.)._\n\n"
        f"## Conditional Logic\n"
        f"_Describe conditional UI rendering, field visibility rules, and business logic conditions found in this component._\n\n"
        f"## Validation Rules\n"
        f"_List all form/input validation rules applied on this page (field, rule, error message if known)._\n\n"
        f"## State Management\n{state_md}\n\n"
        f"## Warnings\n{unknowns_md}\n\n"
        f"---\n\n"
        f"After the markdown above, output EXACTLY this block.\n"
        f"Replace every <<fill: ...>> with real values derived from the source code analysis.\n"
        f"Use plain text (no markdown) inside all JSON string values.\n\n"
        f"<!-- EXCEL_DATA\n"
        f"{json.dumps(excel_seed, indent=2)}\n"
        f"-->"
    )


def undocumented_api_prompt(endpoint: str, usages: List[dict]) -> str:
    """
    Prompt for AI to document an undocumented backend API endpoint.

    `usages` is a list of dicts with keys:
        page_path, page_component, method, via, composable, called_from
    """
    import json

    pages_using = sorted(set(u["page_path"] for u in usages))
    methods = sorted(set(u["method"] for u in usages))

    usage_rows = []
    for u in usages:
        source = (
            f"via `{u['composable']}()`"
            if u.get("composable")
            else f"in `{u.get('called_from', 'UNKNOWN')}`"
        )
        usage_rows.append({
            "page":      u["page_path"],
            "component": u.get("page_component", "UNKNOWN"),
            "method":    u["method"],
            "source":    source,
            "transport": u["via"],
        })

    return (
        f"Generate markdown documentation for an undocumented backend API endpoint "
        f"that is called by the frontend but has no backend documentation yet.\n"
        f"Output ONLY markdown. No intro text, no explanation outside the markdown.\n\n"
        f"ENDPOINT: `{endpoint}`\n"
        f"HTTP METHODS USED: {', '.join(f'`{m}`' for m in methods)}\n"
        f"USED BY {len(pages_using)} PAGE(S): {', '.join(f'`{p}`' for p in pages_using)}\n\n"
        f"USAGE DATA (all calls detected):\n{json.dumps(usage_rows, indent=2)}\n\n"
        f"─────────────────────────────────────────────────────────\n\n"
        f"Generate a documentation page with these exact sections:\n\n"
        f"# Undocumented API: `{endpoint}`\n\n"
        f"1. **Summary table** — endpoint, HTTP methods, total pages using it, "
        f"   whether it requires auth (infer from path), likely resource type (infer from path)\n\n"
        f"2. **## Where It Is Used** — markdown table: Page/Route | Method | Source | Transport\n"
        f"   List every row from USAGE DATA. If the same endpoint is used by multiple pages, "
        f"   show ALL of them.\n\n"
        f"3. **## How It Can Be Used** — infer from the endpoint path what this API likely does:\n"
        f"   - What HTTP method(s) it accepts and why\n"
        f"   - What parameters or request body it likely needs (path params, query params, body)\n"
        f"   - What the response likely looks like\n"
        f"   - Example usage (axios/fetch snippet)\n\n"
        f"4. **## Integration Notes** — per-page breakdown: for each page that calls this "
        f"   endpoint, describe HOW it uses the endpoint (reads list, submits form, etc.)\n\n"
        f"5. **## Documentation Status** — a warning block stating backend docs are missing "
        f"   and listing next steps to document this endpoint.\n\n"
        f"---"
    )


def resolve_dynamic_endpoint_prompt(
    raw_endpoint: str,
    method: str,
    called_from: str,
    context_snippet: str,
    env_config: dict,
    url_constants: dict,
) -> str:
    """
    Ask AI to infer the real (static) API endpoint from a short code snippet
    and available environment / constant context.

    Returns a short human-readable markdown block — NOT a full page doc.
    """
    env_block = ""
    if env_config:
        env_block = "\nKnown .env base URL variables:\n" + "\n".join(
            f"  {k} = {v}" for k, v in sorted(env_config.items())
        )
    const_block = ""
    if url_constants:
        const_block = "\nKnown URL constants from config files:\n" + "\n".join(
            f"  {k} = {v}" for k, v in sorted(url_constants.items())
        )

    return (
        f"The following JavaScript/TypeScript code makes a `{method}` HTTP call "
        f"but the URL could not be determined statically.\n\n"
        f"File: `{called_from}`\n"
        f"Raw endpoint placeholder: `{raw_endpoint}`\n"
        f"{env_block}{const_block}\n\n"
        f"Code snippet around the call:\n"
        f"```js\n{context_snippet}\n```\n\n"
        f"Task: Analyse the code snippet and the available configuration above.\n"
        f"Respond ONLY with a short markdown block (no intro text) containing:\n\n"
        f"1. **Inferred endpoint pattern** — your best guess at the actual URL path "
        f"   (e.g. `/api/users/{{id}}` or `wss://example.com/ws`). "
        f"   If you cannot determine it, write `UNKNOWN`.\n"
        f"2. **Confidence** — High / Medium / Low\n"
        f"3. **Reasoning** — one or two sentences explaining your inference.\n"
        f"4. **How to verify** — one actionable step to confirm the endpoint "
        f"   (e.g. 'Search the backend routes for the matching controller method').\n"
    )
