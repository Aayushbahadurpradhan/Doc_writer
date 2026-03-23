"""
generate_docs.py - Backend documentation generator.

Groups routes by domain auto-detected from URL path.
No hardcoded domain names - works with any project.

Output per domain:
  docs/backend/{domain}/api.md
  docs/backend/{domain}/business.md
  docs/backend/{domain}/legacy_query.sql
  docs/backend/index.md
"""

import json
import os
import re
import sys
import time
from collections import defaultdict
from typing import Dict, List, Optional, Set

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.ai_client import AIConfig, call_ai


# =============================================================================
# DOMAIN DETECTION - purely from URL path, zero hardcoded names
# =============================================================================

def detect_domain(method, path, handler=""):
    """
    Auto-detect a domain grouping from the route path.

    Examples:
      GET  /v2/agent/{id}/commission   ->  agent
      POST /v1/health-enrollment       ->  health
      GET  /acm/get-sync-neura         ->  acm
      GET  /v1/manage-agents           ->  agent   (plural normalised)
      GET  /get-policies               ->  policy  (plural normalised)
    """
    clean = path.lower().strip("/")

    # Skip version and api prefix segments
    parts = [
        p for p in clean.split("/")
        if p
        and not re.match(r"^v\d+$", p)
        and p not in ("api", "api.access", "access")
    ]

    if not parts:
        return "general"

    first = parts[0]

    # Skip path params - use next segment
    if first.startswith("{") or first.startswith(":"):
        first = parts[1] if len(parts) > 1 else "general"

    # Strip leading verb words from hyphenated segments
    # e.g. "get-plan-overviews" -> "plan"
    # e.g. "manage-agents"      -> "agent"
    verb_prefixes = {
        "get", "set", "add", "create", "update", "delete", "remove",
        "upload", "download", "send", "view", "edit", "list", "manage",
        "check", "fetch", "generate", "process", "approve", "reject",
        "import", "export", "restore", "change", "reset", "save",
        "validate", "verify", "mark", "toggle", "submit", "bulk",
        "total", "show", "find", "search", "filter", "load", "build",
    }

    words = first.replace("-", "_").split("_")
    noun_words = words[:]
    while noun_words and noun_words[0] in verb_prefixes:
        noun_words = noun_words[1:]

    domain_word = noun_words[0] if noun_words else words[0]

    # Too short - use full first segment
    if len(domain_word) < 3:
        domain_word = first.split("-")[0].split("_")[0]

    # Normalise plurals to singular for cleaner folder names
    w = domain_word.lower()
    if w.endswith("ies") and len(w) > 4:
        w = w[:-3] + "y"          # policies -> policy
    elif w.endswith("ses") and len(w) > 4:
        w = w[:-2]                 # statuses -> status
    elif w.endswith("s") and len(w) > 4 and not w.endswith("ss"):
        w = w[:-1]                 # agents -> agent, groups -> group

    return w


# =============================================================================
# PROGRESS TRACKER
# =============================================================================

class ProgressTracker:
    def __init__(self, state_dir):
        self.path = os.path.join(state_dir, "progress.json")
        self.data = self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"apis": [], "ai_apis": [], "domains": []}

    def _save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    def api_done(self, method, path, ai=False):
        key = "{} {}".format(method, path)
        if ai:
            return key in self.data.get("ai_apis", [])
        return key in self.data.get("apis", [])

    def mark_api(self, method, path, ai=False):
        key = "{} {}".format(method, path)
        if key not in self.data["apis"]:
            self.data["apis"].append(key)
        if ai:
            if "ai_apis" not in self.data:
                self.data["ai_apis"] = []
            if key not in self.data["ai_apis"]:
                self.data["ai_apis"].append(key)
        self._save()

    def domain_done(self, domain, ai=False):
        key = ("ai_" if ai else "") + domain
        return key in self.data.get("domains", [])

    def mark_domain(self, domain, ai=False):
        key = ("ai_" if ai else "") + domain
        if key not in self.data["domains"]:
            self.data["domains"].append(key)
        self._save()

    def reset(self):
        self.data = {"apis": [], "ai_apis": [], "domains": []}
        self._save()
        print("  Progress reset.")


