import re

from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import clock
from app.db import get_db
from app.deps import coordinator_only, current_user
from app.errors import bad_request, conflict, not_found
from app.models import COORDINATOR, VOLUNTEER, Program, ProgramMember, Shift, User
from app.schemas import (
    MemberIn,
    ProgramIn,
    ProgramOut,
    ProgramPatch,
    ScheduleIn,
    ScheduleOut,
    UserOut,
)
from app.services import presenters, roster, schedule, shifts
from app.services.signups import cancel_for_removed_member

router = APIRouter(prefix="/programs", tags=["programs"])


def _out(db: Session, programs: list[Program]) -> list[ProgramOut]:
    ids = [p.id for p in programs]
    shift_counts = dict(
        db.execute(
            select(Shift.program_id, func.count(Shift.id))
            .where(Shift.program_id.in_(ids), Shift.deleted_at.is_(None))
            .group_by(Shift.program_id)
        ).all()
    )
    member_counts = dict(
        db.execute(
            select(ProgramMember.program_id, func.count(ProgramMember.user_id))
            .where(ProgramMember.program_id.in_(ids))
            .group_by(ProgramMember.program_id)
        ).all()
    )
    return [
        ProgramOut(
            id=p.id, name=p.name, description=p.description, archived=p.archived_at is not None,
            shift_count=shift_counts.get(p.id, 0), member_count=member_counts.get(p.id, 0),
        )
        for p in programs
    ]


def _get(db: Session, program_id: int, user: User) -> Program:
    """Coordinators see every program; volunteers only active programs they belong to."""
    program = db.get(Program, program_id)
    if program is None:
        raise not_found("Program not found")
    if user.role != COORDINATOR and (
        program.archived_at is not None or not shifts.is_member(db, user.id, program.id)
    ):
        raise not_found("Program not found")
    return program


@router.get("", response_model=list[ProgramOut])
def list_programs(include_archived: bool = False, user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(Program).order_by(Program.name, Program.id)
    if user.role != COORDINATOR:
        stmt = stmt.where(Program.id.in_(shifts.visible_program_ids(user)))
    if user.role != COORDINATOR or not include_archived:
        stmt = stmt.where(Program.archived_at.is_(None))
    return _out(db, list(db.scalars(stmt)))


@router.post("", response_model=ProgramOut, status_code=201)
def create_program(data: ProgramIn, user: User = Depends(coordinator_only), db: Session = Depends(get_db)):
    program = Program(name=data.name, description=data.description, created_by=user.id, created_at=clock.now())
    db.add(program)
    db.commit()
    return _out(db, [program])[0]


@router.get("/{program_id}", response_model=ProgramOut)
def get_program(program_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _out(db, [_get(db, program_id, user)])[0]


@router.patch("/{program_id}", response_model=ProgramOut)
def edit_program(
    program_id: int, data: ProgramPatch, user: User = Depends(coordinator_only), db: Session = Depends(get_db)
):
    program = _get(db, program_id, user)
    if data.name is not None:
        if not data.name.strip():
            raise bad_request("Name must not be blank")
        program.name = data.name.strip()
    if data.description is not None:
        program.description = data.description
    db.commit()
    return _out(db, [program])[0]


@router.post("/{program_id}/archive", response_model=ProgramOut)
def archive_program(program_id: int, user: User = Depends(coordinator_only), db: Session = Depends(get_db)):
    program = _get(db, program_id, user)
    if program.archived_at is None:
        program.archived_at = clock.now()
        db.commit()
    return _out(db, [program])[0]


@router.post("/{program_id}/restore", response_model=ProgramOut)
def restore_program(program_id: int, user: User = Depends(coordinator_only), db: Session = Depends(get_db)):
    program = _get(db, program_id, user)
    if program.archived_at is not None:
        program.archived_at = None
        db.commit()
    return _out(db, [program])[0]


# ---- membership (goal 5) ---------------------------------------------------------
@router.get("/{program_id}/members", response_model=list[UserOut])
def list_members(program_id: int, user: User = Depends(coordinator_only), db: Session = Depends(get_db)):
    _get(db, program_id, user)
    return db.scalars(
        select(User)
        .join(ProgramMember, ProgramMember.user_id == User.id)
        .where(ProgramMember.program_id == program_id)
        .order_by(User.name, User.id)
    ).all()


@router.post("/{program_id}/members", response_model=UserOut, status_code=201)
def add_member(
    program_id: int, data: MemberIn, user: User = Depends(coordinator_only), db: Session = Depends(get_db)
):
    program = _get(db, program_id, user)
    volunteer = db.get(User, data.user_id)
    if volunteer is None or volunteer.role != VOLUNTEER:
        raise not_found("Volunteer not found")
    if shifts.is_member(db, volunteer.id, program.id):
        raise conflict(f"{volunteer.name} is already a member of this program")
    db.add(ProgramMember(program_id=program.id, user_id=volunteer.id, added_by=user.id, created_at=clock.now()))
    db.commit()
    return volunteer


@router.delete("/{program_id}/members/{user_id}", status_code=204)
def remove_member(
    program_id: int, user_id: int, user: User = Depends(coordinator_only), db: Session = Depends(get_db)
):
    program = _get(db, program_id, user)
    membership = db.get(ProgramMember, (program.id, user_id))
    if membership is None:
        raise not_found("That volunteer is not a member of this program")
    cancel_for_removed_member(db, program.id, user_id, user)
    db.delete(membership)
    db.commit()
    return Response(status_code=204)


# ---- recurring schedule + roster (goal 7) ------------------------------------------
@router.post("/{program_id}/schedule", response_model=ScheduleOut, status_code=201)
def generate_schedule(
    program_id: int, data: ScheduleIn, user: User = Depends(coordinator_only), db: Session = Depends(get_db)
):
    program = _get(db, program_id, user)
    created, skipped = schedule.generate(db, program, data, user)
    db.commit()
    return ScheduleOut(created=[presenters.to_out(s) for s in created], skipped=skipped)


@router.get("/{program_id}/roster.csv")
def roster_csv(program_id: int, user: User = Depends(coordinator_only), db: Session = Depends(get_db)):
    program = _get(db, program_id, user)
    slug = re.sub(r"[^a-z0-9]+", "-", program.name.lower()).strip("-") or "program"
    return Response(
        content=roster.build_csv(db, program),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="roster-{slug}.csv"'},
    )
