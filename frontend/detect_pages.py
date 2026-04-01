"""
detect_pages.py — Step 1 of the frontend pipeline.

Statically extracts all pages and their API dependencies from Vue/React/Inertia.

Supports:
  - Vue Router (router/index.js, router/index.ts, routes.ts exports)
  - React Router (App.jsx, App.tsx, routes.jsx, routes.tsx)
  - Inertia.js (Inertia::render PHP calls)
  - axios / fetch / $http / $axios / named axios instances
  - this.$axios / this.$http / this.$api (Vue Options API)
  - $api({ url, method }) / $request({ url, method })
  - Template-literal URLs (`/api/${id}`) — static prefix extracted
  - Variable URL resolution: const url = '/api/users'  →  axios.get(url)
  - Composables — recursively traced (2 levels deep)
  - Pinia store defineStore actions scanned for API calls
  - Vuex dispatch('module/action') mapped to store module files
  - services/, api/, stores/, composables/ directories fully scanned
  - GraphQL: Apollo useQuery / useMutation, gql`` tagged templates
  - WebSocket: new WebSocket(url)
  - RTK Query createApi() endpoint definitions
  - React hooks: useQuery, useFetch, useSWR, useMutation, useInfiniteQuery
  - .env / .env.local / .env.production scanned for API base URLs
  - constants.js / config.js / api.config.ts scanned for URL constants
  - @/ alias import paths resolved
  - Nuxt 3 definePageMeta layout detection
"""

import json
import os
import re
from typing import Dict, List, Optional, Set, Tuple

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
    """
    Parse Vue Router definitions.
    Handles:
      - { path: '/foo', component: FooView }
      - { path: '/foo', component: () => import('./FooView.vue') }  (lazy)
      - Flat array exports: export default [ { path, component } ]
      - Named exports: export const routes = [ ... ]
    """
    routes = []
    fname  = os.path.basename(filepath)

    # Lazy: component: () => import('./Foo.vue')
    for m in re.finditer(
        r"\{\s*path\s*:\s*['\"`]([^'\"` \n]+)['\"`]"
        r"[\s\S]{0,300}?component\s*:\s*(?:\(\s*\)\s*=>|)\s*"
        r"(?:import\s*\(\s*['\"`]([^'\"` \n]+)['\"`]\s*\))",
        content, re.DOTALL,
    ):
        path  = m.group(1)
        comp  = os.path.basename(m.group(2))
        if path and path.startswith("/"):
            routes.append({"path": path, "component": comp, "lazy": True,  "source": fname})

    # Static named component: component: FooView
    for m in re.finditer(
        r"\{\s*path\s*:\s*['\"`]([^'\"` \n]+)['\"`]"
        r"[\s\S]{0,200}?component\s*:\s*([A-Za-z_$]\w*)",
        content, re.DOTALL,
    ):
        path = m.group(1)
        comp = m.group(2).strip()
        if path and path.startswith("/") and comp not in ("import", "require", "undefined", "null"):
            routes.append({"path": path, "component": comp, "lazy": False, "source": fname})

    # Deduplicate by (path, component)
    seen: Set[tuple] = set()
    unique = []
    for r in routes:
        k = (r["path"], r["component"])
        if k not in seen:
            seen.add(k)
            unique.append(r)
    return unique


def _detect_react_routes(content: str, filepath: str) -> List[dict]:
    """Parse React Router <Route> and createBrowserRouter() definitions."""
    routes = []
    fname  = os.path.basename(filepath)

    # JSX: <Route path="/foo" element={<FooPage />} />
    for m in re.finditer(
        r'<Route[^>]*path=["\']([^"\']+)["\'][^>]*(?:element=\{<(\w+)|component=\{(\w+))',
        content,
    ):
        comp = m.group(2) or m.group(3) or "UNKNOWN"
        routes.append({"path": m.group(1), "component": comp, "lazy": False, "source": fname})

    # createBrowserRouter / createHashRouter array syntax
    for m in re.finditer(
        r'\{\s*path\s*:\s*["\']([^"\']+)["\']\s*,\s*(?:element|component)\s*:\s*'
        r'(?:<\s*)?(\w+)',
        content,
    ):
        routes.append({"path": m.group(1), "component": m.group(2), "lazy": False, "source": fname})

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

# ── Core HTTP call patterns ───────────────────────────────────────────────────

# Named axios instance calls + standard names + $axios / $http
_AXIOS_RE = re.compile(
    r"(?:this\.)?(?:axios|http|api|request|client|\$http|\$axios|\$api|"
    r"\w+(?:Api|Client|Http|Axios|Service|Instance|Request))"
    r"\s*\.\s*(get|post|put|delete|patch)\s*\(\s*['\"`]([^'\"` \n]+)['\"`]",
    re.IGNORECASE,
)
# Template-literal URLs: api.get(`/path/${id}`)
_AXIOS_TMPL_RE = re.compile(
    r"(?:this\.)?(?:axios|http|api|request|client|\$http|\$axios|\$api|"
    r"\w+(?:Api|Client|Http|Axios|Service|Instance|Request))"
    r"\s*\.\s*(get|post|put|delete|patch)\s*\(\s*`([^`\n]{3,120})`",
    re.IGNORECASE,
)
# Variable URL: axios.get(url) / http.post(endpoint) — variable name, not string
_AXIOS_VAR_RE = re.compile(
    r"(?:this\.)?(?:axios|http|api|request|client|\$http|\$axios|\$api|"
    r"\w+(?:Api|Client|Http|Axios|Service|Instance|Request))"
    r"\s*\.\s*(get|post|put|delete|patch)\s*\(\s*([a-zA-Z_$]\w*)\s*[,)]",
    re.IGNORECASE,
)
# Object-style: $api({ url: '/path', method: 'POST' })
_OBJ_CALL_RE = re.compile(
    r"(?:this\.)?(?:\$api|\$request|\$http|axios|http|api|request|client)"
    r"\s*\(\s*\{[^}]{0,400}url\s*:\s*['\"`]([^'\"` \n]+)['\"`][^}]{0,200}"
    r"(?:method\s*:\s*['\"]([A-Z]+)['\"])?",
    re.IGNORECASE | re.DOTALL,
)
# fetch() with string URL
_FETCH_RE = re.compile(
    r"fetch\s*\(\s*['\"`]([^'\"` \n]+)['\"`]"
    r"(?:[^)]{0,200}method\s*:\s*['\"]([A-Z]+)['\"])?",
    re.DOTALL,
)
# fetch with template literal
_FETCH_TMPL_RE = re.compile(
    r"fetch\s*\(\s*`([^`\n]{3,120})`"
    r"(?:[^)]{0,200}method\s*:\s*['\"]([A-Z]+)['\"])?",
    re.DOTALL,
)
# Inertia form submit
_INERTIA_FORM_RE = re.compile(
    r"form\s*\.\s*(post|put|patch|delete|get)\s*\(\s*['\"`]([^'\"` \n]+)['\"`]",
    re.IGNORECASE,
)
# Inertia router visit
_INERTIA_VISIT_RE = re.compile(
    r"(?:router|Inertia)\s*\.\s*(visit|get|post|put|patch|delete)\s*\(\s*['\"`]([^'\"` \n]+)['\"`]",
    re.IGNORECASE,
)

