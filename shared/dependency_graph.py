"""
Build a frontend ↔ backend dependency graph.

graph = {
  "pages": { "/dashboard": { "component": "Dashboard.vue", ... } },
  "apis":  { "GET /api/users": { "controller": "UserController", ... } },
  "links": [
    { "from": "/dashboard", "to": "/api/users", "method": "GET" }
  ]
}

Export as JSON (and optionally Mermaid.js diagram).
"""

import json
import os
from typing import List, Optional


class DependencyGraph:
    def __init__(self):
        self.pages: dict = {}   # path → page metadata
        self.apis:  dict = {}   # "METHOD /path" → api metadata
        self.links: list = []   # { from, to, method }

    # ─── Loaders ─────────────────────────────────────────────────────────────

    def add_pages(self, pages: List[dict]) -> None:
        """Ingest output from frontend detect_pages."""
        for page in pages:
            path = page.get("path", "UNKNOWN")
            self.pages[path] = {
                "component":       page.get("component", "UNKNOWN"),
                "layout":          page.get("layout", "UNKNOWN"),
                "children":        page.get("children", []),
                "state_management": page.get("state_management", []),
            }
            for call in page.get("api_calls", []):
                endpoint = call.get("endpoint", "UNKNOWN")
                method   = call.get("method", "GET")
                if endpoint != "UNKNOWN":
                    self.links.append({
                        "from":        path,
                        "to":          endpoint,
                        "method":      method,
                        "called_from": call.get("called_from", "UNKNOWN"),
                        "via":         call.get("via", "direct"),
                    })

    def add_apis(self, routes: List[dict]) -> None:
        """Ingest output from backend detect_apis."""
        for r in routes:
            key = f"{r.get('method','?')} {r.get('full_path', r.get('path','?'))}"
            self.apis[key] = {
                "controller": r.get("controller", "UNKNOWN"),
                "action":     r.get("action", "UNKNOWN"),
                "middleware": r.get("middleware", []),
            }

    # ─── Exporters ───────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "pages": self.pages,
            "apis":  self.apis,
            "links": self.links,
        }

    def save_json(self, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        print(f"✅ dependency_graph.json → {path}")

    def save_mermaid(self, path: str) -> None:
        """
        Emit a Mermaid.js diagram showing page → API links.
        Truncated to first 80 links to keep diagrams readable.
        """
        os.makedirs(os.path.dirname(path), exist_ok=True)
        lines = ["graph LR"]
        seen: set = set()
        for link in self.links[:80]:
            frm = link["from"].replace("/", "_").strip("_") or "root"
            to  = link["to"].replace("/", "_").strip("_")   or "api"
            key = f"{frm}-->{to}"
            if key not in seen:
                seen.add(key)
                label = link.get("method", "GET")
                lines.append(f'    {frm}["{link["from"]}"] -->|{label}| {to}["{link["to"]}"]')
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"✅ dependency_graph.mermaid → {path}")

    # ─── Summary ─────────────────────────────────────────────────────────────

    def summary(self) -> dict:
        return {
            "total_pages": len(self.pages),
            "total_apis":  len(self.apis),
            "total_links": len(self.links),
            "pages_with_no_api_calls": [
                p for p in self.pages
                if not any(lk["from"] == p for lk in self.links)
            ],
        }
