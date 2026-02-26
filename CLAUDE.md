# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Siyada Lead Generation — a full-stack B2B lead generation app (React frontend + FastAPI backend + PostgreSQL) deployed on Railway. Users enter natural language queries describing their ideal leads, and the app orchestrates a multi-step pipeline: query parsing (OpenAI), web search (Serper), URL scraping (BeautifulSoup), contact enrichment (Apollo.io), and personalized email generation (OpenAI).

## Common Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server locally (uses .env for config)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Docker build/run
docker build -t leads-railway .
docker run -p 8000:8000 --env-file .env leads-railway
```

There are no tests, linters, or type-checking configured in this project.

## Architecture

### Backend (FastAPI)

**Entry point**: `app/main.py` — creates the FastAPI app, registers routers, sets up CORS, creates DB tables on startup, and serves the React SPA as a catch-all route.

**Layers**:
- `app/api/` — Route handlers (thin controllers). Each file is a separate APIRouter with `/api/*` prefix.
- `app/services/` — Business logic. Services call external APIs and contain the core processing logic.
- `app/models/` — SQLAlchemy ORM models (all use String UUIDs as primary keys).
- `app/schemas/` — Pydantic v2 request/response schemas (use `model_config = {"from_attributes": True}`).
- `app/core/` — Cross-cutting concerns: config (pydantic-settings), security (JWT via python-jose + bcrypt), database (SQLAlchemy engine/session).

### API Routes

| Router | Prefix | Purpose |
|---|---|---|
| `auth` | `/api/auth` | Register, login, get current user (JWT bearer auth) |
| `pipeline` | `/api/pipeline` | Start pipeline runs, list sessions, poll status/logs |
| `leads` | `/api/leads` | CRUD for leads within a session |
| `generate` | `/api/generate` | Trigger/preview email generation for session leads |
| `export` | `/api/export` | CSV download (multiple export types: contacts, companies, outreach, full, custom) |
| `settings` | `/api/settings` | API key management, model selection |

### Pipeline Flow (`app/services/pipeline_service.py`)

The pipeline runs as a **FastAPI BackgroundTask** and progresses through these stages (tracked via `SearchSession.status`):

1. **searching** — `llm_service.parse_query()` parses the natural language query into structured fields, then `serper_service.search()` runs concurrent Google searches
2. **enriching** — `scraper_service.scrape_many()` scrapes discovered URLs (capped at 25, semaphore-limited to 5 concurrent), then `apollo_service.search_people()` enriches contacts per domain (search + per-person enrich calls, with quality filtering)
3. **generating** — `llm_service.generate_email()` creates personalized emails for each lead
4. **completed** / **failed** — terminal states

Real-time progress is tracked via `pipeline_log.py` (in-memory, thread-safe dict) — the frontend polls `GET /api/pipeline/{session_id}/status?after=N` for incremental log entries.

### Config & API Keys

`app/core/config.py` uses **pydantic-settings** `BaseSettings` with `.env` file support. API keys have a two-tier lookup: `api_keys.json` file (set via Settings UI) takes precedence over environment variables. The `api_keys.json` file is gitignored.

**Required env vars**: `DATABASE_URL`, `SECRET_KEY`, `CORS_ORIGINS`
**Optional env vars**: `SERPER_API_KEY`, `APOLLO_API_KEY`, `OPENAI_API_KEY`, `OPENAI_MODEL`

### Database

SQLAlchemy with synchronous sessions. Tables auto-created on startup via `Base.metadata.create_all()`. No Alembic migrations are used despite being in requirements. SQLite for local dev (default), PostgreSQL on Railway.

**Models**: `User` → `SearchSession` (1:many) → `SearchResult` (1:many) and `Lead` (1:many). Leads optionally link to a SearchResult.

### Frontend

React (Vite) SPA. Source in `frontend/`, built output in `static/`.

```bash
cd frontend && npm install && npm run build   # outputs to ../static/
cd frontend && npm run dev                     # dev server on :5173, proxies /api to :8000
```

**Structure**: `frontend/src/` — `App.jsx` (router), `pages/` (Login, Register, Dashboard, Session, Settings), `components/` (PipelineForm, ChannelPicker, TonePicker, ProgressPanel, EmailPreview, Navbar), `context/AuthContext.jsx`, `api/client.js` (axios + JWT interceptor).

Served by FastAPI's `StaticFiles` mount for `/assets` and a catch-all route for SPA routing.

### External APIs

All external calls use `httpx.AsyncClient`:
- **Serper** (Google search) — concurrent queries with URL deduplication
- **Apollo.io** — two-step: search for people at domain, then enrich each person by ID
- **OpenAI** — direct HTTP calls (not the SDK), used for query parsing and email generation
- **Web scraper** — `asyncio.Semaphore(5)` limits concurrent scrapes

### Deployment

Railway deployment via `Dockerfile` (Python 3.11-slim). Config in `railway.json`. The `PORT` env var is set automatically by Railway.