# ── GraphQL ───────────────────────────────────────────────────────────────────
# Apollo useQuery(QUERY_NAME) / useMutation(MUT_NAME)
_APOLLO_RE = re.compile(
    r"\b(useQuery|useMutation|useSubscription|useLazyQuery)\s*\(\s*([A-Z_][A-Z0-9_]*)",
    re.IGNORECASE,
)
# gql`query { users { id } }` or gql`mutation { ... }` — extract operation type
_GQL_TAG_RE = re.compile(
    r"\bgql\s*`\s*(query|mutation|subscription)\s+(\w*)",
    re.IGNORECASE,
)
# Apollo client direct: client.query({ query: GET_USERS })
_APOLLO_CLIENT_RE = re.compile(
    r"client\s*\.\s*(query|mutate|subscribe)\s*\(\s*\{[^}]{0,200}query\s*:\s*([A-Z_]\w*)",
    re.IGNORECASE,
)

# ── WebSocket ─────────────────────────────────────────────────────────────────
_WS_RE = re.compile(
    r"new\s+WebSocket\s*\(\s*['\"`](wss?://[^'\"` \n]+)['\"`]",
    re.IGNORECASE,
)
_WS_TMPL_RE = re.compile(
    r"new\s+WebSocket\s*\(\s*`([^`\n]{3,120})`",
    re.IGNORECASE,
)

# ── RTK Query ─────────────────────────────────────────────────────────────────
# createApi({ baseQuery: fetchBaseQuery({ baseUrl: '/api' }), endpoints: {...} })
_RTK_BASE_RE = re.compile(
    r"fetchBaseQuery\s*\(\s*\{[^}]{0,200}baseUrl\s*:\s*['\"`]([^'\"` \n]+)['\"`]",
    re.IGNORECASE,
)
# builder.query({ query: () => '/users' })  or  builder.mutation({ query: (arg) => '/users' })
_RTK_EP_RE = re.compile(
    r"builder\s*\.\s*(query|mutation)\s*\(\s*\{[^}]{0,400}query\s*:\s*(?:\([^)]*\)\s*=>\s*)?['\"`]([^'\"` \n]+)['\"`]",
    re.IGNORECASE,
)

# ── Composables / Stores ──────────────────────────────────────────────────────
_COMPOSABLE_RE    = re.compile(r"\b(use[A-Z]\w+)\s*\(")
_PINIA_RE         = re.compile(r"\buse(\w+Store)\s*\(")
_VUEX_DISPATCH_RE = re.compile(
    r"(?:store|this\.\$store)\s*\.\s*dispatch\s*\(\s*['\"`]([^'\"` \n]+)['\"`]",
    re.IGNORECASE,
)
_VUEX_RE = re.compile(
    r"(?:store\.(?:dispatch|commit)\s*\(|mapState\s*\(|mapGetters\s*\(|"
    r"mapActions\s*\(|mapMutations\s*\(|useStore\s*\(\s*\)\s*(?!.*pinia))"
)
_RQ_RE = re.compile(r"\b(useQuery|useMutation|useSWR|useInfiniteQuery)\s*\(")

# ── axios.create / config ─────────────────────────────────────────────────────
_AXIOS_BASE_RE = re.compile(
    r"axios\.create\s*\([^)]{0,400}baseURL\s*:\s*['\"`]([^'\"` \n]+)['\"`]",
    re.IGNORECASE | re.DOTALL,
)
# Variable URL declaration: const apiUrl = '/api/v1' or let BASE = '/api'
_VAR_URL_RE = re.compile(
    r"(?:const|let|var)\s+(\w+)\s*=\s*['\"`](/[^'\"` \n]{1,80})['\"`]",
)


def _extract_axios_base_urls(content: str) -> List[str]:
    """Return all baseURL values found in axios.create() calls."""
    return [m.group(1) for m in _AXIOS_BASE_RE.finditer(content)]


def _build_var_url_map(content: str) -> Dict[str, str]:
    """
    Build a map of variable_name -> URL string for variables declared in the file.
    E.g. `const API_URL = '/api/v1'` → {'API_URL': '/api/v1'}
    """
    mapping: Dict[str, str] = {}
    for m in _VAR_URL_RE.finditer(content):
        mapping[m.group(1)] = m.group(2)
    return mapping


def _extract_context_snippet(content: str, match_start: int, lines_before: int = 5,
                              lines_after: int = 5) -> str:
    """
    Return up to `lines_before` + `lines_after` source lines centred on the
    line that contains the character offset `match_start`.
    Used to give AI / devs enough context to infer a runtime-dynamic URL.
    """
    lines = content.splitlines()
    # Find which line index contains match_start
    pos = 0
    target_line = 0
    for i, line in enumerate(lines):
        if pos + len(line) + 1 > match_start:
            target_line = i
            break
        pos += len(line) + 1

    start = max(0, target_line - lines_before)
    end   = min(len(lines), target_line + lines_after + 1)
    return "\n".join(lines[start:end])


