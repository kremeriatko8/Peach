import uuid

from fastapi import APIRouter

from app.auth import UserDep
from app.db import SessionDep
from app.schemas.agenda import AgendaPut, AgendaRead
from app.services import agendas

router = APIRouter(prefix="/meetings", tags=["agendas"])


@router.get("/{meeting_id}/agenda", response_model=AgendaRead | None)
async def get_agenda(meeting_id: uuid.UUID, user: UserDep, session: SessionDep):
    return await agendas.get_agenda(session, meeting_id, user.sub)


@router.put("/{meeting_id}/agenda", response_model=AgendaRead)
async def put_agenda(meeting_id: uuid.UUID, payload: AgendaPut, user: UserDep, session: SessionDep):
    return await agendas.put_agenda(session, meeting_id, user.sub, payload)
