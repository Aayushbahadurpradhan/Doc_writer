# Doc_writer - Updated Documentation Structure

## Overview

The doc_writer has been completely restructured to provide better organization, prevent data loss between backend and frontend runs, and track API responses and missing endpoints.

## New Output Structure

### Backend Documentation (Protected)

```
output/{project}/
  docs/backend/
    index.md                          ← Master index with all domains
    {domain}/
      api.md                          ← Static API reference (no AI)
      responses.md                    ← API Response schemas/examples ✨ NEW
      business.md                     ← AI-generated business logic
      legacy_query.sql                ← AI-generated SQL audit
```

**Key Changes:**

- ✨ **responses.md**: New file documenting API response structures

  ````
  ## GET /v1/login

  **Endpoint**: LoginController@store

  **Path Parameters**: none

  **Response Type**: `json`

  **Response Fields**:
  ```json
  {
    "userId": <value>,
    "token": <value>,
    "name": <value>,
  }
  ````

  ```

  ```

- Backend documentation is **PROTECTED**: Frontend runs will NOT overwrite backend docs

### Frontend Documentation (Reorganized)

```
output/{project}/
  docs/frontend/
    index.md                          ← Master index with page group summary
    {page-group}/
      README.md                       ← Group overview page
      index.md                        ← Documentation for / route
      dashboard.md                    ← Documentation for /dashboard
      detail.md                       ← Documentation for /{id} routes
    undocumented/
      missing_apis.md                 ← APIs called but not in backend ✨ NEW
```

**Key Changes:**

- **Organized by Page Groups**: Pages are now grouped by their route prefix
  - `/home`, `/home/dashboard`, `/home/profile` → `home/` folder
  - `/bill/list`, `/bill/{id}` → `bill/` folder
  - `/settings/profile`, `/settings/security` → `settings/` folder

- **Group READMEs**: Each group has a `README.md` with:
  - What pages are in this group
  - How many API calls per page
  - Quick navigation

- ✨ **Undocumented APIs**: New `undocumented/missing_apis.md` tracks:
  - APIs called by frontend pages
  - Which pages call each API
  - Helps identify gaps in backend documentation

- **No SQL Files**: Frontend docs don't generate SQL (unlike backend)

- **Data Source Tracking**: Each page documents:
  - Component hierarchy (parent/child components)
  - API dependencies with methods
  - State management solutions used
  - Local data from models/hooks

## Detailed Changes

### 1. Backend Responses Documentation ✨

**File**: `backend/generate_docs.py` - New `_write_responses_md()` function

Automatically extracts and documents API responses:

- Detected response types (JSON, etc.)
- Response field names extracted from code
- Examples of response structure
- Per-endpoint URL parameters

**When to use**:

- Always generated for every domain
- No AI needed (static extraction)
- Updated every run (fast)

### 2. Frontend Page Grouping ✨

**File**: `frontend/generate_docs.py` - Complete rewrite

Pages are grouped intelligently:

```python
def _extract_page_group(path: str) -> str:
    """
    /home -> "home"
    /home/dashboard -> "home"
    /bill/list -> "bill"
    /bill/{id}/detail -> "bill"
    /settings/profile -> "settings"
    """
```

Each group gets:

1. A `README.md` overview
2. Individual `.md` files per page
3. Links to other pages in the group

### 3. Undocumented APIs Tracking ✨

**File**: `frontend/generate_docs.py` - New `_write_missing_apis()` function

Automatically finds and documents:

- APIs called by frontend but not documented in backend
- Which pages call each API
- Helps with gap analysis

Example from `docs/frontend/undocumented/missing_apis.md`:

```markdown
# Undocumented APIs

## `GET /api/users/search`

Called by (2 pages):

- /home/search
- /admin/users
```

### 4. Protection from Overwrites ✨

Backend and frontend docs are **completely separate**:

- Backend: `docs/backend/` (protected)
- Frontend: `docs/frontend/` (independent)
- Dependency graph: `docs/dependency_graph.json`
- Cross-validation: `docs/cross_validation.json`

**What this means:**

- Running frontend doesn't break backend docs
- Running backend doesn't break frontend docs
- Each can be regenerated independently

## Per-Endpoint Documentation Updates

### Backend API (responses.md)

````markdown
## GET /v1/agent/{id}/commission

**Endpoint**: AchController@viewCommission

**Path Parameters**:

- `id` - (from URL path)

**Response Type**: `json`

**Response Fields**:

```json
{
  "commission_amount": <value>,
  "status": <value>,
  "effective_date": <value>,
  "notes": <value>,
}
```
````

````

### Frontend Page (individual markdown files)

Each page now shows:
```markdown
# /home/dashboard

**Component**: `Dashboard.vue`

## Layout
DefaultLayout

## Child Components
- `TopNav.vue`
- `Sidebar.vue`
- `DashboardCard.vue`

## API Dependencies
- `GET /api/dashboard/stats` (via hook)
- `GET /api/user/profile` (via composable)
- `POST /api/notifications/mark-read` (via axios)

## State Management
pinia

## Unknowns
None
````

## File Organization Guidelines

### Backend Rules (unchanged):

- ✅ Always generate `api.md` (static)
- ✅ Generate `responses.md` (static)
- ✅ Generate `business.md` with AI
- ✅ Generate `legacy_query.sql` with AI
- ✅ One domain folder per detected domain
- ❌ No HTML or other formats

### Frontend Rules (NEW):