# Patterns to identify what context surrounds an API call
_FN_NAME_RE = re.compile(
    r"(?:async\s+)?(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?"
    r"(?:function|\([^)]*\)\s*=>|\w+\s*=>))",
)
_LIFECYCLE_RE = re.compile(
    r"\b(onMounted|onCreated|onBeforeMount|onUpdated|mounted|created|"
    r"beforeMount|setup|ngOnInit|componentDidMount|componentDidUpdate|"
    r"useEffect|onLoad|onShow|onActivated)\b",
)
_EVENT_HANDLER_RE = re.compile(
    r"(?:@(?:click|submit|change|input|blur|focus|keyup|keydown|keypress|"
    r"select|reset|scroll|load|mouseover|mouseout|mouseenter|mouseleave|"
    r"dblclick|contextmenu)|v-on:\w+|on[A-Z]\w+\s*=|@\w+\s*=)",
)
_COMMENT_RE = re.compile(
    r"(?://\s*(.+)|/\*\*?\s*([\s\S]{0,200}?)\*/)",
)
_WATCHER_RE = re.compile(
    r"\bwatch\s*\(\s*(?:\(\s*\)|[^,)]+),|watchEffect\s*\(",
)


def _infer_call_purpose(content: str, match_start: int) -> dict:
    """
    Analyse the ~30 lines surrounding an API call to infer its business purpose.

    Returns a dict with:
      function_name   : enclosing function/method name (or None)
      trigger         : 'lifecycle' / 'event_handler' / 'watcher' / 'inline' / 'unknown'
      trigger_name    : specific hook or event name (e.g. 'onMounted', '@submit')
      comment         : nearest preceding comment (or None)
      purpose         : short human-readable purpose string (best effort)
    """
    lines       = content.splitlines()
    # Map each character offset to its line index
    pos         = 0
    target_line = 0
    for i, line in enumerate(lines):
        if pos + len(line) + 1 > match_start:
            target_line = i
            break
        pos += len(line) + 1

    # Window: 25 lines before the call
    window_start = max(0, target_line - 25)
    window_lines = lines[window_start:target_line + 1]
    window       = "\n".join(window_lines)

    # ── 1. Find enclosing function name ──────────────────────────────────────
    fn_name = None
    for m in _FN_NAME_RE.finditer(window):
        fn_name = m.group(1) or m.group(2)
    # Also check method shorthand: async submitForm() {
    method_m = re.search(
        r"\b(?:async\s+)?([a-zA-Z_$]\w*)\s*\([^)]*\)\s*\{[^}]*$",
        window,
    )
    if method_m and not fn_name:
        fn_name = method_m.group(1)

    # ── 2. Detect trigger type ──────────────────────────────────────────────
    trigger      = "unknown"
    trigger_name = None

    lc_m = _LIFECYCLE_RE.search(window)
    if lc_m:
        trigger      = "lifecycle"
        trigger_name = lc_m.group(1)

    ev_m = _EVENT_HANDLER_RE.search(window)
    if ev_m:
        trigger      = "event_handler"
        trigger_name = ev_m.group(0).strip()

    wa_m = _WATCHER_RE.search(window)
    if wa_m:
        trigger      = "watcher"
        trigger_name = "watch"

    if trigger == "unknown" and fn_name:
        trigger = "function_call"

    # ── 3. Find nearest preceding comment ────────────────────────────────────
    comment = None
    for m in _COMMENT_RE.finditer(window):
        raw = (m.group(1) or m.group(2) or "").strip()
        if raw:
            comment = raw[:120]        # cap at 120 chars

    # ── 4. Build short purpose string ────────────────────────────────────────
    parts = []
    if trigger == "lifecycle":
        parts.append(f"Called on {trigger_name}")
    elif trigger == "event_handler":
        ev = trigger_name.lstrip("@").lstrip("v-on:").split("=")[0].strip()
        parts.append(f"Triggered by {ev} event")
    elif trigger == "watcher":
        parts.append("Called in reactive watcher")
    elif trigger == "function_call" and fn_name:
        parts.append(f"Called in {fn_name}()")

    if comment:
        parts.append(comment)

    purpose = " — ".join(parts) if parts else "inline call"

    return {
        "function_name": fn_name,
        "trigger":       trigger,
        "trigger_name":  trigger_name,
        "comment":       comment,
        "purpose":       purpose,
    }


