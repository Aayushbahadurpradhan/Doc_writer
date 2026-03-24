"""
All AI prompts for frontend (Vue/React) analysis.
"""


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
    page                = json_data
    path                = page.get("path", "UNKNOWN")
    component           = page.get("component", "UNKNOWN")
    comp_file           = page.get("component_file") or "not found"
    example_url         = page.get("example_url", "N/A")
    layout              = page.get("layout", "UNKNOWN")
    children            = page.get("children", [])
    template_components = page.get("template_components", [])
    composables         = page.get("composables", [])
    api_calls           = page.get("api_calls", [])
    state_mgmt          = page.get("state_management", [])
    unknowns            = page.get("unknowns", [])

    # Merge children + template_components for display
    all_children = children or template_components
    children_md    = "\n".join(f"- {c}" for c in all_children) or "None"
    composables_md = "\n".join(f"- {c}()" for c in composables) or "None"
    state_md       = ", ".join(state_mgmt) if state_mgmt else "none"
    unknowns_md    = "\n".join(f"- {u}" for u in unknowns) or "None"

    api_md_lines = []
    for call in api_calls:
        composable  = call.get("composable")
        via         = call.get("via", "direct")
        source      = f"via `{composable}()`" if composable else f"`{call.get('called_from', 'UNKNOWN')}`"
        api_md_lines.append(
            f"- Endpoint: `{call.get('endpoint', 'UNKNOWN')}`\n"
            f"  - Method: {call.get('method', 'UNKNOWN')}\n"
            f"  - Source: {source}\n"
            f"  - Transport: {via}"
        )
    api_md = "\n".join(api_md_lines) or "None detected"

    return (
        f"Generate markdown documentation for the following frontend page.\n"
        f"Output ONLY the markdown. No intro text.\n\n"
        f"INPUT JSON:\n{json.dumps(page, indent=2)}\n\n"
        f"─────────────────────────────────────────────────────────\n\n"
        f"# Page: `{path}`\n\n"
        f"| Field | Value |\n"
        f"|-------|-------|\n"
        f"| **Component** | `{component}` |\n"
        f"| **Source file** | `{comp_file}` |\n"
        f"| **Layout** | {layout} |\n"
        f"| **Example URL** | `{example_url}` |\n\n"
        f"> To verify this page open: **[{example_url}]({example_url})**\n\n"
        f"## Child Components\n{children_md}\n\n"
        f"## Composables Used\n{composables_md}\n\n"
        f"## Backend API Dependencies\n{api_md}\n\n"
        f"## State Management\n{state_md}\n\n"
        f"## Warnings\n{unknowns_md}\n\n"
        f"---"
    )
