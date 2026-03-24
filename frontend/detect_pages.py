"""
detect_pages.py — Step 1 of the frontend pipeline.

Statically extracts all pages and their API dependencies from Vue/React/Inertia.

Supports:
  - Vue Router (router/index.js, router/index.ts)
  - React Router (App.jsx, App.tsx, routes.jsx, routes.tsx)
  - Inertia.js (Inertia::render PHP calls)
  - axios / fetch / $http / $axios API calls
  - Composables (useUsers, useAuth, ...)
  - React hooks (useQuery, useFetch, useSWR, useMutation)
  - Pinia / Vuex store detection
  - Options API components: {} registration
  - @/ alias import paths (Vue Vite/CLI projects)
  - Nuxt 3 definePageMeta layout detection
"""

import json
import os
import re
from typing import Dict, List, Optional, Set

FRONTEND_EXTS = {".js", ".ts", ".jsx", ".tsx", ".vue"}

SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", "dist", "build",
    ".next", ".nuxt", "coverage",
}

# Composables that belong to frameworks, not the app — skip tracing these
_FRAMEWORK_COMPOSABLES: Set[str] = {
    "useRouter", "useRoute", "useI18n", "useNuxtApp", "useState",
    "useHead", "useRuntimeConfig", "useAttrs", "useSlots", "useContext",
    "useLink", "useNavigate", "useLocation", "useParams", "useSearchParams",
    "useRef", "useState", "useEffect", "useCallback", "useMemo", "useContext",
    "useReducer", "useImperativeHandle", "useLayoutEffect", "useDebugValue",
    "useId", "useDeferredValue", "useTransition",
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


def _is_local_path(p: str) -> bool:
    """True for ./foo, ../foo, or @/foo (Vue alias)."""
    return p.startswith("./") or p.startswith("../") or p.startswith("@/")


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
    """
    Find the actual source file for a component name.
    Handles: FooView, FooPage, Foo, foo.vue, path/to/Foo
    """
    bare = os.path.splitext(os.path.basename(component))[0].lower()
    # Also try stripping common Vue suffixes: View, Page, Component
    bare_stripped = re.sub(r"(view|page|component)$", "", bare)

    for f in all_files:
        fname_bare = os.path.splitext(os.path.basename(f))[0].lower()
        if fname_bare == bare or (bare_stripped and fname_bare == bare_stripped):
            return f
    return None


def _extract_imports(content: str) -> List[str]:
    """
    Extract imported component names from a file.
    Handles:
      - Default imports:  import Foo from './Foo.vue'
      - Default w/ alias: import Foo from '@/components/Foo.vue'
      - Named imports:    import { Foo, Bar } from '@/components'
      - Options API:      components: { Foo, Bar }
      - Async:            defineAsyncComponent(() => import('@/Foo.vue'))
    """
    comps: Set[str] = set()

    # Default imports from local paths (./  ../  @/)
    for m in re.finditer(
        r"import\s+(\w+)\s+from\s*['\"`](@?[./][^'\"` \n]+)['\"`]",
        content,
    ):
        name, path = m.group(1), m.group(2)
        if name[0].isupper() and _is_local_path(path):
            comps.add(name)

    # Named / destructured imports from local paths
    for m in re.finditer(
        r"import\s+\{([^}]+)\}\s+from\s*['\"`](@?[./][^'\"` \n]+)['\"`]",
        content,
    ):
        if _is_local_path(m.group(2)):
            for name in re.findall(r"\b([A-Z]\w+)\b", m.group(1)):
                comps.add(name)

    # Options API: components: { Foo, Bar }
    for m in re.finditer(r"\bcomponents\s*:\s*\{([^}]+)\}", content):
        for name in re.findall(r"\b([A-Z]\w+)\b", m.group(1)):
            comps.add(name)

    # defineAsyncComponent(() => import('./Foo.vue'))
    for m in re.finditer(
        r"defineAsyncComponent\s*\([^)]*import\s*\(\s*['\"`][^'\"` \n]*/(\w+)['\"`]",
        content,
    ):
        comps.add(m.group(1))

    return sorted(comps)


def _extract_layout(content: str) -> str:
    """
    Detect the layout used by a component.
    Priority order:
      1. Nuxt 3 definePageMeta({ layout: '...' })
      2. layout: '...' anywhere in the file (route meta, options API)
      3. <AppLayout>, <MainLayout>, <AdminLayout>, <AuthLayout>, etc.
      4. Generic <*Layout> tags
    """
    # 1. Nuxt 3 definePageMeta
    m = re.search(
        r"definePageMeta\s*\(\s*\{[^}]*\blayout\s*:\s*['\"](\w[\w-]*)['\"]",
        content, re.DOTALL,
    )
    if m:
        return m.group(1)

    # 2. layout property in route meta or options
    m = re.search(r"\blayout\s*:\s*['\"](\w[\w-]*)['\"]", content)
    if m:
        return m.group(1)

    # 3. Named layout component tags: <AppLayout>, <AdminLayout>, etc.
    m = re.search(
        r"<((?:App|Main|Admin|Default|Base|Auth|Dashboard|Public|Private|Guest)"
        r"\w*[Ll]ayout\b)",
        content,
    )
    if m:
        return m.group(1)

    # 4. Any *Layout tag
    m = re.search(r"<(\w*[Ll]ayout\b)", content)
    if m:
        return m.group(1)

    return "UNKNOWN"


# ─── STEP 3: API Usage Tracing ────────────────────────────────────────────────

_AXIOS_RE = re.compile(
    r"(?:axios|http|api|request|client|\$http|\$axios)\s*\.\s*(get|post|put|delete|patch)\s*\(\s*['\"`]([^'\"` \n]+)['\"`]",
    re.IGNORECASE,
)
_FETCH_RE = re.compile(
    r"fetch\s*\(\s*['\"`]([^'\"` \n]+)['\"`]"
    r"(?:[^)]*method\s*:\s*['\"]([A-Z]+)['\"])?",
)
_COMPOSABLE_RE = re.compile(r"\b(use[A-Z]\w+)\s*\(")
_INERTIA_FORM_RE = re.compile(
    r"form\s*\.\s*(?:post|put|patch|delete|get)\s*\(\s*['\"`]([^'\"` \n]+)['\"`]",
    re.IGNORECASE,
)
_PINIA_RE  = re.compile(r"\buse(\w+Store)\s*\(")
_VUEX_RE   = re.compile(
    r"(?:store\.(?:dispatch|commit)\s*\(|mapState\s*\(|mapGetters\s*\(|"
    r"mapActions\s*\(|mapMutations\s*\(|useStore\s*\(\s*\)\s*(?!.*pinia))"
)
_RQ_RE     = re.compile(r"\b(useQuery|useMutation|useSWR|useInfiniteQuery)\s*\(")


def _trace_api_calls(content: str, filepath: str) -> List[dict]:
    """Trace all direct API calls in a single file."""
    calls = []
    fname = os.path.basename(filepath) if filepath else "UNKNOWN"

    for m in _AXIOS_RE.finditer(content):
        method   = m.group(1).upper()
        endpoint = m.group(2)
        if not endpoint.startswith("/") and not endpoint.startswith("http"):
            endpoint = "UNKNOWN"
        calls.append({"endpoint": endpoint, "method": method, "called_from": fname, "via": "axios"})

    for m in _FETCH_RE.finditer(content):
        endpoint = m.group(1)
        method   = (m.group(2) or "GET").upper()
        if not endpoint.startswith("/") and not endpoint.startswith("http"):
            endpoint = "UNKNOWN"
        calls.append({"endpoint": endpoint, "method": method, "called_from": fname, "via": "fetch"})

    for m in _INERTIA_FORM_RE.finditer(content):
        endpoint = m.group(1)
        calls.append({"endpoint": endpoint, "method": "POST", "called_from": fname, "via": "inertia_form"})

    return calls

def _trace_composable_calls(
    composable_name: str,
    all_files: List[str],
    visited: Set[str],
) -> List[dict]:
    """Recursively follow a composable to find API calls inside it."""
    if composable_name in visited:
        return []
    visited.add(composable_name)

    bare = composable_name.lower()
    for f in all_files:
        fname_bare = os.path.splitext(os.path.basename(f))[0].lower()
        if fname_bare == bare or fname_bare == f"use{bare}".lower():
            content = read_file(f)
            return _trace_api_calls(content, f)
    return []


# ─── STEP 4: Template Component Detection ────────────────────────────────────

# Standard HTML / Vue built-in tags — NOT counted as child components
_HTML_TAGS: Set[str] = {
    'a', 'abbr', 'address', 'area', 'article', 'aside', 'audio', 'b', 'br',
    'button', 'canvas', 'caption', 'cite', 'code', 'col', 'colgroup', 'data',
    'datalist', 'dd', 'del', 'details', 'dfn', 'dialog', 'div', 'dl', 'dt',
    'em', 'embed', 'fieldset', 'figcaption', 'figure', 'footer', 'form',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'head', 'header', 'hr', 'html',
    'i', 'iframe', 'img', 'input', 'ins', 'kbd', 'label', 'legend', 'li',
    'link', 'main', 'map', 'mark', 'menu', 'meta', 'meter', 'nav', 'noscript',
    'object', 'ol', 'optgroup', 'option', 'output', 'p', 'picture', 'pre',
    'progress', 'q', 'rp', 'rt', 'ruby', 's', 'samp', 'script', 'section',
    'select', 'small', 'source', 'span', 'strong', 'style', 'sub', 'summary',
    'sup', 'table', 'tbody', 'td', 'template', 'textarea', 'tfoot', 'th',
    'thead', 'time', 'title', 'tr', 'track', 'u', 'ul', 'var', 'video', 'wbr',
    # Vue / Nuxt built-ins
    'component', 'transition', 'transition-group', 'keep-alive', 'slot',
    'router-view', 'router-link', 'nuxt', 'nuxt-link', 'client-only', 'no-ssr',
}


def _extract_template_components(content: str) -> List[str]:
    """
    Detect components actually used in the file's template section.
    Works for:
      - Vuetify v-* components  (grouped as summary: [vuetify] v-dialog, ...)
      - Third-party kebab-case   <multiselect>, <date-picker>, ...
      - PascalCase local usage   <UserTable>, <MyModal>

    Strategy: scan the entire file for opening tags to handle nested
    <template> blocks (e.g. Vue 2 inner <template> for conditionals).
    """
    vuetify: Set[str] = set()
    pascal:  Set[str] = set()
    kebab:   Set[str] = set()

    for m in re.finditer(r'</?([a-zA-Z][a-zA-Z0-9-]*)', content):
        tag = m.group(1)
        if tag.startswith('v-'):
            vuetify.add(tag)
        elif tag[0].isupper():
            pascal.add(tag)
        elif tag.lower() not in _HTML_TAGS:
            # Catches both kebab-case (multiselect-input) and
            # single-word third-party tags (multiselect, datepicker, ...)
            kebab.add(tag)

    result: List[str] = []
    result.extend(sorted(pascal))
    result.extend(sorted(kebab))
    if vuetify:
        sv      = sorted(vuetify)
        preview = ', '.join(sv[:6])
        suffix  = ', ...' if len(sv) > 6 else ''
        result.append(f"[vuetify] {preview}{suffix}")
    return result


# ─── STEP 5: Example URL Builder ──────────────────────────────────────────────

_PARAM_EXAMPLES: Dict[str, str] = {
    'id':         '1',
    'pid':        '1',
    'gid':        '1',
    'aid':        '1',
    'agent_id':   '1',
    'policy_id':  '1',
    'policyid':   '1',
    'invoice_id': '1',
    'groupid':    '1',
    'month':      '2025-01',
    'date':       '2025-01-01',
    'ptdate':     '2025-01-01',
    'invDate':    '2025-01',
    'type':       'all',
    'status':     'active',
    'filter':     'all',
    'val':        '1',
    'cnt':        '1',
    'title':      'example',
    'invType':    'standard',
    'payType':    'check',
    'method':     'card',
}


def _build_example_url(path: str, base_url: str = "http://localhost:8000") -> str:
    """
    Build an example browser URL from a route path.
      /admin/affiliate/configure/:id  →  http://localhost:8000/admin/affiliate/configure/1
      /admin/billing/:invType/:payType/:filter/:date  →  .../standard/check/all/2025-01-01
    """
    if not path or path in ("UNKNOWN", "/"):
        return f"{base_url}/"

    def _replace(m: re.Match) -> str:
        param = m.group(1).rstrip('?')   # strip optional marker
        return _PARAM_EXAMPLES.get(param, f"{{{param}}}")

    result = re.sub(r':([\w?]+)', _replace, path).rstrip('/')
    return f"{base_url}{result}"


# ─── STEP 6: State Management Detection ───────────────────────────────────────

def _detect_state_management(content: str, composable_names: List[str]) -> List[str]:
    """
    Return a deduplicated list of state management patterns found.
    Examples: ['pinia:AuthStore', 'pinia:CartStore', 'react-query:useQuery']
    """
    found: List[str] = []

    # Pinia: _PINIA_RE captures e.g. "AuthStore" from useAuthStore()
    for store_name in _PINIA_RE.findall(content):
        label = f"pinia:{store_name}"
        if label not in found:
            found.append(label)

    # Vuex
    if _VUEX_RE.search(content):
        if "vuex" not in found:
            found.append("vuex")

    # Redux
    if re.search(r"\buseSelector\b|\buseDispatch\b", content):
        if "redux" not in found:
            found.append("redux")

    # React Query / SWR
    for hook in dict.fromkeys(_RQ_RE.findall(content)):
        label = f"react-query:{hook}"
        if label not in found:
            found.append(label)

    # Composables that look like state (contain Store/State/Auth/Session/User/…)
    state_pattern = re.compile(r"Store|State|Auth|Session|User|Cart|Modal|Permission", re.IGNORECASE)
    for cname in composable_names:
        if state_pattern.search(cname) and cname not in _FRAMEWORK_COMPOSABLES:
            label = f"composable:{cname}"
            if label not in found:
                found.append(label)

    return found


# ─── Public API ───────────────────────────────────────────────────────────────

def detect_pages(project_root: str) -> List[dict]:
    """
    Main entry point.
    Returns list of page dicts with full API call traces, children, layout,
    state management, and composable information.
    """
    all_files = _walk_frontend(project_root)
    php_files = []
    for dirpath, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in files:
            if fname.endswith(".php"):
                php_files.append(os.path.join(dirpath, fname))

    # ── Collect raw routes from router files ──────────────────────────────────
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

    # Deduplicate routes by (path, component)
    seen: set = set()
    deduped: List[dict] = []
    for r in raw_routes:
        key = (r["path"], r["component"])
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    raw_routes = deduped

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

    print(f"  [{len(raw_routes)} pages/components detected]")

    # ── Build component -> full page record ───────────────────────────────────
    pages: List[dict] = []

    for route in raw_routes:
        component = route.get("component", "UNKNOWN")
        comp_file = _find_component_file(component, all_files)
        content   = read_file(comp_file) if comp_file else ""

        # ── Direct API calls in this component ──────────────────────────────
        api_calls: List[dict] = _trace_api_calls(content, comp_file or component)

        # ── Composables used (skip framework ones) ───────────────────────────
        raw_composables = _COMPOSABLE_RE.findall(content) if content else []
        composable_names = [c for c in raw_composables if c not in _FRAMEWORK_COMPOSABLES]
        composable_names = list(dict.fromkeys(composable_names))  # deduplicate, keep order

        # ── Trace through composables to find their API calls ────────────────
        for cname in composable_names:
            for call in _trace_composable_calls(cname, all_files, set()):
                call["composable"] = cname
                api_calls.append(call)

        # ── Deduplicate API calls (same endpoint+method+caller) ──────────────
        seen_calls: set = set()
        deduped_calls: List[dict] = []
        for call in api_calls:
            key = (call.get("endpoint"), call.get("method"), call.get("called_from"))
            if key not in seen_calls:
                seen_calls.add(key)
                deduped_calls.append(call)
        api_calls = deduped_calls

        # ── Child components: local imports ───────────────────────────────────
        children = _extract_imports(content) if content else []

        # ── Child components: template component tags (Vue 2 / Vuetify) ──────
        template_components = _extract_template_components(content) if content else []

        # ── Layout ───────────────────────────────────────────────────────────
        layout = _extract_layout(content) if content else "UNKNOWN"

        # ── State management ─────────────────────────────────────────────────
        state_mgmt = _detect_state_management(content, composable_names) if content else []

        # ── Example URL ───────────────────────────────────────────────────────
        example_url = _build_example_url(route.get("path", "UNKNOWN"))

        # ── Unknowns / warnings ──────────────────────────────────────────────
        unknowns: List[str] = []
        if not comp_file:
            unknowns.append(f"Component file not found: {component}")
        for call in api_calls:
            if call.get("endpoint") == "UNKNOWN":
                unknowns.append(
                    f"Dynamic endpoint in {call.get('called_from', '?')}"
                )

        pages.append({
            "path":                route.get("path", "UNKNOWN"),
            "component":           component,
            "component_file":      (
                os.path.relpath(comp_file, project_root).replace("\\", "/")
                if comp_file else None
            ),
            "example_url":         example_url,
            "layout":              layout,
            "children":            children,
            "template_components": template_components,
            "composables":         composable_names,
            "api_calls":           api_calls,
            "state_management":    state_mgmt,
            "unknowns":            unknowns,
        })

    return pages


def save_pages_json(pages: List[dict], output_path: str) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(pages, f, indent=2)
    print(f"  [SAVED] pages.json -> {output_path}")


if __name__ == "__main__":
    import sys
    root  = sys.argv[1] if len(sys.argv) > 1 else "."
    pages = detect_pages(root)
    print(json.dumps(pages[:2], indent=2))
