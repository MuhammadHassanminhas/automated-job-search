import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class OutreachChannel(str, enum.Enum):
    EMAIL = "EMAIL"
    LINKEDIN = "LINKEDIN"
    FORM = "FORM"


class OutreachDirection(str, enum.Enum):
    OUT = "OUT"
    IN = "IN"


class OutreachEvent(TimestampMixin, Base):
    __tablename__ = "outreach_events"
    __table_args__ = (UniqueConstraint("sent_hash", name="uq_outreach_sent_hash"),)

    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[OutreachChannel] = mapped_column(
        Enum(OutreachChannel, name="outreachchannel"), nullable=False
    )
    direction: Mapped[OutreachDirection] = mapped_column(
        Enum(OutreachDirection, name="outreachdirection"), nullable=False
    )
    subject: Mapped[Optional[str]] = mapped_column(String(512))
    body: Mapped[Optional[str]] = mapped_column(Text)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    sent_hash: Mapped[Optional[str]] = mapped_column(String(64))
