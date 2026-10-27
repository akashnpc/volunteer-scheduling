"""Recurring weekly schedule generator (goal 7)."""
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import bad_request
from app.models import Program, Shift, User
from app.schemas import ScheduleIn
from app.services import shifts

MAX_SPAN_DAYS = 366


def generate(db: Session, program: Program, data: ScheduleIn, actor: User):
    """Create one shift per matching weekday in the range. All or nothing (one transaction)."""
    if data.end_date < data.start_date:
        raise bad_request("end_date must not be before start_date")
    if (data.end_date - data.start_date).days > MAX_SPAN_DAYS:
        raise bad_request(f"The date range can span at most {MAX_SPAN_DAYS} days")
    shifts.ensure_program_writable(program)

    first = data.start_date + timedelta(days=(data.day_of_week - data.start_date.weekday()) % 7)
    dates = []
    day = first
    while day <= data.end_date:
        dates.append(day)
        day += timedelta(days=7)

    existing = set(
        db.scalars(
            select(Shift.date).where(
                Shift.program_id == program.id,
                Shift.start_time == data.start_time,
                Shift.deleted_at.is_(None),
                Shift.date.in_(dates),
            )
        )
    ) if dates else set()
    holidays = set(data.excluded_dates)

    created, skipped = [], []
    for day in dates:
        if day in holidays:
            skipped.append({"date": day, "reason": "excluded_holiday"})
        elif day in existing:
            skipped.append({"date": day, "reason": "already_exists"})
        else:
            created.append(
                shifts.create_shift_row(
                    db, program, day, data.start_time, data.duration_minutes,
                    data.location, data.required_headcount, actor,
                )
            )
    return created, skipped
