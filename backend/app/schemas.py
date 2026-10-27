"""Request and response shapes. Roles and fill states are never accepted from clients
except where a coordinator explicitly creates a user."""
from datetime import date as DateType, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- auth / users -------------------------------------------------------
class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=72)


class UserCreateIn(RegisterIn):
    role: Literal["coordinator", "volunteer"] = "volunteer"


class UserOut(ORM):
    id: int
    name: str
    email: str
    role: str


class TokenOut(BaseModel):
    access_token: str
    user: UserOut


# ---- programs -----------------------------------------------------------
class ProgramIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class ProgramPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)


class ProgramOut(ORM):
    id: int
    name: str
    description: str
    archived: bool
    shift_count: int
    member_count: int


class MemberIn(BaseModel):
    user_id: int


# ---- shifts -------------------------------------------------------------
class ShiftIn(BaseModel):
    program_id: int
    date: DateType
    start_time: time
    duration_minutes: int = Field(ge=1, le=1440)
    location: str = Field(min_length=1, max_length=200)
    required_headcount: int = Field(ge=1, le=1000)

    @field_validator("start_time")
    @classmethod
    def drop_seconds(cls, v: time) -> time:
        return v.replace(second=0, microsecond=0, tzinfo=None)


class ShiftPatch(BaseModel):
    date: DateType | None = None
    start_time: time | None = None
    duration_minutes: int | None = Field(default=None, ge=1, le=1440)
    location: str | None = Field(default=None, min_length=1, max_length=200)
    required_headcount: int | None = Field(default=None, ge=1, le=1000)

    @field_validator("start_time")
    @classmethod
    def drop_seconds(cls, v: time | None) -> time | None:
        return v.replace(second=0, microsecond=0, tzinfo=None) if v else v


class ShiftOut(BaseModel):
    id: int
    program_id: int
    program_name: str
    program_archived: bool
    date: DateType
    start_time: time
    duration_minutes: int
    location: str
    required_headcount: int
    signup_count: int
    spots_left: int
    state: str
    state_label: str
    starts_at: datetime
    ends_at: datetime
    my_signup_id: int | None = None


class SignupOut(BaseModel):
    id: int
    shift_id: int
    volunteer_id: int
    volunteer_name: str
    volunteer_email: str
    created_at: datetime
    created_by: int


class ShiftDetailOut(ShiftOut):
    signups: list[SignupOut]
    dismissed_alert: bool = False


class ShiftPage(BaseModel):
    items: list[ShiftOut]
    total: int
    page: int
    page_size: int
    pages: int


class SignupIn(BaseModel):
    # Volunteers omit this (it is always themselves). Coordinators must set it.
    volunteer_id: int | None = None


class NoteIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)

    @field_validator("message")
    @classmethod
    def strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class EventOut(BaseModel):
    id: int
    event_type: str
    actor_id: int
    actor_name: str
    volunteer_id: int | None
    volunteer_name: str | None
    old_state: str | None
    new_state: str | None
    message: str
    created_at: datetime


# ---- alerts -------------------------------------------------------------
class AlertOut(ShiftOut):
    dismissed: bool


class AlertsOut(BaseModel):
    count: int  # undismissed alerts: what the navigation badge shows
    items: list[AlertOut]


# ---- recurring schedule ---------------------------------------------------
class ScheduleIn(BaseModel):
    start_date: DateType
    end_date: DateType
    day_of_week: int = Field(ge=0, le=6, description="0 = Monday ... 6 = Sunday")
    start_time: time
    duration_minutes: int = Field(ge=1, le=1440)
    location: str = Field(min_length=1, max_length=200)
    required_headcount: int = Field(ge=1, le=1000)
    excluded_dates: list[DateType] = Field(default_factory=list, max_length=366)

    @field_validator("start_time")
    @classmethod
    def drop_seconds(cls, v: time) -> time:
        return v.replace(second=0, microsecond=0, tzinfo=None)


class SkippedDate(BaseModel):
    date: DateType
    reason: Literal["excluded_holiday", "already_exists"]


class ScheduleOut(BaseModel):
    created: list[ShiftOut]
    skipped: list[SkippedDate]
