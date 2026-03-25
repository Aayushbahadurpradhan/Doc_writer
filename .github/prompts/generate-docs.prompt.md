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
# API Reference — {Domain}

| Method | Path           | Controller      | Action | Middleware   |
| ------ | -------------- | --------------- | ------ | ------------ |
| GET    | /api/v1/agents | AgentController | index  | auth:sanctum |
| POST   | /api/v1/agents | AgentController | store  | auth:sanctum |

...
```

After the table, for each route add a detail block:

````markdown
## GET /api/v1/agents

**Controller**: `AgentController@index`
**Middleware**: `auth:sanctum`

### Request Parameters

| Param | Type    | Rules | Required |
| ----- | ------- | ----- | -------- |
| page  | integer | min:1 | No       |

### Response

```json
{
  "data": [...],
  "total": 100
}
```
````

````

---

#### 4b. `business.md` — Business Logic Documentation

For each route in the domain, generate a full business logic section using this exact structure:

```markdown
# Business Logic — {Domain}

---

## {METHOD} {path}

**Purpose**: [What business problem this solves — be specific. UNKNOWN if unclear.]

**Execution Flow**:
1. [First step — validation, auth check, etc.]
2. [DB query or service call]
3. [Response or side effect]

**Validation Rules**:
- `field_name`: rule1|rule2 — [plain English meaning]

**Database Operations**:
- `[SELECT/INSERT/UPDATE/DELETE]` on `{table/model}` — [what it reads/writes]

**Side Effects**:
- [Jobs dispatched, events fired, emails sent — or "None detected"]

**Response**:
- Success: `200` — [fields returned]
- Error: `403` — [condition that triggers it]

**Business Rules**:
- [Any conditional logic, permission checks, plan restrictions]

**Unknowns**:
- [Anything that could not be determined from static analysis]

---
````

Use the extracted route data. Do NOT invent logic. Write `UNKNOWN` for anything not in the code.

---

#### 4c. `responses.md` — Response Schemas

````markdown
# Response Schemas — {Domain}

## GET /api/v1/agents

**HTTP 200 — Success**

```json
{
  "data": [
    {
      "id": 1,
      "name": "John Smith",
      "email": "john@example.com"
    }
  ],
  "total": 100,
  "per_page": 15
}
```
````

**HTTP 422 — Validation Error**

```json
{
  "message": "The name field is required.",
  "errors": { "name": ["The name field is required."] }
}
```

---

````

For each response field detected in `response()->json([...])`, include it. If response fields are unknown, write:
```markdown
Response structure could not be determined from static analysis. Refer to controller source.
````

---

#### 4d. `legacy_query.sql` — SQL Audit

```sql
-- ============================================================
-- DOMAIN: {domain}
-- Generated by doc_writer
-- ============================================================

-- Endpoint: GET /api/v1/agents
-- Type: eloquent
-- Model: Agent
-- Operation: SELECT
SELECT * FROM agents WHERE active = 1 ORDER BY name ASC;

-- Endpoint: POST /api/v1/agents
-- Type: eloquent
-- Model: Agent
-- Operation: INSERT
INSERT INTO agents (name, email, created_at, updated_at) VALUES (?, ?, ?, ?);
```

For each query found in controller analysis:

- Classify as `eloquent`, `query_builder`, or `raw_sql`
- Reconstruct the SQL where possible (use `?` for bound params)
- If cannot reconstruct → write `-- UNKNOWN: [reason]`

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

## State Management

Pinia: useAgentStore

## Warnings

- UNKNOWN: layout not declared, inferred from wrapper tag
```

Replace `:id` / `{id}` with `1`, `:month` with `2024-01`, `:year` with `2024` in example URLs.

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
│ Output location  │ ./doc_output/myproject/   │
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
