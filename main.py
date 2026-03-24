#!/usr/bin/env python3
"""
doc_writer -- Auto-detecting documentation generator for Laravel + Vue/React.

Usage:
  python main.py generate-docs --path ./my-project
  python main.py generate-docs --path ./my-project --provider ollama --order backend
  python main.py generate-docs --path ./my-project --api-key gsk_... --order both
"""

import argparse
import json
import os
import re
import sys
import textwrap
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from backend.detect_apis import detect_apis, save_routes_json
from backend.generate_docs import ProgressTracker, generate_all_docs
from backend.validate_backend import (print_validation_summary,
                                      save_validation_report, validate_backend)
from frontend.detect_pages import detect_pages, save_pages_json
from frontend.generate_docs import generate_pages_md
from shared.ai_client import (AIConfig, detect_best_ollama_model,
                              get_ollama_models)
from shared.dependency_graph import DependencyGraph
from shared.validator import validate

# =============================================================================
# PROJECT TYPE AUTO-DETECTION
# =============================================================================

LARAVEL_SIGNALS = [
    "artisan",
    "composer.json",
    os.path.join("routes", "api.php"),
    os.path.join("routes", "web.php"),
    os.path.join("app", "Http", "Controllers"),
    os.path.join("config", "app.php"),
    os.path.join("database", "migrations"),
]

FRONTEND_SIGNALS = [
    "package.json",
    "vite.config.js",
    "vite.config.ts",
    "next.config.js",
    "nuxt.config.js",
    "nuxt.config.ts",
    os.path.join("src", "main.js"),
    os.path.join("src", "main.ts"),
    os.path.join("src", "App.vue"),
    os.path.join("src", "App.jsx"),
    os.path.join("src", "App.tsx"),
    os.path.join("resources", "js"),
    os.path.join("resources", "vue"),
]

BACKEND_SUBFOLDER_NAMES  = {"backend", "api", "server", "laravel", "app-backend"}
FRONTEND_SUBFOLDER_NAMES = {"frontend", "client", "web", "vue", "react", "spa", "app-frontend"}


def _count_signals(root, signals):
    return sum(1 for s in signals if os.path.exists(os.path.join(root, s)))


def detect_project_type(path):
    path     = os.path.abspath(path)
    notes    = []
    be_score = _count_signals(path, LARAVEL_SIGNALS)
    fe_score = _count_signals(path, FRONTEND_SIGNALS)
    notes.append("Backend signals  : {}/{}".format(be_score, len(LARAVEL_SIGNALS)))
    notes.append("Frontend signals : {}/{}".format(fe_score, len(FRONTEND_SIGNALS)))

    try:
        subdirs = {
            d.lower(): os.path.join(path, d)
            for d in os.listdir(path)
            if os.path.isdir(os.path.join(path, d))
        }
    except PermissionError:
        subdirs = {}

    be_sub = fe_sub = None
    for name, sp in subdirs.items():
        if name in BACKEND_SUBFOLDER_NAMES and _count_signals(sp, LARAVEL_SIGNALS) >= 2:
            be_sub = sp
            notes.append("Found backend subfolder  : " + sp)
        if name in FRONTEND_SUBFOLDER_NAMES and _count_signals(sp, FRONTEND_SIGNALS) >= 1:
            fe_sub = sp
            notes.append("Found frontend subfolder : " + sp)

    inertia_js  = os.path.join(path, "resources", "js")
    inertia_vue = os.path.join(path, "resources", "vue")
    has_inertia = os.path.isdir(inertia_js) or os.path.isdir(inertia_vue)

    if be_sub and fe_sub:
        notes.append("Detected: Monorepo with separate backend/frontend folders")
        return {"type": "monorepo", "backend": be_sub,  "frontend": fe_sub,  "notes": notes}

    if be_score >= 3 and (fe_score >= 1 or has_inertia):
        fe_path = (inertia_js  if os.path.isdir(inertia_js)  else
                   inertia_vue if os.path.isdir(inertia_vue) else path)
        notes.append("Detected: Laravel + embedded frontend (Inertia/Vite)")
        return {"type": "monorepo", "backend": path,   "frontend": fe_path, "notes": notes}

    if be_score >= 2 and fe_score <= 1:
        notes.append("Detected: Laravel backend only")
        return {"type": "backend",  "backend": path,   "frontend": None,    "notes": notes}

    if fe_score >= 2 and be_score <= 1:
        notes.append("Detected: Frontend only (Vue/React)")
        return {"type": "frontend", "backend": None,   "frontend": path,    "notes": notes}

    notes.append("Mixed signals -- running both pipelines")
    return {"type": "monorepo", "backend": path, "frontend": path, "notes": notes}


