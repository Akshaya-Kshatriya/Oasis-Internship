from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .models import MessageType


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: str | None = None


class UserBase(BaseModel):
    username: str = Field(min_length=3, max_length=50)


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=64)


class UserLogin(UserBase):
    password: str


class UserOut(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ChatRoomCreate(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    topic: str | None = Field(default=None, max_length=512)


class ChatRoomOut(BaseModel):
    id: int
    name: str
    topic: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    message_type: MessageType = MessageType.TEXT


class MessageOut(BaseModel):
    id: int
    room_id: int
    user_id: int
    username: str
    content: Optional[str] = None
    message_type: MessageType
    file_url: Optional[str] = None
    mime_type: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