def _trace_api_calls(content: str, filepath: str) -> List[dict]:
    """
    Trace ALL API calls in a single file, preserving every occurrence (no dedup).

    Every call entry includes:
      endpoint, method, called_from, via, dynamic, context_snippet,
      purpose (inferred business logic), function_name, trigger, trigger_name

    Detects:
      - Named/standard axios instance calls (string + template literal + variable)
      - fetch() (string + template literal)
      - Object-style $api({ url, method })
      - Inertia form.post() / router.visit()
      - GraphQL Apollo useQuery / useMutation / client.query
      - WebSocket new WebSocket(url)
      - RTK Query builder.query/mutation endpoints
    """
    calls: List[dict] = []
    fname    = os.path.basename(filepath) if filepath else "UNKNOWN"
    var_urls = _build_var_url_map(content)

    def _make(endpoint, method, via, m_start, dynamic=False, extra=None):
        """Build a call dict — always include purpose inference."""
        purpose_info = _infer_call_purpose(content, m_start)
        is_unknown   = (endpoint == "UNKNOWN" or dynamic)
        entry = {
            "endpoint":        endpoint,
            "method":          method,
            "called_from":     fname,
            "via":             via,
            "dynamic":         dynamic,
            "function_name":   purpose_info["function_name"],
            "trigger":         purpose_info["trigger"],
            "trigger_name":    purpose_info["trigger_name"],
            "purpose":         purpose_info["purpose"],
            "comment":         purpose_info["comment"],
            "context_snippet": _extract_context_snippet(content, m_start) if is_unknown else None,
        }
        if extra:
            entry.update(extra)
        return entry

    # ── Axios / HTTP — plain string URL ─────────────────────────────────────
    for m in _AXIOS_RE.finditer(content):
        method   = m.group(1).upper()
        endpoint = m.group(2)
        if not endpoint.startswith("/") and not endpoint.startswith("http"):
            endpoint = "UNKNOWN"
        calls.append(_make(endpoint, method, "axios", m.start(),
                           dynamic=(endpoint == "UNKNOWN")))

    # ── Axios / HTTP — template literal ──────────────────────────────────────
    for m in _AXIOS_TMPL_RE.finditer(content):
        method = m.group(1).upper()
        raw    = m.group(2)
        static = raw.split("${")[0].rstrip("/")
        ep     = static if static.startswith("/") else "DYNAMIC: `" + raw[:60] + "`"
        calls.append(_make(ep, method, "axios", m.start(), dynamic=True))

    # ── Axios — variable URL (try to resolve) ─────────────────────────────────
    for m in _AXIOS_VAR_RE.finditer(content):
        method   = m.group(1).upper()
        var_name = m.group(2)
        resolved = var_urls.get(var_name, "")
        ep       = resolved if resolved else "DYNAMIC: var " + var_name
        calls.append(_make(ep, method, "axios", m.start(),
                           dynamic=not bool(resolved)))

    # ── Object-style call ─────────────────────────────────────────────────────
    for m in _OBJ_CALL_RE.finditer(content):
        endpoint = m.group(1)
        method   = (m.group(2) or "POST").upper()
        if not endpoint.startswith("/") and not endpoint.startswith("http"):
            endpoint = "UNKNOWN"
        calls.append(_make(endpoint, method, "axios_obj", m.start(),
                           dynamic=(endpoint == "UNKNOWN")))

    # ── fetch — plain string ──────────────────────────────────────────────
    for m in _FETCH_RE.finditer(content):
        endpoint = m.group(1)
        method   = (m.group(2) or "GET").upper()
        if not endpoint.startswith("/") and not endpoint.startswith("http"):
            endpoint = "UNKNOWN"
        calls.append(_make(endpoint, method, "fetch", m.start(),
                           dynamic=(endpoint == "UNKNOWN")))

    # ── fetch — template literal ──────────────────────────────────────────────
    for m in _FETCH_TMPL_RE.finditer(content):
        raw    = m.group(1)
        method = (m.group(2) or "GET").upper()
        static = raw.split("${")[0].rstrip("/")
        ep     = static if static.startswith("/") else "DYNAMIC: `" + raw[:60] + "`"
        calls.append(_make(ep, method, "fetch", m.start(), dynamic=True))

    # ── Inertia form + router visits ─────────────────────────────────────────
    for m in _INERTIA_FORM_RE.finditer(content):
        calls.append(_make(m.group(2), m.group(1).upper(), "inertia_form", m.start()))
    for m in _INERTIA_VISIT_RE.finditer(content):
        verb = m.group(1).upper()
        if verb == "VISIT":
            verb = "GET"
        calls.append(_make(m.group(2), verb, "inertia", m.start()))

    # ── GraphQL ─────────────────────────────────────────────────────────────
    for m in _APOLLO_RE.finditer(content):
        hook   = m.group(1)
        qname  = m.group(2)
        method = "MUTATION" if "mutation" in hook.lower() else "QUERY"
        calls.append(_make("graphql:" + qname, method, "apollo", m.start()))
    for m in _GQL_TAG_RE.finditer(content):
        op    = m.group(1).upper()
        qname = m.group(2) or "anonymous"
        calls.append(_make("graphql:" + qname, op, "graphql", m.start()))
    for m in _APOLLO_CLIENT_RE.finditer(content):
        op    = m.group(1).upper()
        qname = m.group(2)
        calls.append(_make("graphql:" + qname, op, "apollo_client", m.start()))

    # ── WebSocket ─────────────────────────────────────────────────────────────
    for m in _WS_RE.finditer(content):
        calls.append(_make(m.group(1), "WS", "websocket", m.start()))
    for m in _WS_TMPL_RE.finditer(content):
        raw    = m.group(1)
        static = raw.split("${")[0].rstrip("/")
        ep     = static if static.startswith("ws") else "DYNAMIC: `" + raw[:60] + "`"
        calls.append(_make(ep, "WS", "websocket", m.start(), dynamic=True))

    # ── RTK Query ────────────────────────────────────────────────────────────
    for m in _RTK_EP_RE.finditer(content):
        op = "GET" if m.group(1).lower() == "query" else "POST"
        calls.append(_make(m.group(2), op, "rtk_query", m.start()))

    return calls


def _trace_composable_calls(
    composable_name: str,
    all_files: List[str],
    visited: Set[str],
) -> List[dict]:
    """
    Recursively follow a composable to find API calls (max 2 levels deep).
    Also handles Pinia defineStore action functions.
    """
    if composable_name in visited:
        return []
    visited.add(composable_name)

    bare = composable_name.lower()
    for f in all_files:
        fname_bare = os.path.splitext(os.path.basename(f))[0].lower()
        if fname_bare == bare or fname_bare == "use" + bare:
            content = read_file(f)
            calls   = _trace_api_calls(content, f)

            # Recurse into inner composables (max depth 2)
            inner = _COMPOSABLE_RE.findall(content)
            for inner_name in inner:
                if inner_name not in visited and inner_name not in _FRAMEWORK_COMPOSABLES:
                    for call in _trace_composable_calls(inner_name, all_files, visited):
                        call["via_composable"] = composable_name
                        calls.append(call)
            return calls
    return []


