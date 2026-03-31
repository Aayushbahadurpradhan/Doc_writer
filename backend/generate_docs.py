"""
generate_docs.py - Backend documentation generator.

Groups routes by domain auto-detected from URL path.
No hardcoded domain names - works with any project.

Output per domain:
  docs/backend/{domain}/api.md              - Static API reference
  docs/backend/{domain}/responses.md        - Response schemas & examples
  docs/backend/{domain}/business.md         - AI-generated business logic
  docs/backend/{domain}/legacy_query.sql    - AI-generated SQL audit
  docs/backend/index.md                     - Master index

Protected output: Frontend runs will NOT overwrite backend docs.
"""

import json
import os
import re
import sys
import time
from collections import defaultdict
from typing import Dict, List, Set

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from prompts.backend_prompts import business_prompt as _business_prompt
from prompts.backend_prompts import business_system as _business_system
from prompts.backend_prompts import response_prompt as _response_prompt
from prompts.backend_prompts import response_system as _response_system
from prompts.backend_prompts import sql_prompt as _sql_prompt
from prompts.backend_prompts import sql_system as _sql_system
from shared.ai_client import AIConfig, call_ai

# =============================================================================
# DOMAIN DETECTION
# Purely dynamic from URL path. Zero hardcoded domain names.
# Works with any project structure.
# =============================================================================

# Known entity/resource words - these get priority when found in a path segment
_ENTITY_WORDS = {
    'agent', 'group', 'policy', 'member', 'plan', 'payment', 'invoice',
    'contract', 'commission', 'enrollment', 'dependent', 'beneficiary',
    'carrier', 'template', 'email', 'bank', 'billing', 'claim', 'document',
    'report', 'license', 'medical', 'platform', 'feature', 'note', 'term',
    'rider', 'address', 'question', 'text', 'tier', 'waive', 'fee', 'file',
    'acm', 'prudential', 'website', 'homepage', 'downline', 'upline',
    'referral', 'webhook', 'notification', 'queue', 'lead', 'script',
    'analytic', 'statistic', 'progress', 'rate', 'price', 'renewal',
    'receipt', 'tax', 'eft', 'ach', 'census', 'credit', 'routing',
    'client', 'user', 'admin', 'resource', 'activity', 'log', 'audit',
    'setting', 'option', 'type', 'status', 'level', 'info', 'detail',
    'summary', 'history', 'request', 'approval', 'security',
    'compare', 'contract', 'business', 'association', 'signature',
}

# Verb/action words - stripped before picking the domain noun
_VERB_WORDS = {
    'get', 'set', 'add', 'create', 'update', 'delete', 'remove',
    'upload', 'download', 'send', 'view', 'edit', 'list', 'manage',
    'check', 'fetch', 'generate', 'process', 'approve', 'reject',
    'import', 'export', 'restore', 'change', 'reset', 'save',
    'validate', 'verify', 'mark', 'toggle', 'submit', 'bulk',
    'total', 'show', 'find', 'search', 'filter', 'load', 'build',
    'activate', 'deactivate', 'enable', 'disable', 'calculate',
    'store', 'define', 'retrieve', 'preview', 'sync', 'onboard',
    'migrate', 'switch', 'resend', 'reprocess', 'refund',
    'new', 'latest', 'recent', 'active', 'uploaded', 'pending', 'signed',
    # Common stopwords / connectors / generic words
    'all', 'and', 'or', 'any', 'the', 'of', 'by', 'old', 'own', 'my',
    'true', 'false', 'yes', 'no',
    # Generic UI/app words that are not meaningful domain names
    'top', 'app', 'main', 'home', 'base', 'core', 'common', 'misc',
    'other', 'item', 'view', 'page', 'form',
    'sign', 'login', 'logout', 'auth',
    # Prefix/modifier words (sub-, multi-, etc.)
    'sub', 'multi', 'bulk',
}

# Words that must NOT be singularized (already in canonical singular form
# or are not count nouns)
_NO_SINGULAR = {
    'status', 'access', 'address', 'process', 'progress', 'canvas',
    'analysis', 'basis', 'axis', 'diagnosis', 'thesis', 'nexus',
    'census', 'bonus', 'focus', 'virus', 'campus', 'minus', 'plus',
}


