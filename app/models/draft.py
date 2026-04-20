import uuid
from typing import Optional

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Draft(TimestampMixin, Base):
    __tablename__ = "drafts"
    __table_args__ = (UniqueConstraint("application_id", name="uq_drafts_application_id"),)

    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    resume_md: Mapped[Optional[str]] = mapped_column(Text)
    cover_letter_md: Mapped[Optional[str]] = mapped_column(Text)
    email_subject: Mapped[Optional[str]] = mapped_column(String(256))
    email_body: Mapped[Optional[str]] = mapped_column(Text)
    model_used: Mapped[Optional[str]] = mapped_column(String(128))
    prompt_version: Mapped[Optional[str]] = mapped_column(String(32))
    prompt_hash: Mapped[Optional[str]] = mapped_column(String(64))
