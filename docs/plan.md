# Plan

## How I broke the work into sessions

The brief suggests about 12 hours in daily sessions of about two hours. I built this with an AI coding
assistant (Claude Code) in one extended working session, so the table below is the order of work, not
separate calendar days. Each chunk ended in a commit (see `git log`). **TODO (you): if you did any of it on
separate days, say so here.**

| Session | Goal | Result |
|---|---|---|
| 0 | Read the brief, choose the stack and hosting, write the plan | Next.js + FastAPI + Postgres; Vercel / Render / Supabase |
| 1 | Data model and rules foundation | tables with constraints, append-only triggers, auth and the coordinator guard |
| 2 | The domain rules | shift lifecycle, signups, overlap, search, recurring generator, roster, dashboard, alerts |
| 3 | Seed and tests | demo data built through the real services; suite covering every goal |
| 4 | Frontend | login, dashboard, shift search, shift detail with history, programs, alerts, people |
| 5 | Verification and deploy prep | ran the suite on real Postgres, browser walk-through, Render blueprint, deploy guide |
| 6 | Documentation | these five docs and `SUBMISSION.md` |

## Order, and why

1. **Schema and constraints first**, because everything else depends on them and because three of the ten
   goals (history that cannot be rewritten, no double bookings, no overfilled shifts) are properties of the
   data, not of the UI. Retrofitting them later is harder than starting with them.
2. **Rules before screens.** The lifecycle (goal 4) is the riskiest part: derived fill state, overlap, close
   and lock, and an explanatory rejection for every illegal move. I wanted it settled and tested through the
   HTTP API before any UI could hide a mistake.
3. **Search, generator, roster, dashboard, alerts** next. They are read-heavy and sit on top of the rules.
4. **Frontend last**, as a thin layer: it shows the server's data and error messages. Doing it last meant the
   API shape was stable, so almost no UI rework.
5. **Deployment prep after the first full local run**, so deployment problems would not be mixed up with
   feature bugs.

## Estimated versus actual

- **Estimate:** the brief's budget is about 12 hours.
- **Actual:** **TODO (you): fill in the real hours you spent**, including reading and understanding the code,
  deploying, and rehearsing the explanations. I am not putting a number here that I cannot back up.
- Where the effort went, factually: the lifecycle edge cases (what "close" and "open" mean, what happens to
  alerts and signups when a shift is edited, deleted or a member removed) produced most of the decisions
  in `decisions.md`; the history triggers had to be written for two database dialects; and the work that had
  to be redone after a first attempt is listed in `ai-prompts.md` (a model/schema typing bug, two test
  expectations, the seed's signup distribution, the shifts list default).

## What I cut when I ran short

- All **stretch ideas** (reminders, waitlist, availability, teams, public signup, milestones, check-in,
  substitutes, translations).
- **Alembic migrations** (decision 5), **password reset / email verification**, token revocation.
- **Pagination on the members and people lists** and on the dashboard drill-downs; they are small by design
  here.
- **Component and end-to-end tests for the frontend.** Business rules are tested at the API; the UI got a
  manual walk-through in a browser only.
- **Real-time updates**: the alert badge polls every minute instead.