def print_detection(result):
    labels = {
        "backend":  "Laravel backend only",
        "frontend": "Vue/React frontend only",
        "monorepo": "Monorepo (backend + frontend)",
        "unknown":  "Unknown",
    }
    print("\n  Project type : " + labels.get(result["type"], result["type"]))
    if result["backend"]:
        print("  Backend      -> " + result["backend"])
    if result["frontend"]:
        print("  Frontend     -> " + result["frontend"])
    for n in result["notes"]:
        print("  * " + n)
    print()


# =============================================================================
# OUTPUT FOLDER — named after project
# =============================================================================

def resolve_output_dir(base, project_path, override=None):
    name = override or os.path.basename(os.path.abspath(project_path))
    name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    return os.path.join(base, name)


# =============================================================================
# RESUME / CACHE HELPERS
# =============================================================================

def _load_mtimes(p):
    if os.path.exists(p):
        try:
            with open(p) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_mtimes(p, d):
    with open(p, "w") as f:
        json.dump(d, f, indent=2)


def _collect_mtimes(root, exts):
    skip = {"node_modules", ".git", "vendor", "__pycache__", "dist", "build", "storage"}
    m    = {}
    for dp, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in skip]
        for fn in files:
            if os.path.splitext(fn)[1] in exts:
                fp = os.path.join(dp, fn)
                m[fp] = os.path.getmtime(fp)
    return m


def _has_changed(root, exts, state_file):
    prev = _load_mtimes(state_file)
    curr = _collect_mtimes(root, exts)
    if prev != curr:
        _save_mtimes(state_file, curr)
        return True
    return False


def _page_filename(route_path):
    safe = route_path.strip("/").replace("/", "_").replace("-", "_") or "home"
    safe = re.sub(r"[^\w]", "_", safe).strip("_") or "home"
    return safe + ".md"


def _get_already_paged(docs_frontend_dir):
    if not os.path.exists(docs_frontend_dir):
        return set()
    return {
        f for f in os.listdir(docs_frontend_dir)
        if f.endswith(".md") and f != "index.md"
    }


# =============================================================================
# FRONTEND PAGE SCANNER
# =============================================================================

