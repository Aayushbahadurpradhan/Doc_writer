"""
detect_apis.py — Step 1 of the backend pipeline.

Statically extracts all API info WITHOUT AI.
Builds an intermediate JSON structure.

Supports:
  - routes/api.php, routes/web.php, and any PHP file under routes/
  - require/include of sub-route files (e.g. require __DIR__.'/v1.php')
  - Route::group(), ::prefix(), ::middleware(), ::controller(), ::namespace()
  - Fluent chaining: Route::prefix()->middleware()->group()
  - closures, controller arrays [Ctrl::class,'method'], Ctrl@method
  - Invokable controllers: Route::get('/path', FooController::class)
  - Route::resource, Route::apiResource, Route::match
  - Laravel 9+ Route::controller(Foo::class)->group()
  - Multi-line route definitions collapsed to single lines
  - Controller logic: validation, service calls, DB, events, errors
  - Case-insensitive method body extraction (PHP methods are case-insensitive)
  - Allman brace style support (opening { on next line)
"""

import json
import os
import re
from typing import Dict, List, Optional, Set, Tuple

# ─── Helpers ──────────────────────────────────────────────────────────────────

def read_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


def _find_php_files(root: str, subdir: str = "") -> List[str]:
    target = os.path.join(root, subdir) if subdir else root
    result = []
    for dirpath, _, files in os.walk(target):
        for f in files:
            if f.endswith(".php"):
                result.append(os.path.join(dirpath, f))
    return result


# ─── Pre-processing helpers ────────────────────────────────────────────────────

def _strip_php_comments(content: str) -> str:
    """Remove PHP block comments (/* … */), line comments (// …), and # comments."""
    content = re.sub(r"/\*.*?\*/", " ", content, flags=re.DOTALL)
    content = re.sub(r"//[^\n]*", "", content)
    content = re.sub(r"(?m)^\s*#[^\n]*", "", content)
    return content


def _remove_strings(text: str) -> str:
    """Replace string *contents* with spaces so brace/bracket counting is safe."""
    result: List[str] = []
    in_str = False
    str_ch = ""
    escape_next = False
    for c in text:
        if escape_next:
            result.append(" ")
            escape_next = False
            continue
        if in_str:
            if c == "\\":
                escape_next = True
                result.append(" ")
            elif c == str_ch:
                in_str = False
                result.append(c)
            else:
                result.append(" ")
        elif c in ('"', "'"):
            in_str = True
            str_ch = c
            result.append(c)
        else:
            result.append(c)
    return "".join(result)


def _count_braces(text: str) -> Tuple[int, int]:
    """Return (opens, closes) counting { } outside PHP strings."""
    clean = _remove_strings(text)
    return clean.count("{"), clean.count("}")


