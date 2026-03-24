# Quick Reference - Doc_writer v2.0 Updates

## 🎯 Problems Solved

| Problem                           | Solution                                   | File Changed                |
| --------------------------------- | ------------------------------------------ | --------------------------- |
| No API response docs              | New `responses.md` generated automatically | `backend/generate_docs.py`  |
| Frontend all in flat file         | Organized into page group folders          | `frontend/generate_docs.py` |
| Can't find missing APIs           | New `undocumented/missing_apis.md`         | `frontend/generate_docs.py` |
| Backend gets overwritten          | Separate output directories                | `main.py`                   |
| No SQL for frontend (unnecessary) | Frontend doesn't generate .sql             | `frontend/generate_docs.py` |
| Can't track data sources          | Pages show components & models used        | `frontend/generate_docs.py` |

## 📁 New Output Structure

```
Backend (PROTECTED):
  docs/backend/
    index.md
    domain_name/
      ├── api.md            (static)
      ├── responses.md      ✨ NEW - Response schemas
      ├── business.md       (AI-generated)
      └── legacy_query.sql  (AI-generated)

Frontend (ORGANIZED):
  docs/frontend/
    index.md               ✨ NEW - Master index
    page_group_name/       ✨ NEW - Grouped by route prefix
      ├── README.md        ✨ NEW - Group overview
      ├── index.md         (page doc)
      ├── other.md         (page doc)
    another_group/
    undocumented/          ✨ NEW - Missing APIs
      └── missing_apis.md  ✨ NEW - Gaps in backend
```

## 🚀 How to Use

### Default (Both Backend & Frontend)

```bash
python main.py generate-docs --path ./my-project --provider ollama
```

✅ Generates everything
✅ Backend separate from frontend
✅ Safe - no overwrites

### Backend Only

```bash
python main.py generate-docs --backend ./laravel --provider ollama --only-backend
```

✅ Only changes `docs/backend/`
✅ Doesn't touch frontend

### Frontend Only

```bash
python main.py generate-docs --frontend ./vue-app --provider ollama --only-frontend
```

✅ Only changes `docs/frontend/`
✅ Doesn't touch backend

### Regenerate Everything

```bash
python main.py generate-docs --path ./my-project --provider ollama --force
```

⚠️ Overwrites all docs (use with care)

## 📋 New Features Explained

### 1️⃣ API Response Documentation (responses.md)

**What it does**: Documents what each API returns

**Example**:

````markdown
## GET /v1/login

**Endpoint**: AuthController@login

**Response Type**: `json`

**Response Fields**:

```json
{
  "userId": <value>,
  "token": <value>,
  "name": <value>,
}
```
````

```

**When it's generated**: Every domain, every run (no AI needed)
**Where to find it**: `docs/backend/{domain}/responses.md`

### 2️⃣ Page Groups (Frontend Organization)

**What it does**: Groups related pages together instead of flat list

**Before**:
```

pages.md (one giant file with ALL pages)

```

**After**:
```

frontend/
home/
README.md (overview)
index.md (/home)
dashboard.md (/home/dashboard)
bill/
README.md (overview)
list.md (/bill/list)
detail.md (/bill/{id})
settings/
...

````

**How pages are grouped**:
- `/home` → `home/`
- `/home/anything` → `home/`
- `/bill/list` → `bill/`
- `/settings/profile` → `settings/`

### 3️⃣ Missing APIs (undocumented/missing_apis.md)

**What it does**: Finds and lists APIs frontend calls that backend doesn't document

**Example**:
```markdown
# Undocumented APIs

## `GET /api/users/search`

Called by (2 pages):
- /home/search
- /admin/users

## `POST /api/webhooks/process`

Called by (1 pages):
- /settings/integrations
````

**Why it's useful**: Quickly find gaps in backend documentation

## 🔒 Safety Feature: Protected Output

**Old Behavior** ⚠️:

- Run backend → creates `docs/frontend/`
- Run frontend → overwrites `docs/`
- Data loss possible!

**New Behavior** ✅:

```
Backend output: docs/backend/    (protected)
Frontend output: docs/frontend/  (protected)
```

- Backend run only touches `docs/backend/`
- Frontend run only touches `docs/frontend/`
- No cross-directory overwrites
- Safe to run independently

## 📊 Page Structure Example

### Group README (docs/frontend/home/README.md)

```markdown
# HOME Pages

Page group: **/home**

## Pages (3)

- [/home](index.md) — `Home.vue` (2 API calls)
- [/home/dashboard](dashboard.md) — `Dashboard.vue` (4 API calls)
- [/home/profile](profile.md) — `Profile.vue` (1 API call)
```

### Individual Page Doc (docs/frontend/home/dashboard.md)

```markdown
# /home/dashboard

