from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import Item
from app.models.meeting import Meeting
from app.reports.metrics import MeetingRecord, TaskMetrics
from app.reports.weeks import ReportingWeek


async def read_meetings(
    session: AsyncSession, owner: str, week: ReportingWeek
) -> list[MeetingRecord]:
    rows = await session.execute(
        select(
            Meeting.id,
            Meeting.title,
            Meeting.starts_at,
            Meeting.duration_minutes,
            Meeting.participant_count,
        ).where(
            Meeting.owner_id == owner,
            Meeting.starts_at >= week.start,
            Meeting.starts_at < week.end,
        )
    )
    return [MeetingRecord(*row) for row in rows]


async def read_tasks(session: AsyncSession, owner: str, week: ReportingWeek) -> TaskMetrics:
    created = await session.scalar(
        select(func.count())
        .select_from(Item)
        .where(Item.owner_id == owner, Item.created_at >= week.start, Item.created_at < week.end)
    )
    rows = await session.execute(
        select(Item.status, func.count()).where(Item.owner_id == owner).group_by(Item.status)
    )
    counts = dict(rows.all())
    return TaskMetrics(
        created or 0, counts.get("todo", 0), counts.get("in_progress", 0), counts.get("done", 0)
    )