def scan_frontend_pages(frontend_root):
    pages = []
    fe    = os.path.abspath(frontend_root)

    try:
        top = os.listdir(fe)
        print("  * Frontend root: {}".format(", ".join(sorted(top)[:12])))
    except Exception:
        pass

    pages = _parse_router_file(fe) or _scan_inertia_pages(fe) or \
            _scan_file_based_pages(fe) or _scan_all_components(fe)

    if not pages:
        print("  WARNING: No pages found in " + fe)
        return []

    print("  * {} pages detected".format(len(pages)))

    for page in pages:
        comp_file = page.get("file")
        content   = ""
        if comp_file and os.path.exists(comp_file):
            try:
                with open(comp_file, encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except Exception:
                pass

        page["api_calls"]        = _trace_api_calls(content, comp_file or "")
        page["children"]         = _extract_imports(content)
        page["layout"]           = _extract_layout(content)
        page["state_management"] = _detect_state(content)
        page["unknowns"]         = (
            ["Component file not found: " + str(comp_file)]
            if not comp_file or not os.path.exists(comp_file or "")
            else []
        )

        # Follow child component files for additional API calls
        for child_name in page["children"]:
            child_file = _find_file(child_name, fe)
            if child_file:
                try:
                    with open(child_file, encoding="utf-8", errors="ignore") as f:
                        child_content = f.read()
                    for call in _trace_api_calls(child_content, child_file):
                        call["via"] = os.path.basename(child_file)
                        page["api_calls"].append(call)
                except Exception:
                    pass

    return pages


def _read(path):
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


def _find_file(name, root):
    bare = os.path.splitext(name)[0].lower()
    for dp, _, files in os.walk(root):
        for fn in files:
            if os.path.splitext(fn)[0].lower() == bare:
                return os.path.join(dp, fn)
    return None


def _parse_router_file(root):
    pages = []
    skip  = {"node_modules", "dist", ".git"}
    for dp, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in skip]
        for fn in files:
            if fn.lower() not in ("index.js", "index.ts", "router.js", "router.ts",
                                   "routes.js", "routes.ts"):
                continue
            fpath   = os.path.join(dp, fn)
            content = _read(fpath)
            if not any(x in content for x in
                       ("createRouter", "vue-router", "BrowserRouter", "Route")):
                continue
            # Vue Router
            for m in re.finditer(
                r"path\s*:\s*['\"`]([^'\"`]+)['\"`].*?"
                r"(?:component\s*:\s*(?:.*?import\s*\(\s*['\"`]([^'\"`]+)['\"`]\s*\)"
                r"|([A-Za-z]\w*)))?",
                content, re.DOTALL,
            ):
                path = m.group(1)
                comp = m.group(2) or m.group(3) or ""
                if not path or path in ("*", "/:pathMatch(.*)", "/:catchAll(.*)"):
                    continue
                comp_file = None
                if comp:
                    comp_abs = os.path.normpath(os.path.join(os.path.dirname(fpath), comp))
                    for ext in ("", ".vue", ".jsx", ".tsx", ".js", ".ts"):
                        if os.path.exists(comp_abs + ext):
                            comp_file = comp_abs + ext
                            break
                    if not comp_file:
                        comp_file = _find_file(os.path.basename(comp), root)
                pages.append({
                    "path":      path,
                    "component": os.path.basename(comp) if comp else "UNKNOWN",
                    "file":      comp_file,
                    "source":    fn,
                })
            # React Router
            for m in re.finditer(r'path=["\']([^"\']+)["\'].*?element=\{<(\w+)', content):
                comp = m.group(2)
                pages.append({
                    "path":      m.group(1),
                    "component": comp,
                    "file":      _find_file(comp, root),
                    "source":    fn,
                })
            if pages:
                return pages
    return pages


def _scan_inertia_pages(root):
    pages_dir = None
    skip      = {"node_modules", "dist", ".git"}
    for dp, dirs, _ in os.walk(root):
        dirs[:] = [d for d in dirs if d not in skip]
        for d in dirs:
            if d.lower() == "pages":
                pages_dir = os.path.join(dp, d)
                break
        if pages_dir:
            break
    if not pages_dir:
        return []
    pages = []
    for dp, dirs, files in os.walk(pages_dir):
        dirs[:] = [d for d in dirs if d not in {"node_modules", "dist"}]
        for fn in files:
            if os.path.splitext(fn)[1].lower() not in (".vue", ".jsx", ".tsx"):
                continue
            fpath = os.path.join(dp, fn)
            rel   = os.path.relpath(fpath, pages_dir).replace("\\", "/").split("/")
            if rel[-1].lower().startswith("index."):
                rel = rel[:-1]
            else:
                rel[-1] = os.path.splitext(rel[-1])[0]
            route = "/" + "/".join(p.lower() for p in rel if p) or "/"
            pages.append({"path": route, "component": fn, "file": fpath,
                          "source": "Pages/ folder"})
    return pages


