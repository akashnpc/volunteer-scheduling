"""Roster CSV export (goal 7): every volunteer with hours from their live signups in a program."""
import csv
import io

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Program, ProgramMember, Shift, Signup, User


def _safe(cell: str) -> str:
    # Spreadsheet apps run text starting with = + - @ as a formula (CSV injection).
    return "'" + cell if cell[:1] in ("=", "+", "-", "@", "\t", "\r") else cell


def build_csv(db: Session, program: Program) -> str:
    totals = {
        volunteer_id: (shifts, minutes)
        for volunteer_id, shifts, minutes in db.execute(
            select(Signup.volunteer_id, func.count(Signup.id), func.sum(Shift.duration_minutes))
            .join(Shift, Shift.id == Signup.shift_id)
            .where(Shift.program_id == program.id, Shift.deleted_at.is_(None), Signup.cancelled_at.is_(None))
            .group_by(Signup.volunteer_id)
        )
    }
    member_ids = set(db.scalars(select(ProgramMember.user_id).where(ProgramMember.program_id == program.id)))
    # Include former members who still hold signups on closed shifts: their hours are real.
    users = db.scalars(select(User).where(User.id.in_(member_ids | set(totals))).order_by(User.name, User.id))

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["volunteer", "email", "shifts_signed_up", "total_hours"])
    for user in users:
        shifts, minutes = totals.get(user.id, (0, 0))
        writer.writerow([_safe(user.name), _safe(user.email), shifts, f"{(minutes or 0) / 60:.2f}"])
    return out.getvalue()
