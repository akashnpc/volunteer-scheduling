"""One place that decides what "now" is, so tests and the seed script can set the time.

Every timestamp in the database is a naive datetime in the organisation's
timezone (ORG_TIMEZONE). Shift dates and times are wall-clock values with no
zone attached, so keeping everything else in the same frame avoids mixing
zones in comparisons like "has this shift's end time passed?".
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app import config

_override: datetime | None = None


def set_override(moment: datetime | None) -> None:
    """Pin "now" to a fixed moment (None restores the real clock)."""
    global _override
    _override = moment


def now() -> datetime:
    if _override is not None:
        return _override
    return datetime.now(ZoneInfo(config.ORG_TIMEZONE)).replace(tzinfo=None, microsecond=0)


def today() -> date:
    return now().date()
