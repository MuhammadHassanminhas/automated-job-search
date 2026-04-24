import uuid
from typing import Annotated

from pydantic import BaseModel, BeforeValidator


def _reject_null_bytes(v: object) -> object:
    if isinstance(v, str) and "\x00" in v:
        raise ValueError("email must not contain null bytes")
    return v


class LoginRequest(BaseModel):
    email: Annotated[str, BeforeValidator(_reject_null_bytes)]
    password: str


class UserRead(BaseModel):
    id: uuid.UUID
    email: str

    model_config = {"from_attributes": True}
