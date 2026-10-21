import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Agenda(Base):
    __tablename__ = "agendas"
    __table_args__ = (
        CheckConstraint("jsonb_typeof(items) = 'array'", name="ck_agendas_items"),
        CheckConstraint("jsonb_typeof(action_items) = 'array'", name="ck_agendas_actions"),
        CheckConstraint("length(trim(language)) > 0", name="ck_agendas_language"),
        CheckConstraint(
            "ai_suggestion IS NULL OR jsonb_typeof(ai_suggestion) = 'object'",
            name="ck_agendas_suggestion",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    items: Mapped[list] = mapped_column(JSONB, nullable=False)
    action_items: Mapped[list] = mapped_column(JSONB, nullable=False)
    language: Mapped[str] = mapped_column(String(64), nullable=False)
    ai_suggestion: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
