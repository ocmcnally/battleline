"""WebSocket connection registry and broadcast helpers."""

from fastapi import WebSocket
from .serializer import game_view
from .game_manager import GameSession


class ConnectionManager:
    def __init__(self):
        # token → active WebSocket
        self._connections: dict[str, WebSocket] = {}

    async def connect(self, token: str, ws: WebSocket):
        await ws.accept()
        self._connections[token] = ws

    def disconnect(self, token: str):
        self._connections.pop(token, None)

    async def send(self, token: str, data: dict):
        ws = self._connections.get(token)
        if ws:
            try:
                await ws.send_json(data)
            except Exception:
                self.disconnect(token)

    async def broadcast_state(self, session: GameSession):
        """Push a player-POV state snapshot to both participants."""
        for idx, token in enumerate(session.tokens):
            state = game_view(session.game, idx)
            await self.send(token, {
                "type": "state",
                "game_id": session.id,
                "state": state,
            })

    async def notify_matched(self, session: GameSession):
        """Tell both players the game has started."""
        for idx, token in enumerate(session.tokens):
            state = game_view(session.game, idx)
            await self.send(token, {
                "type": "game_start",
                "game_id": session.id,
                "player_idx": idx,
                "state": state,
            })
