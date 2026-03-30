"""
All AI prompts for backend (Laravel) analysis.

These are the canonical prompt implementations used by backend/generate_docs.py.
"""


def business_system() -> str:
    return (
        "You are a senior technical writer documenting a web application API.\n"
        "Your documentation must be:\n"
        "- SPECIFIC: use actual variable names and values from the code\n"
        "- COMPLETE: cover every business rule, validation, condition, and side effect\n"
        "- BUSINESS-FOCUSED: explain WHY this endpoint exists, not just what it does\n"
        "- HONEST: if something is unclear say 'inferred from code', never invent details\n"
        "Do NOT assume any specific industry unless it is explicitly visible in the code."
    )


def business_prompt(route: dict) -> str:
    method    = route.get("method", "?")
    path      = route.get("full_path", route.get("path", "?"))
    ctrl      = route.get("controller", "UNKNOWN").split("\\")[-1]
    action    = route.get("action", "UNKNOWN")
    snippet   = route.get("body_snippet", "")
    mw        = route.get("middleware", [])
    title     = path.rstrip("/").split("/")[-1] or "root"

    code_block = (
        "```php\n{}\n```".format(snippet)
        if snippet and snippet.strip()
        else "_No code snippet available._"
    )

    return (
        "Document this API endpoint completely. Output ONLY markdown. No intro text.\n\n"
        "--- ENDPOINT METADATA ---\n"
        "Endpoint   : {} {}\n"
        "Controller : {}@{}\n"
        "Middleware : {}\n"
        "---\n\n"
        "PHP Code:\n{}\n\n"
        "--- INSTRUCTIONS ---\n"
        "Read the code and extract EVERY detail:\n"
        "- All $request->input() / $request->xxx fields -> input parameters\n"
        "- All if/else branches -> business logic conditions\n"
        "- All DB writes (insert/update/delete/save/create) -> side effects\n"
        "- All Mail::send / event() / dispatch() -> side effects\n"
        "- All auth checks (middleware, authorize, gate) -> access control\n"
        "---\n\n"
        "## {}\n\n"
        "| Field | Value |\n"
        "|-------|-------|\n"
        "| **Endpoint** | `{} {}` |\n"
        "| **Controller** | `{}@{}` |\n"
        "| **Auth Required** | [Yes/No] |\n"
        "| **HTTP Method** | {} |\n\n"
        "### Purpose\n"
        "[2-3 sentences: what this does, who calls it, why it exists]\n\n"
        "### Business Logic\n"
        "[Every rule, condition, validation, status transition as a separate bullet]\n\n"
        "### Input Parameters\n"
        "| Parameter | Type | Required | Description |\n"
        "|-----------|------|----------|-------------|\n"
        "[one row per input field, or: No parameters.]\n\n"
        "### Database Operations\n"
        "[numbered: 1. READ/WRITE table_name -- what and why, or: None]\n\n"
        "### Side Effects\n"
        "- **Emails**: [or None]\n"
        "- **Jobs/Queues**: [or None]\n"
        "- **Events**: [or None]\n"
        "- **External APIs**: [or None]\n"
        "- **Files**: [or None]\n\n"
        "---"
    ).format(
        method, path,
        ctrl, action,
        ", ".join(mw) if mw else "None",
        code_block,
        title,
        method, path,
        ctrl, action,
        method,
    )


def sql_system() -> str:
    return (
        "You are a database engineer auditing a Laravel PHP API.\n"
        "Convert ALL ORM and raw SQL patterns to clean, executable SQL.\n\n"
        "CRITICAL: every markdown table cell must contain EXACTLY ONE value.\n"
        "WRONG: | **Type** | eloquent | raw_sql |\n"
        "RIGHT: | **Type** | eloquent |\n\n"
        "ORM PATTERNS:\n"
        "::all() ::get() ::find() ::first() ::where()  -> SELECT\n"
        "::create([]) ::insert([]) new Model; save()   -> INSERT\n"
        "->update([]) $m->save() after fetch            -> UPDATE\n"
        "->delete() ::destroy()                         -> DELETE\n"
        "->with(rel)                                    -> LEFT JOIN\n"
        "DB::beginTransaction() DB::transaction()       -> Transaction: Yes\n"
        "query in foreach/while                         -> N+1 RISK\n\n"
        "RULES:\n"
        "- Use ? for bound parameters\n"
        "- Model to table: UserInfo=user_infos, PolicyHolder=policy_holders\n"
        "- Zero queries in code = output exactly one line: -- No database queries\n"
        "- Transaction field: write only Yes or No, nothing else\n"
        "- Do NOT produce empty blocks for routes with no DB calls"
    )


