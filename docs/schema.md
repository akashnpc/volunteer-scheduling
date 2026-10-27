# Schema

Defined in `backend/app/models.py`; triggers and row level security in `backend/app/db_setup.py`.
All timestamps are naive datetimes in the organisation timezone (see decisions).

## Tables

**users**
| Column | Type | Notes |
|---|---|---|
| id | integer PK | |
| name | varchar(120) | |
| email | varchar(254) | unique, stored lower-case |
| password_hash | varchar(100) | bcrypt |
| role | varchar(20) | CHECK in (`coordinator`, `volunteer`) |
| created_at | datetime | |

**programs**
| Column | Type | Notes |
|---|---|---|
| id | integer PK | |
| name | varchar(120) | |
| description | text | |
| archived_at | datetime, null | NULL = active. Archiving never touches shifts or signups |
| created_by | FK users | |
| created_at | datetime | |

**program_members** (programs <-> volunteers)
| Column | Type | Notes |
|---|---|---|
| program_id | FK programs | composite PK with user_id |
| user_id | FK users | |
| added_by | FK users | |
| created_at | datetime | |

**shifts**
| Column | Type | Notes |
|---|---|---|
| id | integer PK | |
| program_id | FK programs | indexed |
| date | date | indexed |
| start_time | time | |
| duration_minutes | integer | CHECK 1..1440 |
| location | varchar(200) | |
| required_headcount | integer | CHECK >= 1 |
| signup_count | integer | CHECK >= 0 and <= required_headcount. Denormalised, see below |
| state | varchar(20) | CHECK in (`open`, `partially_filled`, `filled`, `closed`). Denormalised |
| starts_at, ends_at | datetime | derived from date + start_time + duration. Indexed together |
| closed_at | datetime, null | set when a coordinator closes the shift |
| deleted_at | datetime, null | soft delete |
| created_by | FK users | |
| created_at | datetime | |

Unique partial index `(program_id, date, start_time) WHERE deleted_at IS NULL`: one live shift per program
per start slot.

**signups**
| Column | Type | Notes |
|---|---|---|
| id | integer PK | |
| shift_id | FK shifts | |
| volunteer_id | FK users | indexed |
| created_by | FK users | the volunteer themself or a coordinator |
| created_at | datetime | indexed (dashboard weekly counts) |
| cancelled_at | datetime, null | a cancelled row is kept, not deleted |
| cancelled_by | FK users, null | |

Unique partial index `(shift_id, volunteer_id) WHERE cancelled_at IS NULL`: at most one live signup per
person per shift, while a cancelled row does not block signing up again.

**shift_events** (the history; append-only)
| Column | Type | Notes |
|---|---|---|
| id | integer PK | ordering within a shift |
| shift_id | FK shifts | indexed with id |
| event_type | varchar(20) | CHECK in created, edited, signup, cancellation, state_change, note, deleted |
| actor_id | FK users | who did it |
| volunteer_id | FK users, null | who a signup/cancellation is about |
| old_state, new_state | varchar(20), null | filled for `state_change` |
| message | text | note text, edit diff, or a short reason |
| created_at | datetime | |

**alert_dismissals**
| Column | Type | Notes |
|---|---|---|
| shift_id | FK shifts, PK | row present = alert dismissed |
| dismissed_by | FK users | |
| dismissed_at | datetime | |

## Relationships

- **One-to-many:** program -> shifts, shift -> signups, shift -> events, user -> signups (as volunteer),
  user -> events (as actor).
- **Many-to-many:** programs <-> volunteers through `program_members`. (A volunteer joins any number of
  programs; a program has any number of volunteers.) volunteers <-> shifts through `signups`, which is also
  an entity with its own history (created_by, cancelled_at).

## What the database enforces vs. what the application enforces

**In the database** (so a bug or a second client cannot break them):
- uniqueness of email, one live shift per program slot, one live signup per volunteer per shift
- value domains: role, state, event type, headcount >= 1, duration 1..1440
- `signup_count` between 0 and `required_headcount`, a backstop against overfilling
- foreign keys everywhere
- **the history is append-only**: triggers raise an error on UPDATE, DELETE (and TRUNCATE on Postgres) for
  `shift_events`. The tests try the raw SQL and expect it to fail
- row level security on every table (Postgres), so Supabase's REST API exposes nothing

**In the application** (`services/`), because they need context or a readable message:
- who may do what (role and membership), program archived or not
- the lifecycle transitions: Filled/Closed shifts take no signups, closing only after the shift ends, a closed
  shift locks signups and cancellations
- **overlap detection**: a range-intersection query across *all* of a volunteer's live signups, in any
  program. This could be a Postgres exclusion constraint, but it would not run on SQLite and cannot return
  the message "you already hold X". The race is closed with a row lock on the volunteer instead
- deriving `state` from the counts, and recording state changes
- clearing an alert dismissal when a Filled shift drops back
- keeping `starts_at/ends_at` in step with date/time/duration

The line: *shape and uniqueness* in the database, *rules that need other rows, the clock, or a good error
message* in code.

## Deliberate denormalisation

- `shifts.signup_count` and `shifts.state`: duplicates of what `COUNT(signups)` would give. Search needs to
  filter and sort by fill state and show "3/4" for a page of shifts without a join and group-by per row.
  Both are written only in `services/signups.py` and `services/shifts.py::refresh_state`, under the shift row
  lock, in the same transaction as the signup, and the CHECK constraints bound the damage if they drift.
- `shifts.starts_at/ends_at`: derived from date + start_time + duration so the overlap query is a plain
  indexed range comparison.
- `signups` keep cancelled rows (with `cancelled_at`) instead of deleting, which is also what the dashboard's
  "signups made this week" and the roster rely on.

## What breaks first at 100x the data

- **`shift_events`** grows fastest (several rows per signup). Listing one shift's timeline is index-backed and
  fine, but the table needs partitioning or archiving of old shifts eventually.
- **Dashboard** counts scan `shifts` and `signups` per request (grouped counts, 8 weekly counts). They are
  cheap now; at 100x they need either composite indexes or a nightly rollup table.
- **Search text matching** uses `ILIKE '%term%'` on program name and location, which cannot use a btree
  index. At 100x it needs a trigram (`pg_trgm`) index or full-text search.
- **Row locks**: signing up locks the volunteer and the shift row; a very popular shift serialises its
  signups. That is correct and still fast, but it is the contention point.
- **The Supabase free tier** itself (500 MB, connection limits, pooler) would be reached long before Postgres
  was.
- **Overlap query** is indexed by `(starts_at, ends_at)` but filters per volunteer by join; a volunteer with
  thousands of lifetime signups would want `(volunteer_id, starts_at)` on a signup-side copy of the window.
