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

    def _build_state(self, session: GameSession, pov: int) -> dict:
        state = game_view(session.game, pov)
        clock = session.clock_state(pov)
        if clock:
            state["clock"] = clock
        return state

    async def broadcast_state(self, session: GameSession):
        """Push a player-POV state snapshot to both participants."""
        for idx, token in enumerate(session.tokens):
            await self.send(token, {
                "type": "state",
                "game_id": session.id,
                "state": self._build_state(session, idx),
            })

    async def notify_matched(self, session: GameSession):
        """Tell both players the game has started."""
        for idx, token in enumerate(session.tokens):
            await self.send(token, {
                "type": "game_start",
                "game_id": session.id,
                "player_idx": idx,
                "state": self._build_state(session, idx),
            })
