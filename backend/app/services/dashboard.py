"""Dashboard numbers (goal 8). "This week" is Monday 00:00 to the following Monday 00:00."""
from datetime import datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import clock
from app.models import CLOSED, COORDINATOR, FILLED, OPEN, PARTIAL, Program, Shift, Signup, User
from app.services import shifts

STATES = [OPEN, PARTIAL, FILLED, CLOSED]


def build(db: Session, user: User) -> dict:
    today = clock.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=7)  # exclusive

    def at(d):
        return datetime.combine(d, time.min)

    shift_scope = [Shift.deleted_at.is_(None), Program.archived_at.is_(None)]
    program_scope = [Program.archived_at.is_(None)]
    if user.role != COORDINATOR:
        shift_scope.append(Shift.program_id.in_(shifts.visible_program_ids(user)))
        program_scope.append(Program.id.in_(shifts.visible_program_ids(user)))

    def count_shifts(*extra) -> int:
        return db.scalar(
            select(func.count(Shift.id)).join(Program, Program.id == Shift.program_id).where(*shift_scope, *extra)
        ) or 0

    def count_signups(start, end) -> int:
        # Counts signups *made* in the window, including ones cancelled since.
        return db.scalar(
            select(func.count(Signup.id))
            .join(Shift, Shift.id == Signup.shift_id)
            .join(Program, Program.id == Shift.program_id)
            .where(*shift_scope, Signup.created_at >= at(start), Signup.created_at < at(end))
        ) or 0

    in_week = (Shift.date >= week_start, Shift.date < week_end)

    by_state = {s: 0 for s in STATES}
    for state, n in db.execute(
        select(Shift.state, func.count(Shift.id))
        .join(Program, Program.id == Shift.program_id)
        .where(*shift_scope)
        .group_by(Shift.state)
    ):
        by_state[state] = n

    programs = db.scalars(select(Program).where(*program_scope).order_by(Program.name)).all()
    per_program = {p.id: {"program_id": p.id, "program_name": p.name, **{s: 0 for s in STATES}} for p in programs}
    for program_id, state, n in db.execute(
        select(Shift.program_id, Shift.state, func.count(Shift.id))
        .join(Program, Program.id == Shift.program_id)
        .where(*shift_scope)
        .group_by(Shift.program_id, Shift.state)
    ):
        per_program[program_id][state] = n
    for row in per_program.values():
        row["total"] = sum(row[s] for s in STATES)

    weekly = []
    for i in range(7, -1, -1):
        start = week_start - timedelta(weeks=i)
        weekly.append({"week_start": start, "signups": count_signups(start, start + timedelta(days=7))})

    return {
        "week_start": week_start,
        "week_end": week_end - timedelta(days=1),
        "shifts_this_week": count_shifts(*in_week),
        "open_shifts_this_week": count_shifts(*in_week, Shift.state == OPEN),
        "signups_this_week": count_signups(week_start, week_end),
        "shifts_closed_this_week": count_shifts(
            Shift.closed_at >= at(week_start), Shift.closed_at < at(week_end)
        ),
        "by_state": by_state,
        "by_program": list(per_program.values()),
        "signups_per_week": weekly,
    }
