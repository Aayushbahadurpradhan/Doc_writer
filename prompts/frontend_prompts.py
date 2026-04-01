"""
All AI prompts for frontend (Vue/React) analysis.
"""

from typing import List


def pages_md_system() -> str:
    return (
        "You are a senior reverse engineer documenting frontend pages.\n\n"
        "Your PRIMARY job: for each frontend page, clearly show WHAT the page does "
        "and WHICH backend API endpoints it calls — like reading a browser Network tab.\n\n"
        "STRICT RULES:\n"
        "- DO NOT invent API calls not present in the JSON input\n"
        "- DO NOT add sections about child components, composables, state management, "
        "  request payloads, validation rules, or conditional logic\n"
        "- Write a concise 2-3 sentence description of what the page does (infer from "
        "  route name, component name, and the APIs it calls)\n"
        "- For every API call: describe WHEN it fires and WHAT it does for the user\n"
        "- If something is unknown → write 'UNKNOWN'\n"
    )


def pages_md_prompt(json_data: dict) -> str:
    import json

    from frontend.detect_pages import _build_example_url

    page         = json_data
    path         = page.get("path", "UNKNOWN")
    component    = page.get("component", "UNKNOWN")
    comp_file    = page.get("component_file") or page.get("file") or "not found"
    api_calls    = page.get("api_calls", [])
    unknowns     = page.get("unknowns", [])
    code_snippet = page.get("code_snippet", "")
    inferred     = page.get("inferred", False)

    # Recompute example_url when cached as None / "N/A" / null
    _cached_url = page.get("example_url")
    if not _cached_url or str(_cached_url).strip() in ("N/A", "None", "null", ""):
        example_url = _build_example_url(path) or "N/A"
    else:
        example_url = str(_cached_url)

    if example_url and example_url != "N/A":
        verify_block = f"> To verify: **[{example_url}]({example_url})**\n\n"
    else:
        verify_block = "> Route has no URL mapping — component may be a modal or child view.\n\n"

    inferred_note = " _(route inferred from file path)_" if inferred else ""

    # ── Build API network-trace table ─────────────────────────────────────────
    api_table_rows = []
    for i, call in enumerate(api_calls, 1):
        method       = (call.get("method") or "?").upper()
        endpoint     = call.get("endpoint", "UNKNOWN")
        trigger_name = call.get("trigger_name", "")
        trigger      = call.get("trigger", "unknown")
        composable   = call.get("composable")
        via_child    = call.get("via_child")
        purpose      = call.get("purpose", "")
        comment      = call.get("comment", "")
        dynamic      = call.get("dynamic", False)

        # When Called column
        if trigger_name:
            when = f"`{trigger_name}`"
        elif trigger == "lifecycle":
            when = "On page load"
        elif trigger == "event_handler":
            when = "On user action"
        elif trigger == "watcher":
            when = "On data change"
        elif trigger == "function_call":
            fn = call.get("function_name", "")
            when = f"In `{fn}()`" if fn else "On function call"
        else:
            when = "On function call"

        if composable:
            when += f" via `{composable}()`"
        if via_child:
            when += f" (child: `{via_child}`)"
        if dynamic:
            endpoint += " ⚡"

        purpose_hint = purpose if purpose and purpose != "inline call" else (comment or "—")
        api_table_rows.append(
            f"| {i} | `{method}` | `{endpoint}` | {when} | {purpose_hint} |"
        )

    if api_table_rows:
        api_table = (
            "| # | Method | Endpoint | When Called | Purpose |\n"
            "|---|--------|----------|-------------|--------|\n"
            + "\n".join(api_table_rows)
        )
    else:
        api_table = "_No API calls detected in this component._"

    # ── Excel seed ─────────────────────────────────────────────────────────────
    screen_name = (
        component
        .replace(".vue", "").replace(".jsx", "").replace(".tsx", "")
        .replace("_", " ").replace("-", " ")
    )
    excel_seed = []
    for call in (api_calls or [{}]):
        excel_seed.append({
            "screen_name":    screen_name,
            "route":          path,
            "component_path": comp_file if comp_file != "not found" else "",
            "frontend_url":   example_url if example_url != "N/A" else "",
            "api_endpoint":   call.get("endpoint", ""),
            "http_method":    call.get("method", ""),
            "when_called":    "<<fill: on page load / on button click / on form submit / on data change>>",
            "purpose":        "<<fill: describe what this API call does for the user and what data it returns>>",
        })

    # ── Unknowns row ──────────────────────────────────────────────────────────
    unknowns_md = ""
    if unknowns:
        unknowns_md = (
            "\n## Notes\n\n"
            + "\n".join(f"- {u}" for u in unknowns)
            + "\n\n"
        )

    return (
        f"You are reverse-engineering a frontend page. Output ONLY the markdown and "
        f"the EXCEL_DATA block. No intro text.\n\n"
        f"Analyze the component source code below and:\n"
        f"1. Write 2-3 sentences for '## What This Page Does' — describe the page's "
        f"   business purpose, what data it shows, what user actions it supports. "
        f"   Base this on the route name, component name, API endpoints called, and the source code.\n"
        f"2. Fill in the '## APIs Called by This Page' table — for each row, replace "
        f"   the 'When Called' and 'Purpose' columns with specific descriptions from the code. "
        f"   Preserve the exact Method and Endpoint values from the table below.\n"
        f"3. Do NOT add sections for child components, composables, state management, "
        f"   request payloads, validation rules, or conditional logic.\n\n"
        f"IMPORTANT — API call rules:\n"
        f"  - Every row in the table is a REAL detected call — keep all of them\n"
        f"  - Same endpoint with different triggers = different rows (keep both)\n"
        f"  - For ⚡ dynamic URLs, describe what the runtime value likely is\n\n"
        f"INPUT JSON:\n{json.dumps(page, indent=2)}\n\n"
        f"COMPONENT SOURCE CODE:\n"
        f"```\n{code_snippet[:3000]}\n```\n\n"
        f"─────────────────────────────────────────────────────────\n\n"
        f"# Page: `{path}`{inferred_note}\n\n"
        f"| Field | Value |\n"
        f"|-------|-------|\n"
        f"| **Component** | `{component}` |\n"
        f"| **Source File** | `{comp_file}` |\n"
        f"| **Frontend URL** | `{example_url}` |\n\n"
        f"{verify_block}"
        f"## What This Page Does\n\n"
        f"_[AI: write 2-3 sentences here]_\n\n"
        f"## APIs Called by This Page\n\n"
        f"{api_table}\n\n"
        f"{unknowns_md}"
        f"---\n\n"
        f"After the markdown above, output EXACTLY this block.\n"
        f"Replace every <<fill: ...>> with real values from the source code analysis.\n"
        f"Use plain text (no markdown) inside JSON string values.\n\n"
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