def _collapse_multiline_routes(content: str) -> str:
    """
    Collapse multi-line Route:: statements into single lines.

    Two patterns handled:
    1. Array handler split across lines:
         Route::post('/path', [\\n  Ctrl::class,\\n  'method'\\n]);
       Collapsed because square brackets [ are unbalanced.

    2. Fluent chain split across lines:
         Route::prefix('v1')\\n  ->middleware([...])\\n  ->group(function() {
       Collapsed because next lines start with '->'

    Group bodies are NOT collapsed (stops at lines ending with '{').
    """
    lines = content.split("\n")
    result: List[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not re.search(r"\bRoute::", stripped):
            result.append(line)
            i += 1
            continue

        collected = [stripped]
        i += 1

        clean = _remove_strings(stripped)
        bracket_depth = clean.count("[") - clean.count("]")

        # Case 1: unclosed [ — collect array continuation lines
        while bracket_depth > 0 and i < len(lines):
            ns = lines[i].strip()
            cnext = _remove_strings(ns)
            bracket_depth += cnext.count("[") - cnext.count("]")
            collected.append(ns)
            i += 1

        # Case 2: fluent chain — collect while next line starts with ->
        while i < len(lines):
            ns = lines[i].strip()
            if not ns.startswith("->"):
                break
            collected.append(ns)
            i += 1
            # If this chained line opens a closure body, stop here
            if ns.rstrip().endswith("{"):
                break

        result.append(" ".join(collected))

    return "\n".join(result)


def _is_group_opener(stripped: str) -> bool:
    """
    True when the line declares a Route namespace/group scope.
    Must ① reference a group call AND ② open a closure body (ends with '{').
    Inline closure routes (Route::get('/p', function(){…})) are not group openers.
    """
    if not stripped.rstrip().endswith("{"):
        return False
    if "function" not in stripped:
        return False
    return bool(re.search(r"(?:Route::group|->group)\s*\(", stripped))


def _parse_group_attrs(
    stripped: str,
    prefix_stack: List[str],
    namespace_stack: List[str],
    middleware_stack: List[List[str]],
    controller_stack: List[str],
) -> dict:
    """Extract prefix / middleware / namespace / controller from a group-opener line."""

    # ── prefix ────────────────────────────────────────────────────────────────
    p = ""
    p_arr = re.search(r"['\"]prefix['\"]\s*=>\s*['\"]([^'\"]*)['\"]", stripped)
    if p_arr:
        p = p_arr.group(1).strip("/")
    else:
        p_flu = re.search(
            r"(?:Route::prefix|->prefix)\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", stripped
        )
        if p_flu:
            p = p_flu.group(1).strip("/")

    # ── namespace ─────────────────────────────────────────────────────────────
    ns = ""
    n_arr = re.search(r"['\"]namespace['\"]\s*=>\s*['\"]([^'\"]*)['\"]", stripped)
    if n_arr:
        ns = n_arr.group(1).strip("\\").replace("/", "\\")
    else:
        n_flu = re.search(
            r"(?:Route::namespace|->namespace)\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", stripped
        )
        if n_flu:
            ns = n_flu.group(1).strip("\\").replace("/", "\\")

    # ── middleware ────────────────────────────────────────────────────────────
    mw: List[str] = list(middleware_stack[-1])

    def _add_mw(raw: str) -> None:
        for x in raw.split(","):
            v = x.strip().strip("'\" ")
            if v:
                mw.append(v)

    mw_arr = re.search(r"['\"]middleware['\"]\s*=>\s*\[([^\]]*)\]", stripped)
    if mw_arr:
        _add_mw(mw_arr.group(1))
    else:
        mw_str = re.search(r"['\"]middleware['\"]\s*=>\s*['\"]([^'\"]+)['\"]", stripped)
        if mw_str:
            mw.append(mw_str.group(1))

    for bracket, string in re.findall(
        r"(?:Route::middleware|->middleware)\s*\(\s*(?:\[([^\]]*)\]|['\"]([^'\"]+)['\"])\s*\)",
        stripped,
    ):
        if bracket:
            _add_mw(bracket)
        if string:
            mw.append(string)

    # ── Laravel 9+ Route::controller(FooController::class) ───────────────────
    ctrl = controller_stack[-1]
    ctrl_m = re.search(r"Route::controller\(\s*([\w\\]+)::class\s*\)", stripped)
    if ctrl_m:
        ctrl = _qualify(ctrl_m.group(1), namespace_stack[-1])

    # ── Build new stack frames ─────────────────────────────────────────────────
    new_prefix = (
        (prefix_stack[-1].rstrip("/") + "/" + p).lstrip("/") if p else prefix_stack[-1]
    )
    new_ns = (
        namespace_stack[-1].rstrip("\\") + "\\" + ns if ns else namespace_stack[-1]
    )

    return {"prefix": new_prefix, "namespace": new_ns, "middleware": mw, "controller": ctrl}


def _find_included_route_files(content: str, base_dir: str) -> List[str]:
    """Resolve require/include statements in a route file to real file paths."""
    found: List[str] = []
    pat = re.compile(
        r"(?:require|include)(?:_once)?\s*\(?\s*(?:__DIR__\s*\.\s*)?['\"]([^'\"]+\.php)['\"]"
    )
    for m in pat.finditer(content):
        rel = m.group(1)
        if not os.path.isabs(rel):
            rel = os.path.join(base_dir, rel)
        path = os.path.normpath(rel)
        if os.path.exists(path):
            found.append(path)
    return found


# ─── STEP 1: Route Extraction ─────────────────────────────────────────────────

# Matches: Route::(verb)('/path', handler...)
_ROUTE_RE = re.compile(
    r"Route::(get|post|put|delete|patch|any|resource|apiResource|options|head)"
    r"\s*\(\s*['\"]([^'\"]*)['\"]"
    r"\s*,\s*(.*)",
    re.IGNORECASE,
)
# Matches: Route::match(['get','post'], '/path', handler...)
_MATCH_RE = re.compile(
    r"Route::match\s*\(\s*\[([^\]]*)\]\s*,\s*['\"]([^'\"]*)['\"]"
    r"\s*,\s*(.*)",
    re.IGNORECASE,
)


def _parse_routes_from_file(content: str, filepath: str) -> List[dict]:
    """
    Parse a Laravel route file.  Two-pass approach:

    Pass 1 – pre-process:
      • Strip PHP comments
      • Collapse multi-line Route:: handler arrays + fluent chains

    Pass 2 – line-by-line with brace-depth group tracking:
      • Group openers  → push prefix/middleware/namespace/controller stacks
      • Brace counting → pop stacks when group scope closes
      • Route lines    → emit route dicts
    """
    routes: List[dict] = []

    prefix_stack:     List[str]       = [""]
    middleware_stack: List[List[str]] = [[]]
    namespace_stack:  List[str]       = ["App\\Http\\Controllers"]
    controller_stack: List[str]       = [""]   # Laravel 9+ Route::controller() groups

    # Stack-tracking: depth value at which each group was opened
    group_at_depth: List[int] = []
    brace_depth: int = 0

    content = content.replace("\r\n", "\n")
    content = _strip_php_comments(content)
    content = _collapse_multiline_routes(content)

    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue

        opens, closes = _count_braces(stripped)

        # ── Group opener ────────────────────────────────────────────────────
        if _is_group_opener(stripped):
            attrs = _parse_group_attrs(
                stripped, prefix_stack, namespace_stack,
                middleware_stack, controller_stack,
            )
            group_at_depth.append(brace_depth)
            prefix_stack.append(attrs["prefix"])
            namespace_stack.append(attrs["namespace"])
            middleware_stack.append(attrs["middleware"])
            controller_stack.append(attrs["controller"])
            brace_depth += opens - closes
            continue

        # ── Update depth then check for group closes ────────────────────────
        brace_depth += opens - closes
        while group_at_depth and group_at_depth[-1] >= brace_depth:
            group_at_depth.pop()
            if len(prefix_stack) > 1:
                prefix_stack.pop()
                namespace_stack.pop()
                middleware_stack.pop()
                controller_stack.pop()

        # ── Route::match(['get','post'], …) ─────────────────────────────────
        mm = _MATCH_RE.search(stripped)
        if mm:
            methods_raw = mm.group(1)
            rel_path    = mm.group(2).strip("/")
            action_raw  = mm.group(3).rstrip(");").strip()
            http_methods = [
                x.strip().strip("'\"").upper()
                for x in methods_raw.split(",") if x.strip()
            ]
            prefix    = prefix_stack[-1].strip("/")
            full_path = ("/" + prefix + "/" + rel_path).replace("//", "/")
            if not full_path.startswith("/"):
                full_path = "/" + full_path
            mw_chain = re.findall(r"->middleware\(\s*['\"]([^'\"]+)['\"]\s*\)", action_raw)
            all_mw   = list(middleware_stack[-1]) + mw_chain
            ctrl, func = _resolve_handler(
                action_raw, namespace_stack[-1], controller_stack[-1]
            )
            params = re.findall(r"\{(\w+)\??}", full_path)
            for meth in http_methods:
                routes.append({
                    "method": meth, "path": rel_path, "full_path": full_path,
                    "controller": ctrl, "action": func,
                    "middleware": all_mw, "params": params,
                    "handler_file": os.path.basename(filepath),
                })
            continue

        # ── Standard Route::(verb) ──────────────────────────────────────────
        m = _ROUTE_RE.search(stripped)
        if not m:
            continue

        http_method = m.group(1).upper()
        rel_path    = m.group(2).strip("/")
        action_raw  = m.group(3).rstrip(");").strip()

        prefix    = prefix_stack[-1].strip("/")
        full_path = ("/" + prefix + "/" + rel_path).replace("//", "/")
        if not full_path.startswith("/"):
            full_path = "/" + full_path

        mw_chain = re.findall(r"->middleware\(\s*['\"]([^'\"]+)['\"]\s*\)", action_raw)
        all_mw   = list(middleware_stack[-1]) + mw_chain

        ctrl, func = _resolve_handler(
            action_raw, namespace_stack[-1], controller_stack[-1]
        )

        if http_method in ("RESOURCE", "APIRESOURCE"):
            expand_fn = _api_resource_routes if http_method == "APIRESOURCE" \
                        else _resource_routes
            for sub in expand_fn(full_path, ctrl):
                sub["middleware"]    = all_mw
                sub["handler_file"]  = os.path.basename(filepath)
                routes.append(sub)
            continue

        params = re.findall(r"\{(\w+)\??}", full_path)
        routes.append({
            "method":       http_method,
            "path":         rel_path,
            "full_path":    full_path,
            "controller":   ctrl,
            "action":       func,
            "middleware":   all_mw,
            "params":       params,
            "handler_file": os.path.basename(filepath),
        })

    return routes


def _resolve_handler(raw: str, namespace: str, current_controller: str = "") -> Tuple[str, str]:
    """Resolve a Laravel handler string to (ControllerClass, method).

    Supports:
      [FooController::class, 'method']       — array style
      'FooController@method'                 — @ style
      'uses' => 'FooController@method'       — named uses
      FooController::class                   — invokable (__invoke)
      'method'                               — bare string inside Route::controller() group
      function(...)                          — closure
    """
    raw = raw.strip()

    # [FooController::class, 'method']
    cls_m = re.search(r"([\w\\]+)::class\s*,\s*['\"](\w+)['\"]", raw)
    if cls_m:
        return _qualify(cls_m.group(1), namespace), cls_m.group(2)

    # Invokable: FooController::class  (bare, no method string)
    invoke_m = re.search(r"^\[?\s*([\w\\]+)::class\s*\]?$", raw.rstrip(");").strip())
    if invoke_m:
        return _qualify(invoke_m.group(1), namespace), "__invoke"

    # 'uses' => 'FooController@method'
    uses_m = re.search(r"['\"]uses['\"]\s*=>\s*['\"]([^'\"]+)['\"]", raw)
    if uses_m:
        return _at_split(_qualify(uses_m.group(1), namespace))

    # 'FooController@method'
    at_m = re.search(r"(['\"])([\w\\]+)@(\w+)\1", raw)
    if at_m:
        return _qualify(at_m.group(2), namespace), at_m.group(3)

    # Bare string method name inside a Route::controller() group
    bare_m = re.search(r"^['\"](\w+)['\"]$", raw.strip().rstrip(");"))
    if bare_m and current_controller:
        return current_controller, bare_m.group(1)

    # Closure
    if "function" in raw.lower() or raw.strip() in ("[]", ""):
        return "Closure", "unknown"

    return _qualify(raw.strip("'\" []"), namespace), "unknown"


def _qualify(ctrl: str, namespace: str) -> str:
    """Add namespace prefix if class is not already fully qualified."""
    if "\\" in ctrl or ctrl in ("Closure", "Unknown", ""):
        return ctrl
    return f"{namespace}\\{ctrl}"


def _at_split(handler: str) -> Tuple[str, str]:
    if "@" in handler:
        parts = handler.split("@", 1)
        return parts[0], parts[1]
    return handler, "unknown"


def _singularize(word: str) -> str:
    """Basic English singularisation — handles the worst edge-cases."""
    if not word:
        return word
    w = word.lower()
    # words that must NOT be changed
    _NO_CHANGE = {
        "news", "series", "species", "address", "access", "process",
        "progress", "status", "canvas", "alias", "axis", "basis",
        "analysis", "diagnosis", "campus", "virus", "census",
    }
    if w in _NO_CHANGE or len(w) <= 3:
        return word
    if w.endswith("ies") and len(w) > 4:
        return word[:-3] + "y"          # policies -> policy
    if w.endswith("ves") and len(w) > 5:
        return word[:-3] + "f"          # leaves -> leaf
    if w.endswith("sses") or w.endswith("xes") or w.endswith("ches") or w.endswith("shes"):
        return word[:-2]                # addresses -> address, boxes -> box
    if w.endswith("ses") and len(w) > 5:
        return word[:-2]                # statuses -> status
    if w.endswith("s") and not w.endswith("ss") and len(w) > 4:
        return word[:-1]                # agents -> agent
    return word


def _resource_routes(base: str, ctrl: str) -> List[dict]:
    """Expand a Route::resource into 7 standard RESTful routes (Laravel default).

    Route::resource registers all 7 CRUD routes including the HTML form helpers
    (create, edit).  Use _api_resource_routes for Route::apiResource which omits
    those two and adds PATCH instead.
    """
    base = base.rstrip("/")
    singular = _singularize(base.split("/")[-1]) or "item"
    return [
        {"method": "GET",    "path": base,
         "full_path": base,
         "controller": ctrl, "action": "index",   "params": []},
        {"method": "GET",    "path": f"{base}/create",
         "full_path": f"{base}/create",
         "controller": ctrl, "action": "create",  "params": []},
        {"method": "POST",   "path": base,
         "full_path": base,
         "controller": ctrl, "action": "store",   "params": []},
        {"method": "GET",    "path": f"{base}/{{{singular}}}",
         "full_path": f"{base}/{{{singular}}}",
         "controller": ctrl, "action": "show",    "params": [singular]},
        {"method": "GET",    "path": f"{base}/{{{singular}}}/edit",
         "full_path": f"{base}/{{{singular}}}/edit",
         "controller": ctrl, "action": "edit",    "params": [singular]},
        {"method": "PUT",    "path": f"{base}/{{{singular}}}",
         "full_path": f"{base}/{{{singular}}}",
         "controller": ctrl, "action": "update",  "params": [singular]},
        {"method": "DELETE", "path": f"{base}/{{{singular}}}",
         "full_path": f"{base}/{{{singular}}}",
         "controller": ctrl, "action": "destroy", "params": [singular]},
    ]


def _api_resource_routes(base: str, ctrl: str) -> List[dict]:
    """Expand Route::apiResource (no create/edit HTML routes; adds PATCH)."""
    base = base.rstrip("/")
    name = base.split("/")[-1]
    singular = _singularize(name) or "item"
    return [
        {"method": "GET",    "path": base, "full_path": base,
         "controller": ctrl, "action": "index",   "params": []},
        {"method": "POST",   "path": base, "full_path": base,
         "controller": ctrl, "action": "store",   "params": []},
        {"method": "GET",    "path": f"{base}/{{{singular}}}",
         "full_path": f"{base}/{{{singular}}}", "controller": ctrl,
         "action": "show",   "params": [singular]},
        {"method": "PUT",    "path": f"{base}/{{{singular}}}",
         "full_path": f"{base}/{{{singular}}}", "controller": ctrl,
         "action": "update", "params": [singular]},
        {"method": "PATCH",  "path": f"{base}/{{{singular}}}",
         "full_path": f"{base}/{{{singular}}}", "controller": ctrl,
         "action": "update", "params": [singular]},
        {"method": "DELETE", "path": f"{base}/{{{singular}}}",
         "full_path": f"{base}/{{{singular}}}", "controller": ctrl,
         "action": "destroy","params": [singular]},
    ]


# ─── STEP 2: Controller Logic Trace ──────────────────────────────────────────

_SKIP_MODELS = {
    "DB", "Auth", "Cache", "Config", "Cookie", "Crypt", "Event", "Facade",
    "File", "Gate", "Hash", "Http", "Job", "Lang", "Log", "Mail",
    "Notification", "Queue", "Redirect", "Request", "Response", "Route",
    "Schema", "Session", "Storage", "Str", "Trans", "URL", "Validator",
    "View", "Carbon", "Artisan", "App", "Bus", "Broadcast", "Pipeline",
    "RateLimiter", "Password", "Arr",
}

_MODEL_RE = re.compile(
    r"\b([A-Z][a-zA-Z0-9]+)::"
    r"(?:query|where|find|findOrFail|create|update|delete|all|get|first|"
    r"firstOrFail|firstOrCreate|updateOrCreate|upsert|insert|select|"
    r"count|sum|avg|max|min|exists|paginate|with|has|whereHas|"
    r"orderBy|groupBy|join|leftJoin|rightJoin|raw)\b"
)
_RAW_SQL_RE = re.compile(
    r"DB::(select|statement|insert|update|delete)\s*\(\s*['\"](.+?)['\"]",
    re.DOTALL | re.I
)
_DB_TABLE_RE    = re.compile(r"DB::table\s*\(\s*['\"]([\w]+)['\"]\s*\)")
_DB_CONN_RE     = re.compile(r"DB::connection\s*\(\s*['\"]([\w]+)['\"]\s*\)")
_SERVICE_RE     = re.compile(r"\$this->(\w+)->|self\.(\w+)\.")
# Static Helper / Facade calls (e.g. AgentHelper::getList(), SomeService::call())
_HELPER_RE      = re.compile(
    r"\b([A-Z][a-zA-Z0-9]*(?:Helper|Facade|Service|Manager|Handler|Repository|Factory|Provider|Sync))"
    r"::(\w+)\s*\("
)
# new SomeRepository() / new SomeService() instantiation
_REPO_INST_RE   = re.compile(
    r"new\s+([A-Z][a-zA-Z0-9]*(?:Repository|Service|Manager|Provider|Handler|Factory))\s*\("
)
# ->get() / ->first() / ->exists() etc. on query builder chains (model-agnostic)
_QUERY_CHAIN_RE = re.compile(
    r"->(get|first|firstOrFail|paginate|exists|count|sum|avg|max|min|all|toArray|pluck|value)\s*\("
)
_VALIDATION_RE = re.compile(
    r"(?:validate|validateWith)\s*\(\s*\[([^\]]+)\]", re.DOTALL
)
_FORM_REQUEST_RE = re.compile(r"\b(\w+Request)\b")
_DISPATCH_RE = re.compile(r"dispatch\s*\(\s*new\s+(\w+)")
_EVENT_RE    = re.compile(r"event\s*\(\s*new\s+(\w+)")
_ABORT_RE    = re.compile(r"abort\s*\(\s*(\d{3})")
_RESPONSE_RE = re.compile(r"response\(\)\s*->json\s*\(")


def _extract_function_body(content: str, func_name: str) -> str:
    """
    Extract a PHP method body robustly.

    Improvements over the original regex approach:
      • Case-insensitive matching (PHP method names are case-insensitive)
      • Proper paren-depth counting for multi-line signatures
      • Handles Allman brace style (opening '{' on next line)
      • Handles return type annotations (: array, : JsonResponse|null, etc.)
      • Skips abstract/interface methods (';' before '{')
    """
    if not func_name or func_name in ("unknown", "inline", "", "__invoke"):
        # For __invoke we search without a specific name below
        if func_name != "__invoke":
            return ""

    if func_name == "__invoke":
        safe = "__invoke"
    else:
        safe = re.escape(func_name.split("\\")[-1])

    pat = re.compile(rf"\bfunction\s+{safe}\s*\(", re.IGNORECASE)
    m = pat.search(content)
    if not m:
        return ""

    n = len(content)
    pos = m.end() - 1  # position of the opening '('

    # Walk paren depth to find the matching ')'
    paren_depth = 0
    while pos < n:
        c = content[pos]
        if c == "(":
            paren_depth += 1
        elif c == ")":
            paren_depth -= 1
            if paren_depth == 0:
                pos += 1
                break
        pos += 1

    if paren_depth != 0:
        return ""  # unmatched parens

    # Scan ahead (up to 500 chars) for '{', handling return-type annotations.
    # An abstract method has ';' before any '{' — skip those.
    window_end = min(pos + 500, n)
    window = content[pos:window_end]
    brace_idx = window.find("{")
    if brace_idx == -1:
        return ""  # abstract / interface method

    semi_idx = window.find(";")
    if semi_idx != -1 and semi_idx < brace_idx:
        return ""  # abstract method — no body

    start = pos + brace_idx + 1

    # Extract body using brace depth counting
    depth = 1
    pos2  = start
    while pos2 < n and depth > 0:
        c = content[pos2]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        pos2 += 1

    return content[start: pos2 - 1].strip()


_FC_SKIP_DIRS = {
    "vendor", "node_modules", ".git", "storage", "__pycache__",
    "tests", "bootstrap", "public", "resources", "database",
    "config", "logs", "docs", "api_audit",
}


def _find_controller_file(ctrl: str, project_root: str) -> Optional[str]:
    r"""
    Locate a PHP controller file.

    Strategy 1 (preferred): convert namespace to filesystem path.
      App\Http\Controllers\Api\V1\AuthController
      -> {root}/app/Http/Controllers/Api/V1/AuthController.php

    Strategy 2 (fallback): walk PHP files, score candidates by how many
      namespace segments appear in their path (most specific wins).
    """
    if not ctrl or ctrl in ("Closure", "Unknown"):
        return None

    bare = ctrl.split("\\")[-1].lower()

    # ── Strategy 1: namespace → path ─────────────────────────────────────────
    if "\\" in ctrl:
        parts = ctrl.split("\\")
        # Laravel convention: top-level 'App' maps to <root>/app/
        if parts[0].lower() == "app":
            parts[0] = "app"
        rel = os.path.join(*parts) + ".php"
        candidate = os.path.join(project_root, rel)
        if os.path.exists(candidate):
            return candidate

        # Sub-path under app/Http/Controllers
        try:
            ci = next(i for i, p in enumerate(parts) if p.lower() == "controllers")
            sub = parts[ci + 1:]
            if sub:
                base = os.path.join(project_root, "app", "Http", "Controllers")
                candidate2 = os.path.join(base, *sub) + ".php"
                if os.path.exists(candidate2):
                    return candidate2
        except StopIteration:
            pass

    # ── Strategy 2: scored directory walk ────────────────────────────────────
    ctrl_lower_parts = [p.lower() for p in ctrl.split("\\")]
    matches: List[Tuple[int, str]] = []

    for dirpath, dirs, files in os.walk(project_root):
        # Prune irrelevant top-level dirs to speed up the walk
        dirs[:] = [d for d in dirs if d.lower() not in _FC_SKIP_DIRS]
        for fname in files:
            if not fname.endswith(".php"):
                continue
            if fname.lower().replace(".php", "") != bare:
                continue
            fpath = os.path.join(dirpath, fname)
            path_lower = fpath.lower().replace("\\", "/")
            score = sum(1 for p in ctrl_lower_parts if p in path_lower)
            matches.append((score, fpath))

    if not matches:
        return None
    return max(matches, key=lambda x: x[0])[1]


def _find_all_controller_files(ctrl: str, project_root: str) -> List[str]:
    """
    Return ALL candidate controller files sorted by score (best first).
    Used for fallback when the top-scoring file doesn't contain the method.
    """
    if not ctrl:
        return []
    bare = ctrl.split("\\")[-1].lower()
    ctrl_lower_parts = [p.lower() for p in ctrl.split("\\")]
    matches: List[Tuple[int, str]] = []

    for dirpath, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if d.lower() not in _FC_SKIP_DIRS]
        for fname in files:
            if not fname.endswith(".php"):
                continue
            if fname.lower().replace(".php", "") != bare:
                continue
            fpath = os.path.join(dirpath, fname)
            path_lower = fpath.lower().replace("\\", "/")
            score = sum(1 for p in ctrl_lower_parts if p in path_lower)
            matches.append((score, fpath))

    matches.sort(key=lambda x: x[0], reverse=True)
    return [m[1] for m in matches]