def _scan_file_based_pages(root):
    pages = []
    for folder in ("pages", "app"):
        pd = os.path.join(root, folder)
        if not os.path.isdir(pd):
            pd = os.path.join(root, "src", folder)
        if not os.path.isdir(pd):
            continue
        for dp, dirs, files in os.walk(pd):
            dirs[:] = [d for d in dirs if not d.startswith("_") and d != "api"]
            for fn in files:
                if os.path.splitext(fn)[1].lower() not in (".vue", ".jsx", ".tsx"):
                    continue
                if fn.startswith("_"):
                    continue
                fpath = os.path.join(dp, fn)
                rel   = os.path.relpath(fpath, pd).replace("\\", "/").split("/")
                if rel[-1].lower().startswith("index."):
                    rel = rel[:-1]
                else:
                    rel[-1] = os.path.splitext(rel[-1])[0]
                pages.append({"path": "/" + "/".join(rel), "component": fn,
                              "file": fpath, "source": folder + "/ folder"})
        if pages:
            break
    return pages


def _scan_all_components(root):
    skip  = {"node_modules", "dist", ".git", "build", "vendor", "__pycache__"}
    pages = []
    seen  = set()
    for dp, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in skip]
        for fn in files:
            if os.path.splitext(fn)[1].lower() not in (".vue", ".jsx", ".tsx"):
                continue
            low = fn.lower()
            if any(low.startswith(x) for x in
                   ("app.", "main.", "index.", "router.", "store.",
                    "plugin", "mixin", "util", "helper", "config",
                    "constant", "service", "composable", "use")):
                continue
            fpath = os.path.join(dp, fn)
            if fpath in seen:
                continue
            seen.add(fpath)
            rel   = os.path.relpath(fpath, root).replace("\\", "/").split("/")
            rel[-1] = os.path.splitext(rel[-1])[0]
            parts = [p.lower() for p in rel if len(p) > 1]
            route = "/" + "/".join(parts) if parts else "/" + os.path.splitext(fn)[0].lower()
            pages.append({"path": route, "component": fn, "file": fpath,
                          "source": "component scan"})
    return pages


def _trace_api_calls(content, filepath):
    calls = []
    fname = os.path.basename(filepath) if filepath else "unknown"
    AXIOS = re.compile(
        r"(?:axios|http|api|service)\s*\.\s*(get|post|put|delete|patch)\s*"
        r"\(\s*['\"`]([^'\"`\s\n]+)['\"`]",
        re.IGNORECASE,
    )
    FETCH = re.compile(
        r"fetch\s*\(\s*['\"`]([^'\"`\s\n]+)['\"`]"
        r"(?:.*?method\s*:\s*['\"]([A-Z]+)['\"])?",
        re.DOTALL,
    )
    INERTIA = re.compile(
        r"(?:router|Inertia)\s*\.\s*(get|post|put|delete|patch|visit)\s*"
        r"\(\s*['\"`]([^'\"`\s\n]+)['\"`]",
        re.IGNORECASE,
    )
    HOOK = re.compile(
        r"(?:useQuery|useMutation|useFetch|useSWR)\s*\([^)]*['\"`]"
        r"(/[^'\"`\s\n]+)['\"`]",
        re.IGNORECASE,
    )
    for m in AXIOS.finditer(content):
        ep = m.group(2)
        if not ep.startswith("/"):
            ep = "UNKNOWN (dynamic)"
        calls.append({"endpoint": ep, "method": m.group(1).upper(),
                      "called_from": fname, "via": "axios"})
    for m in FETCH.finditer(content):
        if m.group(1).startswith("/"):
            calls.append({"endpoint": m.group(1),
                          "method": (m.group(2) or "GET").upper(),
                          "called_from": fname, "via": "fetch"})
    for m in INERTIA.finditer(content):
        ep  = m.group(2)
        mth = m.group(1).upper()
        if mth == "VISIT":
            mth = "GET"
        if ep.startswith("/"):
            calls.append({"endpoint": ep, "method": mth,
                          "called_from": fname, "via": "inertia"})
    for m in HOOK.finditer(content):
        calls.append({"endpoint": m.group(1), "method": "GET",
                      "called_from": fname, "via": "hook"})
    return calls


def _extract_imports(content):
    return [
        m.group(1)
        for m in re.finditer(
            r"import\s+(?:\{[^}]+\}|(\w+))\s+from\s*['\"`](\.[^'\"`]+)['\"`]",
            content,
        )
        if m.group(1)
    ][:20]