# =============================================================================
# AI PROMPTS
# =============================================================================

def _business_system():
    return (
        "You are a senior technical writer documenting a web application API.\n"
        "Your documentation must be:\n"
        "- SPECIFIC: use actual variable names and values from the code\n"
        "- COMPLETE: cover every business rule, validation, condition, and side effect\n"
        "- BUSINESS-FOCUSED: explain WHY this endpoint exists, not just what it does\n"
        "- HONEST: if something is unclear say inferred from code, never invent details\n"
        "Do NOT assume or mention any specific industry domain unless it is explicitly "
        "visible in the code. Only document what you can see."
    )


def _business_prompt(route):
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
        "Read the code carefully and extract EVERY detail:\n"
        "- All $request->input() / $request->xxx fields -> inputs\n"
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
        "[Every rule, condition, validation, status transition as separate bullets]\n\n"
        "### Input Parameters\n"
        "| Parameter | Type | Required | Description |\n"
        "|-----------|------|----------|-------------|\n"
        "[one row per input field or: No parameters.]\n\n"
        "### Database Operations\n"
        "[numbered list: 1. READ/WRITE table_name -- what and why, or: None]\n\n"
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


def _sql_system():
    return (
        "You are a database engineer auditing a Laravel PHP API.\n"
        "Convert ALL ORM and raw SQL patterns to clean, executable SQL.\n\n"
        "CRITICAL FORMAT RULE: every table cell must contain EXACTLY ONE value.\n"
        "WRONG: | **Type** | eloquent | raw_sql |\n"
        "RIGHT: | **Type** | eloquent |\n\n"
        "ORM PATTERNS:\n"
        "::all() ::get() ::find() ::first() ::where()  -> SELECT\n"
        "::create([]) ::insert([]) new Model save()    -> INSERT\n"
        "->update([]) $m->save() after fetch           -> UPDATE\n"
        "->delete() ::destroy()                        -> DELETE\n"
        "->with(rel)                                   -> LEFT JOIN\n"
        "DB::beginTransaction() DB::transaction()      -> Transaction: Yes\n"
        "query in foreach/while                        -> N+1 RISK\n\n"
        "RULES:\n"
        "- Use ? for bound parameters\n"
        "- Model to table: UserInfo=user_infos, PolicyHolder=policy_holders\n"
        "- Zero queries = output exactly: -- No database queries\n"
        "- Transaction: write only Yes or No\n"
        "- Do NOT produce empty blocks"
    )


def _sql_prompt(route):
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
        "For each DB query found output one block in this exact format:\n\n"
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
        "- [one issue per bullet or: No issues identified]\n\n"
        "---\n\n"
        "Output ONLY the query blocks. No intro sentence. No summary."
    ).format(method, path, ctrl, action, code_block, title)


# =============================================================================
# STATIC SQL FALLBACK (used when --no-ai)
# =============================================================================

_RAW_SQL_RE  = re.compile(
    r'DB::(?:select|statement|insert|update|delete)\s*\(\s*[\'"](.*?)[\'"]',
    re.DOTALL | re.I,
)
_DB_TABLE_RE = re.compile(r"DB::table\s*\(\s*['\"](\w+)['\"]\s*\)")
_MODEL_RE    = re.compile(
    r"\b([A-Z][a-zA-Z0-9]+)::"
    r"(?:where|find|findOrFail|create|update|delete|all|get|first|"
    r"firstOrFail|firstOrCreate|updateOrCreate|upsert|insert|"
    r"count|sum|avg|max|min|exists|paginate)\b"
)
_SKIP_MODELS = {
    "DB", "Auth", "Cache", "Config", "Cookie", "Event", "File", "Gate",
    "Hash", "Http", "Log", "Mail", "Queue", "Redirect", "Request",
    "Response", "Route", "Schema", "Session", "Storage", "Str",
    "Validator", "View", "Carbon", "Artisan", "App", "Bus",
    "Broadcast", "Password", "Arr",
}


