# Decisions

The decisions that actually shaped this codebase. Each one had a real alternative.

## Decision 1: Authentication and roles live in the FastAPI app

- **Chose:** email + bcrypt-hashed password, a signed JWT (24 h), and a `coordinator_only` FastAPI dependency on
  every coordinator endpoint. Public registration always creates a volunteer; coordinators are created by
  another coordinator or by the seed.
- **Rejected:** Supabase Auth with row level security policies as the permission model.
- **Why:** The brief says role differences must be enforced on the server and that the stack is free to
  choose. With RLS the rules would be split between SQL policies and the API, and the rules that matter here
  (membership, overlap, lifecycle) need application code anyway. One place to enforce, one place to test: the
  tests call every coordinator endpoint as a volunteer and expect 403. The cost: no password reset, no email
  verification, no token revocation.

## Decision 2: Shifts are soft-deleted; the history table is append-only through database triggers

- **Chose:** `shifts.deleted_at` instead of `DELETE`, and `BEFORE UPDATE/DELETE` triggers on `shift_events`
  (Postgres and SQLite versions). Deleting a shift first cancels its live signups (each recorded), then logs a
  `deleted` event.
- **Rejected:** (a) hard-deleting shifts with `ON DELETE CASCADE` to their events; (b) enforcing "no edits" only
  in the API by not providing update/delete routes.
- **Why:** Goal 9 says nothing in the timeline can be edited or deleted, "including by coordinators". A cascade
  would destroy the history the moment a coordinator deleted a shift, which contradicts it. Not having an edit
  route proves nothing about the data: a future route, a script or a console session could still rewrite it, so
  the guarantee belongs in the database. A test runs raw `UPDATE` and `DELETE` against the table and expects
  them to fail. Limitation: an admin who owns the table can still drop the trigger.

## Decision 3: Fill state and signup count are stored on the shift, not computed on every read

- **Chose:** `shifts.signup_count` and `shifts.state` columns, written only by one function
  (`refresh_state`) in the same transaction as the signup, under a row lock. The state is *derived* from the
  count and headcount; no endpoint accepts it as input.
- **Rejected:** computing the count with `COUNT(*)` and the state in Python/SQL `CASE` every time.
- **Why:** The shifts list must filter by fill state, sort by it, and show "3/4" for a whole page in a single
  query, and the dashboard groups by it. Stored values make those plain column reads. It also makes the
  fill-state history simple: `refresh_state` knows the old and new value at the moment it changes and writes
  the event. The price is the risk of drift, which I contained with a single writer, a
  `signup_count <= required_headcount` CHECK constraint and tests asserting the state after every kind of
  change.

## Decision 4: Overlap detection is an application query guarded by row locks

- **Chose:** a range-intersection query over the volunteer's live signups (any program), preceded by
  `SELECT ... FOR UPDATE` on the volunteer then the shift row. Back-to-back shifts (one ends when the next
  starts) are allowed.
- **Rejected:** a Postgres exclusion constraint (`EXCLUDE USING gist` over a time range per volunteer).
- **Why:** The constraint would be the strongest guarantee, but it needs a `btree_gist` extension, would not
  run on the SQLite I develop with, and gives a generic error instead of "you already hold Food Pantry on
  Thu 29 Oct, 09:00-12:00". Locking the volunteer row removes the race the constraint would have closed
  (two simultaneous signups by one person). Lock order is always user then shift, so no deadlocks.

## Decision 5: Tables are created from the models at startup; no Alembic

- **Chose:** `Base.metadata.create_all` plus idempotent trigger/RLS statements in `db_setup.py`.
- **Rejected:** Alembic migrations.
- **Why:** A single deployment with no existing data and a tight time budget. Alembic's value is evolving a
  live schema, and nothing is live yet. The honest cost is documented in `architecture.md`: the first schema
  change after launch needs Alembic first.

## Decision 6: All timestamps are naive datetimes in one organisation timezone

- **Chose:** `ORG_TIMEZONE` (default UTC); shift date and start time are wall-clock values, and `created_at`,
  `closed_at` and "now" use the same frame (`clock.py`). "This week" is Monday to Sunday in that zone.
- **Rejected:** `timestamptz` everywhere with per-user timezone conversion.
- **Why:** A volunteering programme meets at a place, so "Saturday 08:00 at the trailhead" has no meaningful
  other timezone. Mixing zones would make "has this shift's end passed?" and "within the next three days"
  harder to get right. The cost is that a deployment must pick one zone, and moving organisations across zones
  needs a data migration.

## Decision 7: Tests ran on SQLite only, then also on Postgres

- **Chose (first):** in-memory SQLite for every test, with dialect-specific DDL for the history triggers.
- **Later reversed:** Production is Postgres, and the pieces most likely to differ (plpgsql triggers, partial
  unique indexes, `FOR UPDATE`, `ILIKE ... ESCAPE`, RLS statements) were exactly the ones SQLite cannot vouch
  for. I added `TEST_DATABASE_URL` to the test fixtures and ran the whole suite plus the seed against a real
  PostgreSQL. All 51 tests pass on both. SQLite stays the default because it needs no setup.
- **Rejected:** requiring Docker/Postgres to run any test.
- **Why:** fast default feedback, with the production dialect still verified.

## Decision 8: What the ambiguous dashboard and lifecycle phrases mean

- **Chose:**
  - "Open shifts this week" = shifts dated this week whose fill state is exactly **Open** (no signups yet);
    Partially Filled ones show up in the fill-state breakdown.
  - "Signups made this week" counts signups *created* in the week, including ones cancelled since, because
    they were made.
  - A coordinator can **close** a shift only after its **end** time has passed.
  - An alert counts shifts dated today through three days ahead (inclusive).
- **Rejected:** counting Partially Filled as "open", closing as soon as a shift starts.
- **Why:** The brief names Open as a fill state, so the headline number uses that word the same way. For
  closing, "once a shift's scheduled time has passed" is most naturally the whole scheduled window. Each
  interpretation is covered by a test so a reviewer can see the exact boundary.

## Decision 9: Removing a volunteer from a program cancels their live signups there

- **Chose:** removal cancels that volunteer's signups on non-closed shifts of the program (each recorded in the
  history, attributed to the coordinator). Closed shifts keep their signups as a record, and the roster still
  lists those volunteers.
- **Rejected:** blocking removal while signups exist, or leaving orphan signups for someone no longer a member.
- **Why:** Goal 5 says a volunteer must belong to a program to sign up, so a signup without membership would
  break an invariant. Blocking removal would make a coordinator cancel each signup by hand, and silently
  keeping them would show a volunteer on shifts of a program they cannot see.

## Decision 10: The shifts list starts on upcoming shifts

- **Chose (first):** open the list with no date filter, sorted by date.
- **Later reversed:** The seeded data has three weeks of closed shifts, so the first screen I saw was full of
  October shifts nobody can act on. The page now starts with "from today" and "Clear filters" returns to all
  dates (a coordinator needs those to find past shifts to close).
- **Rejected:** hiding Closed shifts entirely, which would make them unfindable.
- **Why:** the most common question is "what can I sign up for next".
