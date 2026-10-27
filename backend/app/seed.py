"""Demo data, built through the real service functions so the history and alerts are genuine.

Run automatically on startup when SEED_ON_STARTUP=true and the database is empty, or by hand:
    python -m app.seed
Dates are relative to today, so alerts and the dashboard always have something to show.
"""
import random
from datetime import datetime, time, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import clock, config
from app.models import COORDINATOR, VOLUNTEER, Program, ProgramMember, Shift, Signup, User
from app.schemas import ScheduleIn
from app.security import hash_password
from app.services import alerts, schedule, shifts, signups

COORDINATORS = [("Casey Coordinator", "coordinator@example.com")]
VOLUNTEERS = [
    ("Alice Johnson", "alice@example.com"),
    ("Bob Martinez", "bob@example.com"),
    ("Carol Singh", "carol@example.com"),
    ("Dave Okafor", "dave@example.com"),
    ("Erin Walsh", "erin@example.com"),
    ("Frank Li", "frank@example.com"),
]

# name, description, weekly patterns (weekday 0=Mon, start, minutes, location, headcount), member indexes
PROGRAMS = [
    ("Food Pantry", "Sort donations and hand out groceries to local families.",
     [(1, time(9), 180, "Community Hall", 4), (3, time(9), 180, "Community Hall", 4)], [0, 1, 2, 3]),
    ("Weekend Trail Cleanup", "Litter pick-up and trail maintenance on the ridge.",
     [(5, time(8), 240, "Ridge Trailhead", 6)], [1, 2, 4, 5]),
    ("Tutoring Drive", "After-school homework help for grades 3-8.",
     [(0, time(16), 120, "Public Library", 3), (3, time(10), 120, "Public Library", 3)], [0, 2, 3, 4, 5]),
]


def at(moment: datetime):
    clock.set_override(moment)


def seed_if_empty(db: Session) -> bool:
    if db.scalar(select(func.count(User.id))):
        return False
    rng = random.Random(7)
    real_now = clock.now()
    history_start = real_now - timedelta(days=56)  # eight weeks, so the weekly chart has data

    at(history_start)
    password_hash = hash_password(config.SEED_PASSWORD)
    coordinators = [User(name=n, email=e, password_hash=password_hash, role=COORDINATOR, created_at=clock.now())
                    for n, e in COORDINATORS]
    volunteers = [User(name=n, email=e, password_hash=password_hash, role=VOLUNTEER, created_at=clock.now())
                  for n, e in VOLUNTEERS]
    db.add_all(coordinators + volunteers)
    db.flush()
    boss = coordinators[0]

    plans = []  # (program, members)
    for name, description, patterns, member_idx in PROGRAMS:
        program = Program(name=name, description=description, created_by=boss.id, created_at=clock.now())
        db.add(program)
        db.flush()
        members = [volunteers[i] for i in member_idx]
        for v in members:
            db.add(ProgramMember(program_id=program.id, user_id=v.id, added_by=boss.id, created_at=clock.now()))
        week_start = real_now.date() - timedelta(days=real_now.weekday())
        first_day, last_day = week_start - timedelta(weeks=3), week_start + timedelta(weeks=3, days=6)
        for weekday, start, minutes, location, headcount in patterns:
            holiday = [first_day + timedelta(days=(weekday - first_day.weekday()) % 7 + 14)]  # one holiday each
            schedule.generate(db, program, ScheduleIn(
                start_date=first_day, end_date=last_day, day_of_week=weekday, start_time=start,
                duration_minutes=minutes, location=location, required_headcount=headcount,
                excluded_dates=holiday), boss)
        plans.append((program, members))

    archived = Program(name="Winter Coat Drive", description="Collected coats (archived demo program).",
                       created_by=boss.id, created_at=clock.now(), archived_at=real_now - timedelta(days=10))
    db.add(archived)
    db.flush()

    today = real_now.date()
    window_end = today + timedelta(days=config.UNDERSTAFFED_WINDOW_DAYS)
    for program, members in plans:
        program_shifts = db.scalars(select(Shift).where(Shift.program_id == program.id).order_by(Shift.starts_at)).all()
        in_window = [s for s in program_shifts if today <= s.date <= window_end]
        for shift in program_shifts:
            if shift.date < today:
                target = rng.choice([shift.required_headcount] * 3 + [shift.required_headcount - 1, 1, 0])
            elif shift in in_window:
                # keep these short-staffed for the alerts demo; one is Filled so a
                # cancellation can show an alert returning
                target = shift.required_headcount if shift is in_window[-1] and len(in_window) > 1 \
                    else rng.randint(0, shift.required_headcount - 1)
            else:
                target = rng.randint(0, shift.required_headcount)
            actions = []
            earliest = history_start + timedelta(hours=2)
            latest = max(min(real_now - timedelta(minutes=5), shift.starts_at - timedelta(hours=1)), earliest)
            for volunteer in rng.sample(members, min(target, len(members))):
                # spread signups over the history, with a cluster just before the shift
                start_of_range = earliest if rng.random() > 0.35 else max(earliest, latest - timedelta(days=4))
                made = start_of_range + (latest - start_of_range) * rng.random()
                actions.append((made.replace(microsecond=0), "signup", volunteer))
            if shift.date < today:
                actions.append((shift.ends_at + timedelta(hours=1), "close", None))
            for when, kind, volunteer in sorted(actions, key=lambda a: a[0]):
                at(min(when, real_now))
                try:
                    if kind == "signup":
                        by_coordinator = rng.random() < 0.25
                        signups.create_signup(db, shift.id, volunteer.id, boss if by_coordinator else volunteer)
                    else:
                        shifts.close_shift(db, shift, boss)
                except HTTPException:
                    pass  # e.g. an overlap between programs: simply skip, like a real refusal would
            db.flush()

    # A few recent cancellations on upcoming shifts, plus one coordinator note, so the timelines have variety.
    at(real_now - timedelta(hours=3))
    live = db.scalars(
        select(Signup).join(Shift, Shift.id == Signup.shift_id)
        .where(Signup.cancelled_at.is_(None), Shift.state != "closed", Shift.date > today)
        .order_by(Signup.id)
    ).all()
    for signup in live[:: max(len(live) // 4, 1)][:4]:
        shift = shifts.load_shift(db, signup.shift_id, lock=True)
        signups.cancel_row(db, signup, shift, boss if rng.random() < 0.5 else signup.volunteer)
    upcoming = db.scalars(select(Shift).where(Shift.date >= today).order_by(Shift.starts_at).limit(1)).first()
    if upcoming:
        shifts.add_note(db, upcoming, "Bring gloves and closed-toe shoes please.", boss)

    at(real_now)
    shown = [s for s, dismissed in alerts.list_alerts(db, boss) if not dismissed]
    if shown:
        alerts.dismiss(db, shown[0], boss)
    db.commit()
    clock.set_override(None)
    return True


if __name__ == "__main__":
    from app.db import SessionLocal, engine
    from app.db_setup import init_db

    init_db(engine)
    with SessionLocal() as session:
        print("seeded" if seed_if_empty(session) else "database already has data; nothing to do")
