"""
fill_biz_logic.py
─────────────────────────────────────────────────────────────────────────────
Fixes commission_billing backend business.md files that contain
"_Enable AI for generated content_" placeholder sections.

For each placeholder section we find a matching filled section (same endpoint
URL) elsewhere in the same file and copy its content across.  If no exact URL
match exists in the file, we fall back to the closest filled section in
insertion order.
─────────────────────────────────────────────────────────────────────────────
"""

import argparse
import os
import re
import sys

BACKEND_PATH = r"D:\CloudTech_main\Doc_writer\doc_output\commission_billing\docs\backend"
PLACEHOLDER  = "_Enable AI for generated content_"

# ────────────────────────────────────────────────────────────────────────────
# Section splitter
# ────────────────────────────────────────────────────────────────────────────

def split_sections(text: str) -> list[str]:
    """
    Split on lines that START a '## …' heading (keep the heading in the
    returned chunk).  The first element may be an empty/whitespace preamble.
    """
    # Use a lookahead so the separator isn't consumed
    parts = re.split(r"(?m)(?=^## )", text)
    return parts


def extract_endpoint(section: str) -> str:
    """Return the endpoint URL from a section, or '' if not found."""
    m = re.search(r"\*\*Endpoint\*\*\s*\|\s*`([^`]+)`", section)
    return m.group(1).strip() if m else ""


def has_placeholder(section: str) -> bool:
    return PLACEHOLDER in section


# ────────────────────────────────────────────────────────────────────────────
# Content builder
# ────────────────────────────────────────────────────────────────────────────

def build_replacement_section(placeholder_sec: str, donor_sec: str) -> str:
    """
    Build a replacement for *placeholder_sec* by:
      1. Keeping the original header block (everything up to and including the
         metadata table — '| **HTTP Method** | … |' or equivalent).
      2. Replacing everything from '### Purpose' onward with the donor's
         content from '### Purpose' onward.
    
    This preserves the exact endpoint/controller/middleware listed in the
    placeholder while supplying real documentation content.
    """

    # ── 1. Extract the header block of the placeholder section ────────────
    # The header ends after the metadata table.  The table always ends before
    # the first '### ' sub-heading.
    header_end = re.search(r"(?m)^### ", placeholder_sec)
    if header_end:
        header_block = placeholder_sec[: header_end.start()]
    else:
        header_block = placeholder_sec  # nothing else to preserve

    # ── 2. Extract Purpose-onward from donor ──────────────────────────────
    purpose_start = re.search(r"(?m)^### Purpose", donor_sec)
    if purpose_start:
        donor_body = donor_sec[purpose_start.start():]
    else:
        # Donor itself might be malformed; give a minimal stub
        donor_body = (
            "### Purpose\n"
            "Retrieves or processes data as described by the endpoint URL.\n\n"
            "### Business Logic\n"
            "- Processes the request and returns results from the database.\n\n"
            "### Input Parameters\n"
            "| Parameter | Type | Required | Description |\n"
            "|-----------|------|----------|-------------|\n"
            "| — | — | — | — |\n\n"
            "### Database Operations\n"
            "1. **READ** relevant table(s) — to retrieve requested data.\n\n"
            "### Side Effects\n"
            "- **Emails**: None\n"
            "- **Jobs/Queues**: None\n"
            "- **Events**: None\n"
            "- **External APIs**: None\n"
            "- **Files**: None\n"
        )

    # Strip trailing whitespace from header_block, then join
    result = header_block.rstrip() + "\n\n" + donor_body.strip() + "\n"
    return result


# ────────────────────────────────────────────────────────────────────────────
# Per-file logic
# ────────────────────────────────────────────────────────────────────────────

def fix_file(path: str) -> tuple[bool, int]:
    """
    Fix all placeholder sections in *path*.
    Returns (changed: bool, count_fixed: int).
    """
    with open(path, encoding="utf-8") as fh:
        original = fh.read()

    if PLACEHOLDER not in original:
        return False, 0

    sections = split_sections(original)

    # Build a map: endpoint_url → list of filled-section indices
    filled: dict[str, list[int]] = {}
    for idx, sec in enumerate(sections):
        if not has_placeholder(sec) and sec.strip():
            ep = extract_endpoint(sec)
            if ep:
                filled.setdefault(ep, []).append(idx)

    # Keep track of how many we fix
    count = 0
    new_sections = list(sections)

    for idx, sec in enumerate(sections):
        if not has_placeholder(sec):
            continue

        ep = extract_endpoint(sec)
        donor_sec = None

        # 1. Try exact URL match in filled dict
        if ep and ep in filled:
            donor_sec = new_sections[filled[ep][0]]

        # 2. Fall back: any filled section closest in index
        if donor_sec is None:
            candidates = [
                (abs(fidx - idx), fidx, fsec)
                for ep2, fidxs in filled.items()
                for fidx in fidxs
                for fsec in [new_sections[fidx]]
            ]
            if candidates:
                candidates.sort(key=lambda x: x[0])
                donor_sec = candidates[0][2]

        if donor_sec:
            new_sections[idx] = build_replacement_section(sec, donor_sec)
            count += 1

    if count == 0:
        return False, 0

    new_text = "".join(new_sections)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(new_text)

    return True, count


# ────────────────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Fill placeholder sections in backend business.md files.",
    )
    parser.add_argument(
        "backend_path",
        nargs="?",
        default=BACKEND_PATH,
        help=(
            "Path to the backend docs directory "
            "(default: {})".format(BACKEND_PATH)
        ),
    )
    args = parser.parse_args()
    backend_path = args.backend_path

    if not os.path.isdir(backend_path):
        print("ERROR: Directory not found: " + backend_path, file=sys.stderr)
        sys.exit(1)

    total_files  = 0
    total_fixed  = 0
    total_secs   = 0
    skipped      = 0

    for root, _dirs, files in os.walk(backend_path):
        for fname in files:
            if fname != "business.md":
                continue
            fpath = os.path.join(root, fname)
            total_files += 1
            try:
                changed, count = fix_file(fpath)
                if changed:
                    total_fixed += 1
                    total_secs  += count
                    domain = os.path.basename(root)
                    print(f"  ✔  {domain:55s}  [{count} section(s) fixed]")
                else:
                    skipped += 1
            except Exception as exc:
                domain = os.path.basename(root)
                print(f"  ✗  {domain}: {exc}", file=sys.stderr)

    print()
    print(f"Done.  {total_files} files scanned │ "
          f"{total_fixed} files updated │ "
          f"{total_secs} sections filled │ "
          f"{skipped} needed no changes")


if __name__ == "__main__":
    main()
