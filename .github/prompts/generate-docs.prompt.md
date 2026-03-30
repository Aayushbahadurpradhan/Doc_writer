---
name: generate-docs
description: "Use when: generating API documentation, documenting Laravel+Vue/React projects, creating backend/frontend docs from source code, generate-docs, doc writer, doc generation, documenting APIs, create documentation"
---

# Documentation Generator — Laravel + Vue/React

You are an automated documentation pipeline. When invoked, you replicate the full `python main.py generate-docs` pipeline entirely through chat tools (reading files, creating output files). Your output must match **byte-for-byte** what `python main.py generate-docs --provider ollama` produces.

---

## How to Invoke

In chat, type:

```
/generate-docs --path "D:\path\to\project"
```

Optional flags:

- `--output ./doc_output` (default: `./doc_output` relative to project)
- `--order backend|frontend|both` (default: `both`)
- `--domain-start c --domain-end f` (only process backend domains in this letter range, inclusive)
- `--only-backend` / `--only-frontend`
- `--no-ai` (static extraction only, no AI inference)
- `--excel` (also generate color-coded Excel workbooks)
- `--force` (ignore all existing output files, regenerate everything from scratch)

**Resume behaviour** (default, no flags needed): If a previous run (CLI or chat) already wrote docs to the output folder, re-running will automatically skip any domain/page that is already fully documented and continue from where it left off.

---

## Your Full Execution Pipeline

Execute these steps **in order**. Use your file-reading and file-creation tools at every step.

---

### STEP 1 — Detect Project Type

Read the root of `--path`. Check for these signals:

**Backend signals** (Laravel): `artisan`, `composer.json`, `routes/api.php`, `routes/web.php`, `app/Http/Controllers`, `config/app.php`, `database/migrations`

**Frontend signals**: `package.json`, `vite.config.js`, `vite.config.ts`, `next.config.js`, `nuxt.config.js`, `src/main.js`, `src/main.ts`, `src/App.vue`, `resources/js`

**Monorepo detection**: If neither signal is found at root, check for subfolders named `backend`, `api`, `server`, `laravel` (minimun 2 backend signals required → backend root) and `frontend`, `client`, `web`, `vue`, `react`, `spa` (minimum 1 frontend signal → frontend root).

Score each type. If backend signals ≥ 3 → has backend. If frontend signals ≥ 2 → has frontend.

Print a detection summary before proceeding.

---

### STEP 2 — Backend Analysis (skip if no backend detected)

#### 2a. Read all route files

**Pre-processing before parsing:**

1. Find all `.php` files under the `routes/` folder.
2. For each route file, also follow `require`/`include` statements (e.g. `require __DIR__.'/v1.php'`) and read those sub-files recursively.
3. Strip PHP comments (`/* … */`, `// …`, `#`) before parsing.
4. Collapse multi-line Route statements onto one line:
   - Array handler split across lines → join into one line (balance `[…]` depth)
   - Fluent chain (`->middleware()->group()`) split across lines → join lines that start with `->`

**Group scope tracking — use a brace-depth stack, NOT simple `});` matching:**

Push new prefix/middleware/namespace/controller onto a stack when a group opener is seen; pop when brace depth returns to the level at which the group was opened. This correctly handles closures inside route handlers that would otherwise spuriously close the group.

A line is a **group opener** if it (a) contains `->group(` or `Route::group(` AND (b) ends with `{` (opening the closure body) AND (c) contains `function`.

Parse every route declaration:

- `Route::get|post|put|patch|delete|options|any('/path', [Ctrl::class, 'method'])`
- `Route::get|post|...('/path', 'Ctrl@method')`
- **`Route::match(['get','post'], '/path', handler)`** → emit one route per listed method
- **`Route::resource('/path', Ctrl::class)`** → expands to 5 RESTful routes:
  - `GET /path` (index), `POST /path` (store), `GET /path/{id}` (show), `PUT /path/{id}` (update), `DELETE /path/{id}` (destroy)
