"""Shift search (goal 6): filters, text match, sorting and pagination, all in the database."""
from datetime import date

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, contains_eager

from app.errors import bad_request
from app.models import COORDINATOR, FILLED, OPEN, PARTIAL, STATE_LABELS, Program, Shift, Signup, User
from app.services.shifts import visible_program_ids

STATE_ORDER = case(
    (Shift.state == OPEN, 0),
    (Shift.state == PARTIAL, 1),
    (Shift.state == FILLED, 2),
    else_=3,
)

SORT_KEYS = {
    "date": [Shift.date, Shift.start_time],
    "start_time": [Shift.start_time, Shift.date],
    "state": [STATE_ORDER, Shift.date, Shift.start_time],
}


def _like_escape(token: str) -> str:
    return token.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_shifts(
    db: Session, user: User, *, q: str | None, program_id: int | None, state: str | None,
    date_from: date | None, date_to: date | None, mine: bool, include_archived: bool,
    sort: str, order: str, page: int, page_size: int,
) -> tuple[list[Shift], int]:
    if state and state not in STATE_LABELS:
        raise bad_request(f"Unknown fill state '{state}'")
    if sort not in SORT_KEYS:
        raise bad_request("sort must be one of: date, start_time, state")

    conds = [Shift.deleted_at.is_(None)]
    if user.role == COORDINATOR:
        if not include_archived:
            conds.append(Program.archived_at.is_(None))
    else:
        conds += [Program.archived_at.is_(None), Shift.program_id.in_(visible_program_ids(user))]
    if program_id is not None:
        conds.append(Shift.program_id == program_id)
    if state:
        conds.append(Shift.state == state)
    if date_from:
        conds.append(Shift.date >= date_from)
    if date_to:
        conds.append(Shift.date <= date_to)
    if mine:
        conds.append(
            Shift.id.in_(
                select(Signup.shift_id).where(Signup.volunteer_id == user.id, Signup.cancelled_at.is_(None))
            )
        )
    for token in (q or "").split():
        pattern = f"%{_like_escape(token)}%"
        conds.append(or_(Program.name.ilike(pattern, escape="\\"), Shift.location.ilike(pattern, escape="\\")))

    ordering = [k.desc() if order == "desc" else k.asc() for k in SORT_KEYS[sort]] + [Shift.id.asc()]

    total = db.scalar(select(func.count(Shift.id)).join(Program, Program.id == Shift.program_id).where(*conds))
    rows = db.scalars(
        select(Shift)
        .join(Program, Program.id == Shift.program_id)
        .options(contains_eager(Shift.program))
        .where(*conds)
        .order_by(*ordering)
        .limit(page_size)
        .offset((page - 1) * page_size)
    ).all()
    return rows, total or 0
