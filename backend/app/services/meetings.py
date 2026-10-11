import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Meeting
from app.schemas import MeetingCreate, MeetingUpdate


async def list_meetings(
    session: AsyncSession, *, owner_id: str, limit: int, offset: int
) -> tuple[list[Meeting], int]:
    total = (
        await session.scalar(
            select(func.count()).select_from(Meeting).where(Meeting.owner_id == owner_id)
        )
        or 0
    )
    result = await session.execute(
        select(Meeting)
        .where(Meeting.owner_id == owner_id)
        .order_by(Meeting.starts_at.desc(), Meeting.id)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars()), total


async def get_meeting(
    session: AsyncSession, meeting_id: uuid.UUID, *, owner_id: str
) -> Meeting | None:
    return await session.scalar(
        select(Meeting).where(Meeting.id == meeting_id, Meeting.owner_id == owner_id)
    )


async def create_meeting(
    session: AsyncSession, payload: MeetingCreate, *, owner_id: str
) -> Meeting:
    meeting = Meeting(**payload.model_dump(), owner_id=owner_id)
    session.add(meeting)
    await session.flush()
    await session.refresh(meeting)
    return meeting


async def update_meeting(
    session: AsyncSession, meeting: Meeting, payload: MeetingUpdate
) -> Meeting:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(meeting, field, value)
    await session.flush()
    await session.refresh(meeting)
    return meeting


async def delete_meeting(session: AsyncSession, meeting: Meeting) -> None:
    await session.delete(meeting)
    await session.flush()
