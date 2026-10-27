# Submission

## Links

- **GitHub repository:** https://github.com/akashnpc/volunteer-scheduling
- **Live application:** **TODO: paste the Vercel URL here after deploying** (see `docs/deployment.md`)

## Notes for the reviewer

- **The first load can be slow.** The API runs on Render's free plan, which sleeps after about 15 minutes
  without traffic; waking it can take up to a minute. The login page says so if sign-in is slow. Sign-in
  works as soon as the API answers.
- The database is seeded with demo data (7 accounts, 4 programs, 30 shifts, signups, history) whose dates
  are relative to the day it was first deployed, so some shifts are in the past and closed, some are within
  three days and understaffed (the Alerts badge in the navigation), and the rest are upcoming.
- Things worth trying: sign in as Alice and try to sign up for the overlapping Tutoring shift on the same
  morning as her Food Pantry shift (rejected with a reason); as the coordinator, dismiss an alert, then sign up
  volunteers until that shift is Filled and cancel one signup: the alert comes back; generate a recurring schedule with a
  holiday; export a roster CSV; open any shift's History.
- Code map: `backend/app/services/` holds the rules, `backend/tests/` proves them. Start with
  `docs/decisions.md`.

## Demo credentials

Password for every account: `Demo1234!`

| Role | Email | Password |
|------|-------|----------|
| Coordinator | coordinator@example.com | Demo1234! |
| Volunteer (member of Food Pantry and Tutoring Drive) | alice@example.com | Demo1234! |
| Volunteer (Food Pantry, Weekend Trail Cleanup, Tutoring Drive) | carol@example.com | Demo1234! |

More volunteers: bob, dave, erin and frank `@example.com`. Anyone can also create their own volunteer
account on the sign-in page (it belongs to no program until a coordinator adds it).

## Stack

| Layer | What you used | Why |
|-------|---------------|-----|
| Frontend | Next.js 14 (App Router), JavaScript, Recharts | I wanted React with simple hosting; every page is a thin client of the API |
| Backend | Python FastAPI, SQLAlchemy 2, JWT + bcrypt | the rules (lifecycle, overlap, roles) are easiest to write and test in Python; one place enforces permissions |
| Database | PostgreSQL on Supabase (SQLite locally) | relational data with constraints and triggers; free tier |
| Hosting | Vercel (web), Render (API), Supabase (database) | all free; the combination the brief suggested |

## Goal checklist

| # | Goal | Status | Notes |
|---|------|--------|-------|
| 1 | Accounts and roles | Done | email + password, coordinator and volunteer roles enforced by a server-side guard; tests call every coordinator endpoint as a volunteer. No password reset |
| 2 | Programs | Done | create, edit, archive, restore; archiving hides but keeps shifts, and blocks new shifts/signups until restored |
| 3 | Shifts inside programs | Done | date, start, duration, location, headcount; create, edit, delete (soft); a program page lists its shifts |
| 4 | Shift lifecycle with rules | Done | fill state derived from the count and never settable; Filled/Closed reject signups; overlaps rejected across programs; close only after the shift ends and then locks signups and cancellations; every rejection carries a reason |
| 5 | Program membership | Done | coordinators add and remove volunteers; removal cancels their upcoming signups there (decision 9); volunteers only see their programs |
| 6 | Finding shifts | Done | server-side text search (program name, location), filters (program, fill state, date range, mine), sort by date / start time / fill state, pagination with total |
| 7 | Recurring schedule and roster | Done | weekly pattern over a date range with excluded dates, result lists created and skipped (holiday or already exists); roster CSV with total hours per volunteer |
| 8 | Dashboard | Done | this week's four numbers, breakdown by fill state and by program, signups per week for 8 weeks |
| 9 | History you cannot rewrite | Done | append-only events table protected by database triggers (tested with raw SQL); timeline with actors, state changes and coordinator notes |
| 10 | Understaffed alerts | Done | today through 3 days ahead and Open/Partially Filled, nav badge, coordinator dismiss, alert returns when a cancellation un-fills a Filled shift |

Known limits: no frontend automated tests (the rules are tested through the API; the UI was walked through in
a browser), no migrations tool, no password reset, single organisation timezone.

## How much time did you actually spend?

**TODO (you): write your real number of hours and how they were split** (reading and understanding the code,
deployment, rehearsing). The assistant cannot know this.

## What would you do next, with another 12 hours?

- Alembic migrations, and a move from `create_all` before any real data exists.
- Frontend tests (Playwright) for the sign-up/cancel/close flows, and run the Postgres test run in CI.
- Postgres `pg_trgm` index for search and an exclusion-constraint backstop for overlaps.
- Password reset by email, token revocation, and the reminder-message stretch idea (a scheduled job reading the
  same understaffed query the alerts use).
- Let coordinators filter the alerts by program and see who is signed up for a shift from the alert list.

## What are you least happy with in this codebase, and why?

- `services/shifts.py` has grown to hold creation, editing, state machine, search and presentation. Search and
  `to_out` should move out; right now it is the file a new reader has to hold most in their head.
- The denormalised `signup_count`/`state` columns trade query simplicity for a drift risk that I only mitigate
  with a single writer, a CHECK constraint and tests, not with a database-level guarantee.
- The frontend has little reuse between the program page forms and the shift edit form, and no automated tests.
