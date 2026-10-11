import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

KYIV = ZoneInfo("Europe/Kyiv")


@dataclass(frozen=True)
class ReportingWeek:
    label: str
    start: datetime
    end: datetime


def parse_week(value: str) -> ReportingWeek:
    if not re.fullmatch(r"[0-9]{4}-W[0-9]{2}", value):
        raise ValueError("Week must be a valid ISO week in YYYY-Www format")
    try:
        monday = date.fromisocalendar(int(value[:4]), int(value[6:]), 1)
        following = monday + timedelta(days=7)
        start = datetime.combine(monday, time.min, KYIV).astimezone(UTC)
        end = datetime.combine(following, time.min, KYIV).astimezone(UTC)
    except (ValueError, OverflowError) as exc:
        raise ValueError("Week must be a valid ISO week in YYYY-Www format") from exc
    return ReportingWeek(value, start, end)


def previous_week(week: ReportingWeek) -> ReportingWeek:
    try:
        monday = week.start.astimezone(KYIV).date() - timedelta(days=7)
    except OverflowError as exc:
        raise ValueError("The previous ISO week is outside the supported date range") from exc
    year, number, _ = monday.isocalendar()
    return parse_week(f"{year:04d}-W{number:02d}")
