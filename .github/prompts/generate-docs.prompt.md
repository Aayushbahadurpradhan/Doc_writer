---
name: generate-docs
description: "Use when: generating API documentation, documenting Laravel+Vue/React projects, creating backend/frontend docs from source code, generate-docs, doc writer, doc generation, documenting APIs, create documentation"
---

# Documentation Generator — Laravel + Vue/React

You are an automated documentation pipeline. When invoked, you replicate the full `python main.py generate-docs` pipeline entirely through chat tools (reading files, creating output files).

---

## How to Invoke

In chat, type:

```
/generate-docs --path "D:\path\to\project"
```

Optional flags:

- `--output ./doc_output` (default: `./doc_output` relative to project)
- `--order backend|frontend|both` (default: `both`)
- `--domain-start a --domain-end z` (letter range filter for backend domains)
- `--only-backend` / `--only-frontend`

---

## Your Full Execution Pipeline

Execute these steps **in order**. Use your file-reading and file-creation tools at every step.

---

### STEP 1 — Detect Project Type

Read the root of `--path`. Check for these signals:

**Backend signals** (Laravel): `artisan`, `composer.json`, `routes/api.php`, `routes/web.php`, `app/Http/Controllers`, `config/app.php`, `database/migrations`

**Frontend signals**: `package.json`, `vite.config.js`, `vite.config.ts`, `next.config.js`, `nuxt.config.js`, `src/main.js`, `src/main.ts`, `src/App.vue`, `resources/js`

**Monorepo detection**: If neither signal is found at root, check for subfolders named `backend`, `api`, `server`, `laravel` (→ backend root) and `frontend`, `client`, `web`, `vue`, `react`, `spa` (→ frontend root).

Score each type. If backend signals ≥ 3 → has backend. If frontend signals ≥ 2 → has frontend.

Print a detection summary before proceeding.

---

### STEP 2 — Backend Analysis (skip if no backend detected)

#### 2a. Read all route files

Find all `.php` files under the `routes/` folder. Read each one fully.

Parse every route declaration:

- `Route::get|post|put|patch|delete|options('/path', [ControllerClass::class, 'method'])`
- `Route::get|post|...('/path', 'ControllerClass@method')`
- `Route::resource('/path', ControllerClass::class)` → expands to: `GET /path` (index), `POST /path` (store), `GET /path/{id}` (show), `PUT /path/{id}` (update), `DELETE /path/{id}` (destroy)
- `Route::group(['prefix' => 'v1', 'middleware' => [...]], function() { ... })` → apply prefix and middleware to all inner routes
- `Route::prefix('admin')->group(function() { ... })` → chain-style prefix

For each route, record:

```json
{
  "method": "GET",
  "path": "/api/v1/agents",
  "full_path": "/api/v1/agents",
  "controller": "AgentController",
  "action": "index",
  "middleware": ["auth:sanctum"],
  "prefix": "api/v1"
}
```

#### 2b. Trace each controller method

For each unique `(controller, action)` pair:

1. Search for the controller file under `app/Http/Controllers/` (recursively). Match by class name.
2. Read the file. Extract the method body for the action.
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

Build a structured object per route:

```json
{
  "method": "POST",
  "path": "/api/v1/agents",
  "controller": "AgentController",
  "action": "store",
  "validation": {
    "name": "required|string|max:255",
    "email": "required|email"
  },
  "queries": [{ "type": "eloquent", "model": "Agent", "operation": "INSERT" }],
  "steps": [
    { "type": "validate", "detail": "name, email required" },
    { "type": "query", "detail": "Agent::create()" },
    { "type": "response", "detail": "returns created agent" }
  ],
  "response": {
    "type": "json",
    "fields": ["id", "name", "email", "created_at"]
  },
  "errors": [{ "type": "abort", "code": "403", "detail": "if not admin" }],
  "unknowns": []
}
```

---

### STEP 3 — Domain Grouping

Group routes into **domains** (one folder per domain in output).

