import logging
from typing import Dict, List

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    Manages active WebSocket connections keyed by lecture_id.

    One lecture can have multiple simultaneous viewers — each gets every
    broadcast message.
    """

    def __init__(self):
        self._connections: Dict[str, List[WebSocket]] = {}

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(self, lecture_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(lecture_id, []).append(websocket)
        logger.info("WS connected  lecture=%s  total=%d", lecture_id, self.count(lecture_id))

    def disconnect(self, lecture_id: str, websocket: WebSocket) -> None:
        conns = self._connections.get(lecture_id, [])
        if websocket in conns:
            conns.remove(websocket)
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


# Module-level singleton — imported by both the router and AI graph nodes
manager = WebSocketManager()
