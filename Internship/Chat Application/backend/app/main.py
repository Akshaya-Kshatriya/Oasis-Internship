from __future__ import annotations

import mimetypes
from datetime import timedelta
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from sqlalchemy.orm import Session

from . import crud, schemas
from .config import get_settings
from .database import Base, SessionLocal, engine, get_db
from .dependencies import get_current_user, get_room_or_404
from .models import ChatRoom, MessageType, User
from .security import create_access_token, decode_access_token
from .websocket_manager import RoomConnectionManager

settings = get_settings()

app = FastAPI(title="Secure Chat Application", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
if frontend_dir.exists():
    static_dir = frontend_dir / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")


app.mount(
    "/media",
    StaticFiles(directory=settings.media_directory),
    name="media",
)

manager = RoomConnectionManager()


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        crud.get_or_create_default_rooms(db)
    finally:
        db.close()


@app.get("/", response_class=HTMLResponse)
def serve_frontend() -> HTMLResponse:
    index_path = frontend_dir / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Frontend not built.")
    return HTMLResponse(index_path.read_text(encoding="utf-8"))


@app.post("/auth/register", response_model=schemas.UserOut, status_code=status.HTTP_201_CREATED)
def register(
    payload: schemas.UserCreate,
    db: Session = Depends(get_db),
) -> schemas.UserOut:
    user = crud.create_user(db, payload)
    return schemas.UserOut.model_validate(user)


@app.post("/auth/login", response_model=schemas.Token)
def login(
    payload: schemas.UserLogin,
    db: Session = Depends(get_db),
) -> schemas.Token:
    user = crud.authenticate_user(db, payload.username, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )
    return schemas.Token(access_token=access_token)


@app.get("/users/me", response_model=schemas.UserOut)
def read_users_me(current_user: Annotated[User, Depends(get_current_user)]) -> schemas.UserOut:
    return schemas.UserOut.model_validate(current_user)


@app.get("/rooms", response_model=list[schemas.ChatRoomOut])
def list_rooms(db: Session = Depends(get_db)) -> list[schemas.ChatRoomOut]:
    rooms = crud.get_rooms(db)
    return [schemas.ChatRoomOut.model_validate(room) for room in rooms]


@app.post("/rooms", response_model=schemas.ChatRoomOut, status_code=status.HTTP_201_CREATED)
def create_room(
    payload: schemas.ChatRoomCreate,
    _: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
) -> schemas.ChatRoomOut:
    room = crud.create_room(db, payload)
    return schemas.ChatRoomOut.model_validate(room)


@app.get("/rooms/{room_id}/messages", response_model=list[schemas.MessageOut])
def get_messages(
    room: Annotated[ChatRoom, Depends(get_room_or_404)],
    db: Session = Depends(get_db),
    limit: int = 50,
    skip: int = 0,
    _current_user: Annotated[User, Depends(get_current_user)] = None,
) -> list[schemas.MessageOut]:
    messages = crud.get_message_history(db, room_id=room.id, limit=limit, skip=skip)
    return list(messages)


@app.post(
    "/rooms/{room_id}/upload",
    response_model=schemas.MessageOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_file(
    room: Annotated[ChatRoom, Depends(get_room_or_404)],
    current_user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> schemas.MessageOut:
    content_type = file.content_type or mimetypes.guess_type(file.filename)[0] or "application/octet-stream"
    extension = Path(file.filename).suffix
    safe_name = f"{uuid4().hex}{extension}"
    room_dir = settings.media_directory / f"room_{room.id}"
    room_dir.mkdir(parents=True, exist_ok=True)
    file_path = room_dir / safe_name

    file_bytes = await file.read()
    with file_path.open("wb") as buffer:
        buffer.write(file_bytes)

    public_path = f"/media/room_{room.id}/{safe_name}"

    if content_type.startswith("image/"):
        message_type = MessageType.IMAGE
        description = f"Image: {file.filename}"
    elif content_type.startswith("video/"):
        message_type = MessageType.VIDEO
        description = f"Video: {file.filename}"
    else:
        message_type = MessageType.FILE
        description = f"File: {file.filename}"

    message = crud.create_message(
        db,
        room=room,
        user=current_user,
        content=description,
        message_type=message_type,
        file_path=public_path,
        mime_type=content_type,
    )
    message_out = schemas.MessageOut(
        id=message.id,
        room_id=message.room_id,
        user_id=message.user_id,
        username=current_user.username,
        content=description,
        message_type=message_type,
        file_url=public_path,
        mime_type=content_type,
        created_at=message.created_at,
    )

    await manager.broadcast(
        room.id,
        {"event": "message", "payload": message_out.model_dump()},
    )

    return message_out


@app.websocket("/ws/rooms/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: int) -> None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        token_data = decode_access_token(token)
    except HTTPException:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    db = SessionLocal()
    user: User | None = None
    try:
        if token_data.username is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        user = crud.get_user_by_username(db, token_data.username)
        if user is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        room = db.get(ChatRoom, room_id)
        if room is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        await manager.connect(room_id, websocket)
        # Notify others that this user joined (exclude the person who just joined)
        await manager.broadcast(
            room_id,
            {
                "event": "system",
                "payload": {
                    "message": f"{user.username} joined the room",
                    "room_id": room_id,
                },
            },
            exclude=websocket,  # Don't notify the person who just joined
        )

        while True:
            try:
                data = await websocket.receive_json()
                message_in = schemas.MessageCreate(**data)
            except ValidationError as exc:
                await manager.send_personal_message(
                    websocket,
                    {
                        "event": "error",
                        "payload": {"message": "Invalid message payload", "detail": exc.errors()},
                    },
                )
                continue

            message = crud.create_message(
                db,
                room=room,
                user=user,
                content=message_in.content,
                message_type=message_in.message_type,
            )
            message_out = schemas.MessageOut(
                id=message.id,
                room_id=message.room_id,
                user_id=user.id,
                username=user.username,
                content=message_in.content,
                message_type=message_in.message_type,
                file_url=message.file_path,
                mime_type=message.mime_type,
                created_at=message.created_at,
            )

            await manager.broadcast(
                room_id,
                {"event": "message", "payload": message_out.model_dump()},
            )
    except WebSocketDisconnect:
        manager.disconnect(room_id, websocket)
        if user:
            try:
                await manager.broadcast(
                    room_id,
                    {
                        "event": "system",
                        "payload": {
                            "message": f"{user.username} left the room",
                            "room_id": room_id,
                        },
                    },
                )
            except Exception:
                # Ignore errors when broadcasting disconnect message
                pass
    finally:
        db.close()



