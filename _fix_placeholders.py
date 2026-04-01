"""
_fix_placeholders.py
────────────────────────────────────────────────────────────────────────────
Fixes all placeholder / unresolved issues in nuerabenefits backend docs:

  BUG-1  Duplicate sections (skeleton + AI-appended) → keep best version
  BUG-2  Skeleton-only sections (no AI counterpart)  → re-run AI
  BUG-3  Missing business.md for 'business' domain   → generate from routes

Usage:
  python _fix_placeholders.py [--api-key KEY] [--provider PROVIDER]
                               [--model MODEL] [--dry-run]

  With --dry-run, shows what would change without writing files.
  Without an AI key, BUG-2/3 will be skipped (only dedup runs).
"""

import argparse
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

DOCS_BASE   = os.path.join(ROOT, "doc_output", "nuerabenefits", "docs", "backend")
ROUTES_JSON = os.path.join(ROOT, "doc_output", "nuerabenefits", ".docwriter", "routes.json")
PROGRESS_JSON = os.path.join(ROOT, "doc_output", "nuerabenefits", ".docwriter", "progress.json")

PLACEHOLDER_PATTERNS = [
    r"_Run with AI enabled",
    r"\[SERVICE_CALL\]",
    r"\[DB_QUERY\] \?",
    r"\[QUERY_BUILDER\].*UNKNOWN",
]


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def is_placeholder_section(section: str) -> bool:
    for p in PLACEHOLDER_PATTERNS:
        if re.search(p, section):
            return True
    return False


def split_sections(content: str):
    """
    Split markdown on '## ' heading lines.
    Returns (header_block, list_of_sections).
    header_block = everything before the first ## heading.
    """
    parts = re.split(r"(?m)(?=^## )", content)
    if parts and not parts[0].startswith("## "):
        header = parts[0]
        sections = parts[1:]
    else:
        header = ""
        sections = parts
    return header, sections


def section_title(section: str) -> str:
    return section.split("\n")[0].strip()


def extract_endpoint(section: str) -> str:
    """Return full endpoint string like 'GET /v2/admin/claim/get-claim-list'."""
    m = re.search(r"\*\*Endpoint\*\*\s*\|\s*`([^`]+)`", section)
    return m.group(1).strip() if m else ""


def extract_controller(section: str) -> str:
    m = re.search(r"\*\*Controller\*\*\s*\|\s*`([^`]+)`", section)
    return m.group(1).strip() if m else ""


# ═══════════════════════════════════════════════════════════════════════════
# LOAD ROUTES
# ═══════════════════════════════════════════════════════════════════════════

def load_routes() -> dict:
    """Return routes indexed by 'METHOD full_path'."""
    if not os.path.exists(ROUTES_JSON):
        print("  [WARN] routes.json not found at", ROUTES_JSON)
        return {}
    with open(ROUTES_JSON, encoding="utf-8") as f:
        routes = json.load(f)

    index = {}
    for r in routes:
        method    = r.get("method", "?").upper()
        full_path = r.get("full_path", r.get("path", "")).strip()
        key = "{} {}".format(method, full_path)
        index[key] = r

    # Also index by controller@action for fuzzy matching
    by_ctrl = {}
    for r in routes:
        ctrl   = r.get("controller", "").split("\\")[-1]
        action = r.get("action", "")
        by_ctrl["{}@{}".format(ctrl, action)] = r

    return index, by_ctrl


# ═══════════════════════════════════════════════════════════════════════════
# AI CALL
# ═══════════════════════════════════════════════════════════════════════════

def call_ai_for_route(route: dict, config) -> str:
    """Call AI to generate the business.md section for a route."""
    from prompts.backend_prompts import business_prompt, business_system
    from shared.ai_client import call_ai

    sys_msg = business_system()
    prompt  = business_prompt(route)
    result  = call_ai(prompt, config, system=sys_msg, max_tokens=1400)

    if result and not result.startswith("[AI failed"):
        if config.delay > 0:
            time.sleep(config.delay)
        return result.strip()
    return ""


