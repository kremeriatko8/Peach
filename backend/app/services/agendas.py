"""The authenticated API owns all writes; the parser never imports this module."""

from fastapi import HTTPException
from sqlalchemy import select

from app.models import Agenda, Meeting


async def owned_meeting(session, meeting_id, owner_id, *, lock=False):
    query = select(Meeting).where(Meeting.id == meeting_id, Meeting.owner_id == owner_id)
    if lock:
        query = query.with_for_update()
    meeting = await session.scalar(query)
    if meeting is None:
        raise HTTPException(404, "Meeting not found")
    return meeting


async def get_agenda(session, meeting_id, owner_id):
    await owned_meeting(session, meeting_id, owner_id)
    return await session.scalar(select(Agenda).where(Agenda.meeting_id == meeting_id))


async def put_agenda(session, meeting_id, owner_id, payload):
    # Serialize upserts per meeting so duplicate saves cannot create duplicate agendas.
    meeting = await owned_meeting(session, meeting_id, owner_id, lock=True)
    agenda = await session.scalar(select(Agenda).where(Agenda.meeting_id == meeting_id))
    if agenda is None:
        agenda = Agenda(meeting_id=meeting_id)
        session.add(agenda)
    values = payload.model_dump(mode="json", exclude={"meeting"})
    # Omitted provenance means retain it; explicit null clears it for a manual replacement.
    if "ai_suggestion" not in payload.model_fields_set and agenda.id is not None:
        values.pop("ai_suggestion")
    for key, value in values.items():
        setattr(agenda, key, value)
    if payload.meeting:
        for key, value in payload.meeting.model_dump(exclude_unset=True).items():
            setattr(meeting, key, value)
    await session.flush()
    await session.refresh(agenda)
    return agenda
