import uuid

from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class UserRead(BaseModel):
    id: uuid.UUID
    email: str

    model_config = {"from_attributes": True}