Algorithm to detect domain name from a route path:

1. Strip leading `/` and version prefixes: `api/`, `v1/`, `v2/`, `api/v1/`, etc.
2. Take the **first meaningful path segment** (e.g., `/api/v1/agents/{id}/commissions` → `agents`)
3. Remove verb prefixes: `get`, `add`, `create`, `update`, `delete`, `remove`, `set`, `list`, `fetch`, `save`, `load`, `send`, `check`, `run`, `submit`, `approve`, `reject`, `assign`, `build`, `generate`, `process`
4. Normalize plurals to singular: `agents→agent`, `policies→policy`, `commissions→commission`, `entries→entry`, `categories→category` (standard English rules)
5. Use the result as the domain name (lowercase, no hyphens — replace with underscores)

Example mappings:

- `GET /api/v1/agents` → domain `agent`
- `POST /api/v1/addAgentCommissionConfig` → domain `agentcommissionconfig`
- `GET /api/v1/commission/getPolicyList` → domain `commission`

Apply `--domain-start` / `--domain-end` filter: only process domains whose first letter falls in the range.

---

### STEP 4 — Generate Backend Documentation

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

## {action}

- **Endpoint** : `{METHOD} /{path}`
- **Controller** : `{Controller}@{action}`

---
```

One block per endpoint in the domain. `{count}` is the total number of endpoints in this domain.

````

---

#### 4b. `business.md` — Business Logic Documentation

For each route in the domain, generate a full business logic section using this exact structure:

```markdown
## {action}

| Field | Value |
|-------|-------|
| **Endpoint** | `{METHOD} /{path}` |
| **Controller** | `{Controller}@{action}` |
| **Auth Required** | Yes / No |
| **HTTP Method** | {METHOD} |

### Purpose
[What business problem this solves — be specific. UNKNOWN if unclear.]

### Business Logic
- [Step-by-step description of what the method does, bullet points]
- [Include conditional logic, external API calls, assumptions]

### Input Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `param_name` | string | Yes | Description of parameter |

### Database Operations
[Describe each DB operation, or write "None" if no DB interaction]

### Side Effects
- **Emails**: [description or None]
- **Jobs/Queues**: [description or None]
- **Events**: [description or None]
- **External APIs**: [Yes — URL and purpose, or None]
- **Files**: [description or None]
```

One section per endpoint in the domain. Use `UNKNOWN` for anything not determinable from static analysis. Do NOT invent logic.

---

#### 4c. `responses.md` — Response Schemas

```markdown
# API Response Schemas

Response bodies for each endpoint.

---

## {METHOD} /{path}

**Endpoint**: `{Controller}@{action}`

**Response Type**: `{type}` ({description of return type})

**Response Fields**:
```json
{
  "field": "type"
}
```

**Example Response**:
```json
{
  "field": "example value"
}
```

**Description**: [Plain-English description of what the response contains and any caveats about its structure. If fields cannot be determined from static analysis, state that explicitly.]

---
```

One block per endpoint. If response fields are unknown, write the description explaining it cannot be determined from static analysis.

---

#### 4d. `legacy_query.sql` — SQL Audit

```sql
-- ------------------------------------------------------------
-- Endpoint  : {METHOD} /{path}
-- Controller: {Controller}
-- ------------------------------------------------------------

### {action} -- Query N: {index}

| Field | Value |
|-------|-------|
| **Type** | raw_sql / eloquent / query_builder |
| **Operation** | SELECT / INSERT / UPDATE / DELETE |
| **Tables** | table_name |
| **Columns Read** | col1, col2 (or *) |
| **Columns Written** | col1, col2 (or N/A) |
| **Conditions** | WHERE clause summary (or None) |
| **Joins** | JOIN details (or None) |
| **Order / Group** | ORDER BY / GROUP BY (or None) |
| **Aggregates** | COUNT, SUM, etc. (or None) |
| **Transaction** | Yes / No |
| **Soft Deletes** | Yes / No |

