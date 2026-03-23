"""
All AI prompts for backend (Laravel) analysis.
"""


def business_md_system() -> str:
    return (
        "You are a senior technical writer and business analyst documenting a Laravel PHP API.\n\n"
        "Your documentation must be:\n"
        "- SPECIFIC: use actual variable names, field names, and values from the code\n"
        "- COMPLETE: cover every business rule, validation, condition, and side effect found\n"
        "- BUSINESS-FOCUSED: explain WHY this endpoint exists, not just what it does\n"
        "- HONEST: if something is unclear, say 'inferred from code' — never invent details\n\n"
        "STRICT RULES:\n"
        "- DO NOT invent logic not present in the JSON or code\n"
        "- DO NOT infer missing steps\n"
        "- If a field is missing or unknown → write 'UNKNOWN'\n"
        "- Be technical and precise\n"
    )


def business_md_prompt(json_data: dict) -> str:
    import json
    route = json_data
    method = route.get("method", "UNKNOWN")
    path = route.get("full_path", route.get("path", "UNKNOWN"))
    controller = route.get("controller", "UNKNOWN")
    action = route.get("action", "UNKNOWN")
    steps = route.get("steps", [])
    validation = route.get("validation", {})
    response = route.get("response", {})
    queries = route.get("queries", [])
    errors = route.get("errors", [])
    unknowns = route.get("unknowns", [])

    steps_md = "\n".join(
        f"{i+1}. [{s.get('type','?').upper()}] {s.get('detail', s.get('target', s.get('name', 'UNKNOWN')))}"
        for i, s in enumerate(steps)
    ) or "UNKNOWN"

    validation_md = (
        "\n".join(f"- `{k}`: {v}" for k, v in validation.items())
        if validation else "None detected"
    )

    response_md = (
        f"Type: {response.get('type', 'UNKNOWN')}\n"
        f"Fields: {', '.join(response.get('fields', [])) or 'UNKNOWN'}"
        if response else "UNKNOWN"
    )

    queries_md = "\n".join(
        f"- [{q.get('type','?').upper()}] {q.get('model', q.get('query', 'UNKNOWN'))} — {q.get('operation','?')}"
        for q in queries
    ) or "None detected"

    errors_md = "\n".join(
        f"- {e.get('type','?')} {e.get('code','')}: {e.get('detail','')}"
        for e in errors
    ) or "None detected"

    unknowns_md = "\n".join(f"- {u}" for u in unknowns) or "None"

    return (
        f"Generate markdown documentation for the following API endpoint.\n"
        f"Output ONLY the markdown. No intro text.\n\n"
        f"INPUT JSON:\n{json.dumps(route, indent=2)}\n\n"
        f"─────────────────────────────────────────────────────────\n\n"
        f"# API: {path}\n\n"
        f"## Method\n{method}\n\n"
        f"## Description\n"
        f"[Brief description based ONLY on available data. If unknown write UNKNOWN.]\n\n"
        f"## Execution Flow\n{steps_md}\n\n"
        f"## Request Validation\n{validation_md}\n\n"
        f"## Response\n{response_md}\n\n"
        f"## Database Queries\n{queries_md}\n\n"
        f"## Error Handling\n{errors_md}\n\n"
        f"## Unknowns\n{unknowns_md}\n\n"
        f"---"
    )


def legacy_sql_system() -> str:
    return (
        "You are a SQL documentation generator auditing a Laravel PHP API.\n\n"
        "STRICT RULES:\n"
        "- DO NOT invent table names or column names not present in the data\n"
        "- Classify each query as: eloquent | query_builder | raw_sql\n"
        "- Output clean SQL comments + reconstructed query where possible\n"
        "- If query cannot be reconstructed → mark as UNKNOWN with a note\n"
        "- Use ? for bound parameters\n"
    )


def legacy_sql_prompt(json_data: dict) -> str:
    import json
    return (
        f"Extract and classify all database queries from this JSON.\n\n"
        f"For each query output:\n"
        f"```\n"
        f"-- Type: [eloquent|query_builder|raw_sql]\n"
        f"-- Endpoint: METHOD /path\n"
        f"-- Model/Table: name\n"
        f"-- Operation: SELECT|INSERT|UPDATE|DELETE\n"
        f"<SQL here or -- UNKNOWN: reason>\n"
        f"```\n\n"
        f"INPUT:\n{json.dumps(json_data, indent=2)}"
    )


def validation_prompt(routes: list, controllers: list, queries: list) -> str:
    import json
    return (
        f"Review the following extracted API data for completeness.\n\n"
        f"Routes extracted: {json.dumps(routes, indent=2)}\n\n"
        f"Controllers parsed: {json.dumps(controllers, indent=2)}\n\n"
        f"Queries found: {json.dumps(queries, indent=2)}\n\n"
        f"Identify:\n"
        f"1. Routes extracted but not documented\n"
        f"2. Controllers referenced in routes but not parsed\n"
        f"3. Queries detected but not classified\n"
        f"4. UNKNOWN entries that need manual review\n\n"
        f"Output JSON only:\n"
        f"{{\n"
        f'  "undocumented_routes": [],\n'
        f'  "unparsed_controllers": [],\n'
        f'  "unclassified_queries": [],\n'
        f'  "unknowns_requiring_review": []\n'
        f"}}"
    )