def _build_vuex_action_map(all_files: List[str]) -> Dict[str, List[dict]]:
    """
    Scan Vuex store module files and return:
        'moduleName/actionName' -> [api_call, ...]

    Handles:
      - store/modules/user.js  →  'user/fetchAll' etc.
      - store/index.js         →  plain 'fetchAll' (no namespace)
    Pinia stores are handled via service_map, not here.
    """
    action_map: Dict[str, List[dict]] = {}
    _STORE_DIR_RE = re.compile(r"[/\\]stores?[/\\]", re.IGNORECASE)
    _ACTIONS_BLOCK_RE = re.compile(
        r"actions\s*:\s*\{([\s\S]{20,3000}?\})\s*(?:,|\})",
    )
    _ACTION_FN_RE = re.compile(
        r"(?:async\s+)?(\w+)\s*(?:\([^)]*\)|:\s*\w+)\s*\{",
    )

    for fpath in all_files:
        norm = fpath.replace("\\", "/")
        if not _STORE_DIR_RE.search(norm):
            continue
        content = read_file(fpath)
        if not content or "actions" not in content:
            continue

        # Module name = file basename (modules/user.js → 'user')
        mod_name = os.path.splitext(os.path.basename(fpath))[0].lower()
        calls    = _trace_api_calls(content, fpath)
        if not calls:
            continue

        # Map every action function name found in this file
        for ab_m in _ACTIONS_BLOCK_RE.finditer(content):
            for fn_m in _ACTION_FN_RE.finditer(ab_m.group(1)):
                action_name = fn_m.group(1)
                key_ns   = f"{mod_name}/{action_name}"
                key_bare = action_name
                for key in (key_ns, key_bare):
                    if key not in action_map:
                        action_map[key] = []
                    for call in calls:
                        entry = dict(call)
                        entry["resolved_via"] = os.path.basename(fpath)
                        action_map[key].append(entry)

    return action_map


def _scan_env_files(project_root: str) -> Dict[str, str]:
    """
    Read .env files in project_root and return a dict of API-related variables.
    Looks for variables like:
      VUE_APP_API_URL, VITE_API_URL, REACT_APP_API_URL, API_BASE, API_URL, etc.
    """
    env_vars: Dict[str, str] = {}
    _API_KEY_RE = re.compile(
        r"^\s*((?:VUE_APP|VITE|REACT_APP|NEXT_PUBLIC)?_?API(?:_BASE|_URL|_ROOT|_ENDPOINT)?)\s*=\s*(.+)",
        re.IGNORECASE,
    )
    env_files = [".env", ".env.local", ".env.development", ".env.production",
                 ".env.staging", ".env.example"]
    for fname in env_files:
        fpath = os.path.join(project_root, fname)
        if not os.path.exists(fpath):
            continue
        for line in read_file(fpath).splitlines():
            m = _API_KEY_RE.match(line)
            if m:
                key = m.group(1).strip()
                val = m.group(2).strip().strip('"\'')
                env_vars[key] = val
    return env_vars


def _scan_config_url_constants(all_files: List[str]) -> Dict[str, str]:
    """
    Scan constants.js / config.js / api.config.ts type files for exported
    string constants that look like API URL fragments.
    Returns {CONSTANT_NAME: '/api/v1'}.
    """
    constants: Dict[str, str] = {}
    _CFG_FILE_RE = re.compile(
        r"(?:^|[/\\])(?:constants?|config|api\.config|api-config|settings?)\.[jt]sx?$",
        re.IGNORECASE,
    )
    _EXPORT_CONST_RE = re.compile(
        r"export\s+(?:const|let|var)\s+(\w+)\s*=\s*['\"`](/[^'\"` \n]{1,80})['\"`]",
    )
    _PLAIN_CONST_RE = re.compile(
        r"(?:const|let|var)\s+(\w+)\s*=\s*['\"`](/[^'\"` \n]{1,80})['\"`]",
    )

    for fpath in all_files:
        norm = fpath.replace("\\", "/")
        if not _CFG_FILE_RE.search(norm):
            continue
        content = read_file(fpath)
        for m in _EXPORT_CONST_RE.finditer(content):
            constants[m.group(1)] = m.group(2)
        for m in _PLAIN_CONST_RE.finditer(content):
            if m.group(1) not in constants:
                constants[m.group(1)] = m.group(2)
    return constants


def _scan_service_and_store_files(all_files: List[str]) -> Dict[str, List[dict]]:
    """
    Pre-scan service/api/store/composable files and return a mapping:
        function_name -> [api_call, ...]

    Scanned directories / filename patterns:
      - src/services/**,  src/api/**,  src/stores/**,  src/store/**
      - src/composables/**,  src/repositories/**
      - Any file named *.service.ts, *.api.ts, *.store.ts, *.repository.ts
    Also handles Pinia defineStore(name, { actions: { fn() {} } }).
    """
    mapping: Dict[str, List[dict]] = {}

    _SERVICE_DIR_RE = re.compile(
        r"[/\\](?:services|api|stores?|composables|repositories)[/\\]",
        re.IGNORECASE,
    )
    _SERVICE_FILE_RE = re.compile(
        r"\.(?:service|api|store|repository)\.[jt]sx?$",
        re.IGNORECASE,
    )
    _EXPORT_FN_RE = re.compile(
        r"export\s+(?:async\s+)?(?:function\s+|const\s+)(\w+)",
    )
    # Pinia defineStore actions
    _DEFINE_STORE_RE = re.compile(
        r"defineStore\s*\(\s*['\"`](\w+)['\"`]",
    )

    for fpath in all_files:
        norm = fpath.replace("\\", "/")
        if not (_SERVICE_DIR_RE.search(norm) or _SERVICE_FILE_RE.search(norm)):
            continue
        content = read_file(fpath)
        if not content:
            continue
        calls = _trace_api_calls(content, fpath)
        if not calls:
            continue

        base = os.path.splitext(os.path.basename(fpath))[0]

        # Map each exported function name
        for m in _EXPORT_FN_RE.finditer(content):
            fn_name = m.group(1)
            mapping.setdefault(fn_name, [])
            for call in calls:
                entry = dict(call)
                entry["resolved_via"] = os.path.basename(fpath)
                if entry not in mapping[fn_name]:
                    mapping[fn_name].append(entry)

        # Pinia store name → all calls in the store
        for m in _DEFINE_STORE_RE.finditer(content):
            store_name = m.group(1)
            for key in (store_name, base):
                mapping.setdefault(key, [])
                for call in calls:
                    entry = dict(call)
                    entry["resolved_via"] = os.path.basename(fpath)
                    if entry not in mapping[key]:
                        mapping[key].append(entry)

        # File basename fallback key
        mapping.setdefault(base, [])
        for call in calls:
            entry = dict(call)
            entry["resolved_via"] = os.path.basename(fpath)
            if entry not in mapping[base]:
                mapping[base].append(entry)

    return mapping




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


