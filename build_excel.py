"""
build_excel.py
──────────────────────────────────────────────────────────────────────────────
Generates TWO colour-coded Excel workbooks from generated .md documentation.

  1. nuerabenefits_backend.xlsx
       Backend API detail — columns matched to Book.xlsx reference layout.

  2. nuerabenefits_frontend.xlsx
       Frontend page detail — columns matched to RE-Frontend Detail - Copy.xlsx
       reference layout.

Missing / incomplete rows are collected into a "⚠ Needs Fill" sheet in each
workbook so devs know exactly what still needs manual entry or AI generation.
"""

import os
import re
from datetime import datetime

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# ─────────────────────────────── CONFIG / PATHS ───────────────────────────────
# Change PROJECT_NAME and paths to target a different project.
# BACKEND_PATH / FRONTEND_PATH point to the generated .md docs.
# If FRONTEND_PATH sub-folders are empty, the frontend Excel is skipped.
# To use commission_billing frontend docs instead, set:
#   FRONTEND_PATH = r"D:\CloudTech_main\Doc_writer\doc_output\commission_billing\docs\frontend"
PROJECT_NAME = "nuerabenefits"

BACKEND_PATH    = r"D:\CloudTech_main\Doc_writer\doc_output\nuerabenefits\docs\backend"
FRONTEND_PATH   = r"D:\CloudTech_main\Doc_writer\doc_output\nuerabenefits\docs\frontend"
OUTPUT_DIR      = r"D:\CloudTech_main\Doc_writer\doc_output\nuerabenefits"

BACKEND_OUTPUT  = os.path.join(OUTPUT_DIR, f"{PROJECT_NAME}_backend.xlsx")
FRONTEND_OUTPUT = os.path.join(OUTPUT_DIR, f"{PROJECT_NAME}_frontend.xlsx")

# ──────────────────────────────── COLOUR PALETTE ──────────────────────────────
C_TITLE_BG       = "1B2A4A"
C_META_LABEL_BG  = "2563EB"
C_META_VALUE_BG  = "2D3A58"
C_HEADER_BG      = "243B6E"
C_ROW_ODD        = "EFF6FF"
C_ROW_EVEN       = "FFFFFF"
C_HTTP_GET       = "DCFCE7"
C_HTTP_POST      = "EDE9FE"
C_HTTP_PUT       = "FEF3C7"
C_HTTP_PATCH     = "FEF9C3"
C_HTTP_DELETE    = "FFE4E6"
C_RESPONSE       = "FAFAFA"
C_DB_ODD         = "E8F0FE"
C_DB_EVEN        = "F1F5F9"
C_STATUS         = "F0F4FF"
C_ANSWER         = "F0FDF4"
C_MISSING_ROW    = "FFF9C4"
C_MISSING_HDR    = "F59E0B"
C_TEXT_WHITE     = "FFFFFF"
C_TEXT_DARK      = "1E293B"
C_TEXT_BLUE      = "1D4ED8"
C_TEXT_AMBER     = "92400E"
C_TEXT_GREY      = "64748B"

# Frontend teal palette
C_FE_TITLE_BG    = "134E4A"
C_FE_HEADER_BG   = "0F766E"
C_FE_META_LABEL  = "0D9488"
C_FE_ROW_ODD     = "F0FDFA"
C_FE_ROW_EVEN    = "FFFFFF"

HTTP_COLOR = {
    "GET":    C_HTTP_GET,
    "POST":   C_HTTP_POST,
    "PUT":    C_HTTP_PUT,
    "PATCH":  C_HTTP_PATCH,
    "DELETE": C_HTTP_DELETE,
}

# ─────────────────────────────── STYLE HELPERS ────────────────────────────────

def _fill(hex_color):
    return PatternFill("solid", fgColor=hex_color)

def _font(bold=False, color=C_TEXT_DARK, size=10, italic=False):
    return Font(bold=bold, color=color, size=size, italic=italic, name="Segoe UI")

def _align(h="left", v="center", wrap=True):
    return Alignment(horizontal=h, vertical=v, wrap_text=wrap)

def _border(style="thin"):
    s = Side(style=style, color="CBD5E1")
    return Border(left=s, right=s, top=s, bottom=s)

def _make_writer(ws, row_num, default_bg):
    """Return a cell-writing helper bound to the given row and background."""
    def _c(col, value, bg=None, bold=False, h="left", color=C_TEXT_DARK):
        cell = ws.cell(row=row_num, column=col, value=value)
        cell.font      = _font(bold=bold, color=color, size=9)
        cell.fill      = _fill(bg if bg is not None else default_bg)
        cell.alignment = _align(h=h, wrap=True)
        cell.border    = _border()
        return cell
    return _c

