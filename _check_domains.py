import json
import os
import re
import sys

sys.path.insert(0, r'd:\CloudTech_main\Doc_writer')
from backend.generate_docs import detect_domain

bad_domains = ['add','all','app','edit','get','getcontractnamelist',
               'getsignedcontractlevel','list','remove',
               'updateuseraccessfeature','statu','top','ai']

be_dir = r'd:\CloudTech_main\Doc_writer\doc_output\nuerabenefits\docs\backend'

for bad in bad_domains:
    api_md = os.path.join(be_dir, bad, 'api.md')
    if not os.path.exists(api_md):
        continue
    content = open(api_md, encoding='utf-8').read()
    # Find "Endpoint   : `METHOD /path`" lines
    endpoints = re.findall(r"Endpoint\s*\*\*\s*:\s*`([A-Z]+)\s+([^`]+)`", content)
    print(f"=== {bad} ({len(endpoints)} routes) ===")
    for method, path in endpoints:
        new_d = detect_domain(method, path.strip(), '')
        print(f"  {method} {path.strip()}  =>  {new_d}")
    print()
