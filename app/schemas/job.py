from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class JobRead(BaseModel):
    id: uuid.UUID
    title: str
    company: str
    location: Optional[str] = None
    remote_allowed: bool
    url: str
    keyword_score: Optional[float] = None
    embedding_score: Optional[float] = None
    posted_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