# ─────────────────────────────── MARKDOWN PARSERS ─────────────────────────────

def _text_between(text, start_marker, end_markers):
    m = re.search(re.escape(start_marker), text, re.IGNORECASE)
    if not m:
        return ""
    tail    = text[m.end():]
    end_pos = len(tail)
    for em in end_markers:
        ep = re.search(re.escape(em), tail, re.IGNORECASE)
        if ep and ep.start() < end_pos:
            end_pos = ep.start()
    return tail[:end_pos].strip()

def _md_table_to_text(md_table):
    rows = []
    for line in md_table.strip().splitlines():
        line = line.strip()
        if not line or re.match(r"^\|[-| :]+\|$", line):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        rows.append("  |  ".join(c for c in cells if c))
    return "\n".join(rows)

def _clean(t):
    t = re.sub(r"^\s*[—-]\s*None\s*$", "", t, flags=re.MULTILINE)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()

def parse_business_md(path):
    if not os.path.exists(path):
        return []
    text    = open(path, encoding="utf-8").read()
    results = []
    for sec in re.split(r"\n(?=## )", text):
        sec = sec.strip()
        if not sec or sec.startswith("# Business Logic"):
            continue
        name_m = re.match(r"^## (.+)", sec)
        name   = name_m.group(1).strip() if name_m else "Unknown"

        ep_m   = re.search(r"\*\*Endpoint\*\*\s*\|\s*`([^`]+)`",   sec)
        ctrl_m = re.search(r"\*\*Controller\*\*\s*\|\s*`([^`]+)`", sec)
        auth_m = re.search(r"\*\*Auth Required\*\*\s*\|\s*([^\n|]+)", sec)
        http_m = re.search(r"\*\*HTTP Method\*\*\s*\|\s*([A-Z]+)", sec)

        if not ep_m:
            fb       = re.search(r"`((?:GET|POST|PUT|DELETE|PATCH)\s+/[^`]+)`", sec)
            endpoint = fb.group(1).strip() if fb else ""
        else:
            endpoint = ep_m.group(1).strip()

        if not http_m:
            fb2         = re.search(r"\*\*HTTP\*\*:\s*([A-Z]+)", sec)
            http_method = fb2.group(1).strip() if fb2 else ""
        else:
            http_method = http_m.group(1).strip()

        if not http_method and endpoint:
            parts = endpoint.split()
            if parts and parts[0] in ("GET", "POST", "PUT", "PATCH", "DELETE"):
                http_method = parts[0]
                endpoint    = " ".join(parts[1:])

        controller = ctrl_m.group(1).strip() if ctrl_m else ""
        auth_raw   = auth_m.group(1).strip() if auth_m else ""
        if not auth_raw:
            am2      = re.search(r"\*\*Auth\*\*:\s*`([^`]+)`", sec)
            auth_raw = am2.group(1).strip() if am2 else ""

        markers = ["### Purpose","### Business Logic","### Input Parameters",
                   "### Database Operations","### Side Effects","---","## "]
        purpose        = _text_between(sec, "### Purpose",             markers[1:])
        business_logic = _text_between(sec, "### Business Logic",      markers[2:])
        input_raw      = _text_between(sec, "### Input Parameters",    markers[3:])
        db_raw         = _text_between(sec, "### Database Operations", markers[4:])
        side_raw       = _text_between(sec, "### Side Effects",        ["---","## "])

        input_params = _md_table_to_text(input_raw) if "|" in input_raw else _clean(input_raw)
        if input_params.lower() in ("none","— none",""):
            input_params = "—"

        results.append({
            "name":           name,
            "endpoint":       endpoint,
            "http_method":    http_method.upper() if http_method else "—",
            "controller":     controller,
            "auth":           auth_raw or "verify.internal.token",
            "purpose":        _clean(purpose) or "—",
            "business_logic": _clean(business_logic) or "—",
            "input_params":   input_params,
            "db_ops":         _clean(db_raw) or "—",
            "side_effects":   _clean(side_raw) or "—",
        })
    return results

def parse_responses_md(path):
    if not os.path.exists(path):
        return {}
    text = open(path, encoding="utf-8").read()
    out  = {}
    for sec in re.split(r"\n(?=## )", text):
        sec = sec.strip()
        if not sec or sec.startswith("# API Response"):
            continue
        hdr_m = re.match(r"^## (.+)", sec)
        if not hdr_m:
            continue
        hdr = hdr_m.group(1).strip()
        jm  = re.search(r"```json\s*(.*?)```", sec, re.DOTALL)
        out[hdr] = jm.group(1).strip() if jm else re.sub(r"^## .+\n","",sec).strip()
    return out

