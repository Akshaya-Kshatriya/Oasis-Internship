from __future__ import annotations

from datetime import datetime
from typing import Iterable, Sequence

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from . import schemas
from .models import ChatRoom, Message, MessageType, User
from .security import decrypt_text, encrypt_text, get_password_hash, verify_password


def get_user_by_username(db: Session, username: str) -> User | None:
    stmt = select(User).where(User.username == username)
    return db.execute(stmt).scalar_one_or_none()


def create_user(db: Session, user_in: schemas.UserCreate) -> User:
    if get_user_by_username(db, user_in.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username is already taken.",
        )
    user = User(
        username=user_in.username,
        password_hash=get_password_hash(user_in.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = get_user_by_username(db, username)
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


def get_or_create_default_rooms(db: Session) -> Sequence[ChatRoom]:
    """Ensure a baseline set of rooms exists for new deployments."""
    existing = db.execute(select(ChatRoom)).scalars().all()
    if existing:
        return existing

    defaults = [
        ChatRoom(name="General", topic="Company-wide discussions"),
        ChatRoom(name="Development", topic="Engineering and product updates"),
        ChatRoom(name="Support", topic="Customer success and support chats"),
    ]
    db.add_all(defaults)
    db.commit()
    return db.execute(select(ChatRoom)).scalars().all()


def get_rooms(db: Session) -> Sequence[ChatRoom]:
    return db.execute(select(ChatRoom).order_by(ChatRoom.created_at)).scalars().all()


def create_room(db: Session, room_in: schemas.ChatRoomCreate) -> ChatRoom:
    room = ChatRoom(name=room_in.name, topic=room_in.topic)
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


def create_message(
    db: Session,
    *,
    room: ChatRoom,
    user: User,
    content: str | None,
    message_type: MessageType,
    file_path: str | None = None,
    mime_type: str | None = None,
    created_at: datetime | None = None,
) -> Message:
    message = Message(
        room=room,
        user=user,
        content_encrypted=encrypt_text(content),
        message_type=message_type,
        file_path=file_path,
        mime_type=mime_type,
        created_at=created_at or datetime.utcnow(),
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def get_message_history(
    db: Session,
    *,
    room_id: int,
    limit: int = 50,
    skip: int = 0,
) -> Iterable[schemas.MessageOut]:
    stmt = (
        select(Message)
        .options(joinedload(Message.user))
        .where(Message.room_id == room_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
        .offset(skip)
    )
    messages = list(db.execute(stmt).scalars().all())
    results = []
    for message in reversed(messages):
        results.append(
            schemas.MessageOut(
                id=message.id,
                room_id=message.room_id,
                user_id=message.user_id,
                username=message.user.username,
                content=decrypt_text(message.content_encrypted),
                message_type=message.message_type,
                file_url=message.file_path,
                mime_type=message.mime_type,
                created_at=message.created_at,
            )
        )
    return results