def _trace_controller(body: str) -> dict:
    """Extract logic from a controller method body."""
    steps:     List[dict] = []
    unknowns:  List[str]  = []
    queries:   List[dict] = []
    errors:    List[dict] = []
    validation: dict      = {}

    # Validation
    val_m = _VALIDATION_RE.search(body)
    if val_m:
        for rule in val_m.group(1).split(","):
            kv = rule.strip().split("=>")
            if len(kv) == 2:
                k = kv[0].strip().strip("'\" ")
                v = kv[1].strip().strip("'\" ")
                validation[k] = v
        steps.append({"type": "validation", "detail": "inline validate()"})

    # FormRequest
    for fr in _FORM_REQUEST_RE.findall(body):
        steps.append({"type": "validation", "detail": fr})
        validation.setdefault("_form_request", fr)

    # Service calls via injected property (double-arrow: $this->svc->method)
    seen_svc: set = set()
    for svc, svc2 in _SERVICE_RE.findall(body):
        name = svc or svc2
        if name not in seen_svc:
            seen_svc.add(name)
            steps.append({"type": "service_call", "target": name})

    # Static Helper / Facade / Service calls (e.g. AgentHelper::getList())
    seen_helpers: set = set()
    for m in _HELPER_RE.finditer(body):
        cls, method = m.group(1), m.group(2)
        if cls not in _SKIP_MODELS and cls not in seen_helpers:
            seen_helpers.add(cls)
            steps.append({"type": "helper_call", "class": cls, "method": method})

    # new Repository/Service() instantiation
    for m in _REPO_INST_RE.finditer(body):
        cls = m.group(1)
        if cls not in seen_helpers:
            seen_helpers.add(cls)
            steps.append({"type": "service_call", "target": cls})

    # Eloquent models (::where, ::find, ::query, ::create, etc.)
    seen_models: set = set()
    for m in _MODEL_RE.finditer(body):
        model = m.group(1)
        if model not in _SKIP_MODELS:
            op = m.group(0).split("::")[-1]
            key = (model, op)
            if key not in seen_models:
                seen_models.add(key)
                queries.append({"type": "eloquent", "model": model, "operation": op})
                steps.append({"type": "db_query", "query_type": "eloquent", "model": model})

    # DB::table
    for m in _DB_TABLE_RE.finditer(body):
        tbl = m.group(1)
        queries.append({"type": "query_builder", "table": tbl, "operation": "UNKNOWN"})
        steps.append({"type": "db_query", "query_type": "query_builder", "table": tbl})

    # DB::connection
    for m in _DB_CONN_RE.finditer(body):
        queries.append({"type": "query_builder", "connection": m.group(1), "operation": "UNKNOWN"})
        steps.append({"type": "db_query", "query_type": "query_builder", "connection": m.group(1)})

        # Any other ClassName::method() static call not yet caught above
    # Covers custom Eloquent scopes (User::findByEmail), model factories, etc.
    _STATIC_SKIP_SFXS = (
        "Helper", "Facade", "Service", "Manager", "Handler",
        "Repository", "Factory", "Provider", "Sync", "Request",
        "Response", "Controller", "Middleware", "Event", "Job",
        "Rule", "Resource", "Collection", "Listener",
    )
    _BROAD_STATIC_RE = re.compile(r"\b([A-Z][a-zA-Z0-9]+)::(\w+)\s*\(")
    seen_all = set(seen_models) | seen_helpers | set(_SKIP_MODELS)
    for m in _BROAD_STATIC_RE.finditer(body):
        cls, method = m.group(1), m.group(2)
        if cls in seen_all or method in ("class", ""):
            continue
        seen_all.add(cls)
        if any(cls.endswith(s) for s in _STATIC_SKIP_SFXS):
            steps.append({"type": "helper_call", "class": cls, "method": method})
        else:
            queries.append({"type": "eloquent", "model": cls, "operation": method})
            steps.append({"type": "db_query", "query_type": "eloquent", "model": cls})

    # Query builder terminal methods when no model detected yet (anonymous chains)
    if not queries and _QUERY_CHAIN_RE.search(body):
        for m in _QUERY_CHAIN_RE.finditer(body):
            steps.append({"type": "db_query", "query_type": "query_builder",
                          "operation": m.group(1)})
        queries.append({"type": "query_builder", "operation": "UNKNOWN"})

    # Raw SQL
    for m in _RAW_SQL_RE.finditer(body):
        queries.append({"type": "raw_sql", "query": m.group(2)[:200]})
        steps.append({"type": "db_query", "query_type": "raw_sql"})

    # Dispatched jobs
    for job in _DISPATCH_RE.findall(body):
        steps.append({"type": "job_dispatch", "name": job})

    # Events
    for ev in _EVENT_RE.findall(body):
        steps.append({"type": "event", "name": ev})

    # Abort / errors
    for code in _ABORT_RE.findall(body):
        errors.append({"type": "abort", "code": int(code)})

    # Response fields (heuristic)
    response: dict = {}
    if _RESPONSE_RE.search(body):
        response["type"] = "json"
        fields = re.findall(r"['\"](\w+)['\"]\s*=>", body)
        response["fields"] = list(dict.fromkeys(fields))[:20]

    # Detect unknowns (dynamic dispatch)
    if "$this->" in body and not steps:
        unknowns.append("Dynamic method calls detected — manual review needed")

    return {
        "steps":      steps,
        "validation": validation,
        "queries":    queries,
        "errors":     errors,
        "response":   response,
        "unknowns":   unknowns,
    }