**Component**: `Dashboard.vue`

## Layout

DefaultLayout

## Child Components

- `TopNav.vue`
- `Sidebar.vue`
- `Card.vue`

## API Dependencies

- `GET /api/dashboard/stats` (via hook)
- `GET /api/user/profile` (via composable)

## State Management

pinia

## Unknowns

None
```

## 🔍 Where to Find What

| Document          | Location                                     | Purpose                        |
| ----------------- | -------------------------------------------- | ------------------------------ |
| API Responses     | `docs/backend/{domain}/responses.md`         | What each API returns          |
| Business Logic    | `docs/backend/{domain}/business.md`          | Why each API exists            |
| SQL Audit         | `docs/backend/{domain}/legacy_query.sql`     | DB queries per endpoint        |
| Page Groups       | `docs/frontend/{group}/README.md`            | Overview of related pages      |
| Page Docs         | `docs/frontend/{group}/{page}.md`            | Single page documentation      |
| Missing APIs      | `docs/frontend/undocumented/missing_apis.md` | Gaps in backend docs           |
| Dependency Graph  | `docs/dependency_graph.json`                 | Frontend↔Backend mapping       |
| Validation Report | `docs/cross_validation.json`                 | Missing endpoints & mismatches |

## 💿 Files Changed

```diff
backend/generate_docs.py
  + _write_responses_md() [NEW function]
  ~ Updated _write_index() to include responses.md
  ~ Call _write_responses_md() in generate_all_docs()

frontend/generate_docs.py
  - COMPLETE REWRITE (removed old flat structure)
  + _extract_page_group()          [NEW]
  + _safe_page_filename()          [NEW]
  + _write_group_readme()          [NEW]
  + _write_frontend_index()        [NEW]
  + _write_missing_apis()          [NEW]
  ~ generate_pages_md()            [refactored]

main.py
  + Import generate_pages_md
  - Remove write_pages_as_files()
  ~ run_frontend() now calls generate_pages_md()

NEW FILES:
  DOCUMENTATION_STRUCTURE.md  [Full reference guide]
  CHANGES.md                  [Implementation details]
```

## ⚠️ Breaking Changes

**Frontend output structure changed!**

Old:

```
docs/frontend/pages.md  (one big file)
```

New:

```
docs/frontend/
  index.md
  home/
    README.md
    index.md
    dashboard.md
  bill/
    ...
```

**Migration**:

```bash
# Back up old structure
mv docs/frontend docs/frontend_old

# Generate new structure
python main.py generate-docs --frontend ./src --provider ollama

# Compare if needed
diff -r docs/frontend_old docs/frontend
```

## ✅ Verification Checklist

After running the new version:

- [ ] `docs/backend/{domain}/responses.md` exists and has response schemas
- [ ] `docs/frontend/index.md` exists with master index
- [ ] `docs/frontend/{group}/README.md` files exist for each page group
- [ ] `docs/frontend/{group}/{page}.md` files exist for each page
- [ ] `docs/frontend/undocumented/missing_apis.md` exists (if any missing APIs)
- [ ] Backend output wasn't touched when generating frontend
- [ ] Frontend output wasn't touched when generating backend

## 🐛 Troubleshooting

**Backend docs got overwritten**
→ Use `--only-backend` for backend-only runs

**Frontend docs got overwritten**
→ Use `--only-frontend` for frontend-only runs

**Old pages.md still there?**
→ It's safe - delete it manually: `rm docs/frontend/pages.md`

**Pages not grouped correctly**
→ Check `_extract_page_group()` logic - first path segment is the group

**No undocumented APIs file**
→ This file only creates if frontend calls APIs not in backend

**Response fields show `<value>`**
→ This is from static analysis - run with AI for better detection

## 📈 Example Output Comparison

### Backend: API Responses (NEW)

````markdown
## POST /login

**Endpoint**: LoginController@store

**Response Type**: `json`

**Response Fields**:

```json
{
  "userId": <value>,
  "token": <value>,
  "email": <value>,
}
```
````

````

### Frontend: Page Group (NEW)

```markdown
# HOME Pages

Page group: **/home**

## Pages (2)

- [/home](index.md) — `Home.vue` (3 API calls)
- [/home/dashboard](dashboard.md) — `Dashboard.vue` (2 API calls)
````

### Frontend: Missing APIs (NEW)

```markdown
# Undocumented APIs

## `GET /api/sync/neura-platform`

Called by (1 pages):

- /admin/sync-status
```

---

**Ready to test?** Try running:

```bash
python main.py generate-docs --path ./my-project --provider ollama --force
```

**Questions?** Check:

- `DOCUMENTATION_STRUCTURE.md` - Full reference
- `CHANGES.md` - Implementation details
- Source code comments - Code-level explanation
