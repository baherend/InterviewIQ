from pydantic import BaseModel, EmailStr
from datetime import datetime


class UserCreate(BaseModel):
    # Intentionally has no `role` field. Public registration always assigns
    # the `student` role server-side (see routers/auth.py); any `role` sent
    # by a client in the request body is ignored, not applied.
    name: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse
