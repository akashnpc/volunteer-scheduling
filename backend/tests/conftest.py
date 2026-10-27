import sys
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import clock  # noqa: E402
from app.db import get_db  # noqa: E402
from app.db_setup import init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import COORDINATOR, VOLUNTEER, Program, ProgramMember, User  # noqa: E402
from app.security import create_token, hash_password  # noqa: E402

# Wednesday 4 Nov 2026, noon. Every test runs at this frozen moment.
NOW = datetime(2026, 11, 4, 12, 0)


@pytest.fixture(autouse=True)
def frozen_clock():
    clock.set_override(NOW)
    yield
    clock.set_override(None)


@pytest.fixture()
def engine():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    init_db(eng)
    return eng


@pytest.fixture()
def session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def client(session_factory):
    def override():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


class World:
    """A coordinator, three volunteers and one program everyone belongs to."""

    def __init__(self, session_factory):
        self.sf = session_factory
        with session_factory() as db:
            self.coord = self._user(db, "Cora Coord", "cora@example.com", COORDINATOR)
            self.vols = [self._user(db, f"Vol {n}", f"vol{n}@example.com", VOLUNTEER) for n in (1, 2, 3)]
            self.program = Program(name="Food Pantry", description="", created_by=self.coord.id, created_at=NOW)
            db.add(self.program)
            db.flush()
            for v in self.vols:
                db.add(ProgramMember(program_id=self.program.id, user_id=v.id, added_by=self.coord.id, created_at=NOW))
            db.commit()
            self.program_id = self.program.id

    @staticmethod
    def _user(db, name, email, role):
        user = User(name=name, email=email, password_hash=hash_password("Password1!"), role=role, created_at=NOW)
        db.add(user)
        db.flush()
        return user

    @staticmethod
    def auth(user) -> dict:
        return {"Authorization": f"Bearer {create_token(user.id)}"}

    def make_program(self, name="Other Program", members=()):
        with self.sf() as db:
            program = Program(name=name, description="", created_by=self.coord.id, created_at=NOW)
            db.add(program)
            db.flush()
            for v in members:
                db.add(ProgramMember(program_id=program.id, user_id=v.id, added_by=self.coord.id, created_at=NOW))
            db.commit()
            return program.id


@pytest.fixture()
def world(client, session_factory):
    return World(session_factory)


@pytest.fixture()
def make_shift(client, world):
    def _make(day="2026-11-10", start="09:00", minutes=120, headcount=2, program_id=None, location="Hall"):
        r = client.post(
            "/api/shifts",
            headers=world.auth(world.coord),
            json={
                "program_id": program_id or world.program_id, "date": day, "start_time": start,
                "duration_minutes": minutes, "location": location, "required_headcount": headcount,
            },
        )
        assert r.status_code == 201, r.text
        return r.json()

    return _make