def sql_prompt(route: dict) -> str:
    import os as _os
    method  = route.get("method", "?")
    path    = route.get("full_path", route.get("path", "?"))
    ctrl    = route.get("controller", "UNKNOWN").split("\\")[-1]
    action  = route.get("action", "UNKNOWN")
    snippet = route.get("body_snippet", "")
    title   = path.rstrip("/").split("/")[-1] or "root"

    code_block = (
        "```php\n{}\n```".format(snippet)
        if snippet and snippet.strip()
        else "_No code available._"
    )

    return (
        "SQL audit: {} {} | {}@{}\n\n"
        "{}\n\n"
        "For each DB query found, output one block:\n\n"
        "### {} -- Query N: [what it does]\n\n"
        "| Field | Value |\n"
        "|-------|-------|\n"
        "| **Type** | [eloquent / raw_sql / db_facade] |\n"
        "| **Operation** | [SELECT / INSERT / UPDATE / DELETE / UPSERT] |\n"
        "| **Tables** | [table_name] |\n"
        "| **Columns Read** | [columns or *] |\n"
        "| **Columns Written** | [columns or None] |\n"
        "| **Conditions** | [WHERE clause or None] |\n"
        "| **Joins** | [JOIN type and tables or None] |\n"
        "| **Order / Group** | [ORDER BY or None] |\n"
        "| **Aggregates** | [COUNT/SUM/etc or None] |\n"
        "| **Transaction** | [Yes / No] |\n"
        "| **Soft Deletes** | [Yes / No] |\n\n"
        "```sql\n"
        "-- real executable SQL here\n"
        "-- use ? for bound parameters\n"
        "```\n\n"
        "**Optimization Notes:**\n"
        "- [one issue per bullet, or: No issues identified]\n\n"
        "---\n\n"
        "Output ONLY the query blocks. No intro sentence. No summary."
    ).format(method, path, ctrl, action, code_block, title)


def response_system() -> str:
    return (
        "You are a technical API documentation expert.\n"
        "Your task is to extract DETAILED API response structures from PHP controller code.\n\n"
        "CRITICAL RULES:\n"
        "- Extract ALL nested fields - don't say 'array', say what's IN the array\n"
        "- If array of objects, show fields of each object\n"
        "- Show nested object structure with all their fields\n"
        "- Use actual field names from code, not generic types\n"
        "- Be specific: instead of 'data': 'array', show 'data': { 'id': 'integer', 'name': 'string' }\n"
        "- Include array items structure: 'items': [ { 'field1': 'type', 'field2': 'type' } ]\n"
        "- Note pagination fields if present (total, per_page, current_page, etc.)\n"
        "- Only extract what's actually in the code - don't invent fields\n"
        "- Use descriptive hints for complex types, e.g., 'email|string', 'timestamp|datetime'"
    )


def response_prompt(route: dict) -> str:
    method    = route.get("method", "?")
    path      = route.get("full_path", route.get("path", "?"))
    ctrl      = route.get("controller", "UNKNOWN").split("\\")[-1]
    action    = route.get("action", "UNKNOWN")
    snippet   = route.get("body_snippet", "")

    code_block = (
        "```php\n{}\n```".format(snippet)
        if snippet and snippet.strip()
        else "_No code snippet available._"
    )

    return (
        "EXTRACT DETAILED API RESPONSE SCHEMA - Show actual field structure, not just types!\n\n"
        "--- ENDPOINT ---\n"
        "Method    : {}\n"
        "Path      : {}\n"
        "Controller: {}@{}\n"
        "---\n\n"
        "PHP Code:\n{}\n\n"
        "--- DETAILED EXTRACTION TASK ---\n"
        "ANALYZE THE CODE AND:\n"
        "1. Find the return statement - what does this action return?\n"
        "2. If returning an array - SHOW WHAT EACH ARRAY ITEM CONTAINS\n"
        "3. If returning an object - LIST ALL FIELDS\n"
        "4. If returning nested objects - SHOW THE FULL STRUCTURE\n"
        "5. Use actual field names from the code\n"
        "6. For each field, infer the data type from how it's used\n\n"
        "--- OUTPUT FORMAT ---\n\n"
        "**Response Type**: `[json|array_of_objects|nested_json|paginated_array|etc]`\n\n"
        "**Response Fields**:\n"
        "```json\n"
        "{{\n"
        "  \"field1\": \"type_with_description\",\n"
        "  \"field2\": [\n"
        "    {{\n"
        "      \"nested_field1\": \"type\",\n"
        "      \"nested_field2\": \"type\"\n"
        "    }}\n"
        "  ]\n"
        "}}\n"
        "```\n\n"
        "**Description**: [What this response represents and when it's returned]\n\n"
        "If structure cannot be determined:\n"
        "**Response**: Unable to determine detailed structure from available code."
    ).format(method, path, ctrl, action, code_block)


def legacy_sql_system() -> str:
    """Alias for sql_system() — kept for backwards compatibility."""
    return sql_system()


def legacy_sql_prompt(json_data: dict) -> str:
    """Generate legacy SQL prompt from a route dict."""
    return sql_prompt(json_data)


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
