# Volunteer Scheduling

Coordinators set up programs and shifts; volunteers claim the shifts they can work; how many spots are
still needed is always a live count. Built for take-home assignment 18 (the original brief is in
[docs/assignment-brief.md](docs/assignment-brief.md)).

- **Frontend:** Next.js 14 (App Router, JavaScript) + Recharts, hosted on Vercel
- **Backend:** Python FastAPI + SQLAlchemy 2, hosted on Render
- **Database:** PostgreSQL on Supabase (SQLite for local development and tests)

Start with [SUBMISSION.md](SUBMISSION.md) for links, demo logins and the goal checklist, then the docs:
[architecture](docs/architecture.md), [schema](docs/schema.md), [plan](docs/plan.md),
[decisions](docs/decisions.md), [AI prompts](docs/ai-prompts.md), [deployment](docs/deployment.md).

## Run it locally

You need Python 3.12+ and Node 20+.

```bash
# 1. API (http://localhost:8000, docs at /docs)
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                                   # defaults to a local SQLite file
python -m app.seed                                     # demo data, dates relative to today
uvicorn app.main:app --reload

# 2. Web app (http://localhost:3000), in a second terminal
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Demo logins (after seeding), password `Demo1234!`: `coordinator@example.com`, `alice@example.com`
(volunteer; also bob, carol, dave, erin, frank `@example.com`).

## Tests

```bash
cd backend && pytest
cd backend && ruff check app tests   # lint (settings in backend/pyproject.toml)
```

The tests freeze the clock and exercise the rules through the HTTP API: roles, the shift lifecycle and
every rejection, overlap detection, the append-only history (including raw SQL attempts to edit it),
search/sort/pagination, the recurring generator, the roster CSV, dashboard numbers and alert
dismissal/return.

## Layout

```
backend/app/
  models.py        tables and DB constraints          services/   the business rules
  db_setup.py      create tables + triggers + RLS     routers/    thin HTTP layer
  deps.py          auth + coordinator-only guard      seed.py     demo data
frontend/src/
  app/             pages (dashboard, shifts, programs, alerts, people, login)
  components/      shift table, timeline, program forms, shift detail sections
  lib/             API client, auth context, formatting
```
