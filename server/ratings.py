"""Supabase rating read/write via REST API."""
import os
import httpx

PROVISIONAL_THRESHOLD = 10


def _url() -> str:
    return os.getenv("SUPABASE_URL", "")

def _svc_key() -> str:
    return os.getenv("SUPABASE_SERVICE_KEY", "")

def _headers() -> dict:
    key = _svc_key()
    return {
        "apikey":        key,
        "Authorization": f"Bearer {key}",
        "Content-Type":  "application/json",
        "Prefer":        "return=representation",
    }


async def _fetch(user_id: str, client: httpx.AsyncClient) -> dict | None:
    url = (f"{_url()}/rest/v1/profiles"
           f"?id=eq.{user_id}"
           f"&select=id,rating,rd,volatility,games_played")
    r = await client.get(url, headers=_headers())
    if r.status_code != 200:
        return None
    rows = r.json()
    return rows[0] if rows else None


async def settle_game(winner_id: str, loser_id: str) -> dict | None:
    """
    Compute and persist Glicko-2 updates.
    Returns {token: {before, after, provisional_before, provisional_after}} or None on failure.
    """
    if not _url() or not _svc_key():
        return None

    from .glicko2 import update

    async with httpx.AsyncClient() as client:
        w = await _fetch(winner_id, client)
        l = await _fetch(loser_id,  client)
        if not w or not l:
            return None

        wr, wrd, wsig = update(w["rating"], w["rd"], w["volatility"], l["rating"], l["rd"], 1.0)
        lr, lrd, lsig = update(l["rating"], l["rd"], l["volatility"], w["rating"], w["rd"], 0.0)

        base = f"{_url()}/rest/v1/profiles"
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

    return {
        winner_id: {
            "before":             round(w["rating"]),
            "after":              round(wr),
            "provisional_before": w["games_played"] < PROVISIONAL_THRESHOLD,
            "provisional_after":  (w["games_played"] + 1) < PROVISIONAL_THRESHOLD,
        },
        loser_id: {
            "before":             round(l["rating"]),
            "after":              round(lr),
            "provisional_before": l["games_played"] < PROVISIONAL_THRESHOLD,
            "provisional_after":  (l["games_played"] + 1) < PROVISIONAL_THRESHOLD,
        },
    }


async def get_display_rating(user_id: str) -> dict | None:
    """Returns {"rating": int, "provisional": bool} or None if unavailable."""
    if not _url() or not _svc_key():
        return None
    async with httpx.AsyncClient() as client:
        row = await _fetch(user_id, client)
    if not row:
        return None
    return {
        "rating":      round(row["rating"]),
        "provisional": row["games_played"] < PROVISIONAL_THRESHOLD,
    }
