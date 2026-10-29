import math
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import coordinator_only, current_user
from app.errors import bad_request, forbidden, not_found
from app.models import COORDINATOR, AlertDismissal, Program, ShiftEvent, Signup, User
from app.schemas import (
    EventOut,
    NoteIn,
    ShiftDetailOut,
    ShiftIn,
    ShiftOut,
    ShiftPage,
    ShiftPatch,
    SignupIn,
    SignupOut,
)
from app.services import presenters, search, shifts
from app.services.signups import create_signup

router = APIRouter(prefix="/shifts", tags=["shifts"])


def build_detail(db: Session, shift, user: User) -> ShiftDetailOut:
    stmt = (
        select(Signup, User)
        .join(User, User.id == Signup.volunteer_id)
        .where(Signup.shift_id == shift.id, Signup.cancelled_at.is_(None))
        .order_by(Signup.created_at, Signup.id)
    )
    if user.role != COORDINATOR:
        stmt = stmt.where(Signup.volunteer_id == user.id)  # volunteers only see their own signup
    signups = [
        SignupOut(
            id=s.id, shift_id=s.shift_id, volunteer_id=v.id, volunteer_name=v.name,
            volunteer_email=v.email, created_at=s.created_at, created_by=s.created_by,
        )
        for s, v in db.execute(stmt)
    ]
    mine = next((s.id for s in signups if s.volunteer_id == user.id), None)
    base = presenters.to_out(shift, mine)
    return ShiftDetailOut(
        **base.model_dump(),
        signups=signups,
        dismissed_alert=db.get(AlertDismissal, shift.id) is not None,
    )


@router.get("", response_model=ShiftPage)
def list_shifts(
    q: str | None = None,
    program_id: int | None = None,
    state: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    mine: bool = False,
    include_archived: bool = False,
    sort: Literal["date", "start_time", "state"] = "date",
    order: Literal["asc", "desc"] = "asc",
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    rows, total = search.search_shifts(
        db, user, q=q, program_id=program_id, state=state, date_from=date_from, date_to=date_to,
        mine=mine, include_archived=include_archived, sort=sort, order=order, page=page, page_size=page_size,
    )
    mine_ids = presenters.my_signup_ids(db, user, [s.id for s in rows])
    return ShiftPage(
        items=[presenters.to_out(s, mine_ids.get(s.id)) for s in rows],
        total=total, page=page, page_size=page_size, pages=max(math.ceil(total / page_size), 1),
    )


@router.post("", response_model=ShiftOut, status_code=201)
def create_shift(data: ShiftIn, user: User = Depends(coordinator_only), db: Session = Depends(get_db)):
    program = db.get(Program, data.program_id)
    if program is None:
        raise not_found("Program not found")
    shift = shifts.create_shift(db, program, data, user)
    db.commit()
    return presenters.to_out(shift)


@router.get("/{shift_id}", response_model=ShiftDetailOut)
def get_shift(shift_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    shift = shifts.load_shift(db, shift_id)
    shifts.ensure_can_view(db, user, shift)
    return build_detail(db, shift, user)


@router.patch("/{shift_id}", response_model=ShiftOut)
def edit_shift(
    shift_id: int, data: ShiftPatch, user: User = Depends(coordinator_only), db: Session = Depends(get_db)
):
    shift = shifts.update_shift(db, shifts.load_shift(db, shift_id, lock=True), data, user)
    db.commit()
    return presenters.to_out(shift)


@router.delete("/{shift_id}", status_code=204)
def delete_shift(shift_id: int, user: User = Depends(coordinator_only), db: Session = Depends(get_db)):
    shifts.delete_shift(db, shifts.load_shift(db, shift_id, lock=True), user)
    db.commit()
    return Response(status_code=204)


@router.post("/{shift_id}/close", response_model=ShiftOut)
def close_shift(shift_id: int, user: User = Depends(coordinator_only), db: Session = Depends(get_db)):
    shift = shifts.close_shift(db, shifts.load_shift(db, shift_id, lock=True), user)
    db.commit()
    return presenters.to_out(shift)


# ---- signups --------------------------------------------------------------------
@router.post("/{shift_id}/signups", response_model=ShiftDetailOut, status_code=201)
def sign_up(
    shift_id: int, data: SignupIn | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    data = data or SignupIn()
    if user.role == COORDINATOR:
        if data.volunteer_id is None:
            raise bad_request("Choose which volunteer to sign up")
        volunteer_id = data.volunteer_id
    else:
        if data.volunteer_id not in (None, user.id):
            raise forbidden("Volunteers can only sign themselves up")
        volunteer_id = user.id
    create_signup(db, shift_id, volunteer_id, user)
    db.commit()
    return build_detail(db, shifts.load_shift(db, shift_id), user)


# ---- timeline (goal 9) ------------------------------------------------------------
@router.get("/{shift_id}/timeline", response_model=list[EventOut])
def timeline(shift_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    shift = shifts.load_shift(db, shift_id)
    shifts.ensure_can_view(db, user, shift)
    events = db.scalars(select(ShiftEvent).where(ShiftEvent.shift_id == shift.id).order_by(ShiftEvent.id)).all()
    return [
        EventOut(
            id=e.id, event_type=e.event_type, actor_id=e.actor_id, actor_name=e.actor.name,
            volunteer_id=e.volunteer_id, volunteer_name=e.volunteer.name if e.volunteer else None,
            old_state=e.old_state, new_state=e.new_state, message=e.message, created_at=e.created_at,
        )
        for e in events
    ]


@router.post("/{shift_id}/notes", response_model=list[EventOut], status_code=201)
def add_note(shift_id: int, data: NoteIn, user: User = Depends(coordinator_only), db: Session = Depends(get_db)):
    shift = shifts.load_shift(db, shift_id, lock=True)
    shifts.add_note(db, shift, data.message, user)
    db.commit()
    return timeline(shift_id, user, db)
