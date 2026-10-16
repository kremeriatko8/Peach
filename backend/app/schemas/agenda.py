import json
import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.ai.agenda import ActionItem, AgendaItem, ParsedAgenda
from app.schemas.meeting import MeetingUpdate

Text = Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class SavedAgendaItem(AgendaItem):
    model_config = ConfigDict(extra="forbid", strict=True)
    topic: Text
    owner: Annotated[str, Field(max_length=200)] | None = None

    @field_validator("topic")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Topic cannot be blank")
        return value


class SavedActionItem(ActionItem):
    model_config = ConfigDict(extra="forbid")
    task: Text
    owner: Annotated[str, Field(max_length=200)] | None = None

    @field_validator("task")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Task cannot be blank")
        return value


class Suggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agenda: ParsedAgenda
    model: str = Field(min_length=1, max_length=200)
    prompt_version: str = Field(min_length=1, max_length=64)

    @field_validator("agenda")
    @classmethod
    def bounded(cls, value):
        if len(json.dumps(value.model_dump(mode="json"))) > 100_000:
            raise ValueError("Suggestion too large")
        return value


class AgendaPut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[SavedAgendaItem] = Field(max_length=100)
    action_items: list[SavedActionItem] = Field(default_factory=list, max_length=100)
    language: str = Field(min_length=1, max_length=64)
    ai_suggestion: Suggestion | None = None
    meeting: MeetingUpdate | None = None

    @field_validator("language")
    @classmethod
    def language_nonblank(cls, value):
        if not value.strip():
            raise ValueError("Language cannot be blank")
        return value


class AgendaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    meeting_id: uuid.UUID
    items: list[SavedAgendaItem]
    action_items: list[SavedActionItem]
    language: str
    ai_suggestion: Suggestion | None
    created_at: datetime
    updated_at: datetime