```sql
-- reconstructed SQL with ? for bound params
```
```

One block per query per endpoint. Index starts at 0. If the query cannot be reconstructed, write `-- UNKNOWN: [reason]` in the SQL block.

---

#### 4e. `index.md` — Backend Master Index

Create at `{output}/{project_name}/docs/backend/index.md`:

```markdown
# Backend API Documentation — {Project Name}

Generated: {date}
Total routes: {count}
Domains: {count}

## Domains

| Domain     | Routes | Path                                     |
| ---------- | ------ | ---------------------------------------- |
| agent      | 5      | [agent/api.md](./agent/api.md)           |
| commission | 8      | [commission/api.md](./commission/api.md) |

...

## All Routes Summary

| Method | Path | Domain | Controller |
| ------ | ---- | ------ | ---------- |

...
```

---

### STEP 5 — Frontend Analysis (skip if no frontend detected)

#### 5a. Find the router configuration

Search for these files (in priority order):

1. `src/router/index.js` or `src/router/index.ts`
2. `src/router.js` or `src/router.ts`
3. `resources/js/router/index.js`
4. `resources/js/router.js`

Read the file. Extract all route objects matching:

**Vue Router pattern**:

```js
{ path: '/agents', component: AgentList }
{ path: '/agents/:id', component: () => import('./pages/AgentDetail.vue') }
```

**React Router pattern**:

```jsx
<Route path="/agents" element={<AgentList />} />
```

**Inertia (from PHP files)**: `Inertia::render('Agents/Index', [...])` in Laravel controllers.

For each route record:

```json
{
  "path": "/agents/:id",
  "component": "AgentDetail",
  "component_file": "src/pages/AgentDetail.vue",
  "layout": "AppLayout",
  "children": [],
  "composables": [],
  "api_calls": [],
  "state_management": []
}
```

If no router file found: treat all `.vue`, `.jsx`, `.tsx` files under `src/pages/`, `src/views/`, `resources/js/Pages/` as pages.

#### 5b. Trace API calls per component

For each page component file (find it by matching component name to file), read the file and extract:

**API call patterns to detect**:

- `axios.get('/api/...')`, `axios.post(...)`, `axios.put(...)`, `axios.delete(...)`
- `http.get(...)`, `api.get(...)`, `this.$http.get(...)`
- `fetch('/api/...')`
- `useQuery(...)`, composable calls like `useAgentList()`

For composable calls: find the composable file (search under `src/composables/`, `src/hooks/`), read it, extract its API calls. Record the composable as the source.

Record each API call:

```json
{
  "endpoint": "/api/v1/agents",
  "method": "GET",
  "called_from": "AgentList.vue",
  "composable": "useAgentList",
  "via": "axios"
}
```

#### 5c. Detect state management

Look for:

- `useXxxStore()` → **Pinia**
- `mapState`, `this.$store`, `store.dispatch` → **Vuex**
- `useSelector`, `useDispatch` → **Redux**
- `useQuery`, `useMutation` → **React Query**

#### 5d. Detect layout

Look for:

- `definePageMeta({ layout: 'admin' })` → Nuxt 3
- `<AppLayout>`, `<AdminLayout>`, `<DefaultLayout>` wrapper tags
- `layout:` property in options API
- Default if none found: `default`

---

### STEP 6 — Generate Frontend Documentation

For each page group (first path segment, e.g., `/agents/...` → group `agents`):

Create folder: `{output}/{project_name}/docs/frontend/{group}/`

#### 6a. `README.md` — Group Overview

```markdown
# Frontend — {Group} Pages

| Route       | Component   | Layout    | Children | API Calls | State |
| ----------- | ----------- | --------- | -------- | --------- | ----- |
| /agents     | AgentList   | AppLayout | 0        | 3         | Pinia |
| /agents/:id | AgentDetail | AppLayout | 2        | 5         | Pinia |
```

#### 6b. Per-page `{component}.md`

```markdown
# Page: `/agents/:id`

