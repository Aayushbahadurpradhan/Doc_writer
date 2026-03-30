"""
gen_nuerabenefits_excel.py — thin wrapper over build_excel.generate_excel()

Previously this file contained ~500 lines of duplicate Excel-generation code.
It now delegates to build_excel.py which has the canonical implementation.

Usage:
    python gen_nuerabenefits_excel.py
    python gen_nuerabenefits_excel.py --docs-root /path/to/docs --output /path/to/out --project myproject
"""

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)


# Default nuerabenefits paths (original hardcoded values)
_DEFAULT_DOCS   = r"D:\CloudTech_main\Doc_writer\doc_output\nuerabenefits\docs"
_DEFAULT_OUTPUT = r"D:\CloudTech_main\Doc_writer\doc_output\nuerabenefits"
_DEFAULT_NAME   = "nuerabenefits"


def main():
    parser = argparse.ArgumentParser(
        description="Generate Excel workbooks from doc_writer markdown output.",
    )
    parser.add_argument("--docs-root", default=_DEFAULT_DOCS,
                        help="Path to docs/ folder  (default: nuerabenefits docs)")
    parser.add_argument("--output",    default=_DEFAULT_OUTPUT,
                        help="Directory to save .xlsx files")
    parser.add_argument("--project",   default=_DEFAULT_NAME,
                        help="Project name used for workbook titles and filenames")
    args = parser.parse_args()

    from build_excel import generate_excel
    be_path, fe_path = generate_excel(args.docs_root, args.output, args.project)
    if be_path:
        print("Backend Excel  -> " + be_path)
    if fe_path:
        print("Frontend Excel -> " + fe_path)


if __name__ == "__main__":
    main()
