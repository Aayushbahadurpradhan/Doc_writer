"""
detect_apis.py — Step 1 of the backend pipeline.

Statically extracts all API info WITHOUT AI.
Builds an intermediate JSON structure.

Supports:
  - routes/api.php, routes/web.php
  - Route::group(), ::prefix(), ::middleware()
  - closures, controller arrays, nested groups
  - Controller logic: validation, service calls, DB, events, errors
"""

import json
import os
import re
from typing import Dict, List, Optional, Tuple

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


# ─── STEP 1: Route Extraction ─────────────────────────────────────────────────

def _parse_routes_from_file(content: str, filepath: str) -> List[dict]:
    """
    Parse a Laravel route file and return a list of route dicts.
    Handles: groups, prefixes, middleware, controller arrays, @method.
    """
    routes: List[dict] = []
    prefix_stack:     List[str]       = [""]
    middleware_stack: List[List[str]] = [[]]
    namespace_stack:  List[str]       = ["App\\Http\\Controllers"]

    # Normalise line endings
    lines = content.replace("\r\n", "\n").split("\n")

    for line in lines:
        stripped = line.strip()

        # ── Group open ──────────────────────────────────────────────────────
        if "Route::group" in stripped or "Route::prefix" in stripped or \
           "Route::middleware" in stripped:

            p_m = re.search(r"['\"]prefix['\"]\s*=>\s*['\"]([^'\"]*)['\"]", stripped)
            n_m = re.search(r"['\"]namespace['\"]\s*=>\s*['\"]([^'\"]*)['\"]", stripped)
            mw_m = re.search(r"['\"]middleware['\"]\s*=>\s*\[([^\]]*)\]", stripped)
            mw_s = re.search(r"->middleware\(\s*['\"]([^'\"]+)['\"]\)", stripped)

            p = p_m.group(1).strip("/") if p_m else ""
            n = n_m.group(1).strip("\\") if n_m else ""

            new_prefix = (
                (prefix_stack[-1].rstrip("/") + "/" + p).lstrip("/") if p
                else prefix_stack[-1]
            )
            new_ns = (
                namespace_stack[-1].rstrip("\\") + "\\" + n if n
                else namespace_stack[-1]
            )

            mw: List[str] = list(middleware_stack[-1])
            if mw_m:
                mw += [x.strip().strip("'\"") for x in mw_m.group(1).split(",") if x.strip()]
            if mw_s:
                mw.append(mw_s.group(1).strip())

            prefix_stack.append(new_prefix)
            namespace_stack.append(new_ns)
            middleware_stack.append(mw)
            continue

        # ── Group close ─────────────────────────────────────────────────────
        if "});" in stripped or "})" in stripped:
            if len(prefix_stack) > 1:
                prefix_stack.pop()
                namespace_stack.pop()
                middleware_stack.pop()
            continue

        # ── Route definition ────────────────────────────────────────────────
        m = re.search(
            r"Route::(get|post|put|delete|patch|any|resource)\s*\(\s*['\"]([^'\"]*)['\"]"
            r"\s*,\s*(.*)",
            stripped, re.IGNORECASE
        )
        if not m:
            continue

        http_method = m.group(1).upper()
        rel_path    = m.group(2).strip("/")
        action_raw  = m.group(3).rstrip(");").strip()

        prefix = prefix_stack[-1].strip("/")
        full_path = ("/" + prefix + "/" + rel_path).replace("//", "/")
        if not full_path.startswith("/"):
            full_path = "/" + full_path

        # Extract middleware from chained ->middleware()
        mw_chain = re.findall(r"->middleware\(\s*['\"]([^'\"]+)['\"]\s*\)", action_raw)
        all_mw   = list(middleware_stack[-1]) + mw_chain

        # Resolve controller and action
        ctrl, func = _resolve_handler(action_raw, namespace_stack[-1])

        # Expand RESOURCE into RESTful routes
        if http_method == "RESOURCE":
            for sub in _resource_routes(full_path, ctrl):
                sub["middleware"] = all_mw
                sub["handler_file"] = os.path.basename(filepath)
                routes.append(sub)
            continue

        # Path params
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


def _resolve_handler(raw: str, namespace: str) -> Tuple[str, str]:
    """Resolve a Laravel handler string to (ControllerClass, method)."""
    # [FooController::class, 'method']
    cls_m = re.search(r"([\w\\]+)::class\s*,\s*['\"](\w+)['\"]", raw)
    if cls_m:
        return _qualify(cls_m.group(1), namespace), cls_m.group(2)

    # 'uses' => 'FooController@method'
    uses_m = re.search(r"['\"]uses['\"]\s*=>\s*['\"]([^'\"]+)['\"]", raw)
    if uses_m:
        return _at_split(_qualify(uses_m.group(1), namespace))

    # 'FooController@method'
    at_m = re.search(r"(['\"])([\w\\]+)@(\w+)\1", raw)
    if at_m:
        return _qualify(at_m.group(2), namespace), at_m.group(3)

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