def _infer_route_from_file_path(filepath: str, project_root: str) -> Optional[str]:
    """
    Infer a frontend route from the file's position in the project tree.

    Handles Nuxt / Next.js `pages/` directory convention:
      pages/home.vue           → /home
      pages/admin/index.vue    → /admin
      pages/users/[id].vue     → /users/:id   (Next.js)
      pages/users/_id.vue      → /users/:id   (Nuxt 2)

    Falls back to `views/` heuristic for Vue CLI projects:
      src/views/Admin/Dashboard.vue → /admin/dashboard  (inferred)

    Returns None when no useful route can be determined.
    """
    try:
        rel = os.path.relpath(filepath, project_root).replace("\\", "/")
    except ValueError:
        return None

    # ── Nuxt / Next.js pages/ convention ─────────────────────────────────────
    pages_m = re.match(r"(?:src/)?pages?/(.+)", rel, re.IGNORECASE)
    if pages_m:
        route_part = pages_m.group(1)
        # Strip extension
        route_part = re.sub(r"\.(vue|[jt]sx?|mdx?)$", "", route_part, flags=re.IGNORECASE)
        # Next.js: [[...slug]] → :slug, [id] → :id
        route_part = re.sub(r"\[{1,2}\.\.\.(\w+)\]{1,2}", r":\1", route_part)
        route_part = re.sub(r"\[(\w+)\]", r":\1", route_part)
        # Nuxt 2: _id.vue → :id
        route_part = re.sub(r"(?:^|/)_(\w+)", r"/:\1", route_part)
        # Collapse trailing /index
        route_part = re.sub(r"(?:/index$|^index$)", "", route_part)
        route_part = route_part.strip("/")
        return "/" + route_part if route_part else "/"

    # ── views/ heuristic (Vue CLI / Vite) ────────────────────────────────────
    views_m = re.match(r"(?:src/)?views?/(.+)", rel, re.IGNORECASE)
    if views_m:
        route_part = views_m.group(1)
        route_part = re.sub(r"\.(vue|[jt]sx?|mdx?)$", "", route_part, flags=re.IGNORECASE)
        # PascalCase segments → kebab
        route_part = re.sub(
            r"([a-z0-9])([A-Z])", lambda m: m.group(1) + "-" + m.group(2).lower(),
            route_part,
        )
        route_part = route_part.lower()
        # Drop common suffixes stripped from component names
        route_part = re.sub(r"[-/](view|page|screen|component)$", "", route_part)
        # Collapse trailing /index
        route_part = re.sub(r"(?:/index$|^index$)", "", route_part)
        route_part = route_part.strip("/")
        if route_part:
            return "/" + route_part

    return None


def _build_example_url(path: str, base_url: str = "http://localhost:8000") -> str:
    """
    Build an example browser URL from a route path.
      /admin/affiliate/configure/:id  →  http://localhost:8000/admin/affiliate/configure/1
      /admin/billing/:invType/:payType/:filter/:date  →  .../standard/check/all/2025-01-01
      UNKNOWN / None  →  None  (caller will show 'Route not mapped')
    """
    if not path or path == "UNKNOWN":
        return None
    if path == "/":
        return f"{base_url}/"

    def _replace(m: re.Match) -> str:
        param = m.group(1).rstrip('?')   # strip optional marker
        return _PARAM_EXAMPLES.get(param, f"{{{param}}}")

    result = re.sub(r':([\w?]+)', _replace, path).rstrip('/')
    return f"{base_url}{result}"


# ─── STEP 6: Validation Rule Extraction ─────────────────────────────────────

def _extract_validation_rules(content: str) -> List[str]:
    """
    Statically extract form/input validation rules from Vue component source.
    Covers:
      - VeeValidate  rules="required|email"  or  :rules="[v => !!v]"  or  rules: { required: true }
      - Vuelidate    validations: { field: { required, email } }
      - Manual       rules: { fieldName: [...] }  or  v-validate patterns
      - Yup/Zod      .required() .email() .min() .max() chains
    """
    found: List[str] = []

    # VeeValidate string rules: rules="required|email|min:6"
    for m in re.finditer(r'\brules\s*=\s*["\']([\w|: ,]+)["\']', content):
        val = m.group(1).strip()
        if val:
            found.append(val)

    # VeeValidate / manual object: rules: { fieldName: [required, minLength] }
    for m in re.finditer(r'\brules\s*:\s*\{([^}]{1,400})\}', content, re.DOTALL):
        block = m.group(1)
        # Extract field: [...] or field: rule entries
        for fm in re.finditer(r'([a-zA-Z_][\w]*)\s*:\s*([^\n,}]+)', block):
            field = fm.group(1)
            rule  = fm.group(2).strip().rstrip(',')
            if field not in ('true', 'false', 'null', 'undefined'):
                found.append(f"{field}: {rule}")

    # Vuelidate: validations: { field: { required, minLength: minLength(6) } }
    vm = re.search(r'validations\s*[:(]\s*\{([^}]{1,600})\}', content, re.DOTALL)
    if vm:
        for fm in re.finditer(r'([a-zA-Z_][\w]*)\s*:\s*\{([^}]+)\}', vm.group(1), re.DOTALL):
            field   = fm.group(1)
            ruleset = re.sub(r'\s+', ' ', fm.group(2)).strip()
            found.append(f"{field}: {{ {ruleset} }}")

    # Yup / Zod chains: .required() .email() .min() .max() .matches()
    for m in re.finditer(
        r'["\']([a-zA-Z_][\w]*)["\']\s*:\s*[\w.]+(?:\.(?:required|email|min|max|matches|url|uuid)\([^)]*\))+',
        content,
    ):
        found.append(m.group(0).split(':', 1)[1].strip())

    # Deduplicate preserving order
    seen: set = set()
    result: List[str] = []
    for r in found:
        if r not in seen:
            seen.add(r)
            result.append(r)
    return result[:20]


