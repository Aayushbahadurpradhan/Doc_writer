import sys

sys.path.insert(0, r'D:\CloudTech_main\Doc_writer')
from backend.detect_apis import (_extract_function_body, _find_controller_file,
                                 _trace_controller, read_file)

root = r'D:\CloudTech_main\traile\corenroll-api'

cases = [
    ('App\\Http\\Controllers\\Api\\V1\\AuthController', 'login'),
    ('App\\Http\\Controllers\\SMMRInfoController', 'verifySSMRProductUser'),
    ('App\\Http\\Controllers\\ValidationController', 'validateRoutingNumber'),
    ('App\\Http\\Controllers\\Contracts\\GetContractDataController', 'checkContracts'),
    ('App\\Http\\Controllers\\Api\\PetCare\\PetCareInfoController', 'getPetHospitalByZip'),
]
for ctrl, func in cases:
    f = _find_controller_file(ctrl, root)
    body = _extract_function_body(read_file(f), func) if f else ''
    cname = ctrl.split('\\')[-1]
    fname = f.split('\\')[-1] if f else 'NONE'
    trace = _trace_controller(body) if body else {}
    steps = trace.get('steps', [])
    unknowns = trace.get('unknowns', [])
    print(cname + '.' + func + ': file=' + fname + ' bodylen=' + str(len(body)) + ' steps=' + str(len(steps)))
    print('  step_types=' + str([s.get('type') for s in steps[:4]]))
    if unknowns:
        print('  unknowns=' + str(unknowns))
print('DONE')

from backend.detect_apis import (_extract_function_body, _find_controller_file,
                                 read_file)

root = r'D:\CloudTech_main\traile\corenroll-api'
cases = [
    ('App\\\\Http\\\\Controllers\\\\Api\\\\V1\\\\AuthController', 'login'),
    ('App\\\\Http\\\\Controllers\\\\SMMRInfoController', 'verifySSMRProductUser'),
    ('App\\\\Http\\\\Controllers\\\\ValidationController', 'validateRoutingNumber'),
    ('App\\\\Http\\\\Controllers\\\\Contracts\\\\GetContractDataController', 'checkContracts'),
]
for ctrl, func in cases:
    f = _find_controller_file(ctrl, root)
    body = _extract_function_body(read_file(f), func) if f else ''
    cname = ctrl.split('\\\\')[-1]; fname = f.split('\\\\')[-1] if f else 'NONE'
    print(f'{cname}.{func}: file={fname} bodylen={len(body)}')