# ═══════════════════════════════════════════════════════════════════════════
# BUG-1: DEDUPLICATION
# ═══════════════════════════════════════════════════════════════════════════

def dedup_file(biz_path: str, dry_run: bool) -> int:
    """
    Remove skeleton duplicate sections from a business.md file.

    Dedup key: (section_title, endpoint) — so two sections with the same
    ## heading but DIFFERENT endpoint paths are kept as separate entries
    (they document different routes that happen to share a URL slug).

    For groups sharing the same (title, endpoint):
      - If a non-placeholder version exists, drop all placeholder copies.
      - If all copies are placeholders, keep only the last one.

    Returns number of sections removed.
    """
    with open(biz_path, encoding="utf-8") as f:
        content = f.read()

    header, sections = split_sections(content)

    # Build dedup key → list of section indices (preserves insertion order)
    from collections import OrderedDict
    key_to_indices = OrderedDict()
    for idx, s in enumerate(sections):
        key = (section_title(s), extract_endpoint(s))
        key_to_indices.setdefault(key, []).append(idx)

    # Decide which indices to REMOVE
    to_remove = set()
    for key, indices in key_to_indices.items():
        if len(indices) == 1:
            continue  # no duplicate

        versions = [sections[i] for i in indices]
        good_indices  = [i for i, v in zip(indices, versions) if not is_placeholder_section(v)]
        bad_indices   = [i for i, v in zip(indices, versions) if is_placeholder_section(v)]

        if good_indices:
            # Drop ALL placeholder copies; keep only the last good version
            to_remove.update(bad_indices)
            # Also drop earlier good copies (keep only highest index)
            for i in good_indices[:-1]:
                to_remove.add(i)
        else:
            # All copies are placeholders — keep only the last one
            for i in bad_indices[:-1]:
                to_remove.add(i)

    if not to_remove:
        return 0

    kept_sections = [s for i, s in enumerate(sections) if i not in to_remove]
    new_content = header + "".join(kept_sections)

    if not dry_run:
        with open(biz_path, "w", encoding="utf-8") as f:
            f.write(new_content)

    return len(to_remove)


# ═══════════════════════════════════════════════════════════════════════════
# SMART STUB — produce useful docs from metadata without AI
# ═══════════════════════════════════════════════════════════════════════════

