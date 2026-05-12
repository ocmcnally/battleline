"""Supabase rating read/write via REST API."""
import os
import httpx

_URL     = os.getenv("SUPABASE_URL", "")
_SVC_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

PROVISIONAL_THRESHOLD = 10


def _headers() -> dict:
    return {
        "apikey":        _SVC_KEY,
        "Authorization": f"Bearer {_SVC_KEY}",
        "Content-Type":  "application/json",
        "Prefer":        "return=representation",
    }


async def _fetch(user_id: str, client: httpx.AsyncClient) -> dict | None:
    url = (f"{_URL}/rest/v1/profiles"
           f"?id=eq.{user_id}"
           f"&select=id,rating,rd,volatility,games_played")
    r = await client.get(url, headers=_headers())
    if r.status_code != 200:
        return None
    rows = r.json()
    return rows[0] if rows else None


async def settle_game(winner_id: str, loser_id: str) -> bool:
    """Compute and persist Glicko-2 updates for both players. Returns True on success."""
    if not _URL or not _SVC_KEY:
        return False

    from .glicko2 import update

    async with httpx.AsyncClient() as client:
        w = await _fetch(winner_id, client)
        l = await _fetch(loser_id,  client)
        if not w or not l:
            return False

        wr, wrd, wsig = update(w["rating"], w["rd"], w["volatility"], l["rating"], l["rd"], 1.0)
        lr, lrd, lsig = update(l["rating"], l["rd"], l["volatility"], w["rating"], w["rd"], 0.0)

        base = f"{_URL}/rest/v1/profiles"
        await client.patch(
            base + f"?id=eq.{winner_id}",
            json={"rating": round(wr, 1), "rd": round(wrd, 1), "volatility": wsig,
                  "games_played": w["games_played"] + 1},
            headers=_headers(),
        )
        await client.patch(
            base + f"?id=eq.{loser_id}",
            json={"rating": round(lr, 1), "rd": round(lrd, 1), "volatility": lsig,
                  "games_played": l["games_played"] + 1},
            headers=_headers(),
        )
    return True


async def get_display_rating(user_id: str) -> dict | None:
    """Returns {"rating": int, "provisional": bool} or None if unavailable."""
    if not _URL or not _SVC_KEY:
        return None
    async with httpx.AsyncClient() as client:
        row = await _fetch(user_id, client)
    if not row:
        return None
    return {
        "rating":      round(row["rating"]),
        "provisional": row["games_played"] < PROVISIONAL_THRESHOLD,
    }
