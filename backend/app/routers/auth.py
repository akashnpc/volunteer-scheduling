from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clock
from app.db import get_db
from app.deps import current_user
from app.errors import conflict
from app.models import VOLUNTEER, User
from app.schemas import LoginIn, RegisterIn, TokenOut, UserOut
from app.security import create_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

# Compared against when the email is unknown, so response time does not reveal which emails exist.
_DUMMY_HASH = hash_password("not-a-real-password")


@router.post("/register", response_model=TokenOut, status_code=201)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    """Public sign-up always creates a volunteer. Coordinators are created by other coordinators."""
    email = data.email.lower()
    if db.scalars(select(User.id).where(User.email == email)).first():
        raise conflict("An account with that email already exists")
    user = User(
        name=data.name, email=email, password_hash=hash_password(data.password),
        role=VOLUNTEER, created_at=clock.now(),
    )
    db.add(user)
    db.commit()
    return TokenOut(access_token=create_token(user.id), user=user)


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.scalars(select(User).where(User.email == data.email.lower())).first()
    ok = verify_password(data.password, user.password_hash if user else _DUMMY_HASH)
    if user is None or not ok:
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return TokenOut(access_token=create_token(user.id), user=user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user