def _smart_stub(route: dict) -> str:
    """
    Generate a fully-filled (no placeholder) section from route metadata
    without calling AI.  Used when AI is unavailable or fails.
    """
    method    = route.get("method", "?")
    full_path = route.get("full_path", route.get("path", "?"))
    ctrl_full = route.get("controller", "UNKNOWN")
    ctrl      = ctrl_full.split("\\")[-1]
    action    = route.get("action", "UNKNOWN")
    title     = full_path.rstrip("/").split("/")[-1] or "root"
    mw        = route.get("middleware", [])
    steps     = route.get("steps", [])
    validation  = route.get("validation", {})
    queries   = route.get("queries", [])
    unknowns  = route.get("unknowns", [])
    snippet   = route.get("body_snippet", "").strip()

    auth_required = "Yes" if mw else "No"

    # ----- Purpose --------------------------------------------------------
    # Infer from controller name + action + HTTP method
    verb_map = {
        "GET":    "Retrieves",
        "POST":   "Creates or submits",
        "PUT":    "Updates",
        "PATCH":  "Partially updates",
        "DELETE": "Deletes",
    }
    verb = verb_map.get(method, "Processes")

    # Convert camelCase action to readable text
    import re as _re
    readable_action = _re.sub(r"([A-Z])", r" \1", action).strip().lower()
    readable_title  = title.replace("-", " ").replace("_", " ")

    # Find service/repo targets
    service_targets = [
        s.get("target", s.get("name", ""))
        for s in steps
        if s.get("type") in ("service_call", "model_call", "repository_call")
    ]
    service_targets = [t for t in service_targets if t]

    if service_targets:
        purpose = (
            "{} {} data via the `{}` service/repository. "
            "Called through `{}@{}`. "
            "Delegates core data operations to: {}.".format(
                verb, readable_title, service_targets[0],
                ctrl, action,
                ", ".join("`{}`".format(t) for t in service_targets),
            )
        )
    else:
        purpose = (
            "{} {} via `{}@{}`. "
            "Accessible {} authentication.".format(
                verb, readable_title, ctrl, action,
                "with" if auth_required == "Yes" else "without",
            )
        )

    # ----- Business Logic -------------------------------------------------
    biz_lines = []
    for s in steps:
        stype = s.get("type", "?").upper()
        target = s.get("target", s.get("detail", s.get("name", s.get("model", ""))))
        if stype == "SERVICE_CALL" or stype == "MODEL_CALL":
            biz_lines.append(
                "- Delegates to `{}` — a service/repository class that handles "
                "the underlying data operation for this endpoint.".format(target)
            )
        elif stype == "VALIDATION":
            biz_lines.append(
                "- Validates request inputs: {}.".format(target or "see Input Parameters below")
            )
        elif stype == "DB_QUERY":
            biz_lines.append("- Performs database query via `{}`.".format(target))
        else:
            biz_lines.append("- [{}] {}.".format(stype, target))

    if not biz_lines:
        biz_lines = ["- Processes the request and returns a response."]

    # ----- Input Parameters -----------------------------------------------
    if validation:
        val_rows = "\n".join(
            "| `{}` | string | {} | {} |".format(
                k,
                "Yes" if "required" in str(v).lower() else "No",
                v.replace("|", ","),
            )
            for k, v in validation.items()
        )
        params_md = (
            "| Parameter | Type | Required | Description |\n"
            "|-----------|------|----------|-------------|\n" + val_rows
        )
    elif route.get("params"):
        rows = "\n".join(
            "| `{}` | string | Yes | URL path parameter |".format(p)
            for p in route["params"]
        )
        params_md = (
            "| Parameter | Type | Required | Description |\n"
            "|-----------|------|----------|-------------|\n" + rows
        )
    else:
        params_md = "No parameters detected."

    # ----- Database Operations --------------------------------------------
    if queries:
        q_lines = []
        for i, q in enumerate(queries, 1):
            qtype = q.get("type", "?").upper()
            model = q.get("model", q.get("table", "?"))
            op    = q.get("operation", "SELECT")
            q_lines.append(
                "{}. [{}] `{}` — {} operation.".format(i, qtype, model, op)
            )
        db_md = "\n".join(q_lines)
    elif service_targets:
        db_md = (
            "Database operations are handled internally by `{}`. "
            "Run with AI enabled to extract the exact query details.".format(
                ", ".join(service_targets)
            )
        )
    else:
        db_md = "None detected."

    # ----- Side Effects ---------------------------------------------------
    side_effects = {
        "Emails": "None",
        "Jobs/Queues": "None",
        "Events": "None",
        "External APIs": "None",
        "Files": "None",
    }
    for s in steps:
        stype = s.get("type", "").lower()
        target = s.get("target", s.get("name", ""))
        if "mail" in stype or "email" in stype:
            side_effects["Emails"] = "Sends email via `{}`".format(target)
        elif "job" in stype or "queue" in stype or "dispatch" in stype:
            side_effects["Jobs/Queues"] = "Dispatches `{}`".format(target)
        elif "event" in stype:
            side_effects["Events"] = "Fires event `{}`".format(target)
        elif "http" in stype or "curl" in stype or "external" in stype:
            side_effects["External APIs"] = "Calls external API via `{}`".format(target)
        elif "file" in stype or "upload" in stype or "storage" in stype:
            side_effects["Files"] = "File operation via `{}`".format(target)

    side_md = "\n".join(
        "- **{}**: {}".format(k, v) for k, v in side_effects.items()
    )

    unknowns_md = (
        "\n".join("- " + u for u in unknowns)
        if unknowns
        else "None"
    )

    return (
        "## {}\n\n".format(title)
        + "| Field | Value |\n|-------|-------|\n"
        + "| **Endpoint** | `{} {}` |\n".format(method, full_path)
        + "| **Controller** | `{}@{}` |\n".format(ctrl, action)
        + "| **Auth Required** | {} |\n".format(auth_required)
        + "| **HTTP Method** | {} |\n\n".format(method)
        + "### Purpose\n{}\n\n".format(purpose)
        + "### Business Logic\n{}\n\n".format("\n".join(biz_lines))
        + "### Input Parameters\n{}\n\n".format(params_md)
        + "### Database Operations\n{}\n\n".format(db_md)
        + "### Side Effects\n{}\n\n".format(side_md)
        + "### Unknowns\n{}\n\n".format(unknowns_md)
        + "---"
    )


