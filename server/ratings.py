"""Supabase rating read/write via REST API — per time-control category."""
import os
import httpx

PROVISIONAL_THRESHOLD = 10

# Columns in the profiles table for each category
_COLS = {
    "bullet": ("bullet_rating", "bullet_rd", "bullet_volatility", "bullet_games_played"),
    "blitz":  ("blitz_rating",  "blitz_rd",  "blitz_volatility",  "blitz_games_played"),
    "rapid":  ("rapid_rating",  "rapid_rd",  "rapid_volatility",  "rapid_games_played"),
}


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


async def _fetch(user_id: str, category: str, client: httpx.AsyncClient) -> dict | None:
    r_col, rd_col, sig_col, gp_col = _COLS[category]
    url = (f"{_url()}/rest/v1/profiles"
           f"?id=eq.{user_id}"
           f"&select=id,{r_col},{rd_col},{sig_col},{gp_col}")
    r = await client.get(url, headers=_headers())
    print(f"[ratings] fetch {user_id[:8]}… → {r.status_code} {r.text[:300]}")
    if r.status_code != 200:
        return None
    rows = r.json()
    if not rows:
        return None
    row = rows[0]
    # Apply defaults for rows created before the migration
    return {
        "rating":      row.get(r_col)   or 1500,
        "rd":          row.get(rd_col)  or 350,
        "volatility":  row.get(sig_col) or 0.06,
        "games_played": row.get(gp_col) or 0,
    }


async def settle_game(winner_id: str, loser_id: str, category: str | None) -> dict | None:
    """
    Compute and persist Glicko-2 updates for the given category.
    Returns {token: {before, after, provisional_before, provisional_after}} or None on failure.
    """
    if not category or category not in _COLS:
        print(f"[ratings] skipping — no valid category ({category!r})")
        return None
    if not _url() or not _svc_key():
        print("[ratings] SUPABASE_URL or SUPABASE_SERVICE_KEY not set — skipping")
        return None

    print(f"[ratings] settling {category} — {winner_id[:8]} beat {loser_id[:8]}")

    from .glicko2 import update

    r_col, rd_col, sig_col, gp_col = _COLS[category]

    try:
        async with httpx.AsyncClient() as client:
            w = await _fetch(winner_id, category, client)
            l = await _fetch(loser_id,  category, client)
            if not w or not l:
                print(f"[ratings] could not fetch profiles w={w} l={l}")
                return None

            wr, wrd, wsig = update(w["rating"], w["rd"], w["volatility"], l["rating"], l["rd"], 1.0)
            lr, lrd, lsig = update(l["rating"], l["rd"], l["volatility"], w["rating"], w["rd"], 0.0)

            base = f"{_url()}/rest/v1/profiles"
            rw = await client.patch(
                base + f"?id=eq.{winner_id}",
                json={r_col: round(wr, 1), rd_col: round(wrd, 1), sig_col: wsig,
                      gp_col: w["games_played"] + 1},
                headers=_headers(),
            )
            rl = await client.patch(
                base + f"?id=eq.{loser_id}",
                json={r_col: round(lr, 1), rd_col: round(lrd, 1), sig_col: lsig,
                      gp_col: l["games_played"] + 1},
                headers=_headers(),
            )
            print(f"[ratings] patch winner→{rw.status_code} loser→{rl.status_code}")
            if rw.status_code not in (200, 204) or rl.status_code not in (200, 204):
                print(f"[ratings] patch failed: {rw.text[:300]} / {rl.text[:300]}")
                return None
    except Exception as e:
        print(f"[ratings] error: {e}")
        return None

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


async def get_display_rating(user_id: str, category: str | None) -> dict | None:
    """Returns {"rating": int, "provisional": bool} or None if unavailable."""
    if not category or category not in _COLS:
        return None
    if not _url() or not _svc_key():
        return None
    async with httpx.AsyncClient() as client:
        row = await _fetch(user_id, category, client)
    if not row:
        return None
    return {
        "rating":      round(row["rating"]),
        "provisional": row["games_played"] < PROVISIONAL_THRESHOLD,
    }
