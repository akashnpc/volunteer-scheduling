from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clock
from app.db import get_db
from app.deps import coordinator_only
from app.errors import conflict
from app.models import User
from app.schemas import UserCreateIn, UserOut
from app.security import hash_password

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(coordinator_only)])


@router.get("", response_model=list[UserOut])
def list_users(role: str | None = None, db: Session = Depends(get_db)):
    stmt = select(User).order_by(User.name, User.id)
    if role:
        stmt = stmt.where(User.role == role)
    return db.scalars(stmt).all()


@router.post("", response_model=UserOut, status_code=201)
def create_user(data: UserCreateIn, db: Session = Depends(get_db)):
    email = data.email.lower()
    if db.scalars(select(User.id).where(User.email == email)).first():
        raise conflict("An account with that email already exists")
    user = User(
        name=data.name, email=email, password_hash=hash_password(data.password),
        role=data.role, created_at=clock.now(),
    )
    db.add(user)
    db.commit()
    return user