def _resource_routes(base: str, ctrl: str) -> List[dict]:
    """Expand a Route::resource into individual RESTful routes."""
    base = base.rstrip("/")
    singular = base.split("/")[-1].rstrip("s") or "item"
    return [
        {"method": "GET",    "path": base,                   "full_path": base,
         "controller": ctrl, "action": "index",   "params": []},
        {"method": "POST",   "path": base,                   "full_path": base,
         "controller": ctrl, "action": "store",   "params": []},
        {"method": "GET",    "path": f"{base}/{{{singular}}}",
         "full_path": f"{base}/{{{singular}}}", "controller": ctrl,
         "action": "show",   "params": [singular]},
        {"method": "PUT",    "path": f"{base}/{{{singular}}}",
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
    r"(?:where|find|findOrFail|create|update|delete|all|get|first|"
    r"firstOrFail|firstOrCreate|updateOrCreate|upsert|insert|"
    r"count|sum|avg|max|min|exists|paginate|with|has|whereHas)\b"
)
_RAW_SQL_RE = re.compile(
    r"DB::(select|statement|insert|update|delete)\s*\(\s*['\"](.+?)['\"]",
    re.DOTALL | re.I
)
_DB_TABLE_RE = re.compile(r"DB::table\s*\(\s*['\"](\w+)['\"]\s*\)")
_SERVICE_RE  = re.compile(r"\$this->(\w+)->|self\.(\w+)\.")
_VALIDATION_RE = re.compile(
    r"(?:validate|validateWith)\s*\(\s*\[([^\]]+)\]", re.DOTALL
)
_FORM_REQUEST_RE = re.compile(r"\b(\w+Request)\b")
_DISPATCH_RE = re.compile(r"dispatch\s*\(\s*new\s+(\w+)")
_EVENT_RE    = re.compile(r"event\s*\(\s*new\s+(\w+)")
_ABORT_RE    = re.compile(r"abort\s*\(\s*(\d{3})")
_RESPONSE_RE = re.compile(r"response\(\)\s*->json\s*\(")


def _extract_function_body(content: str, func_name: str) -> str:
    if not func_name or func_name in ("unknown", "inline", ""):
        return ""
    safe = re.escape(func_name.split("\\")[-1])
    pat  = re.compile(rf"function\s+{safe}\s*\([^{{]*\{{", re.DOTALL)
    m = pat.search(content)
    if not m:
        return ""
    start = m.end()
    depth, pos = 1, start
    while pos < len(content) and depth > 0:
        if content[pos] == "{":
            depth += 1
        elif content[pos] == "}":
            depth -= 1
        pos += 1
    return content[start: pos - 1].strip()


def _find_controller_file(ctrl: str, project_root: str) -> Optional[str]:
    bare = ctrl.split("\\")[-1].lower()
    for dirpath, _, files in os.walk(project_root):
        for fname in files:
            if fname.endswith(".php") and fname.lower().replace(".php", "") == bare:
                return os.path.join(dirpath, fname)
    return None


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

    # Service calls
    for svc, svc2 in _SERVICE_RE.findall(body):
        name = svc or svc2
        steps.append({"type": "service_call", "target": name})

    # Eloquent models
    for m in _MODEL_RE.finditer(body):
        model = m.group(1)
        if model not in _SKIP_MODELS:
            op = m.group(0).split("::")[-1]
            queries.append({"type": "eloquent", "model": model, "operation": op})
            steps.append({"type": "db_query", "query_type": "eloquent", "model": model})

    # DB::table
    for m in _DB_TABLE_RE.finditer(body):
        queries.append({"type": "query_builder", "table": m.group(1), "operation": "UNKNOWN"})
        steps.append({"type": "db_query", "query_type": "query_builder", "table": m.group(1)})

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
    route_dir  = os.path.join(project_root, "routes")
    route_files = _find_php_files(route_dir) if os.path.isdir(route_dir) \
                  else _find_php_files(project_root)

    all_routes: List[dict] = []
    for rf in route_files:
        if os.path.basename(rf) in ("api.php", "web.php", "routes.php") or \
           "routes" in rf.replace("\\", "/"):
            content = read_file(rf)
            if "Route::" in content:
                all_routes.extend(_parse_routes_from_file(content, rf))

    print(f"  📋 {len(all_routes)} routes extracted from route files")

    # De-duplicate
    seen: dict = {}
    for r in all_routes:
        key = (r["method"], r["full_path"])
        if key not in seen:
            seen[key] = r

    unique = list(seen.values())

    # Trace controller logic
    for route in unique:
        ctrl = route.get("controller", "")
        func = route.get("action", "")
        if ctrl in ("Closure", "Unknown", "") or func == "unknown":
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
                          "errors": [], "response": {}, "unknowns": [f"Controller file not found: {ctrl}"]})
            continue

        body = _extract_function_body(read_file(ctrl_file), func)
        if not body:
            route.update({"steps": [], "validation": {}, "queries": [],
                          "errors": [], "response": {}, "unknowns": [f"Body of {func}() could not be extracted"]})
            continue

        route.update(_trace_controller(body))
        route["body_snippet"] = body[:3000]

    return unique


def save_routes_json(routes: List[dict], output_path: str) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    # Remove body_snippet from JSON (keep docs clean)
    clean = [{k: v for k, v in r.items() if k != "body_snippet"} for r in routes]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2)
    print(f"  ✅ routes.json → {output_path}")


if __name__ == "__main__":
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    routes = detect_apis(root)
    print(json.dumps(routes[:3], indent=2))
