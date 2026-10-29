"""Database tables. See docs/schema.md for the reasoning behind each constraint."""
from datetime import date as DateType
from datetime import datetime, time

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

COORDINATOR = "coordinator"
VOLUNTEER = "volunteer"

OPEN = "open"
PARTIAL = "partially_filled"
FILLED = "filled"
CLOSED = "closed"
STATE_LABELS = {
    OPEN: "Open",
    PARTIAL: "Partially Filled",
    FILLED: "Filled",
    CLOSED: "Closed",
}


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('coordinator','volunteer')", name="ck_users_role"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime)


class Program(Base):
    __tablename__ = "programs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    # NULL means active. Archiving never deletes shifts or signups.
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime)


class ProgramMember(Base):
    """Many-to-many between programs and volunteers."""

    __tablename__ = "program_members"

    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    added_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime)


class Shift(Base):
    __tablename__ = "shifts"
    __table_args__ = (
        CheckConstraint("required_headcount >= 1", name="ck_shifts_headcount_positive"),
        CheckConstraint("duration_minutes >= 1 AND duration_minutes <= 1440", name="ck_shifts_duration"),
        CheckConstraint("signup_count >= 0", name="ck_shifts_count_nonneg"),
        CheckConstraint("signup_count <= required_headcount", name="ck_shifts_not_overfilled"),
        CheckConstraint(
            "state IN ('open','partially_filled','filled','closed')", name="ck_shifts_state"
        ),
        # One live shift per program per date+time; this is what the recurring
        # generator relies on to report "already existed".
        Index(
            "uq_shifts_program_slot",
            "program_id",
            "date",
            "start_time",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_shifts_date", "date"),
        Index("ix_shifts_program", "program_id"),
        Index("ix_shifts_window", "starts_at", "ends_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id"))
    date: Mapped[DateType] = mapped_column(Date)
    start_time: Mapped[time] = mapped_column(Time)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    location: Mapped[str] = mapped_column(String(200))
    required_headcount: Mapped[int] = mapped_column(Integer)
    # Denormalised, maintained only by app.services.shifts.refresh_state().
    signup_count: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[str] = mapped_column(String(20), default=OPEN)
    starts_at: Mapped[datetime] = mapped_column(DateTime)
    ends_at: Mapped[datetime] = mapped_column(DateTime)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Soft delete: the history table must keep pointing at the shift.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime)

    program: Mapped[Program] = relationship()


class Signup(Base):
    __tablename__ = "signups"
    __table_args__ = (
        # A volunteer may hold at most one *active* signup per shift. A cancelled
        # row stays for history and does not block signing up again.
        Index(
            "uq_signups_active",
            "shift_id",
            "volunteer_id",
            unique=True,
            sqlite_where=text("cancelled_at IS NULL"),
            postgresql_where=text("cancelled_at IS NULL"),
        ),
        Index("ix_signups_volunteer", "volunteer_id"),
        Index("ix_signups_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    shift_id: Mapped[int] = mapped_column(ForeignKey("shifts.id"))
    volunteer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelled_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    shift: Mapped[Shift] = relationship()
    volunteer: Mapped[User] = relationship(foreign_keys=[volunteer_id])


class ShiftEvent(Base):
    """Append-only timeline. UPDATE/DELETE/TRUNCATE are blocked by triggers (app/db_setup.py)."""

    __tablename__ = "shift_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('created','edited','signup','cancellation','state_change','note','deleted')",
            name="ck_events_type",
        ),
        Index("ix_events_shift", "shift_id", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    shift_id: Mapped[int] = mapped_column(ForeignKey("shifts.id"))
    event_type: Mapped[str] = mapped_column(String(20))
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    # The volunteer a signup/cancellation is about (may differ from the actor).
    volunteer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    old_state: Mapped[str | None] = mapped_column(String(20), nullable=True)
    new_state: Mapped[str | None] = mapped_column(String(20), nullable=True)
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime)

    actor: Mapped[User] = relationship(foreign_keys=[actor_id])
    volunteer: Mapped[User | None] = relationship(foreign_keys=[volunteer_id])


class AlertDismissal(Base):
    """Presence of a row means the understaffed alert for that shift is dismissed."""

    __tablename__ = "alert_dismissals"

    shift_id: Mapped[int] = mapped_column(ForeignKey("shifts.id"), primary_key=True)
    dismissed_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    dismissed_at: Mapped[datetime] = mapped_column(DateTime)