# ─── STEP 7: Conditional Logic Extraction ────────────────────────────────────

def _extract_conditional_logic(content: str) -> List[str]:
    """
    Statically extract conditional display/rendering rules from Vue template.
    Covers: v-if, v-else-if, v-show, computed ternaries, and :disabled/:readonly.
    """
    found: List[str] = []
    seen: set = set()

    def _add(label: str) -> None:
        label = re.sub(r'\s+', ' ', label).strip()
        if label and label not in seen and len(found) < 15:
            seen.add(label)
            found.append(label)

    # v-if / v-else-if / v-show
    for m in re.finditer(r'v-(if|else-if|show)=["\']([^"\']{3,120})["\']', content):
        directive = m.group(1)
        condition = m.group(2).strip()
        _add(f"v-{directive}: {condition}")

    # Computed ternaries in template: {{ condition ? 'a' : 'b' }}
    for m in re.finditer(r'\{\{([^}]{5,120}\?[^}]{2,80}:[^}]{2,80})\}\}', content):
        _add("ternary: " + m.group(1).strip())

    # :disabled / :readonly attribute bindings
    for m in re.finditer(r':(disabled|readonly|hidden)=["\']([^"\']{3,80})["\']', content):
        _add(f"{m.group(1)}: {m.group(2).strip()}")

    return found


# ─── STEP 8: State Management Detection ───────────────────────────────────────

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

# Router file names to check (both Vue and React)
_ROUTER_FILENAMES: Set[str] = {
    "index.js", "index.ts",
    "router.js", "router.ts",
    "routes.js", "routes.ts",
    "app.js", "app.ts",
    "app.jsx", "app.tsx",
    "routes.jsx", "routes.tsx",
}


