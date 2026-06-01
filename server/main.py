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

import asyncio
import os
from dotenv import load_dotenv
load_dotenv()
print(f"[startup] SUPABASE_URL={'set' if os.getenv('SUPABASE_URL') else 'MISSING'}, "
      f"SUPABASE_SERVICE_KEY={'set' if os.getenv('SUPABASE_SERVICE_KEY') else 'MISSING'}")
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .game_manager import GameManager, is_ai_token, ai_token_for
from .ws_manager import ConnectionManager
from .serializer import game_view
from .ratings import settle_game, get_display_rating
from . import bot

app = FastAPI(title="Battle Line")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

gm = GameManager()
cm = ConnectionManager()
bot.load_model()  # Load at startup so first AI move isn't delayed


# ── Pydantic request bodies ───────────────────────────────────────────────────

class GameRequest(BaseModel):
    token:        str
    username:     str
    time_ms:      int | None  = None
    increment_ms: int         = 0
    rated:        bool        = True
    category:     str | None  = None


class VsAIRequest(BaseModel):
    token:    str
    username: str


# ── HTTP ──────────────────────────────────────────────────────────────────────

async def _finish_game(session) -> None:
    """Settle ratings (if rated) then schedule session cleanup."""
    if session.game.winner is None:
        return
    if session.rated and not session.ratings_settled:
        session.ratings_settled = True
        winner_token = session.tokens[session.game.winner]
        loser_token  = session.tokens[1 - session.game.winner]
        changes = await settle_game(winner_token, loser_token, session.category)
        if changes:
            session.rating_changes = changes
            await cm.broadcast_state(session)
    # Clean up session so it no longer occupies memory
    await asyncio.sleep(30)   # keep alive briefly so late reconnects still get final state
    gm.cleanup_session(session.id)


async def clock_watcher(game_id: str):
    """Background task that enforces time limits and notifies players on timeout."""
    while True:
        session = gm.sessions.get(game_id)
        if not session or session.time_remaining_ms is None:
            break
        if session.game.winner is not None:
            break

        current = session.game.turn % 2
        elapsed_ms = int((__import__("time").time() - session.last_turn_start) * 1000)
        remaining = session.time_remaining_ms[current] - elapsed_ms

        if remaining <= 0:
            session.time_remaining_ms[current] = 0
            session.game.winner = 1 - current
            await cm.broadcast_state(session)
            asyncio.create_task(_finish_game(session))
            break

        await asyncio.sleep(min(remaining / 1000.0, 1.0))


async def _trigger_ai_move(session) -> None:
    """If it's the AI's turn, pick a move and broadcast the result."""
    ai_token = ai_token_for(session.id)
    ai_player = session.tokens.index(ai_token)
    if session.game.turn % 2 != ai_player or session.game.winner is not None:
        return
    await asyncio.sleep(0.4)   # small pause so human sees their move land first
    move = bot.choose_move(session.game, ai_player)
    if move is None:
        return
    card, ti, _ = move
    try:
        session.game.play_card(ai_player, card, ti)
        session.game.draw_card(ai_player)
        session.game.turn += 1
    except Exception as e:
        print(f"[AI] move error: {e}")
        return
    await cm.broadcast_state(session)
    if session.game.winner is not None:
        asyncio.create_task(_finish_game(session))


@app.post("/games/vs-ai")
async def create_vs_ai(req: VsAIRequest):
    game_id = gm.create_ai_game(req.token, req.username)
    return {"game_id": game_id, "player_idx": 0}


@app.post("/games")
async def create_game(req: GameRequest):
    creator_rating = await get_display_rating(req.token, req.category) if req.rated else None
    game_id = gm.create_game(req.token, req.username, req.time_ms, req.increment_ms,
                              req.rated, req.category, creator_rating)
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
    await cm.notify_matched(session)
    if session.time_remaining_ms is not None:
        asyncio.create_task(clock_watcher(game_id))
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
            "state": cm._build_state(session, player_idx),
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
                        if r[0].game.winner is not None:
                            asyncio.create_task(_finish_game(r[0]))
                        elif any(is_ai_token(t) for t in r[0].tokens):
                            asyncio.create_task(_trigger_ai_move(r[0]))
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