def load_domain(domain_path):
    endpoints = parse_business_md(os.path.join(domain_path, "business.md"))
    resp_map  = parse_responses_md(os.path.join(domain_path, "responses.md"))
    for ep in endpoints:
        resp_text = ""
        url = ep["endpoint"]
        for key, val in resp_map.items():
            if url and url in key:
                resp_text = val
                break
        if not resp_text:
            for key, val in resp_map.items():
                if ep["name"].lower() in key.lower():
                    resp_text = val
                    break
        if not resp_text and resp_map:
            values    = list(resp_map.values())
            idx       = endpoints.index(ep)
            resp_text = values[idx] if idx < len(values) else values[0]
        ep["response"] = resp_text or "—"
    return endpoints

# ──────────────────────────── MISSING DATA HELPERS ────────────────────────────

_REQUIRED_BE = ["name","endpoint","http_method","purpose","input_params",
                "db_ops","response","controller"]

def _find_missing(ep):
    return [f for f in _REQUIRED_BE if not ep.get(f) or ep[f] in ("—","Unknown","")]

def _be_status_codes(http):
    return {
        "GET":    "200 OK\n404 Not Found\n422 Validation Error",
        "POST":   "201 Created\n200 OK\n422 Validation Error\n404 Not Found",
        "PUT":    "200 OK\n422 Validation Error\n404 Not Found",
        "PATCH":  "200 OK\n422 Validation Error\n404 Not Found",
        "DELETE": "200 OK\n404 Not Found",
    }.get(http.upper(), "200 OK\n422 Validation Error\n404 Not Found")

def _build_missing_sheet(wb, missing_log, today_str, mode="backend"):
    title = "⚠ Missing Backend" if mode == "backend" else "⚠ Missing Frontend"
    ws    = wb.create_sheet(title=title)
    ws.freeze_panes = "A4"
    ws.row_dimensions[1].height = 28
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=5)
    c = ws.cell(row=1, column=1,
                value="⚠  Incomplete / Missing Data — Needs Manual Fill or AI Generation")
    c.font      = _font(bold=True, color=C_TEXT_WHITE, size=13)
    c.fill      = _fill("92400E")
    c.alignment = _align(h="left", wrap=False)
    ws.row_dimensions[2].height = 18
    ws.cell(row=2, column=1, value=f"Generated: {today_str}").font = _font(size=9, italic=True)
    ws.cell(row=2, column=2,
            value=f"Total items needing attention: {len(missing_log)}").font = _font(size=9, italic=True)
    headers = ["#","Domain / Group","Endpoint / Screen","Missing Fields","Action Required"]
    widths  = [4, 22, 46, 42, 28]
    ws.row_dimensions[3].height = 28
    for idx, (hdr, w) in enumerate(zip(headers, widths), start=1):
        cell = ws.cell(row=3, column=idx, value=hdr)
        cell.font      = _font(bold=True, color=C_TEXT_WHITE, size=10)
        cell.fill      = _fill(C_MISSING_HDR)
        cell.alignment = _align(h="center", v="center")
        cell.border    = _border()
        ws.column_dimensions[get_column_letter(idx)].width = w
    ai_fields = {"purpose","response","db_ops","business_logic","api_calls","http_method"}
    for i, item in enumerate(missing_log, start=1):
        row        = i + 3
        bg         = C_MISSING_ROW if (i % 2 == 1) else "FFFDE7"
        missing_f  = item.get("missing","")
        name_ep    = item.get("endpoint") or item.get("screen") or item.get("name","?")
        domain_grp = item.get("domain") or item.get("group","?")
        is_ai      = any(f.strip() in ai_fields for f in missing_f.split(","))
        action     = "AI Fill Recommended" if is_ai else "Manual Fill"
        ws.row_dimensions[row].height = 20
        _c = _make_writer(ws, row, bg)
        _c(1, i,          h="center")
        _c(2, domain_grp)
        _c(3, name_ep)
        _c(4, missing_f,  color=C_TEXT_AMBER, bold=True)
        _c(5, action,     color="15803D" if "AI" in action else C_TEXT_AMBER)
    return ws

# ══════════════════════════════════════════════════════════════════════════════
#  BACKEND WORKBOOK  — columns matched to Book.xlsx
# ══════════════════════════════════════════════════════════════════════════════

