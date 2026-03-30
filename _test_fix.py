"""
_test_fix.py  —  Manual diagnostic for backend/detect_apis.py

Usage:
    python _test_fix.py
    python _test_fix.py C:/path/to/laravel-project
"""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from backend.detect_apis import (_extract_function_body, _find_controller_file,
                                 _trace_controller, read_file)

# Project root: use first CLI arg or fall back to the default test project
root = sys.argv[1] if len(sys.argv) > 1 else r'D:\CloudTech_main\traile\corenroll-api'

if not os.path.isdir(root):
    print("ERROR: project root not found: " + root)
    sys.exit(1)

print("Running against: " + root)
print()

cases = [
    ('App\\Http\\Controllers\\Api\\V1\\AuthController', 'login'),
    ('App\\Http\\Controllers\\SMMRInfoController', 'verifySSMRProductUser'),
    ('App\\Http\\Controllers\\ValidationController', 'validateRoutingNumber'),
    ('App\\Http\\Controllers\\Contracts\\GetContractDataController', 'checkContracts'),
    ('App\\Http\\Controllers\\Api\\PetCare\\PetCareInfoController', 'getPetHospitalByZip'),
]

for ctrl, func in cases:
    f      = _find_controller_file(ctrl, root)
    body   = _extract_function_body(read_file(f), func) if f else ''
    cname  = ctrl.split('\\')[-1]
    fname  = os.path.basename(f) if f else 'NONE'
    trace  = _trace_controller(body) if body else {}
    steps  = trace.get('steps', [])
    unknowns = trace.get('unknowns', [])
    print('{}.{}: file={} bodylen={} steps={}'.format(
        cname, func, fname, len(body), len(steps)))
    print('  step_types=' + str([s.get('type') for s in steps[:4]]))
    if unknowns:
        print('  unknowns=' + str(unknowns))

print('\nDONE')
