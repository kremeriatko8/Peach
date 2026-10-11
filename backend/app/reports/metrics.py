from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID


@dataclass(frozen=True)
class MeetingRecord:
    id: UUID
    title: str
    starts_at: datetime
    duration_minutes: int
    participant_count: int


@dataclass(frozen=True)
class MeetingMetrics:
    count: int
    minutes: int
    longest: tuple[MeetingRecord, ...]


def meeting_metrics(meetings: list[MeetingRecord]) -> MeetingMetrics:
    ordered = sorted(meetings, key=lambda m: (-m.duration_minutes, m.starts_at, m.id))
    return MeetingMetrics(
        len(meetings), sum(m.duration_minutes for m in meetings), tuple(ordered[:5])
    )


def percentage_change(current: int, previous: int) -> str:
    if previous == 0:
        return "N/A (previous value is zero)"
    change = Decimal(current - previous) * 100 / Decimal(previous)
    return str(change.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class TaskMetrics:
    created: int
    todo: int
    in_progress: int
    done: int