BE_COLUMNS = [
    ("#",                           4),
    ("Function / Endpoint Name",   22),
    ("Purpose / Trigger",          32),
    ("HTTP\nMethod",                9),
    ("Endpoint URL",               35),
    ("Request Fields\n(Params)",   32),
    ("DB Table /\nOperation",      30),
    ("Business Rules /\nNotes",    32),
    ("Open Questions",             24),
    ("Answer / Decision",          24),
    ("Answered By",                14),
    ("Date Answered",              14),
    ("Response Fields",            30),
    ("Status Codes",               16),
    ("Auth / Middleware",          22),
    ("Priority",                   10),
    ("Owner\n(Controller)",        26),
    ("Last Updated",               14),
]
BE_NUM_COLS = len(BE_COLUMNS)

def _write_be_header(ws):
    ws.row_dimensions[3].height = 36
    for col_idx, (col_name, _) in enumerate(BE_COLUMNS, start=1):
        cell = ws.cell(row=3, column=col_idx, value=col_name)
        cell.font      = _font(bold=True, color=C_TEXT_WHITE, size=10)
        cell.fill      = _fill(C_HEADER_BG)
        cell.alignment = _align(h="center", v="center", wrap=True)
        cell.border    = _border()

def _write_title_meta(ws, title_text, meta_pairs, num_cols,
                      title_bg=C_TITLE_BG, meta_label_bg=C_META_LABEL_BG,
                      meta_value_bg=C_META_VALUE_BG):
    ws.row_dimensions[1].height = 28
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=num_cols)
    t = ws.cell(row=1, column=1, value=title_text)
    t.font      = _font(bold=True, color=C_TEXT_WHITE, size=13)
    t.fill      = _fill(title_bg)
    t.alignment = _align(h="left", wrap=False)
    ws.row_dimensions[2].height = 20
    col = 1
    for label, value in meta_pairs:
        lc = ws.cell(row=2, column=col, value=label)
        lc.font      = _font(bold=True, color=C_TEXT_WHITE, size=10)
        lc.fill      = _fill(meta_label_bg)
        lc.alignment = _align(h="right", wrap=False)
        vc = ws.cell(row=2, column=col + 1, value=value)
        vc.font      = _font(color=C_TEXT_WHITE, size=10)
        vc.fill      = _fill(meta_value_bg)
        vc.alignment = _align(h="left", wrap=False)
        col += 2
    for c in range(col, num_cols + 1):
        ws.cell(row=2, column=c).fill = _fill(meta_value_bg)

