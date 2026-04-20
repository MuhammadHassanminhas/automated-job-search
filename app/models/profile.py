import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.application import Application


class Profile(TimestampMixin, Base):
    __tablename__ = "profiles"

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    full_name: Mapped[str] = mapped_column(String(256), nullable=False)
    email: Mapped[str] = mapped_column(String(256), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(64))
    skills: Mapped[Optional[list]] = mapped_column(JSONB)
    projects: Mapped[Optional[dict]] = mapped_column(JSONB)
    education: Mapped[Optional[dict]] = mapped_column(JSONB)
    base_resume_md: Mapped[Optional[str]] = mapped_column(Text)
    style_examples: Mapped[Optional[dict]] = mapped_column(JSONB)

    applications: Mapped[list["Application"]] = relationship(
        "Application", back_populates="profile", cascade="all, delete-orphan"
    )