def _split_segment(seg: str) -> list:
    """
    Split a URL path segment into individual lowercase words.
    Handles: hyphens, underscores, AND camelCase.
      getContractNameList -> ['get', 'contract', 'name', 'list']
      update-agent-info   -> ['update', 'agent', 'info']
      addEFTRequest       -> ['add', 'eft', 'request']
    """
    # Insert underscore between camelCase boundaries before splitting
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', seg)   # camelCase
    s = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', s)   # ACRONYMWord
    s = s.replace('-', '_').lower()
    return [w for w in s.split('_') if w and len(w) >= 2]


def detect_domain(method: str, path: str, handler: str = "") -> str:
    """
    Auto-detect a domain grouping from the route URL path.
    Strips verb words, prefers known entity words.
    Tries multiple path segments before falling back.

    Examples:
      /v1/add-agent-license       -> agent
      /v1/activate-agent          -> agent
      /v1/new-plan                -> plan
      /v1/health-enrollment       -> enrollment
      /v2/agent/{id}/commission   -> agent
      /acm/get-sync-neura         -> acm
      /v1/manage-groups           -> group  (plural normalised)
      /all                        -> general  (stopword, try next segment)
    """
    # Split camelCase BEFORE lowercasing so the boundaries are still visible
    path = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', path)   # camelCase
    path = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', path) # ACRONYMWord
    clean = path.lower().strip().strip("/")

    # Skip version and api prefix segments
    parts = [
        p for p in clean.split("/")
        if p
        and not re.match(r"^v\d+$", p)
        and p not in ("api", "api.access", "access")
    ]

    if not parts:
        return "general"

    domain_word = None

    # Try each path segment in order (up to 3) to find a meaningful entity word
    for seg in parts[:3]:
        if seg.startswith("{") or seg.startswith(":"):
            continue  # skip URL params

        # Split camelCase + hyphen/underscore into individual words
        words = _split_segment(seg)
        if not words:
            continue

        # All non-verb/non-stopword candidates
        noun_words = [w for w in words if w not in _VERB_WORDS]

        # Prefer known entity words (left to right)
        entity_matches = [w for w in noun_words if w in _ENTITY_WORDS]
        if entity_matches:
            domain_word = entity_matches[0]
            break

        # Accept first non-verb word ≥ 3 chars
        for candidate in noun_words:
            if len(candidate) >= 3:
                domain_word = candidate
                break
        if domain_word:
            break

    if domain_word is None:
        # Fallback: last meaningful word of first non-param segment
        first_seg = next(
            (s for s in parts if not s.startswith("{") and not s.startswith(":")),
            parts[0],
        )
        words = _split_segment(first_seg)
        # Filter out verbs/stopwords in fallback too
        noun_words = [w for w in words if w not in _VERB_WORDS and len(w) >= 3]
        domain_word = noun_words[-1] if noun_words else (words[-1] if words else "general")

    if not domain_word or len(domain_word) < 2:
        domain_word = "general"

    # Normalise plurals -> singular for cleaner folder names
    w = domain_word.lower()
    if w in _NO_SINGULAR:
        pass                            # never singularize these words
    elif w.endswith("ies") and len(w) > 4:
        w = w[:-3] + "y"               # policies -> policy
    elif w.endswith("ses") and len(w) > 4:
        w = w[:-1]                     # statuses -> status  (remove only the trailing s)
    elif w.endswith("s") and len(w) > 4 and not w.endswith("ss"):
        w = w[:-1]                     # agents -> agent, groups -> group

    # Final guard: if result is still a verb/stopword, use general
    if w in _VERB_WORDS:
        return "general"

    return w


# =============================================================================
# PROGRESS TRACKER
# Tracks which APIs have been documented so runs can resume mid-way.
# =============================================================================