def detect_pages(project_root: str) -> List[dict]:
    """
    Main entry point.
    Returns list of page dicts with full API call traces, children, layout,
    state management, and composable information.

    Detection layers:
      - Direct axios/fetch/inertia calls (string, template-literal, variable)
      - Object-style $api({ url, method }) calls
      - this.$axios / this.$http Vue Options API
      - GraphQL Apollo useQuery / useMutation / client.query
      - WebSocket new WebSocket(url)
      - RTK Query builder.query/mutation
      - Composable tracing (2 levels deep)
      - Service / store / Pinia / Vuex scan (pre-indexed)
      - .env base-URL resolution
      - constants.js / config.js URL constant resolution
      - Vuex store.dispatch('module/action') → store file API calls
      - Variable URL resolution (const url = '/path' → axios.get(url))
      - File list built ONCE (no repeated os.walk)
    """
    # Build file list ONCE — avoids O(pages × children) fs walks
    all_files = _walk_frontend(project_root)
    # Build a lowercase-name → path index for fast component lookup
    _file_index: Dict[str, str] = {}
    for fpath in all_files:
        bare = os.path.splitext(os.path.basename(fpath))[0].lower()
        if bare not in _file_index:
            _file_index[bare] = fpath

    php_files = []
    for dirpath, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in files:
            if fname.endswith(".php"):
                php_files.append(os.path.join(dirpath, fname))

    # ── Environment / config scanning (done once) ─────────────────────────────
    print("  [scan] Reading .env / config files for base URLs...")
    env_config    = _scan_env_files(project_root)
    url_constants = _scan_config_url_constants(all_files)
    if env_config:
        print("  [scan] .env vars found: {}".format(list(env_config.keys())))
    if url_constants:
        print("  [scan] URL constants found: {}".format(len(url_constants)))

    # ── Pre-scan service / store / api / composable files (only once) ────────
    print("  [scan] Indexing service/store/api files...")
    service_map = _scan_service_and_store_files(all_files)
    if service_map:
        print("  [scan] {} exported functions with API calls found".format(len(service_map)))

    # ── Pre-scan Vuex store modules (only once) ───────────────────────────────
    vuex_action_map = _build_vuex_action_map(all_files)
    if vuex_action_map:
        print("  [scan] {} Vuex actions with API calls indexed".format(len(vuex_action_map)))

    # ── Collect raw routes from router files ──────────────────────────────────
    raw_routes: List[dict] = []

    for fpath in all_files:
        fname = os.path.basename(fpath).lower()
        if fname in _ROUTER_FILENAMES:
            content = read_file(fpath)
            if "createRouter" in content or "vue-router" in content or "routes" in content.lower():
                raw_routes.extend(_detect_vue_routes(content, fpath))
            if "react-router" in content or "<Route" in content or "createBrowserRouter" in content:
                raw_routes.extend(_detect_react_routes(content, fpath))

    for fpath in php_files:
        content = read_file(fpath)
        if "Inertia::render" in content:
            raw_routes.extend(_detect_inertia_routes(content, fpath))

    # Deduplicate routes by (path, component)
    seen_routes: Set[tuple] = set()
    deduped: List[dict] = []
    for r in raw_routes:
        key = (r["path"], r["component"])
        if key not in seen_routes:
            seen_routes.add(key)
            deduped.append(r)
    raw_routes = deduped

    # If no router files found, treat ALL .vue/.jsx/.tsx files as pages
    # and try to infer route from file path (Nuxt/Next pages/ or views/ heuristic)
    if not raw_routes:
        for fpath in all_files:
            ext = os.path.splitext(fpath)[1]
            if ext in (".vue", ".jsx", ".tsx"):
                fname          = os.path.basename(fpath)
                inferred_route = _infer_route_from_file_path(fpath, project_root)
                raw_routes.append({
                    "path":      inferred_route or "UNKNOWN",
                    "component": fname,
                    "lazy":      False,
                    "source":    fname,
                    "inferred":  bool(inferred_route),
                })

    print(f"  [{len(raw_routes)} pages/components detected]")

    # ── Build component -> full page record ───────────────────────────────────
    pages: List[dict] = []

    for route in raw_routes:
        component = route.get("component", "UNKNOWN")
        # Fast lookup using pre-built index
        bare_comp  = os.path.splitext(component)[0].lower()
        bare_strip = re.sub(r"(view|page|component)$", "", bare_comp)
        comp_file  = (
            _file_index.get(bare_comp)
            or _file_index.get(bare_strip)
        )
        content = read_file(comp_file) if comp_file else ""

        # ── Direct API calls in this component ──────────────────────────────
        api_calls: List[dict] = _trace_api_calls(content, comp_file or component)

        # ── Composables used (skip framework ones) ───────────────────────────
        raw_composables = _COMPOSABLE_RE.findall(content) if content else []
        composable_names = [c for c in raw_composables if c not in _FRAMEWORK_COMPOSABLES]
        composable_names = list(dict.fromkeys(composable_names))

        # ── Trace through composables to find their API calls ────────────────
        for cname in composable_names:
            for call in _trace_composable_calls(cname, all_files, set()):
                call["composable"] = cname
                api_calls.append(call)

        # ── Pull API calls from matching service/store exports ────────────────
        # Check if this component imports any known service functions
        for line in (content.splitlines() if content else []):
            # import { fetchUsers, createUser } from '@/services/users'
            imp_m = re.search(r"import\s*\{([^}]+)\}\s*from", line)
            if imp_m:
                for fn_name in re.findall(r"\b(\w+)\b", imp_m.group(1)):
                    if fn_name in service_map:
                        for call in service_map[fn_name]:
                            entry = dict(call)
                            entry["composable"] = fn_name
                            api_calls.append(entry)

        # ── Resolve Vuex store.dispatch('module/action') calls ────────────────
        for m in _VUEX_DISPATCH_RE.finditer(content):
            action_key = m.group(1)
            if action_key in vuex_action_map:
                for call in vuex_action_map[action_key]:
                    entry = dict(call)
                    entry["via"] = "vuex_dispatch"
                    entry["vuex_action"] = action_key
                    api_calls.append(entry)
            else:
                # Dispatch target not found in known store files — still record it
                api_calls.append({
                    "endpoint": "UNKNOWN",
                    "method":   "DISPATCH",
                    "called_from": os.path.basename(comp_file or component),
                    "via":      "vuex_dispatch",
                    "vuex_action": action_key,
                })

        # ── Deduplicate only exact same calls (keep different-purpose duplicates) ──
        # Two calls to GET /api/users onMounted vs on @submit are DIFFERENT — keep both
        _seen_exact: Set[tuple] = set()
        _unique_calls: List[dict] = []
        for call in api_calls:
            key = (
                call.get("endpoint"), call.get("method"),
                call.get("called_from"), call.get("purpose"),
                call.get("trigger"), call.get("function_name"),
            )
            if key not in _seen_exact:
                _seen_exact.add(key)
                _unique_calls.append(call)
        api_calls = _unique_calls

        # ── Child components: local imports ───────────────────────────────────
        children = _extract_imports(content) if content else []

        # ── Child components: template component tags (Vue 2 / Vuetify) ──────
        template_components = _extract_template_components(content) if content else []

        # ── Scan child components for their API calls (1 level deep) ─────────
        child_calls: List[dict] = []
        scanned_children: Set[str] = set()
        for child_name in list(children) + list(template_components):
            bare_child = os.path.splitext(child_name)[0].lower()
            bare_strip = re.sub(r"(view|page|component)$", "", bare_child)
            child_file = _file_index.get(bare_child) or _file_index.get(bare_strip)
            if child_file and child_file not in scanned_children and child_file != comp_file:
                scanned_children.add(child_file)
                child_content = read_file(child_file)
                for call in _trace_api_calls(child_content, child_file):
                    call["via_child"] = child_name
                    child_calls.append(call)
        # Dedup child calls the same way
        _child_seen: Set[tuple] = set()
        for call in child_calls:
            key = (
                call.get("endpoint"), call.get("method"),
                call.get("called_from"), call.get("purpose"),
                call.get("function_name"),
            )
            if key not in _child_seen:
                _child_seen.add(key)
                api_calls.append(call)

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
            ep  = call.get("endpoint", "")
            via = call.get("via", "")
            if ep == "UNKNOWN":
                if via == "vuex_dispatch":
                    unknowns.append(
                        "Vuex dispatch target not found in store: "
                        + call.get("vuex_action", "?")
                    )
                else:
                    unknowns.append(
                        f"Unresolved endpoint in {call.get('called_from', '?')}"
                    )
            elif ep.startswith("DYNAMIC:"):
                unknowns.append(
                    f"Dynamic (runtime-computed) URL in {call.get('called_from', '?')}: {ep}"
                )

        # ── Static Excel fields (no-AI fallback) ────────────────────────────
        validation_static    = _extract_validation_rules(content) if content else []
        conditional_static   = _extract_conditional_logic(content) if content else []

        # ── Route inference for UNKNOWN paths ────────────────────────────────
        # If the route says UNKNOWN (e.g. Inertia pages without a PHP route mapping)
        # but we found the component file, try to infer the route from file location.
        route_path = route.get("path", "UNKNOWN")
        is_inferred = route.get("inferred", False)
        if route_path == "UNKNOWN" and comp_file:
            inferred_r = _infer_route_from_file_path(comp_file, project_root)
            if inferred_r:
                route_path  = inferred_r
                is_inferred = True
                # Recompute example_url with the inferred path
                example_url = _build_example_url(route_path)

        pages.append({
            "path":                route_path,
            "component":           component,
            "inferred":            is_inferred,
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
            "env_config":          env_config if env_config else None,
            "url_constants":       {k: v for k, v in url_constants.items() if v} if url_constants else None,
            "validation_rules_static":   validation_static,
            "conditional_logic_static":  conditional_static,
            "code_snippet":              content[:3000] if content else "",
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