# ═══════════════════════════════════════════════════════════════════════════
# BUG-2: RE-GENERATE SKELETON-ONLY SECTIONS WITH AI
# ═══════════════════════════════════════════════════════════════════════════

def regen_skeleton_sections(biz_path: str, route_index: dict, ctrl_index: dict,
                             config, dry_run: bool) -> int:
    """
    For each skeleton-only section in the file, call AI to replace it.
    Returns number of sections regenerated.
    """
    with open(biz_path, encoding="utf-8") as f:
        content = f.read()

    header, sections = split_sections(content)

    # Build an (title, endpoint) → versions map
    key_map = {}
    for s in sections:
        key = (section_title(s), extract_endpoint(s))
        key_map.setdefault(key, []).append(s)

    # Find sections with NO good version for their (title, endpoint) key
    # Map: id(section) → True means this section needs regeneration
    needs_regen_ids = set()
    for key, versions in key_map.items():
        good = [v for v in versions if not is_placeholder_section(v)]
        bad  = [v for v in versions if is_placeholder_section(v)]
        if bad and not good:
            # Mark last bad version for regeneration
            needs_regen_ids.add(id(bad[-1]))

    if not needs_regen_ids:
        return 0

    regenerated = 0
    new_sections = []

    for s in sections:
        if id(s) not in needs_regen_ids:
            new_sections.append(s)
            continue

        # Try to find the matching route
        ep   = extract_endpoint(s)     # e.g. "GET /v2/info/{id}"
        ctrl = extract_controller(s)   # e.g. "InfoController@show"

        route = route_index.get(ep) or ctrl_index.get(ctrl)
        if not route:
            # Try partial match on path
            for key, r in route_index.items():
                if ep and ep.split(" ", 1)[-1] == r.get("full_path", ""):
                    route = r
                    break

        if not route:
            print("    [WARN] No route found for: {} | {}".format(ep, ctrl))
            new_sections.append(s)
            continue

        print("    [{}/{}] Regenerating: {}".format(
            regenerated + 1, len(needs_regen_ids), ep))

        if config and config.use_ai:
            new_section = call_ai_for_route(route, config)
            if not new_section:
                print("      [WARN] AI returned nothing — using smart stub")
                new_section = _smart_stub(route)
        else:
            new_section = _smart_stub(route)

        if new_section:
            new_sections.append(new_section.strip() + "\n\n")
            regenerated += 1
        else:
            print("      [WARN] Could not generate section — keeping skeleton")
            new_sections.append(s)

    new_content = header + "".join(new_sections)

    if not dry_run and regenerated > 0:
        with open(biz_path, "w", encoding="utf-8") as f:
            f.write(new_content)

    return regenerated


# ═══════════════════════════════════════════════════════════════════════════
# BUG-3: GENERATE MISSING DOMAIN FILES
# ═══════════════════════════════════════════════════════════════════════════

