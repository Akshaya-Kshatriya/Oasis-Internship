from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect


class RoomConnectionManager:
    """Tracks active websocket connections per chat room."""

    def __init__(self) -> None:
        self.active_connections: dict[int, set[WebSocket]] = defaultdict(set)

    async def connect(self, room_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections[room_id].add(websocket)

    def disconnect(self, room_id: int, websocket: WebSocket) -> None:
        connections = self.active_connections.get(room_id)
        if not connections:
            return
        connections.discard(websocket)
        if not connections:
            self.active_connections.pop(room_id, None)

    async def broadcast(self, room_id: int, message: dict[str, Any], exclude: WebSocket | None = None) -> None:
        """Broadcast message to all connections in a room, optionally excluding one."""
        connections = self.active_connections.get(room_id, set()).copy()
        to_remove: list[WebSocket] = []
        for connection in connections:
            # Skip the excluded connection
            if exclude is not None and connection is exclude:
                continue
            try:
                await connection.send_json(message)
            except (WebSocketDisconnect, RuntimeError, ConnectionError, Exception):
                # Catch all exceptions including RuntimeError for closed connections
                to_remove.append(connection)
        for conn in to_remove:
            self.disconnect(room_id, conn)

    async def send_personal_message(
        self, websocket: WebSocket, message: dict[str, Any]
    ) -> None:
        try:
            await websocket.send_json(message)
        except (WebSocketDisconnect, RuntimeError, ConnectionError, Exception):
            # Silently ignore errors for closed connections
            pass


