# Architecture

## The moving pieces and how they talk

```
 Browser (React pages)           Render (free web service)              Supabase (free)
 Next.js app on Vercel  --JSON/HTTPS-->  FastAPI app  --SQL (psycopg2)-->  PostgreSQL
 token in localStorage   Authorization:   routers -> services -> models    tables, triggers,
                         Bearer <JWT>                                      constraints
```

- **Next.js frontend** (`frontend/`). Every page is a client component that calls the API with `fetch`. It
  holds no business rules: it shows what the server returns and displays the server's rejection message
  verbatim. The signed-in user and their JWT live in an auth context (token in `localStorage`).
- **FastAPI backend** (`backend/app/`), in three layers:
  - `routers/`: HTTP only (parse the request, call a service, commit, shape the response).
  - `services/`: the rules (signup lifecycle, overlap check, fill-state machine, alerts, dashboard,
    schedule generator, roster CSV) plus `search.py` (shift filters, sorting, pagination) and `presenters.py`
    (row to response model). No HTTP in here.
  - `models.py` / `db_setup.py`: tables and the constraints the database enforces itself.
- **PostgreSQL** is the only stateful piece. There is no cache, queue or worker.

Authorisation is a FastAPI dependency (`coordinator_only` in `deps.py`) on every coordinator endpoint, plus
visibility filters in the queries (a volunteer's queries are constrained to programs they belong to). Hiding
buttons in the UI is cosmetic; the tests call the API directly as a volunteer and expect 403s.

## Where each piece runs

| Piece | Runs on | Notes |
|---|---|---|
| Next.js app | Vercel (free Hobby) | static + client-rendered pages |
| FastAPI | Render free web service | sleeps after ~15 min idle, first request can take ~1 min |
| PostgreSQL | Supabase free project | reached through the Session pooler (IPv4) |
| Local dev / tests | your machine | SQLite file by default; the same test suite also passes on Postgres via `TEST_DATABASE_URL` |

Configuration comes from environment variables only (`backend/app/config.py`, listed in `docs/deployment.md`).

## One request end to end: a volunteer signs up for a shift

`POST /api/shifts/42/signups` from the "Sign up" button on the shifts list.

1. The browser sends the JSON request with `Authorization: Bearer <jwt>`. CORS is checked against
   `CORS_ORIGINS`.
2. `deps.current_user` verifies the JWT signature and loads the user row (401 if invalid).
3. `routers/shifts.py::sign_up` works out *who* is being signed up. A volunteer can only sign themselves up
   (anything else is 403); a coordinator must name a volunteer.
4. `services/signups.py::create_signup` runs in one transaction:
   1. `SELECT ... FOR UPDATE` on the volunteer row, then on the shift row. Locking the volunteer serialises
      two simultaneous signups by the same person so the overlap check cannot be raced; locking the shift
      protects the headcount. Lock order is always user, then shift, so two requests cannot deadlock.
   2. Rules, each with its own message: program not archived, volunteer is a member, shift not Closed, shift
      not Filled, no existing live signup, no overlapping shift the volunteer already holds.
   3. Insert the `signups` row, increment `shifts.signup_count`, append a `signup` event.
   4. `shifts.refresh_state` derives the fill state from count vs headcount; if it changed it appends a
      `state_change` event (old and new state). A Filled-to-understaffed change also deletes any alert
      dismissal for the shift.
5. The router commits, reloads the shift and returns it. Any rule violation raises an `HTTPException(409)`
   with the explanation, nothing is committed, and the UI shows the text in a banner.
6. The frontend refreshes the list and the navigation's alert badge (it re-fetches `/alerts` whenever any
   mutating request succeeds).

## What I decided not to build

- **No Supabase Auth, no row level security policies as the permission model.** The brief wants the server to
  enforce roles; one FastAPI codebase does that and is testable. (RLS is switched on with *no* policies purely
  to stop Supabase's public REST API exposing the tables.)
- **No Alembic migrations.** Tables are created from the models at startup. Fine for a single deployment with
  no data to migrate; the first schema change after launch would need Alembic.
- **No email, reminders, waitlist, availability, check-in** or any other stretch idea. All ten required goals
  came first.
- **No background jobs.** Alerts are computed on read from dates and fill state, so nothing has to run on a
  schedule (and a sleeping free-tier server cannot miss a job).
- **No server-side sessions or refresh tokens.** One 24-hour JWT; signing out just forgets it. Acceptable for
  a demo, not for production (no revocation).
- **No real-time updates.** The badge polls every 60 seconds and after each mutation.
- **No timezone support per user.** Shift times are wall-clock times in one organisation timezone
  (`ORG_TIMEZONE`).