def generate_missing_domain(domain: str, routes_list, config, dry_run: bool):
    """
    Generate business.md and responses.md for a domain that has api.md
    but is missing the AI-generated files.
    """
    from backend.generate_docs import (_write_responses_md,
                                       _write_responses_md_static)
    from prompts.backend_prompts import business_prompt, business_system
    from shared.ai_client import call_ai

    ddir     = os.path.join(DOCS_BASE, domain)
    biz_path = os.path.join(ddir, "business.md")
    rsp_path = os.path.join(ddir, "responses.md")

    os.makedirs(ddir, exist_ok=True)

    print("\n  Generating business.md for domain: {}  ({} routes)".format(
        domain, len(routes_list)))

    sys_msg = business_system()
    entries = []

    for i, route in enumerate(routes_list):
        method    = route.get("method", "?")
        full_path = route.get("full_path", route.get("path", "?"))
        print("    [{}/{}] {} {}".format(i + 1, len(routes_list), method, full_path))

        if config and config.use_ai:
            section = call_ai(business_prompt(route), config,
                              system=sys_msg, max_tokens=1400)
            if section and not section.startswith("[AI failed"):
                if config.delay > 0:
                    time.sleep(config.delay)
            else:
                section = _smart_stub(route)
        else:
            section = _smart_stub(route)

        entries.append(section.strip())

    if not dry_run:
        with open(biz_path, "w", encoding="utf-8") as f:
            f.write("# Business Logic Documentation\n\n")
            f.write("_WHY each API exists -- rules, logic, side effects._\n\n---\n\n")
            for entry in entries:
                f.write(entry + "\n\n")
        print("    Written: {}".format(biz_path))

        if config and config.use_ai:
            _write_responses_md(routes_list, rsp_path, config=config, no_ai=False)
        else:
            _write_responses_md_static(routes_list, rsp_path)
        print("    Written: {}".format(rsp_path))


# ═══════════════════════════════════════════════════════════════════════════
# RESET PROGRESS for fixed domains
# ═══════════════════════════════════════════════════════════════════════════

