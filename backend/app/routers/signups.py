from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models import User
from app.routers.shifts import build_detail
from app.schemas import ShiftDetailOut
from app.services.signups import cancel_signup

router = APIRouter(prefix="/signups", tags=["signups"])


@router.delete("/{signup_id}", response_model=ShiftDetailOut)
def cancel(signup_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Cancel a signup: the volunteer cancels their own, a coordinator may cancel anyone's."""
    shift = cancel_signup(db, signup_id, user)
    db.commit()
    return build_detail(db, shift, user)
