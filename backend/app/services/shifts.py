"""Shift rules: creation, editing, the fill-state machine, overlap, closing and deleting."""
from datetime import date, datetime, time, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import clock
from app.errors import conflict, not_found
from app.models import (
    CLOSED,
    COORDINATOR,
    FILLED,
    OPEN,
    PARTIAL,
    AlertDismissal,
    Program,
    ProgramMember,
    Shift,
    Signup,
    User,
)
from app.schemas import ShiftIn, ShiftPatch
from app.services import events


# ---- small pure helpers ----------------------------------------------------
def window(day: date, start: time, minutes: int) -> tuple[datetime, datetime]:
    starts = datetime.combine(day, start)
    return starts, starts + timedelta(minutes=minutes)


def derive_state(signup_count: int, required_headcount: int) -> str:
    """Fill level is a pure function of the counts; nothing sets it by hand."""
    if signup_count <= 0:
        return OPEN
    if signup_count < required_headcount:
        return PARTIAL
    return FILLED


# ---- visibility ---------------------------------------------------------
def is_member(db: Session, user_id: int, program_id: int) -> bool:
    return db.get(ProgramMember, (program_id, user_id)) is not None


def visible_program_ids(user: User):
    """Subquery of program ids a volunteer may see (coordinators see all)."""
    return select(ProgramMember.program_id).where(ProgramMember.user_id == user.id)


def load_shift(db: Session, shift_id: int, lock: bool = False) -> Shift:
    stmt = select(Shift).where(Shift.id == shift_id, Shift.deleted_at.is_(None))
    if lock:
        stmt = stmt.with_for_update()
    shift = db.scalars(stmt).first()
    if shift is None:
        raise not_found("Shift not found")
    return shift


def ensure_can_view(db: Session, user: User, shift: Shift) -> None:
    if user.role == COORDINATOR:
        return
    if shift.program.archived_at is not None or not is_member(db, user.id, shift.program_id):
        raise not_found("Shift not found")


def ensure_program_writable(program: Program) -> None:
    if program.archived_at is not None:
        raise conflict(f'Program "{program.name}" is archived. Restore it before changing its shifts.')


# ---- state machine ---------------------------------------------------------
def set_state(db: Session, shift: Shift, new_state: str, actor_id: int, message: str = "") -> None:
    old_state = shift.state
    if old_state == new_state:
        return
    shift.state = new_state
    events.log(
        db, shift.id, "state_change", actor_id,
        old_state=old_state, new_state=new_state, message=message,
    )
    if old_state == FILLED and new_state in (OPEN, PARTIAL):
        # Goal 10: a cancellation that un-fills a shift brings its alert back.
        db.execute(delete(AlertDismissal).where(AlertDismissal.shift_id == shift.id))


def refresh_state(db: Session, shift: Shift, actor_id: int) -> None:
    if shift.state == CLOSED:
        return
    set_state(db, shift, derive_state(shift.signup_count, shift.required_headcount), actor_id)


# ---- overlap ------------------------------------------------------------
def find_overlap(
    db: Session, volunteer_id: int, starts_at: datetime, ends_at: datetime, exclude_shift_id: int | None
) -> Shift | None:
    """A shift the volunteer already holds that intersects [starts_at, ends_at)."""
    stmt = (
        select(Shift)
        .join(Signup, Signup.shift_id == Shift.id)
        .where(
            Signup.volunteer_id == volunteer_id,
            Signup.cancelled_at.is_(None),
            Shift.deleted_at.is_(None),
            Shift.starts_at < ends_at,
            Shift.ends_at > starts_at,
        )
        .limit(1)
    )
    if exclude_shift_id is not None:
        stmt = stmt.where(Shift.id != exclude_shift_id)
    return db.scalars(stmt).first()


def describe(shift: Shift) -> str:
    return (
        f'"{shift.program.name}" on {shift.date:%a %d %b %Y}, '
        f"{shift.starts_at:%H:%M}-{shift.ends_at:%H:%M}"
    )


# ---- create / edit / close / delete -----------------------------------------
def slot_taken(db: Session, program_id: int, day: date, start: time, exclude_id: int | None = None) -> bool:
    stmt = select(Shift.id).where(
        Shift.program_id == program_id,
        Shift.date == day,
        Shift.start_time == start,
        Shift.deleted_at.is_(None),
    )
    if exclude_id is not None:
        stmt = stmt.where(Shift.id != exclude_id)
    return db.scalars(stmt.limit(1)).first() is not None


