import logging
from typing import Dict, List, Optional

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    Manages active WebSocket connections keyed by lecture_id.

    One lecture can have multiple simultaneous viewers — each gets every
    broadcast message.

    Additionally tracks user_id → websocket mappings so targeted messages
    (e.g. teacher reply → specific student) can be delivered directly.
    """

    def __init__(self):
        self._connections: Dict[str, List[WebSocket]] = {}
        # user_id → list[WebSocket] — a user can have multiple tabs open
        self._user_connections: Dict[str, List[WebSocket]] = {}

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(
        self,
        lecture_id: str,
        websocket: WebSocket,
        user_id: Optional[str] = None,
    ) -> None:
        await websocket.accept()
        self._connections.setdefault(lecture_id, []).append(websocket)
        if user_id:
            self._user_connections.setdefault(user_id, []).append(websocket)
        logger.info("WS connected  lecture=%s  total=%d", lecture_id, self.count(lecture_id))

    def disconnect(self, lecture_id: str, websocket: WebSocket) -> None:
        conns = self._connections.get(lecture_id, [])
        if websocket in conns:
            conns.remove(websocket)
        # Also remove from user-indexed map
        for user_id, sockets in list(self._user_connections.items()):
            if websocket in sockets:
                sockets.remove(websocket)
                if not sockets:
                    del self._user_connections[user_id]
                break
        logger.info("WS disconnected lecture=%s  total=%d", lecture_id, self.count(lecture_id))

    def count(self, lecture_id: str) -> int:
        return len(self._connections.get(lecture_id, []))

    # ------------------------------------------------------------------
    # Broadcast
    # ------------------------------------------------------------------

    async def broadcast(self, lecture_id: str, message: dict) -> None:
        """Send a JSON message to all clients watching this lecture."""
        dead: List[WebSocket] = []
        for ws in list(self._connections.get(lecture_id, [])):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(lecture_id, ws)

    async def send_personal(self, websocket: WebSocket, message: dict) -> None:
        """Send a message to a single connected client."""
        try:
            await websocket.send_json(message)
        except Exception:
            pass

    async def send_to_user(self, user_id: str, message: dict) -> None:
        """Send a message to all WebSocket connections of a specific user."""
        dead: List[WebSocket] = []
        for ws in list(self._user_connections.get(user_id, [])):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            # find which lecture this WS belongs to and disconnect cleanly
            for lecture_id, sockets in list(self._connections.items()):
                if ws in sockets:
                    self.disconnect(lecture_id, ws)
                    break


# Module-level singleton — imported by both the router and AI graph nodes
manager = WebSocketManager()
