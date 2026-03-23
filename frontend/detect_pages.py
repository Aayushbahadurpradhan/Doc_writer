"""
detect_pages.py — Step 1 of the frontend pipeline.

Statically extracts all pages and their API dependencies from Vue/React/Inertia.

Supports:
  - Vue Router (router/index.js, router/index.ts)
  - React Router (App.jsx, App.tsx, routes.jsx, routes.tsx)
  - Inertia.js (Inertia::render PHP calls)
  - axios / fetch API calls
  - Composables (useUsers, useAuth …)
  - React hooks (useQuery, useFetch, useSWR)
  - Pinia / Vuex actions
"""

import json
import os
import re
from typing import List, Optional

FRONTEND_EXTS = {".js", ".ts", ".jsx", ".tsx", ".vue"}

SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", "dist", "build",
    ".next", ".nuxt", "coverage",
}

# ─── Helpers ──────────────────────────────────────────────────────────────────

def read_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


def _walk_frontend(root: str) -> List[str]:
    result = []
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in files:
            _, ext = os.path.splitext(fname)
            if ext in FRONTEND_EXTS:
                result.append(os.path.join(dirpath, fname))
    return result


# ─── STEP 1: Route Detection ──────────────────────────────────────────────────

def _detect_vue_routes(content: str, filepath: str) -> List[dict]:
    """Parse Vue Router definitions."""
    routes = []
    # { path: '/foo', component: FooView, ... }
    for m in re.finditer(
        r"\{\s*path\s*:\s*['\"`]([^'\"` ]+)['\"`]"
        r"(?:.*?component\s*:\s*(?:import\(['\"`][^'\"` ]+['\"`]\)\s*,\s*\(\s*\)\s*=>\s*import\(['\"`]([^'\"` ]+)['\"`]\)|(['\"`]?[\w./]+['\"`]?)))?",
        content, re.DOTALL
    ):
        path       = m.group(1)
        component  = (m.group(2) or m.group(3) or "UNKNOWN").strip("'\"` ")
        lazy       = "import(" in m.group(0)
        routes.append({
            "path":      path,
            "component": os.path.basename(component) if component != "UNKNOWN" else "UNKNOWN",
            "lazy":      lazy,
            "source":    os.path.basename(filepath),
        })
    return routes


def _detect_react_routes(content: str, filepath: str) -> List[dict]:
    """Parse React Router <Route> elements."""
    routes = []
    # <Route path="/foo" element={<FooPage />} />
    for m in re.finditer(
        r'<Route[^>]*path=["\']([^"\']+)["\'][^>]*(?:element=\{<(\w+)',
        content
    ):
        routes.append({
            "path":      m.group(1),
            "component": m.group(2) + ".jsx" if m.group(2) else "UNKNOWN",
            "lazy":      False,
            "source":    os.path.basename(filepath),
        })
    return routes


def _detect_inertia_routes(content: str, filepath: str) -> List[dict]:
    """Detect Inertia::render() calls in PHP files."""
    routes = []
    for m in re.finditer(r"Inertia::render\s*\(\s*['\"]([^'\"]+)['\"]", content):
        routes.append({
            "path":      "UNKNOWN",
            "component": m.group(1),
            "lazy":      False,
            "source":    os.path.basename(filepath),
        })
    return routes


# ─── STEP 2: Component Mapping ───────────────────────────────────────────────

def _find_component_file(component: str, all_files: List[str]) -> Optional[str]:
    """Find the actual file for a component name."""
    bare = os.path.splitext(os.path.basename(component))[0].lower()
    for f in all_files:
        if os.path.splitext(os.path.basename(f))[0].lower() == bare:
            return f
    return None


def _extract_imports(content: str) -> List[str]:
    """Extract imported component names from a file."""
    comps = []
    for m in re.finditer(
        r"import\s+(?:\{[^}]+\}|(\w+))\s+from\s*['\"`]([^'\"` ]+)['\"`]",
        content
    ):
        name = m.group(1)
        path = m.group(2)
        # Only local components (starts with ./ or ../)
        if name and (path.startswith("./") or path.startswith("../")):
            comps.append(name)
    return comps


def _extract_layout(content: str) -> str:
    """Try to detect layout wrappers in a component."""
    # <MainLayout>, <DefaultLayout>, <AppLayout>
    m = re.search(r"<(\w*[Ll]ayout\w*)", content)
    if m:
        return m.group(1)
    # definePageMeta({ layout: 'default' })  (Nuxt)
    m2 = re.search(r"layout\s*:\s*['\"](\w+)['\"]", content)
    if m2:
        return m2.group(1)
    return "UNKNOWN"


# ─── STEP 3: API Usage Tracing ────────────────────────────────────────────────

_AXIOS_RE = re.compile(
    r"(?:axios|http|api|request|client)\s*\.\s*(get|post|put|delete|patch)\s*\(\s*['\"`]([^'\"` \n]+)['\"`]",
    re.IGNORECASE
)
_FETCH_RE = re.compile(
    r"fetch\s*\(\s*['\"`]([^'\"` \n]+)['\"`]"
    r"(?:.*?method\s*:\s*['\"]([A-Z]+)['\"])?"
)
_COMPOSABLE_RE = re.compile(
    r"\b(use[A-Z]\w+)\s*\("
)
_INERTIA_FORM_RE = re.compile(
    r"useForm\s*\(|form\.(?:post|put|patch|delete)\s*\(\s*['\"`]([^'\"` \n]+)['\"`]",
    re.IGNORECASE
)
_PINIA_RE = re.compile(r"\buse(\w+Store)\s*\(")
_VUEX_RE  = re.compile(r"store\.dispatch\s*\(\s*['\"]([^'\"]+)['\"]")


