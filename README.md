# doc_writer

**AI-powered Documentation Generator for Laravel + Vue/React codebases**

Statically parses your PHP backend routes, controllers, DB queries, and frontend pages/API calls, then feeds the structured data into an AI model to generate clean, readable documentation.

---

## 📁 Project Structure

```
doc_writer/
├── prompts/
│   ├── backend_prompts.py       # All AI prompts for backend analysis
│   └── frontend_prompts.py      # All AI prompts for frontend analysis
├── backend/
│   ├── detect_apis.py           # Step 1: Parse routes → controllers → logic
│   ├── generate_docs.py         # Step 2: AI-powered doc generation
│   └── validate_backend.py      # Step 3: Completeness check
├── frontend/
│   ├── detect_pages.py          # Step 1: Pages, routes, API usage
│   └── generate_docs.py         # Step 2: AI-powered doc generation
├── shared/
│   ├── ai_client.py             # Unified AI interface (local LLM or API key)
│   ├── dependency_graph.py      # Build frontend ↔ backend graph
│   └── validator.py             # Cross-check frontend APIs vs backend
├── output/
│   └── docs/
│       ├── backend/
│       │   ├── business.md
│       │   └── legacy.sql
│       └── frontend/
│           └── pages.md
└── main.py                      # CLI entry point
```

---

## 🚀 Quick Start

### No installation required — pure Python stdlib (3.8+)

```bash
# From scratch — clone or copy doc_writer/ anywhere, then:

# Full run with Ollama (local, FREE)
python main.py generate-docs \
  --backend  ./path/to/laravel \
  --frontend ./path/to/vue-app \
  --provider ollama \
  --output   ./my-docs

# Groq (cloud, FREE tier)
python main.py generate-docs \
  --backend ./laravel \
  --api-key gsk_YOUR_KEY

# Static only (no AI needed)
python main.py generate-docs \
  --backend ./laravel \
  --no-ai
```

---

## 🤖 AI Providers

| Provider   | Key prefix  | Free? | Notes                        |
|------------|-------------|-------|------------------------------|
| `ollama`   | (none)      | ✅    | Local. Needs `ollama serve`  |
| `groq`     | `gsk_`      | ✅    | Cloud. Fast.                 |
| `anthropic`| `sk-ant-`   | ❌    | Best quality                 |
| `openai`   | `sk-`       | ❌    | GPT-4o-mini                  |
| `gemini`   | `AIza`      | ✅    | Free tier (rate-limited)     |
| `deepseek` | —           | ❌    | DeepSeek V3                  |

Set via `--api-key` flag or `AI_API_KEY` environment variable.

### Ollama setup
```bash
# Install: https://ollama.com/download
ollama serve
ollama pull qwen2.5-coder:7b   # recommended (~5GB)
```

---

## 📋 CLI Reference

```
python main.py generate-docs [OPTIONS]

Required (at least one):
  --backend   PATH     Laravel project root
  --frontend  PATH     Vue/React project root

Output:
  --output    PATH     Output dir (default: ./doc_output)

AI:
  --provider  NAME     anthropic|groq|openai|gemini|ollama|deepseek
  --api-key   KEY      API key (or set AI_API_KEY env var)
  --model     NAME     Override model name
  --ai-mode   MODE     local | api
  --no-ai              Static extraction only (no AI)

Filters:
  --only-backend       Skip frontend pipeline
  --only-frontend      Skip backend pipeline
  --skip-validation    Skip completeness checks
  --rerun-changed-only Re-process only changed files
```

---

## 📦 Output Files

| File                              | Description                                      |
|-----------------------------------|--------------------------------------------------|
| `docs/backend/business.md`        | One section per API: flow, validation, response  |
| `docs/backend/legacy.sql`         | All DB queries, classified and annotated         |
| `docs/frontend/pages.md`          | One section per page: component, APIs, state     |
| `docs/dependency_graph.json`      | Machine-readable frontend ↔ backend API map      |
| `docs/dependency_graph.mermaid`   | Mermaid.js diagram of page → API links           |
| `docs/cross_validation.json`      | Missing APIs, unused APIs, method mismatches     |
| `validation_report.json`          | Backend completeness gaps, unknowns              |

---

## 🔹 Pipeline Flow

```
[Source Code Files]
       ↓
[Python Static Parsers]     ← detect_apis.py, detect_pages.py
       ↓
[Structured Intermediate JSON]
       ↓
[AI Documentation Generator] ← generate_docs.py (backend + frontend)
       ↓
[Output Files]
  docs/backend/business.md
  docs/backend/legacy.sql
  docs/frontend/pages.md
       ↓
[Validation + Cross-Check]  ← validate_backend.py, validator.py
       ↓
[Final Report: gaps, mismatches, unknowns]
```

---

## ⚙️ Environment Variables

```bash
AI_API_KEY=gsk_...          # API key
AI_PROVIDER=groq            # Provider name
AI_MODEL=llama-3.3-70b      # Override model
AI_MODE=api                 # 'local' or 'api'
```

---

## ⚠️ Global Rules

The parser never guesses or hallucinates:
- Only extracts what is **statically visible** in source code
- Unknown values are always marked `"UNKNOWN"` and added to `unknowns[]`
- AI prompts include strict rules against inventing logic
