# AI prompts

I used **Claude Code (Claude Sonnet 5.5)** as a pair programmer for this project: it wrote the first draft of
the code, tests and docs while I set the direction, and I reviewed and ran what it produced. The prompts
below are my actual messages to it, in order. The assistant also made many small tool calls on its own
(reading files, running tests, starting servers) inside those instructions; those are not separate prompts.

Everything in this repository is therefore AI-drafted. **I am accountable for it and have to be able to
explain it**: the sections "What you corrected" record the places where the first draft was wrong, which are
also good starting points for the review call.

The sections after "Building the whole project" cover deployment and clean-up. I did not paste secrets into this
file: one prompt below contained my database connection string, which I have left out.

## Planning: reading the brief and choosing the stack

### Prompt

> We have to set up this project end-to-end while using the instruction better given in the Zip file I have
> attached ... follow all the instructions that I need to have to create a successful submission. Also you
> have to tell me all the services that we need to have for the complete project deployment. For example,
> Vercel for front end, backend we are going to use Render, and for database we are going to use Supabase.
> And also if it needs any other services, find the free alternative ... But first telling me whatever you
> need, where I need to save those as the ENV variables, etc. For tech stack, mainly use React, JavaScript for
> React or Next.js for front end, and for backend you can use Python. And for database, SQL database, we are
> going to use Supabase. So go through and first make a plan.

(with the assignment zip attached)

### What you got

A written plan: Next.js + FastAPI + Supabase Postgres on Vercel / Render / Supabase, the build order, the
environment variables and where each is stored, and a list of what I had to do myself (create accounts, supply
the database URL). The assistant first unpacked the zip and read every file before answering.

### What you corrected

My first message did not show me the plan in a readable form, so I asked again.

## Planning: asking for the plan again

### Prompt

> give me the plan i can not see the plan

### What you got

The same plan re-posted in full as text.

### What you corrected

Nothing in the content; I simply could not see the first reply in the interface.

## Building the whole project

### Prompt

> I HAVE LOGGED IN MY GITHUB ACCOUNT YOU CAN START BUILDING THE PROJECT END TO END AND AFTER COMPLETING THE
> PROJECT YOU CAN GIVE ME THE STEPS TO THE ENV VARIABLES AND STEPS TO DEPLOYMENT

### What you got

The backend, tests, seed data, frontend, deployment config and these docs, built in the order described in
`plan.md` with incremental commits.

### What you corrected

These are mistakes in the assistant's first drafts that were caught by running the code, and what was done:

1. **Wrong, and fixed: a Python scoping bug in the Pydantic schemas and SQLAlchemy models.** It wrote
   `date: date | None = None` and `date: Mapped[date] = ...`. Python evaluates the default *before* the
   annotation, so inside the class `date` was already `None` (or the column object) and the app crashed on
   import with `TypeError: unsupported operand type(s) for |`. Fix: import the type under another name
   (`from datetime import date as DateType`) in `schemas.py` and `models.py`.
2. **Wrong test, fixed.** A test indexed `signups[1]` in a volunteer's response, but the rule the code
   implements is that a volunteer sees only their own signup on a shift's detail (coordinators see all). The code was right and the test
   wrong, so the test was changed.
3. **Wrong test, fixed.** A test meant to prove "moving a shift cannot double-book a volunteer" moved the
   shift to the same start time in the same program, which the slot-uniqueness rule rejects *first*. The test
   was changed to move it to an overlapping but different start time, and a second assertion now covers the
   same-slot rejection explicitly.
4. **Seed data too lumpy, fixed.** The first seed clamped most signup times to "now", so the weekly signups
   chart had zero bars for most weeks and a spike this week. The signup times are now spread across an
   eight-week history, with a cluster shortly before each shift.
5. **UX default reversed.** The first shifts list opened on past, closed October shifts (decision 10).
6. **Test coverage gap closed.** The first suite only ran on SQLite although production is Postgres, so the
   Postgres-only SQL (triggers, partial indexes, RLS) had never run. The suite now accepts
   `TEST_DATABASE_URL`, and all 51 tests and the seed were run against a real PostgreSQL (decision 7).
7. **Tooling hiccups (not product bugs):** the assistant's temp-folder path was too long for Windows
   (extracting the zip failed) and it fell back to a short path; a first attempt to start the preview servers
   looked in the wrong folder, so it started them directly instead.

## Deployment: creating the repo and the first walkthrough

### Prompts

> Create and push

> give the one by one step of deployment

### What you got

The public GitHub repository with the 12 commits, then a step-by-step guide for Supabase, Render and Vercel
(it is also in `docs/deployment.md`).

### What you corrected

Nothing in the code. The guide was followed by hand, and it surfaced the problems in the next section.

## Deployment: fixing what broke on Render, Vercel and Supabase

### Prompts

> (pasted the Render build log) `ERROR: Could not open requirements file`

> (pasted the next Render log) `could not translate host name "...@aws-0-ap-northeast-2.pooler.supabase.com"`

> (screenshot of the live login page showing "Incorrect email or password")

> (my Supabase connection string) fix everything

### What you got

Three separate causes, each found from the log or screenshot:

1. **Render ran the build from the repository root.** The service had been created by hand, so the
   `rootDir: backend` and `PYTHON_VERSION` settings from `render.yaml` were not applied. Fixed in the Render
   dashboard (Root Directory `backend`).
2. **The database password contained an `@`**, so the URL parser read part of the password as the host name.
   Fixed by resetting the password to letters and numbers only.
3. **The deployed database was empty**, because `SEED_ON_STARTUP` was not set on Render, so every login failed
   with a 401. The assistant first ran a read-only check of the database (all tables existed and were empty),
   then ran the seed once against it: 7 users, 4 programs, 30 shifts, 68 signups.

### What you corrected

Sharing the connection string in a chat was a mistake on my side; I reset the database password afterwards.

## Checking the submission, and commit history

### Prompts

> how should i test everything that was needed in submission

> remove you name from commits it should not appear in any future commit

> Force-push

> 24 hours

### What you got

A test checklist covering the deliverables, the ten goals on the live site, and the automated tests. The
`Co-Authored-By` trailer was removed from all 12 commit messages by rewriting history and force-pushing; the
files in every commit are unchanged. Finally my real hours (about 24) and the live URL were written into
`SUBMISSION.md` and `docs/plan.md`.

### What you corrected

I decided to keep this file's statement that the project was AI-drafted, because the brief asks for honest
disclosure of AI use even though the commit trailers were removed.
