"""The only code that writes to shift_events. It only ever inserts."""
from sqlalchemy.orm import Session

from app import clock
from app.models import ShiftEvent


def log(
    db: Session,
    shift_id: int,
    event_type: str,
    actor_id: int,
    *,
    volunteer_id: int | None = None,
    old_state: str | None = None,
    new_state: str | None = None,
    message: str = "",
) -> ShiftEvent:
    event = ShiftEvent(
        shift_id=shift_id,
        event_type=event_type,
        actor_id=actor_id,
        volunteer_id=volunteer_id,
        old_state=old_state,
        new_state=new_state,
        message=message,
        created_at=clock.now(),
    )
    db.add(event)
    return event
