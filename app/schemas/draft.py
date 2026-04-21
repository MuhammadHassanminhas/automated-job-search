from __future__ import annotations

import uuid
from typing import Optional

from pydantic import BaseModel


class DraftRead(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    resume_md: Optional[str] = None
    cover_letter_md: Optional[str] = None
    email_subject: Optional[str] = None
    email_body: Optional[str] = None
    model_used: Optional[str] = None
    prompt_version: Optional[str] = None

    model_config = {"from_attributes": True}


class DraftPatch(BaseModel):
    resume_md: Optional[str] = None
    cover_letter_md: Optional[str] = None
    email_subject: Optional[str] = None
    email_body: Optional[str] = None


class ApplicationRead(BaseModel):
    id: uuid.UUID
    status: str

    model_config = {"from_attributes": True}