def create_shift_row(
    db: Session, program: Program, day: date, start: time, minutes: int,
    location: str, headcount: int, actor: User,
) -> Shift:
    starts_at, ends_at = window(day, start, minutes)
    shift = Shift(
        program_id=program.id, date=day, start_time=start, duration_minutes=minutes,
        location=location.strip(), required_headcount=headcount, signup_count=0, state=OPEN,
        starts_at=starts_at, ends_at=ends_at, created_by=actor.id, created_at=clock.now(),
    )
    shift.program = program
    db.add(shift)
    db.flush()
    events.log(
        db, shift.id, "created", actor.id,
        new_state=OPEN, message=f"Shift created, needs {headcount} volunteer(s)",
    )
    return shift


def create_shift(db: Session, program: Program, data: ShiftIn, actor: User) -> Shift:
    ensure_program_writable(program)
    if slot_taken(db, program.id, data.date, data.start_time):
        raise conflict(
            f'"{program.name}" already has a shift on {data.date:%d %b %Y} at {data.start_time:%H:%M}'
        )
    return create_shift_row(
        db, program, data.date, data.start_time, data.duration_minutes,
        data.location, data.required_headcount, actor,
    )


def update_shift(db: Session, shift: Shift, patch: ShiftPatch, actor: User) -> Shift:
    if shift.state == CLOSED:
        raise conflict("This shift is closed and can no longer be edited")
    ensure_program_writable(shift.program)

    changes = patch.model_dump(exclude_unset=True, exclude_none=True)
    new = {
        "date": changes.get("date", shift.date),
        "start_time": changes.get("start_time", shift.start_time),
        "duration_minutes": changes.get("duration_minutes", shift.duration_minutes),
        "location": changes.get("location", shift.location).strip(),
        "required_headcount": changes.get("required_headcount", shift.required_headcount),
    }
    if new["required_headcount"] < shift.signup_count:
        raise conflict(
            f"This shift already has {shift.signup_count} signup(s); the required headcount "
            f"cannot go below that. Cancel signups first."
        )
    starts_at, ends_at = window(new["date"], new["start_time"], new["duration_minutes"])
    time_changed = (starts_at, ends_at) != (shift.starts_at, shift.ends_at)
    if time_changed:
        if slot_taken(db, shift.program_id, new["date"], new["start_time"], exclude_id=shift.id):
            raise conflict("Another shift in this program already starts at that date and time")
        # Moving a shift must not silently double-book people who already signed up.
        volunteers = db.execute(
            select(User).join(Signup, Signup.volunteer_id == User.id).where(
                Signup.shift_id == shift.id, Signup.cancelled_at.is_(None)
            )
        ).scalars()
        for volunteer in volunteers:
            clash = find_overlap(db, volunteer.id, starts_at, ends_at, exclude_shift_id=shift.id)
            if clash:
                raise conflict(
                    f"Moving the shift would double-book {volunteer.name}, who also holds {describe(clash)}"
                )

    diffs = []
    for field, value in new.items():
        old = getattr(shift, field)
        if old != value:
            diffs.append(f"{field.replace('_', ' ')}: {old} -> {value}")
            setattr(shift, field, value)
    if not diffs:
        return shift
    shift.starts_at, shift.ends_at = starts_at, ends_at
    events.log(db, shift.id, "edited", actor.id, message="; ".join(diffs))
    refresh_state(db, shift, actor.id)  # a headcount change can move Filled <-> Partially Filled
    return shift


def close_shift(db: Session, shift: Shift, actor: User) -> Shift:
    if shift.state == CLOSED:
        raise conflict("This shift is already closed")
    if clock.now() < shift.ends_at:
        raise conflict(
            f"A shift can only be closed after its scheduled time has passed "
            f"(this one ends {shift.ends_at:%d %b %Y %H:%M})"
        )
    shift.closed_at = clock.now()
    set_state(db, shift, CLOSED, actor.id, message="Closed by coordinator")
    return shift


def delete_shift(db: Session, shift: Shift, actor: User) -> None:
    from app.services.signups import cancel_row  # local import: signups imports this module

    if shift.state == CLOSED:
        raise conflict("Closed shifts are kept for the record and cannot be deleted")
    active = db.scalars(select(Signup).where(Signup.shift_id == shift.id, Signup.cancelled_at.is_(None)))
    for signup in active:
        cancel_row(db, signup, shift, actor, reason="Shift was deleted", refresh=False)
    shift.deleted_at = clock.now()
    events.log(db, shift.id, "deleted", actor.id, message="Shift deleted by coordinator")


def add_note(db: Session, shift: Shift, message: str, actor: User) -> None:
    events.log(db, shift.id, "note", actor.id, message=message)