| Field           | Value                       |
| --------------- | --------------------------- |
| **Component**   | `AgentDetail`               |
| **Source file** | `src/pages/AgentDetail.vue` |
| **Layout**      | AppLayout                   |
| **Example URL** | `/agents/1`                 |

> To verify this page open: **[/agents/1](/agents/1)**

## Child Components

- AgentProfileCard
- CommissionTable
- DocumentUploader

## Composables Used

- useAgentDetail()
- useCommissions()

## Backend API Dependencies

- Endpoint: `GET /api/v1/agents/{id}`
  - Method: GET
  - Source: via `useAgentDetail()`
  - Transport: axios
- Endpoint: `GET /api/v1/agents/{id}/commissions`
  - Method: GET
  - Source: via `useCommissions()`
  - Transport: axios

## Request Payload / Query Parameters

List all query parameters or request body fields for each API call above.
Include: field name, type, required/optional, and description.

## Conditional Logic

Describe conditional UI rendering rules, field visibility conditions, and business logic
found in the component (e.g. "SSN field only shown when plan requires it").

## Validation Rules

List every form/input validation rule (field, rule, error message if known).
Example: `email` — required, valid email format, duplicate check on blur.

## State Management

Pinia: useAgentStore

## Warnings

- UNKNOWN: layout not declared, inferred from wrapper tag
```

Replace `:id` / `{id}` with `1`, `:month` with `2024-01`, `:year` with `2024` in example URLs.

At the END of each page markdown, append an `EXCEL_DATA` HTML comment block (one JSON object per API call):

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
    "validation_rules": "None — read-only page",
    "open_questions": "Does the endpoint return soft-deleted agents?"
  }
]
-->
```

#### 6c. `frontend_detail.xlsx` — Structured Excel Output

After all page markdown files are written, produce `{output}/{project_name}/docs/frontend/frontend_detail.xlsx`.

The sheet is named **Frontend Detail** and has exactly these 13 columns (matching the reference sheet format):

| # | Screen Name | Route / URL | Vue Component Path | API Endpoint | HTTP Method | Request Payload / Query Parameters | Conditional Logic | Validation Rules | Open Questions / Notes | Answer / Decision | Answered By | Date Answered |

- One row per (page × API call). Pages with no API calls get one row with empty endpoint columns.
- Populate **Answer / Decision**, **Answered By**, **Date Answered** as empty (to be filled by BA/team).
- Header row: dark navy background (#1F4E79), white bold text.
- Freeze pane at B2. Auto-filter on all headers.

#### 6c. `missing_apis.md` — Cross-validation

After generating all docs, compare frontend API calls against backend routes. List any frontend calls that have NO matching backend route:

```markdown
# Missing Backend APIs

These endpoints are called from the frontend but have no matching backend route documented.

| Frontend Call         | Method | Called From   |
| --------------------- | ------ | ------------- |
| /api/v1/agents/export | GET    | AgentList.vue |
```

#### 6d. Frontend `index.md`

```markdown
# Frontend Documentation — {Project Name}

| Group      | Pages | Prefix      |
| ---------- | ----- | ----------- |
| agents     | 3     | /agents     |
| commission | 5     | /commission |

...
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
        frontend_detail.xlsx          ← structured Excel (one row per page × API call)
        {group}/
          README.md
          {ComponentName}.md
          missing_apis.md
      dependency_graph.json
```

---

## Strict Rules

1. **Do NOT invent** field names, table names, or logic not present in the source code
2. Write **`UNKNOWN`** for anything that cannot be determined from static analysis
3. Every output file must match the exact format shown above
4. Process backend then frontend by default (unless `--order` overrides)
5. Tell the user your progress at each major step: detection, per-domain analysis, per-group analysis
6. If a controller file is not found, note it in the domain's `business.md` under Unknowns
7. After all files are written, print a **summary table**:

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
````
