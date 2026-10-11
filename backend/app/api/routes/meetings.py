import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import UserDep
from app.db import SessionDep
from app.schemas import MeetingCreate, MeetingList, MeetingRead, MeetingUpdate
from app.services import meetings as meetings_service

router = APIRouter(prefix="/meetings", tags=["meetings"])


async def _get_or_404(session: AsyncSession, meeting_id: uuid.UUID, owner_id: str):
    meeting = await meetings_service.get_meeting(session, meeting_id, owner_id=owner_id)
    if meeting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")
    return meeting


@router.get("", response_model=MeetingList)
async def list_meetings(
    user: UserDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MeetingList:
    meetings, total = await meetings_service.list_meetings(
        session, owner_id=user.sub, limit=limit, offset=offset
    )
    return MeetingList(meetings=[MeetingRead.model_validate(m) for m in meetings], total=total)


@router.post("", response_model=MeetingRead, status_code=status.HTTP_201_CREATED)
async def create_meeting(payload: MeetingCreate, user: UserDep, session: SessionDep) -> MeetingRead:
    meeting = await meetings_service.create_meeting(session, payload, owner_id=user.sub)
    return MeetingRead.model_validate(meeting)


@router.get("/{meeting_id}", response_model=MeetingRead)
async def get_meeting(meeting_id: uuid.UUID, user: UserDep, session: SessionDep) -> MeetingRead:
    return MeetingRead.model_validate(await _get_or_404(session, meeting_id, user.sub))


@router.patch("/{meeting_id}", response_model=MeetingRead)
async def update_meeting(
    meeting_id: uuid.UUID, payload: MeetingUpdate, user: UserDep, session: SessionDep
) -> MeetingRead:
    meeting = await _get_or_404(session, meeting_id, user.sub)
    return MeetingRead.model_validate(
        await meetings_service.update_meeting(session, meeting, payload)
    )


@router.delete("/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meeting(meeting_id: uuid.UUID, user: UserDep, session: SessionDep) -> Response:
    meeting = await _get_or_404(session, meeting_id, user.sub)
    await meetings_service.delete_meeting(session, meeting)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
