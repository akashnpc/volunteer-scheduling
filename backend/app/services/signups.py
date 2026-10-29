"""Signup rules (goal 4). All state changes go through create_signup / cancel_row."""
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import clock
from app.errors import conflict, forbidden, not_found
from app.models import CLOSED, COORDINATOR, FILLED, VOLUNTEER, Shift, Signup, User
from app.services import events, shifts


def create_signup(db: Session, shift_id: int, volunteer_id: int, actor: User) -> Signup:
    # Lock order is always user -> shift. Locking the volunteer serialises two
    # simultaneous signups by the same person, so the overlap check below cannot
    # be raced; locking the shift protects the headcount.
    volunteer = db.scalars(select(User).where(User.id == volunteer_id).with_for_update()).first()
    if volunteer is None or volunteer.role != VOLUNTEER:
        raise not_found("Volunteer not found")
    shift = shifts.load_shift(db, shift_id, lock=True)
    program = shift.program
    acting_for_self = actor.id == volunteer.id

    shifts.ensure_program_writable(program)
    if not shifts.is_member(db, volunteer.id, program.id):
        who = "You must" if acting_for_self else f"{volunteer.name} must"
        message = f'{who} be a member of "{program.name}" before signing up for its shifts'
        raise (forbidden if acting_for_self else conflict)(message)
    if shift.state == CLOSED:
        raise conflict("This shift is closed, so it no longer accepts signups")
    if shift.state == FILLED:
        raise conflict(
            f"This shift is already filled ({shift.signup_count} of {shift.required_headcount} spots taken)"
        )
    already = db.scalars(
        select(Signup.id).where(
            Signup.shift_id == shift.id, Signup.volunteer_id == volunteer.id, Signup.cancelled_at.is_(None)
        )
    ).first()
    if already:
        raise conflict(f"{'You are' if acting_for_self else volunteer.name + ' is'} already signed up for this shift")
    clash = shifts.find_overlap(db, volunteer.id, shift.starts_at, shift.ends_at, exclude_shift_id=shift.id)
    if clash:
        raise conflict(
            f"{'You' if acting_for_self else volunteer.name} already "
            f"{'hold' if acting_for_self else 'holds'} an overlapping shift: {shifts.describe(clash)}"
        )

    signup = Signup(
        shift_id=shift.id, volunteer_id=volunteer.id, created_by=actor.id, created_at=clock.now()
    )
    db.add(signup)
    try:
        db.flush()
    except IntegrityError:  # unique index backstop if two requests slipped through
        db.rollback()
        raise conflict("That signup already exists") from None
    shift.signup_count += 1
    events.log(
        db, shift.id, "signup", actor.id, volunteer_id=volunteer.id,
        message="Signed up" if acting_for_self else f"Signed up by {actor.name}",
    )
    shifts.refresh_state(db, shift, actor.id)
    return signup


def cancel_row(db: Session, signup: Signup, shift: Shift, actor: User, reason: str = "", refresh: bool = True) -> None:
    """Cancel one active signup on an already-locked shift and record it."""
    signup.cancelled_at = clock.now()
    signup.cancelled_by = actor.id
    shift.signup_count -= 1
    by_self = actor.id == signup.volunteer_id
    note = reason or ("Cancelled" if by_self else f"Cancelled by {actor.name}")
    events.log(db, shift.id, "cancellation", actor.id, volunteer_id=signup.volunteer_id, message=note)
    if refresh:
        shifts.refresh_state(db, shift, actor.id)


def cancel_signup(db: Session, signup_id: int, actor: User) -> Shift:
    signup = db.get(Signup, signup_id)
    if signup is None:
        raise not_found("Signup not found")
    if actor.role != COORDINATOR and signup.volunteer_id != actor.id:
        raise forbidden("You can only cancel your own signups")
    shift = shifts.load_shift(db, signup.shift_id, lock=True)
    db.refresh(signup)  # another request may have cancelled it while we waited for the lock
    if signup.cancelled_at is not None:
        raise conflict("This signup was already cancelled")
    if shift.state == CLOSED:
        raise conflict("This shift is closed, so its signups can no longer be cancelled")
    cancel_row(db, signup, shift, actor)
    return shift


def cancel_for_removed_member(db: Session, program_id: int, volunteer_id: int, actor: User) -> int:
    """When a volunteer leaves a program, drop their live signups in it (closed shifts stay as history)."""
    rows = db.execute(
        select(Signup.id, Signup.shift_id)
        .join(Shift, Shift.id == Signup.shift_id)
        .where(
            Signup.volunteer_id == volunteer_id,
            Signup.cancelled_at.is_(None),
            Shift.program_id == program_id,
            Shift.deleted_at.is_(None),
            Shift.state != CLOSED,
        )
    ).all()
    for signup_id, shift_id in rows:
        shift = shifts.load_shift(db, shift_id, lock=True)
        signup = db.get(Signup, signup_id)
        db.refresh(signup)
        if signup.cancelled_at is None:
            cancel_row(db, signup, shift, actor, reason="Removed from the program by a coordinator")
    return len(rows)
