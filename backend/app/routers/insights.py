"""Dashboard (goal 8) and understaffed alerts (goal 10)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import coordinator_only, current_user
from app.models import User
from app.schemas import AlertOut, AlertsOut
from app.services import alerts, dashboard, presenters, shifts

router = APIRouter(tags=["insights"])


@router.get("/dashboard")
def get_dashboard(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return dashboard.build(db, user)


@router.get("/alerts", response_model=AlertsOut)
def get_alerts(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = alerts.list_alerts(db, user)
    mine = presenters.my_signup_ids(db, user, [s.id for s, _ in rows])
    return AlertsOut(
        count=sum(1 for _, dismissed in rows if not dismissed),
        items=[
            AlertOut(**presenters.to_out(s, mine.get(s.id)).model_dump(), dismissed=dismissed)
            for s, dismissed in rows
        ],
    )


@router.post("/alerts/{shift_id}/dismiss", response_model=AlertsOut)
def dismiss_alert(shift_id: int, user: User = Depends(coordinator_only), db: Session = Depends(get_db)):
    alerts.dismiss(db, shifts.load_shift(db, shift_id), user)
    db.commit()
    return get_alerts(user, db)