def _model_to_table(model):
    s = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", model).lower()
    if s.endswith("y") and len(s) > 1 and s[-2] not in "aeiou":
        return s[:-1] + "ies"
    if s.endswith(("s", "sh", "ch", "x", "z")):
        return s + "es"
    return s + "s"


def _static_sql(snippet):
    if not snippet:
        return []
    results = []
    seen: Set[str] = set()
    for m in _RAW_SQL_RE.finditer(snippet):
        sql = m.group(1).strip()
        if sql not in seen:
            seen.add(sql)
            results.append({"kind": "raw_sql", "sql": sql})
    for m in _DB_TABLE_RE.finditer(snippet):
        table = m.group(1)
        key   = "dbtable:" + table
        if key not in seen:
            seen.add(key)
            results.append({"kind": "db_facade", "sql": "SELECT * FROM {};".format(table)})
    for m in _MODEL_RE.finditer(snippet):
        model = m.group(1)
        if model in _SKIP_MODELS:
            continue
        key = "eloquent:" + model
        if key not in seen:
            seen.add(key)
            table = _model_to_table(model)
            op    = m.group(0).split("::")[-1].upper()
            results.append({
                "kind": "eloquent",
                "sql":  "-- {}::{}\nSELECT * FROM {};".format(model, op, table),
            })
    return results


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def generate_all_docs(routes, docs_root, config, no_ai=False, force=False, state_dir=""):
    """
    Group routes by auto-detected domain and write per-domain docs.

    Output:
      docs/backend/
        index.md
        {domain}/
          api.md
          business.md
          legacy_query.sql
    """
    state_dir = state_dir or os.path.join(docs_root, "..", ".docwriter")
    os.makedirs(state_dir, exist_ok=True)
    os.makedirs(docs_root,  exist_ok=True)

    progress = ProgressTracker(state_dir)
    if force:
        progress.reset()

    use_ai = not no_ai and config.use_ai

    # Group by auto-detected domain
    domain_map: Dict[str, List[dict]] = defaultdict(list)
    for r in routes:
        domain = detect_domain(
            r.get("method", "GET"),
            r.get("full_path", r.get("path", "/")),
            r.get("controller", ""),
        )
        domain_map[domain].append(r)

    domains = sorted(domain_map.keys())
    total   = sum(len(v) for v in domain_map.values())
    print("\n  {} domains | {} routes".format(len(domains), total))
    print("  Domains: {}".format(", ".join(domains)))

    for domain in domains:
        domain_routes = domain_map[domain]
        ddir          = os.path.join(docs_root, domain)
        os.makedirs(ddir, exist_ok=True)

        # Find routes not yet documented
        pending = [
            r for r in domain_routes
            if not progress.api_done(
                r.get("method", "?"),
                r.get("full_path", r.get("path", "")),
                ai=use_ai,
            )
        ]

        if not pending and not force:
            print("  skip {} ({} routes -- all done)".format(domain, len(domain_routes)))
            continue

        routes_to_doc = domain_routes if force else pending
        print("\n  [{}] {} routes ({} pending)".format(
            domain, len(domain_routes), len(routes_to_doc)))

        # api.md -- always write, fast, no AI
        _write_api_md(domain_routes, os.path.join(ddir, "api.md"))
        print("    api.md written")

        # business.md
        _write_business_md(
            routes_to_doc,
            os.path.join(ddir, "business.md"),
            config, no_ai, progress,
            append=(bool(pending) and not force),
        )
        print("    business.md written")

        # legacy_query.sql
        _write_sql(
            routes_to_doc,
            os.path.join(ddir, "legacy_query.sql"),
            config, no_ai, progress,
            append=(bool(pending) and not force),
        )
        print("    legacy_query.sql written")

        progress.mark_domain(domain, ai=use_ai)

    # Master index
    _write_index(domain_map, docs_root)
    print("\n  index.md written")


# =============================================================================
# FILE WRITERS
# =============================================================================

