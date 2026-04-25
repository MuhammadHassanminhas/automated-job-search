import enum
from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Enum, Float, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class JobSource(str, enum.Enum):
    REMOTEOK = "REMOTEOK"
    INTERNSHALA = "INTERNSHALA"
    ROZEE = "ROZEE"


class Job(TimestampMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_jobs_source_external_id"),
        Index(
            "jobs_description_embedding_hnsw_idx",
            "description_embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"description_embedding": "vector_cosine_ops"},
        ),
    )

    source: Mapped[JobSource] = mapped_column(Enum(JobSource, name="jobsource"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(256), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    company: Mapped[str] = mapped_column(String(256), nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(256))
    remote_allowed: Mapped[bool] = mapped_column(default=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    description_embedding: Mapped[Optional[list]] = mapped_column(Vector(384))
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    hash: Mapped[Optional[str]] = mapped_column(String(64), unique=True)
    keyword_score: Mapped[Optional[float]] = mapped_column(Float)
    embedding_score: Mapped[Optional[float]] = mapped_column(Float)
    llm_score: Mapped[Optional[float]] = mapped_column(Float)
    llm_reasoning: Mapped[Optional[str]] = mapped_column(Text)
    source_etag: Mapped[Optional[str]] = mapped_column(String(256))
    llm_matched_skills: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
