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
    page = json_data
    path = page.get("path", "UNKNOWN")
    component = page.get("component", "UNKNOWN")
    layout = page.get("layout", "UNKNOWN")
    children = page.get("children", [])
    api_calls = page.get("api_calls", [])
    state_mgmt = page.get("state_management", [])
    unknowns = page.get("unknowns", [])

    children_md = "\n".join(f"- {c}" for c in children) or "None"
    state_md = ", ".join(state_mgmt) if state_mgmt else "none"
    unknowns_md = "\n".join(f"- {u}" for u in unknowns) or "None"

    api_md_lines = []
    for call in api_calls:
        api_md_lines.append(
            f"- Endpoint: `{call.get('endpoint', 'UNKNOWN')}`\n"
            f"  - Method: {call.get('method', 'UNKNOWN')}\n"
            f"  - Called from: `{call.get('called_from', 'UNKNOWN')}`\n"
            f"  - Via: {call.get('via', 'direct') or call.get('composable', 'direct')}"
        )
    api_md = "\n".join(api_md_lines) or "None detected"

    return (
        f"Generate markdown documentation for the following frontend page.\n"
        f"Output ONLY the markdown. No intro text.\n\n"
        f"INPUT JSON:\n{json.dumps(page, indent=2)}\n\n"
        f"─────────────────────────────────────────────────────────\n\n"
        f"# Page: {path}\n\n"
        f"## Component\n`{component}`\n\n"
        f"## Layout\n{layout}\n\n"
        f"## Child Components\n{children_md}\n\n"
        f"## API Dependencies\n{api_md}\n\n"
        f"## State Management\n{state_md}\n\n"
        f"## Unknowns\n{unknowns_md}\n\n"
        f"---"
    )
