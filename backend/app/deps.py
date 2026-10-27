from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import forbidden
from app.models import COORDINATOR, User
from app.security import decode_token

bearer = HTTPBearer(auto_error=False)


def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    user_id = decode_token(creds.credentials) if creds else None
    user = db.get(User, user_id) if user_id is not None else None
    if user is None:
        raise HTTPException(status_code=401, detail="Please sign in again")
    return user


def coordinator_only(user: User = Depends(current_user)) -> User:
    """Server-side role gate: every coordinator endpoint depends on this."""
    if user.role != COORDINATOR:
        raise forbidden("Only coordinators can do this")
    return user
