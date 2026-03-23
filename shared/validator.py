"""
Cross-check frontend API calls vs backend routes.

Output:
{
  "missing_in_backend":  ["/api/xyz"],
  "unused_backend_apis": ["/api/deprecated"],
  "mismatches": [
    {
      "frontend_calls":  "POST /api/users",
      "backend_defines": "GET /api/users",
      "issue":           "method mismatch"
    }
  ]
}

Rules:
  - Match on full_path + method
  - Ignore query parameters in matching
  - Flag every mismatch — do not silently skip
"""

import re
from typing import List, Optional


def _normalise_path(path: str) -> str:
    """
    Normalise a path for comparison:
    - Strip query string
    - Remove trailing slash
    - Collapse numeric IDs → {id}
    - Lowercase
    """
    path = path.split("?")[0].rstrip("/").lower()
    path = re.sub(r"/\d+", "/{id}", path)
    return path


def _path_matches(a: str, b: str) -> bool:
    """True if two normalised paths are equivalent."""
    na, nb = _normalise_path(a), _normalise_path(b)
    if na == nb:
        return True
    # One may have {id} where the other has a literal param
    pat_a = re.sub(r"\{[^}]+\}", r"[^/]+", re.escape(na))
    pat_b = re.sub(r"\{[^}]+\}", r"[^/]+", re.escape(nb))
    return bool(re.fullmatch(pat_a, nb)) or bool(re.fullmatch(pat_b, na))


def validate(
    frontend_calls: List[dict],
    backend_routes: List[dict],
) -> dict:
    """
    frontend_calls  — list of { "method": "GET", "endpoint": "/api/users" }
    backend_routes  — list of { "method": "GET", "full_path": "/api/users" }

    Returns validation report dict.
    """
    missing_in_backend:  list = []
    unused_backend_apis: list = []
    mismatches:          list = []

    # Index backend routes: normalised_path → list of methods
    backend_index: dict = {}
    for route in backend_routes:
        np = _normalise_path(route.get("full_path", route.get("path", "")))
        m  = route.get("method", "GET").upper()
        if np not in backend_index:
            backend_index[np] = set()
        backend_index[np].add(m)

    # Track which backend paths were referenced by frontend
    referenced_backend: set = set()

    for call in frontend_calls:
        endpoint = call.get("endpoint", "")
        method   = call.get("method", "GET").upper()

        if endpoint == "UNKNOWN" or not endpoint:
            continue

        np = _normalise_path(endpoint)

        # Find matching backend path
        matched_path: Optional[str] = None
        for bp in backend_index:
            if _path_matches(np, bp):
                matched_path = bp
                break

        if matched_path is None:
            missing_in_backend.append(f"{method} {endpoint}")
            continue

        referenced_backend.add(matched_path)
        backend_methods = backend_index[matched_path]

        # Exact method check
        if method not in backend_methods and "ANY" not in backend_methods:
            for bm in backend_methods:
                mismatches.append({
                    "frontend_calls":  f"{method} {endpoint}",
                    "backend_defines": f"{bm} {endpoint}",
                    "issue":           "method mismatch",
                })

    # Unused backend APIs
    for bp, methods in backend_index.items():
        if bp not in referenced_backend:
            for m in methods:
                unused_backend_apis.append(f"{m} {bp}")

    return {
        "missing_in_backend":  sorted(set(missing_in_backend)),
        "unused_backend_apis": sorted(set(unused_backend_apis)),
        "mismatches":          mismatches,
    }