def _write_api_md(routes, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("# API Reference\n\nTotal: **{}**\n\n---\n\n".format(len(routes)))
        for r in routes:
            method    = r.get("method", "?")
            full_path = r.get("full_path", r.get("path", "?"))
            ctrl      = r.get("controller", "UNKNOWN").split("\\")[-1]
            action    = r.get("action", "UNKNOWN")
            title     = full_path.rstrip("/").split("/")[-1] or "root"
            mw        = r.get("middleware", [])
            params    = r.get("params", [])
            queries   = r.get("queries", [])
            models    = list({q.get("model", "") for q in queries if q.get("model")})

            f.write("## {}\n\n".format(title))
            f.write("- **Endpoint**   : `{} {}`\n".format(method, full_path))
            f.write("- **Controller** : `{}@{}`\n".format(ctrl, action))
            if mw:
                f.write("- **Middleware** : {}\n".format(", ".join(mw)))
            if params:
                f.write("- **Params**     : {}\n".format(
                    ", ".join("`{{{}}}`".format(p) for p in params)))
            if models:
                f.write("- **Models**     : {}\n".format(
                    ", ".join("`{}`".format(m) for m in models[:5])))
            f.write("\n---\n\n")


def _write_business_md(routes, path, config, no_ai, progress, append=False):
    if not routes:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sys_msg = _business_system()
    use_ai  = not no_ai and config.use_ai
    entries = []

    for i, route in enumerate(routes):
        method    = route.get("method", "?")
        full_path = route.get("full_path", route.get("path", "?"))

        if progress.api_done(method, full_path, ai=use_ai) and not append:
            continue

        print("    [{}/{}] {} {}".format(i + 1, len(routes), method, full_path))

        if no_ai or not config.use_ai:
            section = _skeleton_section(route)
        else:
            section = call_ai(_business_prompt(route), config,
                              system=sys_msg, max_tokens=1200)
            if section.startswith("[AI failed"):
                print("       fallback: " + section[:70])
                section = _skeleton_section(route)
            if config.delay > 0:
                time.sleep(config.delay)

        entries.append(section)
        progress.mark_api(method, full_path, ai=use_ai)

    if not entries:
        return

    mode = "a" if append else "w"
    with open(path, mode, encoding="utf-8") as f:
        if not append:
            f.write("# Business Logic Documentation\n\n")
            f.write("_WHY each API exists -- rules, logic, side effects._\n\n---\n\n")
        for entry in entries:
            f.write(entry.strip() + "\n\n")


def _skeleton_section(route):
    method    = route.get("method", "?")
    full_path = route.get("full_path", route.get("path", "?"))
    ctrl      = route.get("controller", "UNKNOWN").split("\\")[-1]
    action    = route.get("action", "UNKNOWN")
    title     = full_path.rstrip("/").split("/")[-1] or "root"
    steps     = route.get("steps", [])
    validation = route.get("validation", {})
    queries   = route.get("queries", [])
    errors    = route.get("errors", [])
    unknowns  = route.get("unknowns", [])
    mw        = route.get("middleware", [])

    steps_md = "\n".join(
        "{}. [{}] {}".format(
            i + 1, s.get("type", "?").upper(),
            s.get("detail", s.get("target", s.get("name", s.get("model", "?")))),
        )
        for i, s in enumerate(steps)
    ) or "_Enable AI for generated content_"

    val_md = (
        "\n".join("- `{}`: {}".format(k, v) for k, v in validation.items())
        if validation else "None detected"
    )
    q_md = (
        "\n".join(
            "{}. [{}] {} -- {}".format(
                i + 1, q.get("type", "?").upper(),
                q.get("model", q.get("table", "?")),
                q.get("operation", "?"),
            )
            for i, q in enumerate(queries)
        )
        if queries else "None detected"
    )
    err_md = (
        "\n".join("- abort({})".format(e.get("code", "?")) for e in errors)
        if errors else "None detected"
    )
    unk_md = (
        "\n".join("- " + u for u in unknowns)
        if unknowns else "None"
    )

    return (
        "## {}\n\n".format(title)
        + "| Field | Value |\n|-------|-------|\n"
        + "| **Endpoint** | `{} {}` |\n".format(method, full_path)
        + "| **Controller** | `{}@{}` |\n".format(ctrl, action)
        + "| **Middleware** | {} |\n\n".format(", ".join(mw) or "None")
        + "### Purpose\n_Run with AI enabled for description._\n\n"
        + "### Business Logic\n{}\n\n".format(steps_md)
        + "### Input Parameters\n{}\n\n".format(val_md)
        + "### Database Operations\n{}\n\n".format(q_md)
        + "### Errors\n{}\n\n".format(err_md)
        + "### Unknowns\n{}\n\n".format(unk_md)
        + "---"
    )


def _write_sql(routes, path, config, no_ai, progress, append=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    use_ai   = not no_ai and config.use_ai
    sections = []

    for route in routes:
        method    = route.get("method", "?")
        full_path = route.get("full_path", route.get("path", "?"))
        snippet   = route.get("body_snippet", "")
        sql_key   = "SQL_{}".format(method)

        if progress.api_done(sql_key, full_path, ai=use_ai) and not append:
            continue

        if no_ai or not config.use_ai:
            static_qs = _static_sql(snippet)
            if not static_qs:
                continue
            block = "\n".join(q["sql"] for q in static_qs)
        else:
            if not snippet and not route.get("queries"):
                continue
            block = call_ai(_sql_prompt(route), config,
                            system=_sql_system(), max_tokens=900)
            if block.startswith("[AI failed"):
                static_qs = _static_sql(snippet)
                if not static_qs:
                    continue
                block = "\n".join(q["sql"] for q in static_qs)
            if config.delay > 0:
                time.sleep(config.delay)

        ctrl = route.get("controller", "?").split("\\")[-1]
        sections.append(
            "-- {}\n".format("-" * 60)
            + "-- Endpoint  : {} {}\n".format(method, full_path)
            + "-- Controller: {}\n".format(ctrl)
            + "-- {}\n\n".format("-" * 60)
            + block.strip() + "\n"
        )
        progress.mark_api(sql_key, full_path, ai=use_ai)

    if not sections:
        return

    mode = "a" if append else "w"
    with open(path, mode, encoding="utf-8") as f:
        if not append:
            f.write("-- SQL / Eloquent Audit\n")
            f.write("-- Generated by doc_writer\n")
            f.write("-- {}\n\n".format("-" * 60))
        for s in sections:
            f.write(s + "\n")


def _write_index(domain_map, docs_root):
    total = sum(len(v) for v in domain_map.values())
    with open(os.path.join(docs_root, "index.md"), "w", encoding="utf-8") as f:
        f.write("# Backend API Index\n\n")
        f.write("Total endpoints: **{}**\n\n".format(total))
        f.write("| Domain | Endpoints | API Ref | Business Docs | SQL Audit |\n")
        f.write("|--------|-----------|---------|---------------|-----------|\n")
        for domain in sorted(domain_map.keys()):
            count = len(domain_map[domain])
            b = "./{}".format(domain)
            f.write(
                "| **{}** | {} | [api.md]({}/api.md) "
                "| [business.md]({}/business.md) "
                "| [legacy_query.sql]({}/legacy_query.sql) |\n".format(
                    domain, count, b, b, b
                )
            )
        f.write("\n---\n_Generated by doc_writer_\n")


# =============================================================================
# COMPATIBILITY WRAPPERS (used by main.py)
# =============================================================================

def generate_business_md(routes, output_path, config, no_ai=False, append=False):
    state_dir = os.path.join(os.path.dirname(output_path), "..", ".docwriter")
    os.makedirs(state_dir, exist_ok=True)
    progress  = ProgressTracker(state_dir)
    _write_business_md(routes, output_path, config, no_ai, progress, append)


def generate_legacy_sql(routes, output_path, config, no_ai=False, append=False):
    state_dir = os.path.join(os.path.dirname(output_path), "..", ".docwriter")
    os.makedirs(state_dir, exist_ok=True)
    progress  = ProgressTracker(state_dir)
    _write_sql(routes, output_path, config, no_ai, progress, append)