# ─── Public API ───────────────────────────────────────────────────────────────

def detect_apis(project_root: str) -> List[dict]:
    """
    Main entry point.
    Returns a list of enriched route dicts with controller logic traced.
    """
    route_dir   = os.path.join(project_root, "routes")
    route_files = _find_php_files(route_dir) if os.path.isdir(route_dir) \
                  else _find_php_files(project_root)

    # Resolve only files that look like route registrations
    def _is_route_file(path: str) -> bool:
        norm = path.replace("\\", "/")
        name = os.path.basename(path)
        return (
            name in ("api.php", "web.php", "routes.php")
            or "/routes/" in norm
        )

    # Collect route files (including those pulled in via require/include)
    processed_files: Set[str] = set()
    pending: List[str] = [rf for rf in route_files if _is_route_file(rf)]

    all_routes: List[dict] = []
    while pending:
        rf = pending.pop(0)
        rf_norm = os.path.normpath(rf)
        if rf_norm in processed_files:
            continue
        processed_files.add(rf_norm)

        content = read_file(rf)
        if "Route::" not in content:
            continue

        all_routes.extend(_parse_routes_from_file(content, rf))

        # Discover sub-route files pulled in via require/include
        base_dir = os.path.dirname(rf)
        for sub in _find_included_route_files(content, base_dir):
            sub_norm = os.path.normpath(sub)
            if sub_norm not in processed_files:
                pending.append(sub)

    print("[*] {} routes extracted from route files".format(len(all_routes)))

    # De-duplicate (method + full_path) — keep last registration, matching
    # Laravel's behaviour where the last Route::xxx() definition wins.
    seen: dict = {}
    for r in all_routes:
        key = (r["method"], r["full_path"])
        seen[key] = r   # overwrite → last one wins
    unique = list(seen.values())

    dup_count = len(all_routes) - len(unique)
    if dup_count:
        print(
            "[!] {} duplicate route registration(s) found in source and removed "
            "(same method+path registered more than once).".format(dup_count)
        )

    # Trace controller logic
    for route in unique:
        ctrl = route.get("controller", "")
        func = route.get("action", "")

        # Normalize mixed forward/backslash in controller namespace
        ctrl = ctrl.replace("/", "\\")
        route["controller"] = ctrl

        if ctrl in ("Closure", "Unknown", "") or func in ("unknown",):
            route["steps"]      = []
            route["validation"] = {}
            route["queries"]    = []
            route["errors"]     = []
            route["response"]   = {}
            route["unknowns"]   = ["Closure or unknown handler — cannot trace statically"]
            continue

        ctrl_file = _find_controller_file(ctrl, project_root)
        if not ctrl_file:
            route.update({"steps": [], "validation": {}, "queries": [],
                          "errors": [], "response": {},
                          "unknowns": [f"Controller file not found: {ctrl}"]})
            continue

        body = _extract_function_body(read_file(ctrl_file), func)

        # Fallback: try all other candidate files
        if not body:
            for alt_file in _find_all_controller_files(ctrl, project_root):
                if alt_file == ctrl_file:
                    continue
                alt_body = _extract_function_body(read_file(alt_file), func)
                if alt_body:
                    body = alt_body
                    ctrl_file = alt_file
                    break

        if not body:
            route.update({"steps": [], "validation": {}, "queries": [],
                          "errors": [], "response": {},
                          "unknowns": [f"Body of {func}() could not be extracted"]})
            continue

        route.update(_trace_controller(body))
        route["body_snippet"] = body[:3000]

    return unique


def save_routes_json(routes: List[dict], output_path: str) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(routes, f, indent=2)
    print(f"  [OK] routes.json -> {output_path}")


if __name__ == "__main__":
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    routes = detect_apis(root)
    print(json.dumps(routes[:3], indent=2))
