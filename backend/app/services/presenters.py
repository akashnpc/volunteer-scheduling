"""Turning shift rows into API output models."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import STATE_LABELS, Shift, Signup, User
from app.schemas import ShiftOut


def to_out(shift: Shift, my_signup_id: int | None = None) -> ShiftOut:
    return ShiftOut(
        id=shift.id,
        program_id=shift.program_id,
        program_name=shift.program.name,
        program_archived=shift.program.archived_at is not None,
        date=shift.date,
        start_time=shift.start_time,
        duration_minutes=shift.duration_minutes,
        location=shift.location,
        required_headcount=shift.required_headcount,
        signup_count=shift.signup_count,
        spots_left=max(shift.required_headcount - shift.signup_count, 0),
        state=shift.state,
        state_label=STATE_LABELS[shift.state],
        starts_at=shift.starts_at,
        ends_at=shift.ends_at,
        my_signup_id=my_signup_id,
    )


def my_signup_ids(db: Session, user: User, shift_ids: list[int]) -> dict[int, int]:
    """The user's live signup id for each of the given shifts that they hold."""
    if not shift_ids:
        return {}
    rows = db.execute(
        select(Signup.shift_id, Signup.id).where(
            Signup.volunteer_id == user.id,
            Signup.cancelled_at.is_(None),
            Signup.shift_id.in_(shift_ids),
        )
    )
    return dict(rows.tuples().all())