def _extract_layout(content):
    m = re.search(r"<(\w*[Ll]ayout\w*)", content)
    if m:
        return m.group(1)
    m = re.search(r"layout\s*:\s*['\"](\w+)['\"]", content)
    return m.group(1) if m else "UNKNOWN"


def _detect_state(content):
    s = []
    if re.search(r"use\w+Store\s*\(", content):
        s.append("pinia")
    if "useSelector" in content or "useDispatch" in content:
        s.append("redux")
    if "store.dispatch" in content or "mapState" in content:
        s.append("vuex")
    return s


# =============================================================================
# PER-PAGE FILE WRITER
# =============================================================================

# =============================================================================
# AI ORDER PROMPT
# =============================================================================

def ask_ai_order():
    print("\n  Both backend and frontend detected.")
    print("  Which do you want to document first?\n")
    print("    [1] Backend first  (Laravel routes, DB queries)")
    print("    [2] Frontend first (Pages, components, API calls)")
    print("    [3] Both together  (default)\n")
    choice = input("  Enter 1, 2, or 3 [default: 3]: ").strip()
    if choice == "1":
        return "backend"
    if choice == "2":
        return "frontend"
    return "both"


# =============================================================================
# PIPELINE
# =============================================================================

def cmd_generate_docs(args):

    # Resolve paths
    if args.path and not args.backend and not args.frontend:
        project_path  = os.path.abspath(args.path)
        print("\n  Scanning: " + project_path)
        print("  Auto-detecting project type...")
        detection     = detect_project_type(project_path)
        print_detection(detection)
        backend_root  = detection["backend"]
        frontend_root = detection["frontend"]
        project_type  = detection["type"]
    else:
        project_path  = os.path.abspath(args.backend or args.frontend)
        backend_root  = os.path.abspath(args.backend)  if args.backend  else None
        frontend_root = os.path.abspath(args.frontend) if args.frontend else None
        project_type  = (
            "monorepo" if backend_root and frontend_root else
            "backend"  if backend_root else "frontend"
        )

    if args.only_backend:
        frontend_root = None
    if args.only_frontend:
        backend_root  = None

    if not backend_root and not frontend_root:
        print("ERROR: No backend or frontend found.")
        sys.exit(1)

    # Output dir named after project
    output_dir = resolve_output_dir(args.output, project_path, args.project_name)
    state_dir  = os.path.join(output_dir, ".docwriter")
    os.makedirs(state_dir, exist_ok=True)

    docs_backend  = os.path.join(output_dir, "docs", "backend")
    docs_frontend = os.path.join(output_dir, "docs", "frontend")
    os.makedirs(docs_backend,  exist_ok=True)
    os.makedirs(docs_frontend, exist_ok=True)

    print("  Output dir : " + output_dir)

    # AI order
    if backend_root and frontend_root and not args.no_ai:
        order = args.order or ask_ai_order()
        print("  Pipeline order : " + order)
    else:
        order = "both"

    # AI config
    config = AIConfig(
        api_key  = args.api_key,
        provider = args.provider,
        model    = args.model,
        mode     = args.ai_mode,
    )
    no_ai = args.no_ai

    if config.provider == "ollama" and not no_ai:
        if not get_ollama_models():
            print("  Ollama not running -- falling back to --no-ai")
            no_ai = True
        else:
            print("  Ollama model : " + detect_best_ollama_model())
    elif config.use_ai and not no_ai:
        print("  AI provider  : {}  model: {}".format(
            config.provider, config.resolved_model()))
    else:
        print("  Mode         : static extraction (no AI)")

    start  = time.time()
    routes = []
    pages  = []

    # ── BACKEND ──────────────────────────────────────────────────────────────

    def run_backend():
        nonlocal routes
        print("\n" + "-" * 60)
        print("  BACKEND -> " + backend_root)
        print("-" * 60)

        routes_cache = os.path.join(state_dir, "routes.json")
        be_state     = os.path.join(state_dir, "backend_mtimes.json")

        if os.path.exists(routes_cache) and not args.force:
            if not _has_changed(backend_root, {".php"}, be_state):
                print("\n  [CACHE] No PHP changes -- loading from routes.json")
                with open(routes_cache, encoding="utf-8") as fp:
                    routes.extend(json.load(fp))
                print("  {} routes loaded".format(len(routes)))
            else:
                print("\n  PHP changed -- re-extracting...")
                routes.extend(_do_extract_backend(backend_root, routes_cache))
        else:
            if args.force:
                print("\n  --force: re-extracting from scratch...")
            print("\n  Step 1: Extracting routes & controller logic...")
            routes.extend(_do_extract_backend(backend_root, routes_cache))

        print("\n  Step 2: Generating per-domain docs...")
        generate_all_docs(
            routes, docs_backend, config,
            no_ai=no_ai, force=args.force, state_dir=state_dir,
        )

        if not args.skip_validation:
            print("\n  Step 3: Validating completeness...")
            report = validate_backend(routes)
            save_validation_report(
                report, os.path.join(output_dir, "validation_report.json"))
            print_validation_summary(report)

    # ── FRONTEND ─────────────────────────────────────────────────────────────

    def run_frontend():
        nonlocal pages
        print("\n" + "-" * 60)
        print("  FRONTEND -> " + frontend_root)
        print("-" * 60)

        pages_cache = os.path.join(state_dir, "pages.json")
        fe_state    = os.path.join(state_dir, "frontend_mtimes.json")

        if os.path.exists(pages_cache) and not args.force:
            if not _has_changed(
                frontend_root,
                {".js", ".ts", ".jsx", ".tsx", ".vue"},
                fe_state,
            ):
                print("\n  [CACHE] No frontend changes -- loading from pages.json")
                with open(pages_cache, encoding="utf-8") as fp:
                    pages.extend(json.load(fp))
                print("  {} pages loaded".format(len(pages)))
            else:
                print("\n  Frontend changed -- re-scanning...")
                pages.extend(_do_extract_frontend(frontend_root, pages_cache))
        else:
            if args.force:
                print("\n  --force: re-scanning from scratch...")
            print("\n  Step 1: Detecting pages & API calls...")
            pages.extend(_do_extract_frontend(frontend_root, pages_cache))

        print("\n  Step 2: Generating organized frontend documentation...")
        generate_pages_md(
            pages, docs_frontend, config,
            no_ai=no_ai,
        )

    # ── Execute in order ─────────────────────────────────────────────────────

    if order == "backend":
        if backend_root:
            run_backend()
        if frontend_root:
            run_frontend()
    elif order == "frontend":
        if frontend_root:
            run_frontend()
        if backend_root:
            run_backend()
    else:
        if backend_root:
            run_backend()
        if frontend_root:
            run_frontend()

    # ── Dependency graph ─────────────────────────────────────────────────────

    if routes or pages:
        print("\n" + "-" * 60)
        print("  Dependency Graph & Cross-Validation")
        print("-" * 60)

        graph = DependencyGraph()
        if routes:
            graph.add_apis(routes)
        if pages:
            graph.add_pages(pages)
        graph.save_json(os.path.join(output_dir, "docs", "dependency_graph.json"))
        graph.save_mermaid(os.path.join(output_dir, "docs", "dependency_graph.mermaid"))

        if not args.skip_validation and routes and pages:
            fe_calls  = [c for pg in pages for c in pg.get("api_calls", [])]
            be_routes = [
                {"method": r.get("method"),
                 "full_path": r.get("full_path", r.get("path"))}
                for r in routes
            ]
            cross = validate(fe_calls, be_routes)
            with open(os.path.join(output_dir, "docs", "cross_validation.json"), "w") as f:
                json.dump(cross, f, indent=2)
            print("  Missing in backend  : " + str(len(cross.get("missing_in_backend", []))))
            print("  Unused backend APIs : " + str(len(cross.get("unused_backend_apis", []))))
            print("  Method mismatches   : " + str(len(cross.get("mismatches", []))))

        s = graph.summary()
        print("  Pages : {}  |  APIs : {}  |  Links : {}".format(
            s["total_pages"], s["total_apis"], s["total_links"]))

    # ── Final summary ─────────────────────────────────────────────────────────

    elapsed = time.time() - start
    print("\n" + "=" * 60)
    print("  Done in {:.1f}s  |  project: {}  |  type: {}".format(
        elapsed, os.path.basename(output_dir), project_type))
    print("  Output -> " + os.path.join(output_dir, "docs"))
    print("=" * 60 + "\n")


