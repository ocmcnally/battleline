"""
Battle Line API server.

Run from the project root:
    uvicorn server.main:app --reload

HTTP endpoints
──────────────
POST /join          { username }  → { token, status, game_id?, player_idx? }
GET  /game/{id}     ?token=...   → { state }

WebSocket
─────────
WS /ws?token=...

Client → Server messages
  { "action": "move", "move": <MoveObject> }
  { "action": "ping" }

Server → Client messages
  { "type": "waiting" }
  { "type": "game_start",  "game_id", "player_idx", "state" }
  { "type": "state",       "game_id", "state" }
  { "type": "error",       "message" }
  { "type": "pong" }

MoveObject shapes
  play_card:        { action, card, totem, draw_from_tactics? }
  play_wild:        { action, tactic, totem, suit, value, draw_from_tactics? }
  play_environment: { action, tactic, totem, draw_from_tactics? }
  scout_reveal:     { action, tactic, troop_count, tactics_count }
  scout_return:     { action, returns: [{card, dest}] }
  play_redeploy:    { action, tactic, from_totem, card, to_totem?, draw_from_tactics? }
  play_traitor:     { action, tactic, from_totem, card, to_totem, draw_from_tactics? }
  play_deserter:    { action, tactic, from_totem, card, draw_from_tactics? }

Card shapes
  troop:   { type:"troop",   suit, value }
  tactics: { type:"tactics", name }
  wild:    { type:"wild",    tactic_name, suit, value }
"""

import uuid
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .game_manager import GameManager
from .ws_manager import ConnectionManager
from .serializer import game_view

app = FastAPI(title="Battle Line")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten to your frontend origin in production
    allow_methods=["*"],
    allow_headers=["*"],
)

gm = GameManager()
cm = ConnectionManager()


# ── HTTP ──────────────────────────────────────────────────────────────────────

class JoinRequest(BaseModel):
    username: str


@app.post("/join")
async def join(req: JoinRequest):
    token = str(uuid.uuid4()).replace("-", "")[:16]
    game_id = gm.enqueue(token, req.username)

    if game_id is None:
        return {"token": token, "status": "waiting"}

    session = gm.sessions[game_id]
    player_idx = gm.token_to_player[token]

    # Notify the waiting player via WebSocket if they're already connected
    other_token = session.tokens[1 - player_idx]
    await cm.notify_matched(session)

    return {
        "token": token,
        "status": "matched",
        "game_id": game_id,
        "player_idx": player_idx,
    }


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

    # If player is already matched, send current state immediately
    result = gm.get_session(token)
    if result:
        session, player_idx = result
        state = game_view(session.game, player_idx)
        await ws.send_json({"type": "state", "game_id": session.id, "state": state})
    else:
        await ws.send_json({"type": "waiting"})

    try:
        while True:
            data = await ws.receive_json()
            action = data.get("action")

            if action == "move":
                move = data.get("move", {})
                msg, ok = gm.apply_move(token, move)
                if ok:
                    result = gm.get_session(token)
                    if result:
                        await cm.broadcast_state(result[0])
                else:
                    await ws.send_json({"type": "error", "message": msg})

            elif action == "ping":
                await ws.send_json({"type": "pong"})

            else:
                await ws.send_json({"type": "error", "message": f"Unknown action: {action!r}"})

    except WebSocketDisconnect:
        cm.disconnect(token)
