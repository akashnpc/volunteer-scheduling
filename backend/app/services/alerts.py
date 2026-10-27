"""Understaffed shift alerts (goal 10).

A shift is understaffed when its date is today or within the next
UNDERSTAFFED_WINDOW_DAYS days and it is still Open or Partially Filled.
Dismissals live in alert_dismissals; services.shifts.set_state removes the row
when a Filled shift drops back, which is what makes the alert return.
"""
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, contains_eager

from app import clock, config
from app.errors import conflict
from app.models import COORDINATOR, OPEN, PARTIAL, AlertDismissal, Program, Shift, User
from app.services import shifts


def _understaffed_conditions(user: User):
    today = clock.today()
    conds = [
        Shift.deleted_at.is_(None),
        Shift.state.in_([OPEN, PARTIAL]),
        Shift.date >= today,
        Shift.date <= today + timedelta(days=config.UNDERSTAFFED_WINDOW_DAYS),
        Program.archived_at.is_(None),
    ]
    if user.role != COORDINATOR:
        conds.append(Shift.program_id.in_(shifts.visible_program_ids(user)))
    return conds


def list_alerts(db: Session, user: User) -> list[tuple[Shift, bool]]:
    """Every understaffed shift the viewer can see, with whether it is dismissed."""
    rows = db.execute(
        select(Shift, AlertDismissal.shift_id)
        .join(Program, Program.id == Shift.program_id)
        .outerjoin(AlertDismissal, AlertDismissal.shift_id == Shift.id)
        .options(contains_eager(Shift.program))
        .where(*_understaffed_conditions(user))
        .order_by(Shift.date, Shift.start_time, Shift.id)
    ).all()
    return [(shift, dismissed_id is not None) for shift, dismissed_id in rows]


def dismiss(db: Session, shift: Shift, actor: User) -> None:
    active_ids = {s.id for s, _ in list_alerts(db, actor)}
    if shift.id not in active_ids:
        raise conflict("This shift is not currently understaffed, so there is no alert to dismiss")
    if db.get(AlertDismissal, shift.id) is None:
        db.add(AlertDismissal(shift_id=shift.id, dismissed_by=actor.id, dismissed_at=clock.now()))