def _do_extract_backend(backend_root, cache_path):
    routes = detect_apis(backend_root)
    save_routes_json(routes, cache_path)
    return routes


def _do_extract_frontend(frontend_root, cache_path):
    pages = scan_frontend_pages(frontend_root)
    save_pages_json(pages, cache_path)
    return pages


# =============================================================================
# CLI
# =============================================================================

def build_parser():
    p = argparse.ArgumentParser(
        description="doc_writer -- Laravel + Vue/React documentation generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
        ── Quick start ──────────────────────────────────────────────────────────
          python main.py generate-docs --path ./my-project --no-ai
          python main.py generate-docs --path ./my-project --provider ollama
          python main.py generate-docs --path ./my-project --api-key gsk_...

        ── Skip the order prompt ────────────────────────────────────────────────
          python main.py generate-docs --path ./project --order backend
          python main.py generate-docs --path ./project --order frontend
          python main.py generate-docs --path ./project --order both

        ── Force full regeneration ──────────────────────────────────────────────
          python main.py generate-docs --path ./project --force

        ── Output (named after your project) ────────────────────────────────────
          doc_output/nuerabenefits/
            docs/
              backend/
                index.md
                agent/    api.md  business.md  legacy_query.sql
                group/    api.md  business.md  legacy_query.sql
                policy/   api.md  business.md  legacy_query.sql
                billing/  ...
              frontend/
                index.md
                home.md
                payment.md
                admin_users.md
              dependency_graph.json
              cross_validation.json
            validation_report.json
        """),
    )
    sub = p.add_subparsers(dest="command")
    gen = sub.add_parser("generate-docs")

    paths = gen.add_argument_group("Project paths")
    paths.add_argument("--path",         default=None,
                       help="Project root (auto-detects backend/frontend/monorepo)")
    paths.add_argument("--backend",      default=None, help="Explicit Laravel root")
    paths.add_argument("--frontend",     default=None, help="Explicit Vue/React root")
    paths.add_argument("--output",       default="./doc_output",
                       help="Base output directory (default: ./doc_output)")
    paths.add_argument("--project-name", default=None,
                       help="Override the project folder name")

    ai = gen.add_argument_group("AI options")
    ai.add_argument("--ai-mode",  default="", choices=["", "local", "api"])
    ai.add_argument("--api-key",  default=os.environ.get("AI_API_KEY", ""),
                    help="API key (or set AI_API_KEY env var)")
    ai.add_argument("--provider", default=os.environ.get("AI_PROVIDER", ""),
                    help="anthropic | groq | openai | gemini | ollama | deepseek")
    ai.add_argument("--model",    default=os.environ.get("AI_MODEL", ""),
                    help="Override model name")
    ai.add_argument("--no-ai",    action="store_true",
                    help="Static extraction only -- no AI")
    ai.add_argument("--order",    default=None,
                    choices=["backend", "frontend", "both"],
                    help="Pipeline order (skips the interactive prompt)")
    ai.add_argument("--force",    action="store_true",
                    help="Ignore all caches and regenerate everything")

    flt = gen.add_argument_group("Filters")
    flt.add_argument("--only-backend",       action="store_true")
    flt.add_argument("--only-frontend",      action="store_true")
    flt.add_argument("--skip-validation",    action="store_true")
    flt.add_argument("--rerun-changed-only", action="store_true",
                     help="Only re-process files changed since last run")

    return p


def main():
    parser = build_parser()
    args   = parser.parse_args()
    if args.command == "generate-docs":
        if not args.path and not args.backend and not args.frontend:
            print("ERROR: provide --path, --backend, or --frontend.\n")
            parser.print_help()
            sys.exit(1)
        cmd_generate_docs(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()