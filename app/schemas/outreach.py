from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.outreach_event import OutreachChannel, OutreachDirection


class OutreachEventRead(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    channel: OutreachChannel
    direction: OutreachDirection
    subject: Optional[str] = None
    body: Optional[str] = None
    sent_at: Optional[datetime] = None
    received_at: Optional[datetime] = None
    sent_hash: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OutreachEventCreate(BaseModel):
    application_id: uuid.UUID
    channel: OutreachChannel
    direction: OutreachDirection
    subject: Optional[str] = None
    body: Optional[str] = None
    sent_at: Optional[datetime] = None
    received_at: Optional[datetime] = None
    sent_hash: Optional[str] = None
