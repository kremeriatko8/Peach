import uuid
from datetime import UTC, datetime
from typing import Annotated

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

MeetingTitle = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
]
Duration = Annotated[int, Field(strict=True, ge=1, le=1440)]
Participants = Annotated[int, Field(strict=True, ge=1, le=10000)]
Notes = Annotated[str, Field(max_length=2000)]


class MeetingBase(BaseModel):
    title: MeetingTitle
    starts_at: AwareDatetime
    duration_minutes: Duration
    participant_count: Participants
    notes: Notes | None = None

    @field_validator("starts_at", mode="before")
    @classmethod
    def timestamp_is_explicit(cls, value: object) -> object:
        # Pydantic otherwise also accepts numeric Unix timestamps.
        if not isinstance(value, (str, datetime)):
            raise ValueError("Start time must be an ISO timestamp with a UTC offset")
        return value

    @field_validator("starts_at")
    @classmethod
    def normalize_start(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class MeetingCreate(MeetingBase):
    model_config = ConfigDict(extra="forbid")


class MeetingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: MeetingTitle | None = None
    starts_at: AwareDatetime | None = None
    duration_minutes: Duration | None = None
    participant_count: Participants | None = None
    notes: Notes | None = None

    @field_validator("title", "starts_at", "duration_minutes", "participant_count", mode="before")
    @classmethod
    def required_fields_cannot_be_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("This field cannot be null")
        return value

    _explicit_timestamp = field_validator("starts_at", mode="before")(
        MeetingBase.timestamp_is_explicit.__func__
    )
    _normalize_start = field_validator("starts_at")(MeetingBase.normalize_start.__func__)


class MeetingRead(MeetingBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class MeetingList(BaseModel):
    meetings: list[MeetingRead]
    total: int
