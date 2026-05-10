"""
Battle Line API server.

Run from the project root:
    uvicorn server.main:app --reload

HTTP endpoints
──────────────
POST /games              { token, username }      → { game_id }
GET  /games                                       → { games: [...] }
POST /games/{id}/join    { token, username }      → { game_id, player_idx }
DELETE /games/{id}       ?token=...               → { ok }
GET  /game/{id}          ?token=...               → { state }

WebSocket
─────────
WS /ws?token=...

Server → Client
  { type:"waiting",    game_id? }
  { type:"game_start", game_id, player_idx, state }
  { type:"state",      game_id, state }
  { type:"error",      message }
  { type:"pong" }

Client → Server
  { action:"move", move:<MoveObject> }
  { action:"ping" }
"""

import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .game_manager import GameManager
from .ws_manager import ConnectionManager
from .serializer import game_view

app = FastAPI(title="Battle Line")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

gm = GameManager()
cm = ConnectionManager()


# ── Pydantic request bodies ───────────────────────────────────────────────────

class GameRequest(BaseModel):
    token:    str
    username: str


# ── HTTP ──────────────────────────────────────────────────────────────────────

@app.post("/games")
async def create_game(req: GameRequest):
    game_id = gm.create_game(req.token, req.username)
    return {"game_id": game_id}


@app.get("/games")
async def list_games():
    return {"games": gm.list_open_games()}


@app.post("/games/{game_id}/join")
async def join_game(game_id: str, req: GameRequest):
    ok, err = gm.join_game(req.token, req.username, game_id)
    if not ok:
        raise HTTPException(400, err)
    session = gm.sessions[game_id]
    # Notify creator (already on WS) that opponent joined
    await cm.notify_matched(session)
    return {"game_id": game_id, "player_idx": gm.token_to_player[req.token]}


@app.delete("/games/{game_id}")
async def cancel_game(game_id: str, token: str = Query(...)):
    pending = gm._pending.get(game_id)
    if not pending or pending.token != token:
        raise HTTPException(403, "Not the game creator.")
    gm.cancel_pending(token)
    return {"ok": True}


@app.get("/game/{game_id}")
async def get_game(game_id: str, token: str = Query(...)):
    session = gm.sessions.get(game_id)
    if not session:
        raise HTTPException(404, "Game not found.")
    player_idx = gm.token_to_player.get(token)
    if player_idx is None or session.tokens[player_idx] != token:
        raise HTTPException(403, "Not a participant in this game.")
    return {"state": game_view(session.game, player_idx)}


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket, token: str = Query(...)):
    await cm.connect(token, ws)

    result = gm.get_session(token)
    if result:
        session, player_idx = result
        await ws.send_json({
            "type": "state",
            "game_id": session.id,
            "state": game_view(session.game, player_idx),
        })
    else:
        # Could be a pending game (creator waiting) or unknown token
        pending_id = gm.is_pending(token)
        await ws.send_json({"type": "waiting", "game_id": pending_id})

    try:
        while True:
            data = await ws.receive_json()
            action = data.get("action")

            if action == "move":
                msg, ok = gm.apply_move(token, data.get("move", {}))
                if ok:
                    r = gm.get_session(token)
                    if r:
                        await cm.broadcast_state(r[0])
                else:
                    await ws.send_json({"type": "error", "message": msg})

            elif action == "ping":
                await ws.send_json({"type": "pong"})

            else:
                await ws.send_json({"type": "error", "message": f"Unknown action: {action!r}"})

    except WebSocketDisconnect:
        cm.disconnect(token)


# Serve React build — must be mounted after all API/WS routes
_dist = os.path.join(os.path.dirname(__file__), "..", "client", "dist")
if os.path.isdir(_dist):
    app.mount("/", StaticFiles(directory=_dist, html=True), name="spa")