- **`Route::apiResource('/path', Ctrl::class)`** → expands to 6 routes (same as resource but adds `PATCH /path/{id}` for update, no `create`/`edit` HTML routes)
- **Invokable controller** — `Route::get('/path', FooController::class)` (bare `::class`, no method string) → `action = __invoke`
- **`Route::group(['prefix'=>'v1', 'middleware'=>[...]], function() { ... })`** → array-style group
- **`Route::prefix('admin')->middleware([...])->group(function() { ... })`** → fluent chain-style group
- **`Route::namespace('Api\\V1')->group(...)`** → namespace group; prepend to controller class names inside
- **Laravel 9+ `Route::controller(FooController::class)->group(function() { Route::get('/path', 'index'); })`** → bare string method names resolved against the group's controller

**Middleware extraction (in order of priority):**

1. `'middleware' => [...]` in group array
2. `'middleware' => 'single'` in group array
3. `->middleware([...])` or `->middleware('single')` chained on the Route or group
4. `->middleware('...')` chained on individual route lines

**Namespace normalization:** Any `/` characters in a namespace or controller class string are converted to `\` before use (e.g. `Api/V1\FooController` → `App\Http\Controllers\Api\V1\FooController`).

For each route, record:

```json
{
  "method": "GET",
  "path": "/api/v1/agents",
  "full_path": "/api/v1/agents",
  "controller": "App\\Http\\Controllers\\Api\\V1\\AgentController",
  "action": "index",
  "middleware": ["auth:sanctum"],
  "params": ["id"]
}
```

#### 2b. Trace each controller method

For each unique `(controller, action)` pair:

1. Search for the controller file under `app/Http/Controllers/` (recursively). Match by class name.
   - **Strategy 1**: Convert namespace to path (`App\Http\Controllers\Api\V1\AgentController` → `app/Http/Controllers/Api/V1/AgentController.php`)
   - **Strategy 2 fallback**: Walk all `.php` files, score by how many namespace segments appear in the path; use highest-scoring match.
2. Read the file. Extract the method body for the action.
   - **Case-insensitive match**: PHP method names are case-insensitive — match `renderAgentsCommissions` even if route file used lowercase.
   - **Allman brace style**: Opening `{` may be on the next line after the signature — scan forward up to 500 chars past `)` to find `{`.
   - **Multi-line signature**: Walk paren-depth to find the matching `)` before looking for `{`.
   - **Abstract/interface methods**: If `;` appears before `{` in the lookahead window, skip (no body).
   - **Fallback**: If the best-scoring file doesn't contain the method, try the next-best-scoring candidate files.
3. From the method body, extract:

| What to extract        | How                                                                                                                                                                 |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Validation rules**   | `$request->validate([...])` or `FormRequest` class name                                                                                                             |
| **DB queries**         | `DB::table()`, `DB::select()`, `Model::where()`, `Model::find()`, `->get()`, `->first()`, `->paginate()`, `->create()`, `->update()`, `->delete()`, raw SQL strings |
| **Response fields**    | `response()->json([...])` contents                                                                                                                                  |
| **Service/repo calls** | `$this->serviceName->methodName()`                                                                                                                                  |
| **Jobs dispatched**    | `dispatch(new JobName(...))`, `JobName::dispatch(...)`                                                                                                              |
| **Events fired**       | `event(new EventName(...))`                                                                                                                                         |
| **Abort calls**        | `abort(403, ...)`, `abort(404)`                                                                                                                                     |

---

### STEP 3 — Domain Grouping

Group routes into **domains** (one folder per domain in output).

Algorithm to detect domain name from a route path (mirrors `detect_domain()` in `backend/generate_docs.py`):

1. Strip leading `/` and version/api prefixes: `api/`, `v1/`, `v2/`, `v3/`, `api.access/`, `access/`
2. Iterate the first **up to 3** path segments (skip `{param}` and `:param` segments)
3. For each segment, split on `-` and `_`, filter words:
   - **Verb/stopword list to REMOVE**: `get set add create update delete remove upload download send view edit list manage check fetch generate process approve reject import export restore change reset save validate verify mark toggle submit bulk total show find search filter load build activate deactivate enable disable calculate store define retrieve preview sync onboard migrate switch resend reprocess refund new latest recent active all and or any the of by old own my true false yes no`
   - **Entity/resource words (prefer these)**: `agent group policy member plan payment invoice contract commission enrollment dependent beneficiary carrier template email bank billing claim document report license medical platform feature note term rider address question text tier waive fee acm prudential website homepage downline upline referral webhook notification queue lead script analytic statistic progress rate price renewal receipt tax eft ach census credit routing client user admin resource activity log audit setting option type status level info detail summary history request approval sub`
4. Stop at the first segment that yields a noun candidate of **≥ 3 characters**. Prefer entity words over generic nouns.
5. If ALL segments yield only verbs/stopwords, use the last word of the first segment as fallback.
6. Normalize plurals to singular:
   - ends with `ies` (len > 4) → replace with `y` (policies→policy)
   - ends with `ses` (len > 4) → remove `s` (statuses→status)
   - ends with `s` (len > 4, not `ss`) → remove `s` (agents→agent, groups→group)
7. Result is lowercase. Use as the domain folder name.

**Example mappings**:

- `GET /api/v1/agents` → domain `agent`
- `GET /all` → skipped (`all` is a stopword), try next segment or fall back → `general` if no segments
- `POST /api/v1/addAgentCommissionConfig` → `agentcommissionconfig` (verb `add` stripped, first noun candidate ≥ 3 chars)
- `GET /api/v1/commission/getPolicyList` → `commission`
- `GET /api/v1/add-agent-license` → `agent` (verb `add` stripped, `agent` is entity word)

Apply `--domain-start` / `--domain-end` filter: only process domains whose name sorts alphabetically within the range.

---

### STEP 4 — Generate Backend Documentation

#### 4-pre. Domain filter (--domain-start / --domain-end)

Before processing any domain, apply the letter-range filter:

- If `--domain-start` is given, **skip** any domain whose name sorts alphabetically **before** that letter (case-insensitive).
- If `--domain-end` is given, **skip** any domain whose name sorts alphabetically **after** that letter.
- Example: `--domain-start c --domain-end f` → process only domains starting with c, d, e, or f.
- Print a one-line summary: `[domain-filter] processing domains c–f (skipping N others)`

#### 4-pre. Resume logic (skip already-documented routes)

Before generating `business.md`, `responses.md`, or `legacy_query.sql` for a domain, check whether the file already exists on disk:

- **`business.md` exists** → scan its headings (`## endpoint_name` lines). Any route whose last-path-segment heading is already present is **already done** — skip it. Only append the missing routes.
- **`responses.md` exists** → same: scan `## METHOD /full/path` headings. Skip routes already present.
- **`legacy_query.sql` exists** → scan `-- Endpoint  : METHOD /full/path` comment lines. Skip routes already present.
- **`api.md`** — always regenerate (it's fast, no AI, and reflects the full route list).
- If ALL routes in the domain are already documented, print `skip {domain} ({N} routes — all done)` and move on.
- If `--force` is passed, ignore all existing files and regenerate everything from scratch.

This means: if you ran the CLI (or a previous chat session) and it completed some domains, re-running `/generate-docs` in chat will continue from where it left off.

For each domain, create a folder at:

```
{output}/{project_name}/docs/backend/{domain_name}/
```

Generate these **4 files** per domain:

---

#### 4a. `api.md` — Route Reference Table

```markdown
# API Reference

Total: **{count}**

---

## {last_path_segment}

- **Endpoint** : `{METHOD} {full_path}`
- **Controller** : `{Controller}@{action}`
- **Middleware** : {middleware_list or omit line}
- **Params** : `{param1}`, `{param2}` (or omit line)
- **Models** : `{Model1}`, `{Model2}` (or omit line)

---
```

One block per endpoint. `{count}` is the total endpoints in this domain.

---

#### 4b. `business.md` — Business Logic Documentation

Header line (once at top of file):

```markdown
# Business Logic Documentation
```

For each route in the domain, one section using this exact structure:

```markdown
## {last_path_segment}

| Field             | Value                   |
| ----------------- | ----------------------- |
| **Endpoint**      | `{METHOD} {full_path}`  |
| **Controller**    | `{Controller}@{action}` |
| **Auth Required** | Yes / No                |
| **HTTP Method**   | {METHOD}                |

### Purpose

[2-3 sentences: what this does, who calls it, why it exists. Write UNKNOWN if unclear.]

### Business Logic

- [Step-by-step bullet points of what the method does]
- [Include conditional logic, auth checks, external API calls]
- [Use UNKNOWN if something cannot be determined from static analysis]

### Input Parameters

| Parameter    | Type   | Required | Description |
| ------------ | ------ | -------- | ----------- |
| `param_name` | string | Yes      | Description |

(or write: No parameters.)

### Database Operations

1. READ/WRITE table_name — what and why
   (or write: None)

### Side Effects

- **Emails**: [description or None]
- **Jobs/Queues**: [description or None]
- **Events**: [description or None]
- **External APIs**: [description or None]
- **Files**: [description or None]

---
```

Do NOT invent logic. Write **`UNKNOWN`** for anything not determinable from static analysis.

---

#### 4c. `responses.md` — Response Schemas

````markdown
# API Response Schemas

Response bodies for each endpoint.

---

## {METHOD} {full_path}

**Endpoint**: `{Controller}@{action}`

**Path Parameters**:

- `{param}` - (from URL path)
  (or omit if no params)

**Response Type**: `{json|array_of_objects|nested_json|paginated_array}`

**Response Fields**:

```json
{
  "field1": "type — description",
  "field2": [
    {
      "nested_field": "type"
    }
  ]
}
```
````

**Example Response**:

```json
{ "example": "with actual values" }
```

**Description**: [Plain-English description of what the response contains.]

---

````

If response fields cannot be determined from static analysis, write:
`**Response**: Unable to determine from available code.`

---

#### 4d. `legacy_query.sql` — SQL Audit

For each DB query found, output one block:

```sql
-- Endpoint  : {METHOD} {full_path}
-- Controller: {Controller}@{action}

### {last_path_segment} -- Query N: {what it does}

| Field | Value |
|-------|-------|
| **Type** | eloquent / raw_sql / db_facade |
| **Operation** | SELECT / INSERT / UPDATE / DELETE / UPSERT |
| **Tables** | table_name |
| **Columns Read** | col1, col2 (or *) |
| **Columns Written** | col1, col2 (or None) |
| **Conditions** | WHERE clause summary (or None) |
| **Joins** | JOIN details (or None) |
| **Order / Group** | ORDER BY / GROUP BY (or None) |
| **Aggregates** | COUNT, SUM, etc. (or None) |
| **Transaction** | Yes / No |
| **Soft Deletes** | Yes / No |

```sql
-- reconstructed SQL with ? for bound params
SELECT * FROM table_name WHERE id = ?;
````

**Optimization Notes:**

- [one issue per bullet, or: No issues identified]

---

````

If zero DB queries: output exactly one comment: `-- No database queries`

---

#### 4e. `index.md` — Backend Master Index

Create at `{output}/{project_name}/docs/backend/index.md`:

```markdown
# Backend API Index

Total routes: {count} | Domains: {count}

## Domains

| Domain | Routes | Files |
|--------|--------|-------|
| agent | 5 | [api.md](./agent/api.md) · [business.md](./agent/business.md) |
````

---

### STEP 5 — Frontend Analysis (skip if no frontend detected)

#### 5a. Find the router configuration

Search for files (priority order):

1. `src/router/index.js` or `src/router/index.ts`
2. `src/router.js` or `src/router.ts`
3. `resources/js/router/index.js`
4. Any file with `createRouter` or `vue-router` in it

Also check: `app.jsx`, `app.tsx`, `routes.jsx`, `routes.tsx` for React Router `<Route path=...>` patterns.

Also check `.php` files for `Inertia::render('ComponentName', [...])`.

For each route, record:

```json
{
  "path": "/agents/:id",
  "component": "AgentDetail",
  "component_file": "src/pages/AgentDetail.vue",
  "example_url": "http://localhost:8000/agents/1",
  "layout": "AppLayout",
  "children": ["AgentProfileCard", "CommissionTable"],
  "template_components": ["[vuetify] v-dialog, v-table, ..."],
  "composables": ["useAgentDetail", "useCommissions"],
  "api_calls": [],
  "state_management": ["pinia:AgentStore"],
  "unknowns": [],
  "validation_rules_static": ["email: required|email"],
  "conditional_logic_static": ["v-if: isAdmin", "v-show: hasPermission"]
}
```

**Example URL building** — replace route params with these fixed values:
`id`/`pid`/`gid`/`aid` → `1`, `month`/`invDate` → `2025-01`, `date`/`ptdate` → `2025-01-01`, `type`/`filter` → `all`, `status` → `active`, `val`/`cnt` → `1`, anything else → `{paramName}` (keep as-is)

If no router file found: treat all `.vue`, `.jsx`, `.tsx` files under `src/pages/`, `src/views/`, `resources/js/Pages/` as pages with `path: UNKNOWN`.

#### 5b. Trace API calls per component

For each component file, read it and extract:

- `axios.get('/api/...')`, `axios.post(...)`, `axios.put(...)`, `axios.delete(...)`
- `http.get(...)`, `api.get(...)`, `$http.get(...)`, `$axios.get(...)`
- `fetch('/api/...')`
- `form.post(...)`, `form.put(...)`, `form.delete(...)` (Inertia forms)
- `useQuery(...)`, `useSWR(...)`, `useFetch(...)`, `useMutation(...)` hooks

For composable calls (`use{Something}()`): skip framework composables (`useRouter`, `useRoute`, `useI18n`, `useState`, `useEffect`, etc.). For app-specific composables, find the composable file under `src/composables/` or `src/hooks/`, read it, extract its API calls, and tag them with `"composable": "useComposableName"`.

Deduplicate API calls by `(endpoint, method, called_from)`.

Record each call:

```json
{
  "endpoint": "/api/v1/agents",
  "method": "GET",
  "called_from": "AgentList.vue",
  "composable": "useAgentList",
  "via": "axios"
}
```

If `ai_placeholder_apis.json` exists at the project root: for any call with `endpoint: "UNKNOWN"`, check if any key from the file appears in the component's source code. If so, resolve the endpoint to the first entry in the matching `endpoints` array.

#### 5c. Extract static fields

For each component, also extract:

**Validation rules** (`validation_rules_static`): VeeValidate `rules="required|email"`, Vuelidate `validations: {}`, Yup/Zod chains, manual `rules: { field: [...] }` objects.

**Conditional logic** (`conditional_logic_static`): `v-if`, `v-else-if`, `v-show` directives; ternaries in `{{ }}` blocks; `:disabled`/`:readonly` bindings.

**State management** (`state_management`): Pinia (`useXxxStore()` → `"pinia:XxxStore"`), Vuex (`mapState`, `$store`, `store.dispatch` → `"vuex"`), Redux (`useSelector`, `useDispatch` → `"redux"`), React Query (`useQuery`, `useSWR` → `"react-query:hookName"`).

---

### STEP 6 — Generate Frontend Documentation

#### 6-pre. Resume logic (skip already-documented pages)

Before generating any per-page `.md` file, check whether it already exists on disk:

- If `{output}/{project_name}/docs/frontend/{group}/{safe_filename}.md` **already exists**, skip it — do not overwrite.
- If `--force` is passed, regenerate all pages from scratch regardless.
- Print `skip {component} — already documented` for each skipped page.
- The `README.md` group index and `frontend/index.md` are always regenerated (they are fast and reflect the full page list).

For each page group (first non-param path segment, e.g., `/agents/...` → group `agents`; no route or missing file → group `undocumented`):

Create folder: `{output}/{project_name}/docs/frontend/{group}/`

#### 6a. `README.md` — Group Overview

```markdown
# /{group} Pages

Route prefix: **`/{group}`**

## Summary

| Route                | Component   | Layout    | Children | APIs | State | Example URL                    |
| -------------------- | ----------- | --------- | -------- | ---- | ----- | ------------------------------ |
| [/agents](agents.md) | `AgentList` | AppLayout | 2        | 3    | pinia | `http://localhost:8000/agents` |
```

One row per page in the group. Children count = max(children list, template_components list).

#### 6b. Per-page `{safe_filename}.md`

Use this exact structure (mirrors `_skeleton_page()` / `pages_md_prompt()` output):

```markdown
# `{path}`

| Field           | Value                                                  |
| --------------- | ------------------------------------------------------ |
| **Component**   | `{component}`                                          |
| **Source file** | `{component_file}` (or _not found on disk_ if missing) |
| **Layout**      | {layout}                                               |
| **Example URL** | `{example_url}` (or _Route not mapped_ if no URL)      |

> To verify this page open: **[{example_url}]({example_url})**
> (or: > Route has no URL mapping — component may be rendered as a modal or child.)

## Child Components

- `ComponentName` _(imported)_
  (or if from template scan: - `ComponentName`)
  (or: _None — no imported or template sub-components detected_)
  (or: _Could not scan — source file not found on disk_)

## Composables Used

- `useComposableName()`
  (or: _None — no composable/hook calls detected_)

## Backend API Dependencies

| Method | Endpoint         | Source               | Transport |
| ------ | ---------------- | -------------------- | --------- |
| `GET`  | `/api/v1/agents` | via `useAgentList()` | axios     |

(or: _None — no axios/fetch/form calls detected_)

## Request Payload / Query Parameters

_For each API call, list all query parameters or request body fields with name, type, required/optional, and description._
(When AI is enabled, fill these in from code analysis. Static-only: _Static extraction only — run with AI enabled to infer payload fields._)

## Conditional Logic

{extracted v-if / v-show / ternary rules, one bullet per rule}
(or: _Static extraction only — run with AI enabled to infer conditional rendering rules._)

## Validation Rules

{extracted VeeValidate/Vuelidate/Yup rules, one bullet per rule}
(or: _Static extraction only — run with AI enabled to infer validation rules._)

## State Management

**pinia**: `AgentStore`, `UserStore`
(or: _None — no Pinia/Vuex/Redux usage detected_)

## Warnings

- Component file not found: AgentDetail
  (or: _None_)

---
```

When AI is enabled (not `--no-ai`), after the `---` append the `EXCEL_DATA` block:

```
<!-- EXCEL_DATA
[
  {
    "screen_name": "Agent Detail",
    "route": "/agents/:id",
    "component_path": "src/pages/AgentDetail.vue",
    "api_endpoint": "/api/v1/agents/{id}",
    "http_method": "GET",
    "request_payload": "id (path, required) — agent identifier",
    "conditional_logic": "Commission tab hidden when agent has no active plan",
    "validation_rules": "None — read-only page"
  }
]
-->
```

**Filename convention**: `{path.strip('/').replace('/', '_').replace('-', '_') or 'index'}.md`. Strip URL param segments (`{id}` becomes `detail`, `_{param}` removed).

---

#### 6c. `frontend_detail.xlsx` — Structured Excel Output

After all page markdown files are written, produce `{output}/{project_name}/docs/frontend/frontend_detail.xlsx`.

Sheet name: **Frontend Detail**. Exactly these **9 columns**:

| # | Screen Name | Route / URL | Vue Component Path | API Endpoint | HTTP Method | Request Payload / Query Parameters | Conditional Logic | Validation Rules |

- One row per (page × API call). Pages with no API calls → one row with empty endpoint columns.
- Header: dark navy (#1F4E79), white bold text, size 11.
- Freeze pane at B2. Auto-filter on all headers.
- Wrap text on all cells.

---

#### 6d. `undocumented/missing_apis.md` — Cross-validation

After generating all docs, list API calls that appear in the frontend but cannot be matched to any backend route:

```markdown
# Undocumented API Endpoints

These API endpoints are called by frontend pages but do not have corresponding backend documentation.

**Total**: {N} unique endpoints

| Endpoint                | Methods | Pages Using It | Detail                                 |
| ----------------------- | ------- | -------------- | -------------------------------------- |
| `/api/v1/agents/export` | `GET`   | 1              | [detail](apis/api_v1_agents_export.md) |
```

Also create per-endpoint files at `undocumented/apis/{endpoint_safe}.md`.

---

#### 6e. Frontend `index.md`

```markdown
# Frontend Documentation

**Documented pages**: {N} | **API dependencies**: {N} | **Undocumented**: {N}

## Page Groups

| Group                        | Route Prefix | Pages | APIs |
| ---------------------------- | ------------ | ----- | ---- |
| [agents](./agents/README.md) | `/agents`    | 3     | 12   |
```

---

### STEP 7 — Dependency Graph

Create `{output}/{project_name}/docs/dependency_graph.json`:

```json
{
  "pages": {
    "/agents": {
      "component": "AgentList",
      "layout": "AppLayout",
      "api_calls": 3
    }
  },
  "apis": {
    "GET /api/v1/agents": { "controller": "AgentController", "action": "index" }
  },
  "links": [
    { "from": "/agents", "to": "GET /api/v1/agents", "via": "useAgentList" }
  ]
}
```

Also create `dependency_graph.mermaid` (truncated to 80 links maximum):

```
graph LR
  "/agents" --> "GET /api/v1/agents"
```

If cross-validation was run, also create `cross_validation.json`:

```json
{
  "missing_in_backend": [{ "endpoint": "/api/v1/export", "method": "GET" }],
  "unused_backend_apis": [{ "endpoint": "/api/v1/legacy", "method": "DELETE" }],
  "mismatches": [
    {
      "endpoint": "/api/v1/agents/{id}",
      "frontend_method": "POST",
      "backend_method": "PUT"
    }
  ]
}
```

---

## Output Structure

```
{output}/
  {project_name}/
    docs/
      backend/
        index.md
        {domain}/
          api.md
          business.md
          responses.md
          legacy_query.sql
      frontend/
        index.md
        frontend_detail.xlsx
        {group}/
          README.md
          {page_safe_name}.md
        undocumented/
          README.md
          missing_apis.md
          apis/
            {endpoint_safe}.md
      dependency_graph.json
      dependency_graph.mermaid
      cross_validation.json
    validation_report.json
    .docwriter/
      progress.json
      routes.json
      pages.json
```

---

## Strict Rules

1. **Do NOT invent** field names, table names, or logic not visible in the source code
2. Write **`UNKNOWN`** for anything that cannot be determined from static analysis
3. Every output file must match the exact format shown in the sections above
4. Process backend then frontend by default (unless `--order` overrides)
5. Tell the user your progress at each major step: detection, per-domain, per-group
6. If a controller file is not found, note it in the domain's `business.md` under Warnings
7. Domain stopwords (`all`, `and`, `get`, `add`, etc.) are stripped — never create a domain folder named after a stopword
8. Static extraction only (no inference) when `--no-ai` is set — use the exact fallback text shown in the page format above
9. After all files are written, print a **summary table**:

```
┌─────────────────────────────────────────────┐
│  Documentation Generation Complete           │
├──────────────────┬──────────────────────────┤
│ Backend domains  │ 24                        │
│ Routes covered   │ 187                       │
│ Frontend groups  │ 12                        │
│ Pages documented │ 48                        │
│ Missing APIs     │ 3                         │
│ Excel rows       │ 112                       │
│ Output location  │ ./doc_output/myproject/   │
│ Excel location   │ docs/frontend/frontend_detail.xlsx │
└──────────────────┴──────────────────────────┘
```

---

## Example Usage in Chat

```
/generate-docs --path "D:\CloudTech_main\commission_billing"
```

```
/generate-docs --path "D:\CloudTech_main\nuerabenefits" --order backend --domain-start a --domain-end m
```

```
/generate-docs --path "D:\CloudTech_main\myapp" --only-frontend --output D:\docs\output
```

```
/generate-docs --path "D:\CloudTech_main\nuerabenefits" --no-ai --order both
```