def build_backend_workbook(domains_data, domain_summary, today_str):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    missing_log = []

    # ── Index sheet ────────────────────────────────────────────────────────
    ws_idx = wb.create_sheet(title="📋 Index")
    ws_idx.freeze_panes = "A4"
    _write_title_meta(
        ws_idx,
        f"📋  {PROJECT_NAME.upper()} — Backend API Documentation Index",
        [("Project:", PROJECT_NAME), ("Generated:", today_str),
         ("Total Domains:", str(len(domain_summary)))],
        6,
    )
    idx_headers = ["#","Domain","Endpoints","Controller(s)","Version / Prefix","Description"]
    idx_widths  = [4,   20,     12,          38,              18,                52]
    ws_idx.row_dimensions[3].height = 28
    for col_idx, (hdr, w) in enumerate(zip(idx_headers, idx_widths), start=1):
        cell = ws_idx.cell(row=3, column=col_idx, value=hdr)
        cell.font      = _font(bold=True, color=C_TEXT_WHITE, size=10)
        cell.fill      = _fill(C_HEADER_BG)
        cell.alignment = _align(h="center", v="center")
        cell.border    = _border()
        ws_idx.column_dimensions[get_column_letter(col_idx)].width = w
    for i, (domain, ep_count, controllers, version, description) in \
            enumerate(domain_summary, start=1):
        row = i + 3
        bg  = C_ROW_ODD if (i % 2 == 1) else C_ROW_EVEN
        ws_idx.row_dimensions[row].height = 18
        _c = _make_writer(ws_idx, row, bg)
        _c(1, i,            h="center")
        _c(2, domain,       bold=True, color=C_TEXT_BLUE)
        _c(3, ep_count,     h="center")
        _c(4, controllers)
        _c(5, version)
        _c(6, description)

    # ── Combined backend sheet ─────────────────────────────────────────────
    ws = wb.create_sheet(title=f"{PROJECT_NAME} Backend")
    ws.freeze_panes = "A4"
    for col_idx, (_, width) in enumerate(BE_COLUMNS, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = width
    _write_title_meta(
        ws,
        f"🔌  API Detail Sheet — {PROJECT_NAME.upper()} BACKEND",
        [("Module:", PROJECT_NAME), ("Last Updated:", today_str),
         ("Status:", "In Progress"), ("API Version:", "V1 / V2 / V3")],
        BE_NUM_COLS,
    )
    _write_be_header(ws)

    row_num  = 4
    glob_idx = 1

    for domain_name, endpoints in domains_data:
        if not endpoints:
            continue
        # Domain divider row
        ws.merge_cells(start_row=row_num, start_column=1,
                       end_row=row_num, end_column=BE_NUM_COLS)
        s = ws.cell(row=row_num, column=1, value=f"  ◆  {domain_name.upper()}")
        s.fill      = _fill(C_TITLE_BG)
        s.font      = _font(bold=True, color=C_TEXT_WHITE, size=10)
        s.alignment = _align(h="left", wrap=False)
        ws.row_dimensions[row_num].height = 22
        row_num += 1

        for i, ep in enumerate(endpoints):
            is_odd = (i % 2 == 0)
            row_bg = C_ROW_ODD if is_odd else C_ROW_EVEN
            db_bg  = C_DB_ODD  if is_odd else C_DB_EVEN
            http   = ep.get("http_method", "—")
            c_http = HTTP_COLOR.get(http.upper(), C_ROW_ODD)
            missing = _find_missing(ep)
            if missing:
                missing_log.append({
                    "domain":   domain_name,
                    "name":     ep.get("name","?"),
                    "endpoint": ep.get("endpoint",""),
                    "missing":  ", ".join(missing),
                })
                row_bg = C_MISSING_ROW
            ws.row_dimensions[row_num].height = max(60, 15 * max(
                len(ep.get("input_params","").split("\n")),
                len(ep.get("db_ops","").split("\n")),
                len(ep.get("business_logic","").split("\n")),
                3,
            ))
            _c = _make_writer(ws, row_num, row_bg)
            _c(1,  glob_idx,
               bg=C_TITLE_BG, bold=True, h="center", color=C_TEXT_WHITE)
            _c(2,  ep.get("name","—"),             bold=True)
            _c(3,  ep.get("purpose","—"))
            _c(4,  http, bg=c_http,                bold=True, h="center")
            _c(5,  ep.get("endpoint","—"),         bold=True, color=C_TEXT_BLUE)
            _c(6,  ep.get("input_params","—"),     bg=C_RESPONSE)
            _c(7,  ep.get("db_ops","—"),           bg=db_bg)
            _c(8,  ep.get("business_logic","—"),   bg=db_bg)
            _c(9,  "")
            _c(10, "", bg=C_ANSWER)
            _c(11, "")
            _c(12, "")
            _c(13, ep.get("response","—"),         bg=C_RESPONSE)
            _c(14, _be_status_codes(http),         bg=C_STATUS)
            _c(15, ep.get("auth","—"))
            _c(16, "—", bg=C_ROW_ODD, h="center")
            _c(17, ep.get("controller","—"),       color=C_TEXT_GREY)
            _c(18, today_str,                      h="center")
            row_num  += 1
            glob_idx += 1

    ws.auto_filter.ref = f"A3:{get_column_letter(BE_NUM_COLS)}{row_num - 1}"
    if missing_log:
        _build_missing_sheet(wb, missing_log, today_str, "backend")
    return wb, glob_idx - 1, missing_log

# ══════════════════════════════════════════════════════════════════════════════
#  FRONTEND WORKBOOK  — columns matched to RE-Frontend Detail - Copy.xlsx
# ══════════════════════════════════════════════════════════════════════════════

FE_COLUMNS = [
    ("#",                                   4),
    ("Screen Name",                        26),
    ("Route / URL",                        30),
    ("Vue Component Path",                 38),
    ("API Endpoint",                       36),
    ("HTTP Method",                        12),
    ("Request Payload /\nQuery Parameters", 38),
    ("Conditional Logic",                  32),
    ("Validation Rules",                   32),
    ("Open Questions / Notes",             30),
    ("Answer / Decision",                  28),
    ("Answered By",                        14),
    ("Date Answered",                      14),
]
FE_NUM_COLS = len(FE_COLUMNS)

def _write_fe_header(ws):
    ws.row_dimensions[3].height = 36
    for col_idx, (col_name, _) in enumerate(FE_COLUMNS, start=1):
        cell = ws.cell(row=3, column=col_idx, value=col_name)
        cell.font      = _font(bold=True, color=C_TEXT_WHITE, size=10)
        cell.fill      = _fill(C_FE_HEADER_BG)
        cell.alignment = _align(h="center", v="center", wrap=True)
        cell.border    = _border()

def parse_frontend_md(path):
    if not os.path.exists(path):
        return []
    text  = open(path, encoding="utf-8").read()
    pages = []
    for sec in re.split(r"\n(?=# (?:Page|`/))", text):
        sec = sec.strip()
        if not sec:
            continue
        route = ""
        hm = re.match(r"^#\s+(?:Page:\s*)?`([^`]+)`", sec)
        if hm:
            route = hm.group(1).strip()

        def _field(label):
            m = re.search(
                rf"\|\s*\*\*{re.escape(label)}\*\*\s*\|\s*`?([^|\n`]+)`?\s*\|", sec)
            return m.group(1).strip() if m else ""

        component   = _field("Component")
        source_file = _field("Source file")
        layout      = _field("Layout")
        example_url = _field("Example URL")

        children = []
        cm = re.search(r"## Child Components\n+(.*?)(?=\n##|\Z)", sec, re.DOTALL)
        if cm:
            block = cm.group(1).strip()
            NONE_V = {"none","none detected",
                      "none — no imported or template sub-components detected"}
            if block.lower() not in NONE_V:
                children = [ln.lstrip("- ").strip().strip("`")
                            for ln in block.splitlines()
                            if ln.strip().startswith("-")]

        composables = []
        cmp_m = re.search(r"## Composables Used\n+(.*?)(?=\n##|\Z)", sec, re.DOTALL)
        if cmp_m:
            block = cmp_m.group(1).strip()
            if block.lower() not in ("none","none detected"):
                composables = [ln.lstrip("- ").strip().strip("`").rstrip("()")
                               for ln in block.splitlines()
                               if ln.strip().startswith("-")]

        api_calls = []
        api_m = re.search(r"## Backend API Dependencies\n+(.*?)(?=\n##|\Z)", sec, re.DOTALL)
        if api_m:
            block = api_m.group(1).strip()
            if block.lower() not in ("none","none detected"):
                for row in re.finditer(
                    r"\|\s*`([A-Z]+)`\s*\|\s*`([^`]+)`\s*\|([^|]+)\|([^|]+)\|", block
                ):
                    api_calls.append({
                        "method":   row.group(1).strip(),
                        "endpoint": row.group(2).strip(),
                        "source":   row.group(3).strip(),
                        "via":      row.group(4).strip(),
                    })
                if not api_calls:
                    for ep_line in re.finditer(
                        r"-\s*Endpoint:\s*`([^`]+)`.*?Method:\s*([A-Z]+)",
                        block, re.DOTALL,
                    ):
                        api_calls.append({
                            "method":   ep_line.group(2).strip(),
                            "endpoint": ep_line.group(1).strip(),
                            "source":   "",
                            "via":      "axios",
                        })

        st_m = re.search(r"## State Management\n+(.*?)(?=\n##|\Z)", sec, re.DOTALL)
        state_mgmt = st_m.group(1).strip() if st_m else "—"
        if state_mgmt.lower() in ("none","none detected","—"):
            state_mgmt = "—"

        wn_m = re.search(r"## Warnings\n+(.*?)(?=\n##|\Z)", sec, re.DOTALL)
        warnings = wn_m.group(1).strip() if wn_m else ""
        if warnings.lower() in ("none","_none_"):
            warnings = ""

        pages.append({
            "route":       route or "UNKNOWN",
            "component":   component,
            "source_file": source_file,
            "layout":      layout,
            "example_url": example_url,
            "children":    children,
            "composables": composables,
            "api_calls":   api_calls,
            "state_mgmt":  state_mgmt,
            "warnings":    warnings,
        })
    return pages

def load_frontend_group(group_dir):
    pages = []
    for fname in sorted(os.listdir(group_dir)):
        if fname.lower() == "readme.md" or not fname.endswith(".md"):
            continue
        parsed = parse_frontend_md(os.path.join(group_dir, fname))
        for p in parsed:
            p["_filename"] = fname
        pages.extend(parsed)
    return pages

def build_frontend_workbook(fe_groups_data, today_str):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    missing_fe = []
    fe_summary = []

    for group_name, pages in fe_groups_data:
        safe_title = re.sub(r"[\\/*?:\[\]]", "", f"FE_{group_name}")[:31]
        ws = wb.create_sheet(title=safe_title)
        ws.freeze_panes = "A4"
        for col_idx, (_, w) in enumerate(FE_COLUMNS, start=1):
            ws.column_dimensions[get_column_letter(col_idx)].width = w
        _write_title_meta(
            ws,
            f"🖥️  Frontend Pages — /{group_name}",
            [("Group:", f"/{group_name}"), ("Pages:", str(len(pages))),
             ("Last Updated:", today_str)],
            FE_NUM_COLS,
            title_bg=C_FE_TITLE_BG,
            meta_label_bg=C_FE_META_LABEL,
            meta_value_bg=C_META_VALUE_BG,
        )
        _write_fe_header(ws)

        if not pages:
            ws.row_dimensions[4].height = 24
            cell = ws.cell(row=4, column=1, value="No page data found for this group.")
            cell.font      = _font(italic=True, color="94A3B8", size=9)
            cell.fill      = _fill(C_FE_ROW_ODD)
            cell.alignment = _align(h="center")
            ws.merge_cells(start_row=4, start_column=1, end_row=4, end_column=FE_NUM_COLS)
            fe_summary.append((group_name, 0, 0))
            continue

        row_num   = 4
        total_api = 0
        for page in pages:
            api_calls   = page.get("api_calls", [])
            screen_name = page.get("component","") or page.get("route","UNKNOWN")
            route       = page.get("route","UNKNOWN")
            source_file = page.get("source_file","—") or "—"

            if api_calls:
                for j, call in enumerate(api_calls):
                    total_api += 1
                    method   = call.get("method","?")
                    endpoint = call.get("endpoint","?")
                    payload  = call.get("source","—") or "—"
                    c_http   = HTTP_COLOR.get(method.upper(), C_FE_ROW_ODD)
                    is_odd   = (row_num % 2 == 0)
                    row_bg   = C_FE_ROW_ODD if is_odd else C_FE_ROW_EVEN
                    ws.row_dimensions[row_num].height = 36
                    _c = _make_writer(ws, row_num, row_bg)
                    _c(1,  row_num - 3,
                       bg=C_FE_TITLE_BG, bold=True, h="center", color=C_TEXT_WHITE)
                    _c(2,  screen_name, bold=(j == 0))
                    _c(3,  route,       bold=True, color=C_TEXT_BLUE)
                    _c(4,  source_file, color=C_TEXT_GREY)
                    _c(5,  endpoint,    bold=True, color=C_TEXT_BLUE)
                    _c(6,  method, bg=c_http, bold=True, h="center")
                    _c(7,  payload if payload != "—" else "")
                    _c(8,  "")
                    _c(9,  "")
                    _c(10, "")
                    _c(11, "", bg=C_ANSWER)
                    _c(12, "")
                    _c(13, "")
                    row_num += 1
            else:
                ws.row_dimensions[row_num].height = 36
                _c = _make_writer(ws, row_num, C_MISSING_ROW)
                _c(1,  row_num - 3,
                   bg=C_FE_TITLE_BG, bold=True, h="center", color=C_TEXT_WHITE)
                _c(2,  screen_name, bold=True)
                _c(3,  route, bold=True, color=C_TEXT_BLUE)
                _c(4,  source_file, color=C_TEXT_GREY)
                _c(5,  "[NEEDS FILL]", color=C_TEXT_AMBER, bold=True)
                _c(6,  "—")
                _c(7,  "—")
                _c(8,  "")
                _c(9,  "")
                _c(10, "No API calls detected — verify or fill manually",
                   color=C_TEXT_AMBER)
                _c(11, "", bg=C_ANSWER)
                _c(12, "")
                _c(13, "")
                missing_fe.append({
                    "group":   group_name,
                    "screen":  screen_name,
                    "route":   route,
                    "missing": "api_endpoint, http_method, request_payload",
                })
                row_num += 1

        ws.auto_filter.ref = f"A3:{get_column_letter(FE_NUM_COLS)}{row_num - 1}"
        fe_summary.append((group_name, len(pages), total_api))

    # Frontend index sheet
    ws_idx = wb.create_sheet(title="🖥️ FE Index", index=0)
    ws_idx.freeze_panes = "A4"
    _write_title_meta(
        ws_idx,
        f"🖥️  {PROJECT_NAME.upper()} Frontend — Page Groups Index",
        [("Project:", PROJECT_NAME), ("Generated:", today_str),
         ("Groups:", str(len(fe_summary)))],
        5,
        title_bg=C_FE_TITLE_BG,
        meta_label_bg=C_FE_META_LABEL,
        meta_value_bg=C_META_VALUE_BG,
    )
    idx_hdrs = ["#","Group / Prefix","Pages","API Calls","Sheet Name"]
    idx_ws   = [4,   24,              10,      12,          28]
    ws_idx.row_dimensions[3].height = 28
    for col_idx, (hdr, w) in enumerate(zip(idx_hdrs, idx_ws), start=1):
        cell = ws_idx.cell(row=3, column=col_idx, value=hdr)
        cell.font      = _font(bold=True, color=C_TEXT_WHITE, size=10)
        cell.fill      = _fill(C_FE_HEADER_BG)
        cell.alignment = _align(h="center", v="center")
        cell.border    = _border()
        ws_idx.column_dimensions[get_column_letter(col_idx)].width = w
    for i, (group, page_count, api_count) in enumerate(fe_summary, start=1):
        row        = i + 3
        bg         = C_FE_ROW_ODD if (i % 2 == 1) else C_FE_ROW_EVEN
        sheet_name = re.sub(r"[\\/*?:\[\]]", "", f"FE_{group}")[:31]
        ws_idx.row_dimensions[row].height = 18
        _c = _make_writer(ws_idx, row, bg)
        _c(1, i,            h="center")
        _c(2, f"/{group}",  bold=True, color=C_TEXT_BLUE)
        _c(3, page_count,   h="center")
        _c(4, api_count,    h="center")
        _c(5, sheet_name)

    if missing_fe:
        _build_missing_sheet(wb, missing_fe, today_str, "frontend")
    return wb, missing_fe

# ──────────────────────────────────────────────────────────────────────────────
#  MAIN
# ──────────────────────────────────────────────────────────────────────────────

def main():
    today_str = datetime.today().strftime("%Y-%m-%d")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ══ BACKEND ════════════════════════════════════════════════════════════════
    print(f"=== Building BACKEND Excel for [{PROJECT_NAME}] ===")
    if not os.path.isdir(BACKEND_PATH):
        print(f"[ERROR] Backend path not found: {BACKEND_PATH}")
        return

    domains = sorted([
        d for d in os.listdir(BACKEND_PATH)
        if os.path.isdir(os.path.join(BACKEND_PATH, d))
    ])
    print(f"Found {len(domains)} backend domains.")

    domains_data   = []
    domain_summary = []
    for domain in domains:
        domain_path = os.path.join(BACKEND_PATH, domain)
        print(f"  Processing: {domain}")
        endpoints = load_domain(domain_path)
        domain_summary.append((domain, len(endpoints), "", "", ""))
        domains_data.append((domain, endpoints))

    wb_be, total_eps, be_missing = build_backend_workbook(
        domains_data, domain_summary, today_str
    )
    wb_be.save(BACKEND_OUTPUT)
    print(f"\nSaved  → {BACKEND_OUTPUT}")
    print(f"  Sheets          : {list(wb_be.sheetnames)}")
    print(f"  Total endpoints : {total_eps}")
    print(f"  Incomplete rows : {len(be_missing)}  (see sheet: ⚠ Missing Backend)")

    # ══ FRONTEND ═══════════════════════════════════════════════════════════════
    print(f"\n=== Building FRONTEND Excel for [{PROJECT_NAME}] ===")
    if not os.path.isdir(FRONTEND_PATH):
        print(f"[WARN] Frontend docs not found at: {FRONTEND_PATH}")
        print("       Skipping frontend Excel generation.")
        return

    fe_dirs = sorted([
        d for d in os.listdir(FRONTEND_PATH)
        if os.path.isdir(os.path.join(FRONTEND_PATH, d))
        and d not in ("undocumented",)
    ])
    if not fe_dirs:
        print("[INFO] Frontend folder exists but contains no group sub-folders.")
        print("       Skipping frontend Excel generation.")
        return

    print(f"Found {len(fe_dirs)} frontend groups.")
    fe_groups_data = []
    for group in fe_dirs:
        group_dir = os.path.join(FRONTEND_PATH, group)
        print(f"  FE Group: {group}")
        pages = load_frontend_group(group_dir)
        fe_groups_data.append((group, pages))

    wb_fe, fe_missing = build_frontend_workbook(fe_groups_data, today_str)
    wb_fe.save(FRONTEND_OUTPUT)
    total_pages = sum(len(ps) for _, ps in fe_groups_data)
    print(f"\nSaved  → {FRONTEND_OUTPUT}")
    print(f"  Sheets          : {list(wb_fe.sheetnames)}")
    print(f"  Total pages     : {total_pages}")
    print(f"  Incomplete rows : {len(fe_missing)}  (see sheet: ⚠ Missing Frontend)")


if __name__ == "__main__":
    main()