- ✅ Auto-group by page prefix
- ✅ One markdown file per page
- ✅ Generate group `README.md` files
- ✅ Track missing APIs in `undocumented/`
- ✅ Generate master `index.md`
- ❌ No SQL files (unlike backend)
- ❌ Don't overwrite backend docs

## Running the Updated Generator

### Full regeneration:

```bash
python main.py generate-docs \
  --backend ./laravel-app \
  --frontend ./vue-app \
  --provider ollama
```

### Backend only (doesn't touch frontend):

```bash
python main.py generate-docs \
  --backend ./laravel-app \
  --provider ollama \
  --only-backend
```

### Frontend only (doesn't touch backend):

```bash
python main.py generate-docs \
  --frontend ./vue-app \
  --provider ollama \
  --only-frontend
```

### Force regenerate both (overwrites everything):

```bash
python main.py generate-docs \
  --backend ./laravel-app \
  --frontend ./vue-app \
  --provider ollama \
  --force
```

## Validation & Reporting

After running both pipelines, you'll get:

1. **dependency_graph.json** - Complete frontend↔backend mapping
2. **cross_validation.json** - Gaps report:
   - Missing APIs (called by frontend but not in backend)
   - Unused backend APIs (defined but not called by frontend)
   - Method mismatches (GET vs POST, etc.)

Example:

```json
{
  "missing_in_backend": [
    { "method": "GET", "endpoint": "/api/users/search", "called_by": 5 }
  ],
  "unused_backend_apis": [
    { "method": "DELETE", "endpoint": "/api/old-feature" }
  ],
  "mismatches": [
    {
      "endpoint": "/api/data",
      "frontend_method": "POST",
      "backend_method": "GET"
    }
  ]
}
```

## Memory/State Files

Generated automatically in `.docwriter/` folder:

- `routes.json` - Extracted backend routes (cached)
- `pages.json` - Extracted frontend pages (cached)
- `progress.json` - Backend generation progress
- `backend_mtimes.json` - Track PHP file changes
- `frontend_mtimes.json` - Track JS/Vue file changes

**Use `--force` to bypass cache and regenerate from scratch**

## Examples of New Output

### Backend Response Schema (NEW)

````markdown
# API Response Schemas

## GET /v1/agent/list

**Endpoint**: AgentController@index

**Response Type**: `json`

**Response Fields**:

```json
{
  "agent_id": <value>,
  "first_name": <value>,
  "last_name": <value>,
  "email": <value>,
  "status": <value>,
  "commission_rate": <value>,
}
```
````

## GET /v1/policy/{policyId}

**Endpoint**: PolicyController@show

**Path Parameters**:

- `policyId` - (from URL path)

**Response Type**: `json`

**Response Fields**:

```json
{
  "policy_id": <value>,
  "holder_id": <value>,
  "carrier": <value>,
  "effective_date": <value>,
  "premium": <value>,
}
```

````

### Frontend Group Overview (NEW)
```markdown
# AGENT Pages

Page group: **/agent**

## Pages (5)

- [/agent](.md) — `AgentList.vue` (3 API calls)
- [/agent/create](create.md) — `AgentForm.vue` (1 API call)
- [/agent/{id}](detail.md) — `AgentDetail.vue` (4 API calls)
- [/agent/{id}/edit](edit.md) — `AgentForm.vue` (2 API calls)
- [/agent/{id}/commission](commission.md) — `CommissionTracker.vue` (2 API calls)
````

### Frontend Missing APIs (NEW)

```markdown
# Undocumented APIs

Frontend pages are calling these APIs, but no backend documentation was found.

## `GET /api/sync/neura`

Called by (1 pages):

- /dashboard/status

## `POST /api/webhooks/process`

Called by (3 pages):

- /admin/webhooks
- /settings/integrations
- /debug/webhooks
```

## Migration from Old Structure

If you had docs with the old flat structure, you can:

1. **Keep old docs**: Rename `docs/frontend/` to `docs/frontend_old/`
2. **Generate new ones**: Run with new code - creates organized structure
3. **Compare and merge**: Use diff tools to merge any custom additions

## Troubleshooting

**Question**: Why is my backend doc overwritten?
**Answer**: Make sure you use `--only-backend` or `--only-frontend` if generating separate pipelines.

**Question**: How do I update just responses.md?
**Answer**: Run with `--only-backend` - responses.md is always regenerated (no AI needed).

**Question**: Where do I find undocumented APIs?
**Answer**: `docs/frontend/undocumented/missing_apis.md`

**Question**: Why are some response fields showing `<value>`?
**Answer**: The static analyzer couldn't extract the exact type - run with AI enabled for better details.

## Summary of Improvements

| Feature               | Before              | After                     | Benefit                       |
| --------------------- | ------------------- | ------------------------- | ----------------------------- |
| API Responses         | ❌ Not documented   | ✅ responses.md generated | Know what each API returns    |
| Frontend Organization | Flat list           | Grouped by page           | Better navigation             |
| Missing APIs          | ❌ No tracking      | ✅ undocumented/ folder   | Find gaps in backend docs     |
| Data Protection       | Overwrites possible | ✅ Separate directories   | Safe independent runs         |
| Frontend Structure    | Static pages.md     | ✅ Individual files       | Easier to maintain and update |
| Data Sources          | ❌ Not shown        | ✅ Models/hooks tracked   | Understand data flow          |

---

**Generated**: 2026-03-24
**Version**: 2.0 (Reorganized Output Structure)
