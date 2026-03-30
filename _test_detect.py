"""Quick smoke-test for detect_apis improvements."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from backend.detect_apis import (_api_resource_routes,
                                 _collapse_multiline_routes,
                                 _extract_function_body, _is_group_opener,
                                 _parse_routes_from_file, _strip_php_comments,
                                 detect_apis)

# ── Test 1: comment stripping ─────────────────────────────────────────────────
code = "/* block */ Route::get('/a', [\n// line comment\n]);  # hash"
stripped = _strip_php_comments(code)
assert "block" not in stripped, "block comment not stripped"
assert "line comment" not in stripped, "line comment not stripped"
print("PASS  _strip_php_comments")

# ── Test 2: collapse multi-line array handler ─────────────────────────────────
code2 = "Route::post('/path', [\n    FooController::class,\n    'store'\n]);"
collapsed = _collapse_multiline_routes(code2)
lines = [l for l in collapsed.split("\n") if l.strip()]
assert len(lines) == 1, f"Expected 1 line, got {len(lines)}: {lines}"
assert "FooController" in lines[0] and "'store'" in lines[0]
print("PASS  _collapse_multiline_routes (array)")

# ── Test 3: collapse fluent chained group opener ──────────────────────────────
code3 = "Route::prefix('v1')\n    ->middleware(['auth'])\n    ->group(function () {"
collapsed3 = _collapse_multiline_routes(code3)
lines3 = [l for l in collapsed3.split("\n") if l.strip()]
assert len(lines3) == 1, f"Expected 1 line, got {len(lines3)}: {lines3}"
assert "->group(" in lines3[0]
print("PASS  _collapse_multiline_routes (chained)")

# ── Test 4: is_group_opener ───────────────────────────────────────────────────
assert _is_group_opener("Route::group(['prefix'=>'api'], function () {")
assert _is_group_opener("Route::prefix('v1') ->middleware(['auth']) ->group(function () {")
assert not _is_group_opener("Route::get('/path', function () {")   # route WITH closure
assert not _is_group_opener("Route::get('/users', [UserController::class, 'index']);")
print("PASS  _is_group_opener")

# ── Test 5: _extract_function_body ── case-insensitive and Allman style ───────
php_code = """
<?php
class FooController {
    public function MyMethod(Request $request)
    {
        $x = User::where('id', 1)->first();
        return response()->json(['ok' => true]);
    }

    public function anotherMethod(): array {
        return [];
    }
}
"""
body = _extract_function_body(php_code, "mymethod")   # lowercase → should still match
assert "User::where" in body, f"Expected body, got: {repr(body)}"
print("PASS  _extract_function_body (case-insensitive)")

body2 = _extract_function_body(php_code, "anotherMethod")
assert "return []" in body2, f"Expected body2, got: {repr(body2)}"
print("PASS  _extract_function_body (inline brace style)")

# ── Test 6: full route parsing with brace-depth group tracking ────────────────
sample = """<?php
Route::middleware(['auth:sanctum'])->prefix('api/v1')->group(function () {
    Route::get('/users', [UserCtrl::class, 'index']);
    Route::post('/users', [UserCtrl::class, 'store']);

    Route::prefix('admin')->group(function () {
        Route::get('/dashboard', [AdminCtrl::class, 'index']);
    });

    Route::get('/users/{id}', function() {
        return response()->json([]);
    });
});
Route::get('/health', HealthCtrl::class);
"""
routes = _parse_routes_from_file(sample, "test.php")
paths = {r["full_path"] for r in routes}
methods_map = {r["full_path"]: r["method"] for r in routes}
controllers = {r["full_path"]: r["controller"] for r in routes}
actions_map = {r["full_path"]: r["action"] for r in routes}

assert "/api/v1/users" in paths, f"Missing /api/v1/users, got: {paths}"
assert "/api/v1/admin/dashboard" in paths, f"Missing admin dashboard, got: {paths}"
assert "/health" in paths, f"Missing health route, got: {paths}"
assert actions_map.get("/health") == "__invoke", f"Expected __invoke for health, got {actions_map.get('/health')}"
print(f"PASS  _parse_routes_from_file basic ({len(routes)} routes)")

# inline closure route should NOT mess up prefix stack
user_id_route = [r for r in routes if "{id}" in r["full_path"]]
assert user_id_route, "Missing {id} route"
assert user_id_route[0]["full_path"].startswith("/api/v1"), f"Wrong prefix: {user_id_route[0]['full_path']}"
print("PASS  _parse_routes_from_file inline closure doesn't break prefix stack")

# ── Test 7: apiResource expansion ────────────────────────────────────────────
sample_api = """<?php
Route::prefix('v1')->group(function () {
    Route::apiResource('/products', ProductCtrl::class);
});
"""
api_routes = _parse_routes_from_file(sample_api, "test.php")
methods = sorted(r["method"] for r in api_routes)
assert "GET" in methods and "POST" in methods and "DELETE" in methods and "PATCH" in methods, \
    f"apiResource missing methods: {methods}"
assert all("/v1/products" in r["full_path"] for r in api_routes), \
    f"Wrong prefix on apiResource: {[r['full_path'] for r in api_routes]}"
print(f"PASS  apiResource expansion ({len(api_routes)} routes)")

# ── Test 8: Route::match ──────────────────────────────────────────────────────
sample_match = """<?php
Route::match(['get', 'post'], '/login', [AuthCtrl::class, 'login']);
"""
match_routes = _parse_routes_from_file(sample_match, "test.php")
match_methods = {r["method"] for r in match_routes}
assert "GET" in match_methods and "POST" in match_methods, f"Route::match methods: {match_methods}"
print("PASS  Route::match")

# ── Test 9: Laravel 9+ Route::controller() group ─────────────────────────────
sample_ctrl_grp = """<?php
Route::controller(UserCtrl::class)->group(function () {
    Route::get('/users', 'index');
    Route::post('/users', 'store');
});
"""
ctrl_routes = _parse_routes_from_file(sample_ctrl_grp, "test.php")
assert len(ctrl_routes) == 2, f"Expected 2, got {len(ctrl_routes)}"
for r in ctrl_routes:
    assert "UserCtrl" in r["controller"], f"controller: {r['controller']}"
    assert r["action"] in ("index", "store"), f"action: {r['action']}"
print("PASS  Route::controller() group (Laravel 9+)")

# ── Test 10: real project run (if available) ──────────────────────────────────
project = None
for candidate in [
    r"d:\CloudTech_main\nuerabenefits",
    r"d:\CloudTech_main\commission_billing",
    r"d:\CloudTech_main\commission-billing",
]:
    if os.path.exists(candidate):
        project = candidate
        break

if project:
    print(f"\nRunning on real project: {project}")
    routes = detect_apis(project)
    body_fail = sum(1 for r in routes if any("Body of" in u for u in r.get("unknowns", [])))
    not_found = sum(1 for r in routes if any("not found" in u for u in r.get("unknowns", [])))
    closure   = sum(1 for r in routes if r.get("controller") == "Closure")
    success   = sum(1 for r in routes if r.get("steps") or r.get("queries"))
    print(f"  Total routes     : {len(routes)}")
    print(f"  Successfully traced: {success}")
    print(f"  Body fail        : {body_fail}")
    print(f"  Controller !found: {not_found}")
    print(f"  Closure routes   : {closure}")
else:
    print("\n(No real project found — skipping integration test)")

print("\nAll tests passed!")