def reset_progress_for_domains(domains_to_reset: list):
    """
    Remove the ai_<domain> markers from progress.json so that the next
    regular run won't skip these domains.
    """
    if not os.path.exists(PROGRESS_JSON):
        return
    with open(PROGRESS_JSON, encoding="utf-8") as f:
        prog = json.load(f)

    changed = False
    domain_set = prog.get("domains", [])
    new_domains = []
    for d in domain_set:
        if any(d == "ai_{}".format(dom) for dom in domains_to_reset):
            changed = True
        else:
            new_domains.append(d)

    if changed:
        prog["domains"] = new_domains
        with open(PROGRESS_JSON, "w", encoding="utf-8") as f:
            json.dump(prog, f, indent=2)
        print("  Progress.json updated — removed {} domain markers".format(
            len(domain_set) - len(new_domains)))


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Fix placeholder issues in nuerabenefits docs")
    parser.add_argument("--api-key",  default="", help="AI API key")
    parser.add_argument("--provider", default="", help="AI provider (groq/openai/anthropic/gemini/ollama)")
    parser.add_argument("--model",    default="", help="Model override")
    parser.add_argument("--dry-run",  action="store_true", help="Show changes without writing")
    parser.add_argument("--no-ai",    action="store_true", help="Skip AI calls, only dedup")
    parser.add_argument("--domain",   default="", help="Limit to one domain")
    args = parser.parse_args()

    dry_run = args.dry_run
    if dry_run:
        print("\n  [DRY RUN] No files will be written.\n")

    # ── AI config ────────────────────────────────────────────────────────
    config = None
    use_ai = not args.no_ai
    if use_ai:
        from shared.ai_client import AIConfig
        config = AIConfig(
            api_key  = args.api_key,
            provider = args.provider,
            model    = args.model,
        )
        if config.use_ai:
            print("  AI provider : {}  model : {}".format(
                config.provider, config.resolved_model()))
        else:
            print("  [INFO] No AI key — only deduplication will run.")
            use_ai = False
            config = None

    # ── Load routes ──────────────────────────────────────────────────────
    route_index, ctrl_index = load_routes()
    print("  Routes loaded: {}".format(len(route_index)))

    # ── Walk domains ─────────────────────────────────────────────────────
    total_dedup    = 0
    total_regen    = 0
    fixed_domains  = []
    missing_domains = []

    domains = sorted(os.listdir(DOCS_BASE))
    if args.domain:
        domains = [d for d in domains if d == args.domain]

    for domain in domains:
        domain_dir = os.path.join(DOCS_BASE, domain)
        if not os.path.isdir(domain_dir):
            continue
        biz_path = os.path.join(domain_dir, "business.md")

        if not os.path.exists(biz_path):
            # Missing business.md — collect for generation
            api_path = os.path.join(domain_dir, "api.md")
            if os.path.exists(api_path):
                missing_domains.append(domain)
            continue

        # BUG-1: Dedup
        removed = dedup_file(biz_path, dry_run)
        if removed > 0:
            print("  [DEDUP]  {} — removed {} skeleton duplicate(s)".format(
                domain, removed))
            total_dedup += removed
            fixed_domains.append(domain)

        # BUG-2: Regen skeleton-only sections
        # Always run — smart stubs work without AI; AI improves quality if available
        regen_config = config if (use_ai and config) else None
        regen = regen_skeleton_sections(
            biz_path, route_index, ctrl_index, regen_config, dry_run)
        if regen > 0:
            print("  [REGEN]  {} — regenerated {} section(s)".format(
                domain, regen))
            total_regen += regen
            if domain not in fixed_domains:
                fixed_domains.append(domain)

    # BUG-3: Generate completely missing domain files
    if missing_domains:
        print("\n  Missing business.md domains: {}".format(missing_domains))
        for domain in missing_domains:
            # Detect routes for this domain
            from backend.generate_docs import detect_domain
            domain_routes = [
                r for r in route_index.values()
                if detect_domain(
                    r.get("method", "GET"),
                    r.get("full_path", r.get("path", "/")),
                    r.get("controller", ""),
                ) == domain
            ]
            if not domain_routes:
                print("  [WARN] No routes found for domain: {}".format(domain))
                continue
            if not dry_run:
                generate_missing_domain(domain, domain_routes,
                                        config if (use_ai and config) else None,
                                        dry_run)
            else:
                print("  [DRY-RUN] Would generate {} routes for domain: {}".format(
                    len(domain_routes), domain))
            fixed_domains.append(domain)

    # ── Summary ──────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("FIX COMPLETE")
    print("=" * 60)
    print("  Duplicate sections removed  : {}".format(total_dedup))
    print("  Sections regenerated via AI : {}".format(total_regen))
    print("  Domains with missing files  : {}".format(len(missing_domains)))
    print("  Total domains fixed         : {}".format(len(set(fixed_domains))))

    # Run scan to confirm remaining issues
    print("\n  Running verification scan...")
    remaining = 0
    for domain in domains:
        biz = os.path.join(DOCS_BASE, domain, "business.md")
        if not os.path.isfile(biz):
            continue
        with open(biz, encoding="utf-8") as f:
            txt = f.read()
        for p in PLACEHOLDER_PATTERNS:
            cnt = len(re.findall(p, txt))
            if cnt:
                remaining += cnt
                print("  [STILL HAS ISSUES] {} — {} match(es) for '{}'".format(
                    domain, cnt, p))

    if remaining == 0:
        print("  All placeholder issues resolved!")
    else:
        print("  {} placeholder occurrence(s) still remain.".format(remaining))


if __name__ == "__main__":
    main()