def _trace_api_calls(content: str, filepath: str) -> List[dict]:
    """Trace all API calls in a single file."""
    calls = []
    fname = os.path.basename(filepath)

    for m in _AXIOS_RE.finditer(content):
        method   = m.group(1).upper()
        endpoint = m.group(2)
        if not endpoint.startswith("/"):
            endpoint = "UNKNOWN"
        calls.append({
            "endpoint":    endpoint,
            "method":      method,
            "called_from": fname,
            "via":         "axios",
        })

    for m in _FETCH_RE.finditer(content):
        endpoint = m.group(1)
        method   = m.group(2) or "GET"
        if not endpoint.startswith("/"):
            endpoint = "UNKNOWN"
        calls.append({
            "endpoint":    endpoint,
            "method":      method.upper(),
            "called_from": fname,
            "via":         "fetch",
        })

    # Inertia form submissions
    for m in _INERTIA_FORM_RE.finditer(content):
        endpoint = m.group(1) if m.group(1) else "UNKNOWN"
        calls.append({
            "endpoint":    endpoint,
            "method":      "POST",
            "called_from": fname,
            "via":         "inertia_form",
        })

    return calls


def _trace_composable_calls(
    composable_name: str,
    all_files: List[str],
    visited: set,
) -> List[dict]:
    """Recursively follow a composable to find API calls inside it."""
    if composable_name in visited:
        return []
    visited.add(composable_name)

    # Find the composable file
    bare = composable_name.lower()
    for f in all_files:
        fname_bare = os.path.splitext(os.path.basename(f))[0].lower()
        if fname_bare == bare or fname_bare == f"use{bare}".lower():
            content = read_file(f)
            return _trace_api_calls(content, f)
    return []


# ─── Public API ───────────────────────────────────────────────────────────────

def detect_pages(project_root: str) -> List[dict]:
    """
    Main entry point.
    Returns list of page dicts with API call traces.
    """
    all_files = _walk_frontend(project_root)
    php_files = []
    for dirpath, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in files:
            if fname.endswith(".php"):
                php_files.append(os.path.join(dirpath, fname))

    # ── Collect raw routes from router files ─────────────────────────────────
    raw_routes: List[dict] = []

    for fpath in all_files:
        fname = os.path.basename(fpath).lower()
        if fname in ("index.js", "index.ts", "router.js", "router.ts"):
            content = read_file(fpath)
            if "createRouter" in content or "vue-router" in content:
                raw_routes.extend(_detect_vue_routes(content, fpath))

        if fname in ("app.jsx", "app.tsx", "routes.jsx", "routes.tsx"):
            content = read_file(fpath)
            if "react-router" in content or "<Route" in content:
                raw_routes.extend(_detect_react_routes(content, fpath))

    for fpath in php_files:
        content = read_file(fpath)
        if "Inertia::render" in content:
            raw_routes.extend(_detect_inertia_routes(content, fpath))

    # If no router files found, treat ALL .vue/.jsx/.tsx files as pages
    if not raw_routes:
        for fpath in all_files:
            ext = os.path.splitext(fpath)[1]
            if ext in (".vue", ".jsx", ".tsx"):
                fname = os.path.basename(fpath)
                raw_routes.append({
                    "path":      "UNKNOWN",
                    "component": fname,
                    "lazy":      False,
                    "source":    fname,
                })

    print(f"  📄 {len(raw_routes)} pages/components detected")

    # ── Build component → API call map ────────────────────────────────────────
    pages: List[dict] = []
    visited_composables: set = set()

    for route in raw_routes:
        component = route.get("component", "UNKNOWN")
        comp_file = _find_component_file(component, all_files)
        content   = read_file(comp_file) if comp_file else ""

        # Direct API calls in this component
        api_calls = _trace_api_calls(content, comp_file or component)

        # Follow composables
        for m in _COMPOSABLE_RE.finditer(content):
            cname = m.group(1)
            for call in _trace_composable_calls(cname, all_files, set(visited_composables)):
                call["composable"] = cname
                api_calls.append(call)

        # Child components
        children = _extract_imports(content) if content else []

        # Layout
        layout = _extract_layout(content) if content else "UNKNOWN"

        # State management
        state_mgmt: List[str] = []
        if _PINIA_RE.search(content):
            state_mgmt.append("pinia")
        if _VUEX_RE.search(content):
            state_mgmt.append("vuex")
        if "useSelector" in content or "useDispatch" in content:
            state_mgmt.append("redux")

        # Unknowns
        unknowns: List[str] = []
        if not comp_file:
            unknowns.append(f"Component file not found: {component}")
        for call in api_calls:
            if call.get("endpoint") == "UNKNOWN":
                unknowns.append(
                    f"API endpoint could not be determined in {call.get('called_from','?')}"
                )

        pages.append({
            "path":             route.get("path", "UNKNOWN"),
            "component":        component,
            "layout":           layout,
            "children":         children,
            "api_calls":        api_calls,
            "state_management": state_mgmt,
            "unknowns":         unknowns,
        })

    return pages


def save_pages_json(pages: List[dict], output_path: str) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(pages, f, indent=2)
    print(f"  ✅ pages.json → {output_path}")


if __name__ == "__main__":
    import sys
    root  = sys.argv[1] if len(sys.argv) > 1 else "."
    pages = detect_pages(root)
    print(json.dumps(pages[:2], indent=2))