class ProgressTracker:
    """
    Tracks which APIs have been documented so runs can resume mid-way.
    Internally uses sets for O(1) membership tests; serialises as lists to JSON.
    """

    def __init__(self, state_dir: str):
        self.path = os.path.join(state_dir, "progress.json")
        self._sets: Dict[str, Set[str]] = self._load()

    # ── persistence ──────────────────────────────────────────────────────────

    def _load(self) -> Dict[str, Set[str]]:
        blank: Dict[str, Set[str]] = {
            "apis": set(), "ai_apis": set(),
            "sql_apis": set(), "sql_ai_apis": set(),
            "domains": set(),
        }
        if os.path.exists(self.path):
            try:
                with open(self.path, encoding="utf-8") as f:
                    raw = json.load(f)
                for k, v in raw.items():
                    blank[k] = set(v) if isinstance(v, list) else set()
            except Exception:
                pass
        return blank

    def _save(self) -> None:
        # Write to a temp file first, then rename — avoids corrupt JSON on
        # interrupted writes (important for parallel terminal mode).
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({k: sorted(v) for k, v in self._sets.items()}, f, indent=2)
        os.replace(tmp, self.path)

    def _ensure_key(self, key: str) -> None:
        if key not in self._sets:
            self._sets[key] = set()

    # ── public API ────────────────────────────────────────────────────────────

    def api_done(self, method: str, path: str, ai: bool = False) -> bool:
        field = "ai_apis" if ai else "apis"
        self._ensure_key(field)
        return "{} {}".format(method, path) in self._sets[field]

    def sql_done(self, method: str, path: str, ai: bool = False) -> bool:
        field = "sql_ai_apis" if ai else "sql_apis"
        self._ensure_key(field)
        return "{} {}".format(method, path) in self._sets[field]

    def mark_api(self, method: str, path: str, ai: bool = False) -> None:
        token = "{} {}".format(method, path)
        for field in (("apis", "ai_apis") if ai else ("apis",)):
            self._ensure_key(field)
            self._sets[field].add(token)
        self._save()

    def mark_sql(self, method: str, path: str, ai: bool = False) -> None:
        token = "{} {}".format(method, path)
        for field in (("sql_apis", "sql_ai_apis") if ai else ("sql_apis",)):
            self._ensure_key(field)
            self._sets[field].add(token)
        self._save()

    def domain_done(self, domain: str, ai: bool = False) -> bool:
        key = ("ai_" if ai else "") + domain
        return key in self._sets.get("domains", set())

    def mark_domain(self, domain: str, ai: bool = False) -> None:
        key = ("ai_" if ai else "") + domain
        self._ensure_key("domains")
        self._sets["domains"].add(key)
        self._save()

    def reset(self) -> None:
        self._sets = {
            "apis": set(), "ai_apis": set(),
            "sql_apis": set(), "sql_ai_apis": set(),
            "domains": set(),
        }
        self._save()
        print("  Progress reset.")


# =============================================================================
# AI PROMPTS (imported from prompts/backend_prompts.py)
# _business_system, _business_prompt, _sql_system, _sql_prompt,
# _response_system, _response_prompt are all imported at module top.
# =============================================================================

# =============================================================================
# STATIC SQL FALLBACK (when --no-ai)
# =============================================================================

