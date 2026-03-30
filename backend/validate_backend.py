"""
validate_backend.py — Step 3 of the backend pipeline.

Checks completeness of extraction:
  - Routes extracted but not documented
  - Controllers referenced but not parsed
  - Queries detected but not classified
  - UNKNOWN entries needing manual review

Output:
{
  "undocumented_routes":       [],
  "unparsed_controllers":      [],
  "unclassified_queries":      [],
  "unknowns_requiring_review": []
}
"""

import json
import os
from typing import List


def validate_backend(routes: List[dict]) -> dict:
    """
    Run completeness checks on the extracted route list.
    Returns a validation report dict.
    """
    undocumented_routes:       List[str] = []
    unparsed_controllers:      List[str] = []
    unclassified_queries:      List[str] = []
    unknowns_requiring_review: List[str] = []

    for route in routes:
        method    = route.get("method", "?")
        full_path = route.get("full_path", route.get("path", "?"))
        ctrl      = route.get("controller", "")
        action    = route.get("action", "")
        label     = f"{method} {full_path}"

        # No steps → not meaningfully documented
        if not route.get("steps"):
            undocumented_routes.append(label)

        # Controller not resolved
        if ctrl in ("Closure", "Unknown", "", None) or action in ("unknown", "", None):
            unparsed_controllers.append(label)

        # Unclassified queries
        for q in route.get("queries", []):
            if q.get("type", "unknown") == "unknown" or not q.get("type"):
                unclassified_queries.append(
                    f"{label} — {q.get('raw', q.get('query', '(no detail)'))[:60]}"
                )

        # Unknowns
        for u in route.get("unknowns", []):
            unknowns_requiring_review.append(f"{label}: {u}")

    # De-duplicate
    return {
        "undocumented_routes":       sorted(set(undocumented_routes)),
        "unparsed_controllers":      sorted(set(unparsed_controllers)),
        "unclassified_queries":      sorted(set(unclassified_queries)),
        "unknowns_requiring_review": list(dict.fromkeys(unknowns_requiring_review)),
        "summary": {
            "total_routes":              len(routes),
            "undocumented":              len(set(undocumented_routes)),
            "unparsed_controllers":      len(set(unparsed_controllers)),
            "unclassified_queries":      len(set(unclassified_queries)),
            "unknowns_requiring_review": len(unknowns_requiring_review),
        }
    }


def save_validation_report(report: dict, output_path: str) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"  [OK] validation_report.json -> {output_path}")


def print_validation_summary(report: dict) -> None:
    s = report.get("summary", {})
    total = s.get("total_routes", 0)
    print("\n  --- Backend Validation Summary --------------------------")
    print(f"  Total routes       : {total}")
    print(f"  Undocumented       : {s.get('undocumented', 0)}")
    print(f"  Unparsed controllers: {s.get('unparsed_controllers', 0)}")
    print(f"  Unclassified queries: {s.get('unclassified_queries', 0)}")
    print(f"  Unknowns for review: {s.get('unknowns_requiring_review', 0)}")
    print("  ---------------------------------------------------------")

    for key in ("undocumented_routes", "unparsed_controllers",
                "unclassified_queries", "unknowns_requiring_review"):
        items = report.get(key, [])
        if items:
            label = key.replace("_", " ").title()
            print(f"\n  [WARN] {label}:")
            for item in items[:10]:
                print(f"    - {item}")
            if len(items) > 10:
                print(f"    ... and {len(items)-10} more")
