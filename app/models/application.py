import enum
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.profile import Profile


class ApplicationStatus(str, enum.Enum):
    DRAFTED = "DRAFTED"
    APPROVED = "APPROVED"
    SENDING = "SENDING"
    SENT = "SENT"
    RESPONDED = "RESPONDED"
    INTERVIEWING = "INTERVIEWING"
    OFFERED = "OFFERED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"
    FAILED = "FAILED"


class Application(TimestampMixin, Base):
    __tablename__ = "applications"

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    profile_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE")
    )
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus, name="applicationstatus"),
        nullable=False,
        default=ApplicationStatus.DRAFTED,
    )

    profile: Mapped[Optional["Profile"]] = relationship("Profile", back_populates="applications")