_RAW_SQL_RE  = re.compile(
    r'DB::(?:select|statement|insert|update|delete)\s*\(\s*[\'"](.+?)[\'"]',
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


def _model_to_table(model: str) -> str:
    s = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", model).lower()
    if s.endswith("y") and len(s) > 1 and s[-2] not in "aeiou":
        return s[:-1] + "ies"
    if s.endswith(("s", "sh", "ch", "x", "z")):
        return s + "es"
    return s + "s"


def _static_sql(snippet: str) -> list:
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
            results.append({"kind": "db_facade",
                             "sql": "SELECT * FROM {};".format(table)})
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

def generate_all_docs(
    routes: List[dict],
    docs_root: str,
    config: AIConfig,
    no_ai: bool = False,
    force: bool = False,
    state_dir: str = "",
) -> None:
    """
    Group routes by auto-detected domain and write per-domain docs.

    Output structure:
      docs/backend/
        index.md                    <- master index
        {domain}/
          api.md                    <- route reference (no AI)
          business.md               <- AI business logic docs
          legacy_query.sql          <- AI SQL audit
    """
    state_dir = state_dir or os.path.join(docs_root, "..", ".docwriter")
    os.makedirs(state_dir, exist_ok=True)
    os.makedirs(docs_root,  exist_ok=True)

    progress = ProgressTracker(state_dir)
    if force:
        progress.reset()

    use_ai = not no_ai and config.use_ai

    # Group routes by auto-detected domain
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
        # Sanitize domain name: strip whitespace, replace spaces/special chars
        safe_domain = re.sub(r'[^\w-]', '_', domain.strip()).strip('_') or 'general'
        ddir = os.path.join(docs_root, safe_domain)
        os.makedirs(ddir, exist_ok=True)

        # Find routes pending for business.md
        pending_biz = [
            r for r in domain_routes
            if not progress.api_done(
                r.get("method", "?"),
                r.get("full_path", r.get("path", "")),
                ai=use_ai,
            )
        ]

        # Find routes pending for SQL (tracked separately)
        pending_sql = [
            r for r in domain_routes
            if not progress.sql_done(
                r.get("method", "?"),
                r.get("full_path", r.get("path", "")),
                ai=use_ai,
            )
        ]

        responses_stale = _responses_have_unknown(os.path.join(ddir, "responses.md"))
        if not pending_biz and not pending_sql and not responses_stale and not force:
            print("  skip {} ({} routes -- all done)".format(
                domain, len(domain_routes)))
            continue

        biz_pending_count = len(pending_biz) if not force else len(domain_routes)
        sql_pending_count = len(pending_sql) if not force else len(domain_routes)
        print("\n  [{}] {} routes  biz:{} pending  sql:{} pending".format(
            domain, len(domain_routes), biz_pending_count, sql_pending_count))

        # api.md -- always rewrite (fast, no AI)
        _write_api_md(domain_routes, os.path.join(ddir, "api.md"))
        print("    api.md")

        # responses.md -- API response schemas (uses AI to extract response details)
        if use_ai:
            _write_responses_md(
                domain_routes,
                os.path.join(ddir, "responses.md"),
                config=config,
                no_ai=no_ai,
            )
            print("    responses.md (with AI enhancement)")
        else:
            _write_responses_md_static(
                domain_routes,
                os.path.join(ddir, "responses.md"),
            )
            print("    responses.md (static)")

        # business.md
        routes_for_biz = domain_routes if force else pending_biz
        if routes_for_biz:
            _write_business_md(
                routes_for_biz,
                os.path.join(ddir, "business.md"),
                config, no_ai, progress,
                append=(bool(pending_biz) and not force),
            )
            print("    business.md")

        # legacy_query.sql - tracked with its own separate counter
        routes_for_sql = domain_routes if force else pending_sql
        if routes_for_sql:
            _write_sql(
                routes_for_sql,
                os.path.join(ddir, "legacy_query.sql"),
                config, no_ai, progress,
                append=(bool(pending_sql) and not force),
            )
            print("    legacy_query.sql")

        # Only mark domain done when both biz AND sql are complete
        all_biz_done = all(
            progress.api_done(r.get("method","?"),
                              r.get("full_path", r.get("path","")), ai=use_ai)
            for r in domain_routes
        )
        all_sql_done = all(
            progress.sql_done(r.get("method","?"),
                              r.get("full_path", r.get("path","")), ai=use_ai)
            for r in domain_routes
        )
        if all_biz_done and all_sql_done:
            progress.mark_domain(domain, ai=use_ai)

    # Master index
    _write_index(domain_map, docs_root)
    print("\n  index.md written")


# =============================================================================
# FILE WRITERS
# =============================================================================

def _responses_have_unknown(path: str) -> bool:
    """Return True if responses.md exists and still has unresolved placeholders."""
    if not os.path.exists(path):
        return False
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
        return "Unable to determine from available code." in content
    except Exception:
        return False


def _write_api_md(routes: List[dict], path: str) -> None:
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


def _write_responses_md(
    routes: List[dict],
    path: str,
    config: AIConfig = None,
    no_ai: bool = False,
) -> None:
    """Generate responses.md with API response schemas using AI when needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    use_ai = not no_ai and config and config.use_ai
    
    with open(path, "w", encoding="utf-8") as f:
        f.write("# API Response Schemas\n\n")
        f.write("Response bodies for each endpoint.\n\n---\n\n")
        
        for i, r in enumerate(routes):
            method    = r.get("method", "?")
            full_path = r.get("full_path", r.get("path", "?"))
            response  = r.get("response", {})
            ctrl      = r.get("controller", "UNKNOWN").split("\\")[-1]
            action    = r.get("action", "UNKNOWN")
            params    = r.get("params", [])
            snippet   = r.get("body_snippet", "")
            
            f.write("## {} {}\n\n".format(method, full_path))
            f.write("**Endpoint**: `{}@{}`\n\n".format(ctrl, action))
            
            if params:
                f.write("**Path Parameters**:\n")
                for p in params:
                    f.write("- `{}` - (from URL path)\n".format(p))
                f.write("\n")
            
            # Try static response first
            if response and response.get("fields"):
                resp_type = response.get("type", "json")
                fields = response.get("fields", [])
                f.write("**Response Type**: `{}`\n\n".format(resp_type))
                f.write("**Response Fields**:\n```json\n{\n")
                for field in fields:
                    f.write("  \"{}\": <value>,\n".format(field))
                f.write("}\n```\n\n")
            elif use_ai and snippet:
                # Use AI to extract response
                print(f"    [{i+1}/{len(routes)}] AI analyze response: {method} {full_path}")
                sys_msg = _response_system()
                prompt = _response_prompt(r)
                ai_response = call_ai(prompt, config, system=sys_msg, max_tokens=600)
                
                if ai_response and not ai_response.startswith("[AI failed"):
                    f.write(ai_response.strip() + "\n\n")
                    if config.delay > 0:
                        time.sleep(config.delay)
                else:
                    f.write("**Response**: Unable to determine from code analysis.\n\n")
            else:
                f.write("**Response**: Unable to determine from available code.\n\n")
            
            f.write("---\n\n")


def _write_responses_md_static(routes: List[dict], path: str) -> None:
    """Generate responses.md with API response schemas (static only, no AI)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("# API Response Schemas\n\n")
        f.write("Response bodies for each endpoint.\n\n---\n\n")
        
        for r in routes:
            method    = r.get("method", "?")
            full_path = r.get("full_path", r.get("path", "?"))
            response  = r.get("response", {})
            ctrl      = r.get("controller", "UNKNOWN").split("\\")[-1]
            action    = r.get("action", "UNKNOWN")
            title     = full_path.rstrip("/").split("/")[-1] or "root"
            params    = r.get("params", [])
            
            f.write("## {} {}\n\n".format(method, full_path))
            f.write("**Endpoint**: `{}@{}`\n\n".format(ctrl, action))
            
            if params:
                f.write("**Path Parameters**:\n")
                for p in params:
                    f.write("- `{}` - (from URL path)\n".format(p))
                f.write("\n")
            
            if response:
                resp_type = response.get("type", "unknown")
                fields = response.get("fields", [])
                f.write("**Response Type**: `{}`\n\n".format(resp_type))
                
                if fields:
                    f.write("**Response Fields**:\n```json\n{\n")
                    for field in fields:
                        f.write("  \"{}\": <value>,\n".format(field))
                    f.write("}\n```\n"
                    )
                else:
                    f.write("**Response Fields**: Not detected (inferred from code)\n\n")
            else:
                f.write("**Response**: Not detected in static analysis. Run with AI for details.\n\n")
            
            f.write("---\n\n")


def _write_business_md(
    routes: List[dict],
    path: str,
    config: AIConfig,
    no_ai: bool,
    progress: ProgressTracker,
    append: bool = False,
) -> None:
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
            section = call_ai(
                _business_prompt(route), config,
                system=sys_msg, max_tokens=1200,
            )
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


def _skeleton_section(route: dict) -> str:
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

    return (
        "## {}\n\n".format(title)
        + "| Field | Value |\n|-------|-------|\n"
        + "| **Endpoint** | `{} {}` |\n".format(method, full_path)
        + "| **Controller** | `{}@{}` |\n".format(ctrl, action)
        + "| **Middleware** | {} |\n\n".format(", ".join(mw) or "None")
        + "### Purpose\n_Run with AI enabled for full description._\n\n"
        + "### Business Logic\n{}\n\n".format(steps_md)
        + "### Input Parameters\n{}\n\n".format(val_md)
        + "### Database Operations\n{}\n\n".format(q_md)
        + "### Unknowns\n{}\n\n".format(
            "\n".join("- " + u for u in unknowns) if unknowns else "None")
        + "---"
    )


def _write_sql(
    routes: List[dict],
    path: str,
    config: AIConfig,
    no_ai: bool,
    progress: ProgressTracker,
    append: bool = False,
) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    use_ai   = not no_ai and config.use_ai
    sections = []

    for route in routes:
        method    = route.get("method", "?")
        full_path = route.get("full_path", route.get("path", "?"))
        snippet   = route.get("body_snippet", "")

        # SQL tracked separately from business docs
        if progress.sql_done(method, full_path, ai=use_ai) and not append:
            continue

        if no_ai or not config.use_ai:
            # Static regex fallback
            static_qs = _static_sql(snippet)
            if static_qs:
                block = "\n".join(q["sql"] for q in static_qs)
            else:
                # Mark as done (no queries) so we don't retry forever
                progress.mark_sql(method, full_path, ai=False)
                continue
        else:
            # Only send to AI if there's something to analyze
            if not snippet and not route.get("queries"):
                progress.mark_sql(method, full_path, ai=use_ai)
                continue

            block = call_ai(
                _sql_prompt(route), config,
                system=_sql_system(), max_tokens=900,
            )
            if block.startswith("[AI failed"):
                # Fallback to static
                static_qs = _static_sql(snippet)
                if not static_qs:
                    progress.mark_sql(method, full_path, ai=use_ai)
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
        progress.mark_sql(method, full_path, ai=use_ai)

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


def _write_index(domain_map: Dict[str, List[dict]], docs_root: str) -> None:
    total = sum(len(v) for v in domain_map.values())
    with open(os.path.join(docs_root, "index.md"), "w", encoding="utf-8") as f:
        f.write("# Backend API Index\n\n")
        f.write("Total endpoints: **{}**\n\n".format(total))
        f.write("| Domain | Endpoints | API Ref | Responses | Business Docs | SQL Audit |\n")
        f.write("|--------|-----------|---------|-----------|---------------|-----------|\n")
        for domain in sorted(domain_map.keys()):
            count = len(domain_map[domain])
            b     = "./{}".format(domain)
            f.write(
                "| **{}** | {} "
                "| [api.md]({}/api.md) "
                "| [responses.md]({}/responses.md) "
                "| [business.md]({}/business.md) "
                "| [legacy_query.sql]({}/legacy_query.sql) |\n".format(
                    domain, count, b, b, b, b,
                )
            )
        f.write("\n---\n_Generated by doc_writer_\n")


# =============================================================================
# COMPATIBILITY WRAPPERS (used by main.py)
# =============================================================================

def generate_business_md(
    routes: List[dict], output_path: str, config: AIConfig,
    no_ai: bool = False, append: bool = False,
) -> None:
    state_dir = os.path.join(os.path.dirname(output_path), "..", ".docwriter")
    os.makedirs(state_dir, exist_ok=True)
    progress  = ProgressTracker(state_dir)
    _write_business_md(routes, output_path, config, no_ai, progress, append)


def generate_legacy_sql(
    routes: List[dict], output_path: str, config: AIConfig,
    no_ai: bool = False, append: bool = False,
) -> None:
    state_dir = os.path.join(os.path.dirname(output_path), "..", ".docwriter")
    os.makedirs(state_dir, exist_ok=True)
    progress  = ProgressTracker(state_dir)
    _write_sql(routes, output_path, config, no_ai, progress, append)