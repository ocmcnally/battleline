import { useState, useEffect, useCallback } from "react";
import type { User, OpenGame } from "../types";

interface Props {
  user:           User;
  onCreateGame:   (gameId: string) => void;
  onJoinGame:     (gameId: string) => void;
  onSignOut:      () => void;
  onViewProfile:  () => void;
}

function timeAgo(ts: number): string {
  const secs = Math.floor(Date.now() / 1000 - ts);
  if (secs < 5)  return "just now";
  if (secs < 60) return `${secs}s ago`;
  return `${Math.floor(secs / 60)}m ago`;
}

type TimeControl = "unlimited" | "bullet" | "blitz" | "rapid";

// All values in seconds; step is always 30s
const TC_RANGES: Record<Exclude<TimeControl, "unlimited">, { min: number; max: number; default: number }> = {
  bullet: { min: 120, max: 270, default: 180 },
  blitz:  { min: 300, max: 570, default: 420 },
  rapid:  { min: 600, max: 1200, default: 900 },
};

function formatSecs(s: number): string {
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}:${String(sec).padStart(2, "0")}`;
}

function formatRating(rating: number | null, provisional: boolean | null): string {
  if (rating === null) return "?";
  return provisional ? `${Math.round(rating)}?` : `${Math.round(rating)}`;
}

export default function LobbyPage({ user, onCreateGame, onJoinGame, onSignOut, onViewProfile }: Props) {
  const [openGames, setOpenGames] = useState<OpenGame[]>([]);
  const [codeInput, setCodeInput] = useState("");
  const [creating, setCreating]   = useState(false);
  const [joining, setJoining]     = useState<string | null>(null);
  const [error, setError]         = useState<string | null>(null);

  const [timeControl,    setTimeControl]    = useState<TimeControl>("unlimited");
  const [timeSecs,       setTimeSecs]       = useState(180);
  const [incrementSecs,  setIncrementSecs]  = useState(0);
  const [rated,          setRated]          = useState(true);

  const fetchGames = useCallback(async () => {
    try {
      const res = await fetch("/games");
      const data = await res.json() as { games: OpenGame[] };
      setOpenGames(data.games);
    } catch {
      // silently ignore poll failures
    }
  }, []);

  // Poll open games every 4 seconds
  useEffect(() => {
    fetchGames();
    const id = setInterval(fetchGames, 4000);
    return () => clearInterval(id);
  }, [fetchGames]);

  const timeMsForCreate = timeControl === "unlimited" ? null : timeSecs * 1000;
  const isRated = timeControl !== "unlimited" && rated;

  async function handleCreate() {
    setCreating(true);
    setError(null);
    try {
      const res = await fetch("/games", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          token: user.token,
          username: user.displayName,
          time_ms: timeMsForCreate,
          increment_ms: timeControl === "unlimited" ? 0 : incrementSecs * 1000,
          rated: isRated,
          category: timeControl === "unlimited" ? null : timeControl,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json() as { game_id: string };
      onCreateGame(data.game_id);
    } catch (e) {
      setError(String(e));
      setCreating(false);
    }
  }

  async function handleJoin(gameId: string) {
    setJoining(gameId);
    setError(null);
    try {
      const res = await fetch(`/games/${gameId}/join`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: user.token, username: user.displayName }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: "Unknown error" })) as { detail: string };
        throw new Error(body.detail);
      }
      onJoinGame(gameId);
    } catch (e) {
      setError(String(e));
      setJoining(null);
    }
  }

  async function handleJoinByCode() {
    const code = codeInput.trim().toUpperCase();
    if (!code) return;
    await handleJoin(code);
  }

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>

      {/* Nav */}
      <nav style={{
        padding: "14px 32px", display: "flex", justifyContent: "space-between",
        alignItems: "center", borderBottom: "1px solid var(--surface2)",
        background: "var(--surface)",
      }}>
        <span style={{ fontWeight: 800, fontSize: "1.1rem", color: "var(--accent)" }}>
          Battle Line
        </span>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <button
            onClick={onViewProfile}
            style={{
              background: "transparent", border: "none", padding: 0,
              color: "var(--text-dim)", fontSize: "0.9rem", cursor: "pointer",
            }}
          >
            {user.displayName}
            {timeControl !== "unlimited" && (() => {
              const cr = user.ratings[timeControl];
              return cr ? (
                <span style={{ marginLeft: 8, color: "var(--accent)", fontWeight: 700, fontFamily: "monospace" }}>
                  {formatRating(cr.rating, cr.provisional)}
                </span>
              ) : null;
            })()}
          </button>
          <button
            onClick={onSignOut}
            style={{
              background: "transparent", border: "1px solid var(--surface2)",
              color: "var(--text-dim)", padding: "5px 14px", fontSize: "0.85rem",
            }}
          >
            Sign Out
          </button>
        </div>
      </nav>

      {/* Main content */}
      <main style={{ flex: 1, maxWidth: 720, margin: "0 auto", width: "100%", padding: "40px 24px" }}>

        {error && (
          <div style={{
            padding: "10px 16px", marginBottom: 24,
            background: "#5c1a1a", color: "#ff9999",
            borderRadius: 8, fontSize: "0.9rem",
          }}>
            {error}
          </div>
        )}

        {/* Create game card */}
        <div style={{
          background: "var(--surface)", borderRadius: 12, padding: "28px 32px",
          border: "1px solid var(--surface2)", marginBottom: 32,
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 24, marginBottom: 24 }}>
            <div>
              <h2 style={{ fontSize: "1.2rem", marginBottom: 6 }}>Start a New Game</h2>
              <p style={{ color: "var(--text-dim)", fontSize: "0.9rem", maxWidth: 360 }}>
                Create a private game and share the code with a friend, or wait for
                someone to join from the open games list.
              </p>
            </div>
            <button
              onClick={handleCreate}
              disabled={creating}
              style={{
                background: "var(--accent)", color: "#fff", fontWeight: 700,
                fontSize: "1rem", padding: "12px 28px", flexShrink: 0,
                whiteSpace: "nowrap",
              }}
            >
              {creating ? "Creating…" : "Create Game →"}
            </button>
          </div>

          {/* Time control settings */}
          <div style={{ borderTop: "1px solid var(--surface2)", paddingTop: 20 }}>
            <div style={{ fontSize: "0.78rem", fontWeight: 700, color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 10 }}>
              Time Control
            </div>

            {/* Preset buttons */}
            <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
              {(["unlimited", "bullet", "blitz", "rapid"] as TimeControl[]).map(tc => (
                <button
                  key={tc}
                  onClick={() => {
                    setTimeControl(tc);
                    if (tc !== "unlimited") setTimeSecs(TC_RANGES[tc].default);
                  }}
                  style={{
                    padding: "6px 16px", borderRadius: 6, fontWeight: 600, fontSize: "0.85rem",
                    cursor: "pointer", textTransform: "capitalize",
                    background: timeControl === tc ? "var(--accent)" : "var(--bg)",
                    color:      timeControl === tc ? "#fff" : "var(--text-dim)",
                    border:     timeControl === tc ? "1.5px solid var(--accent)" : "1.5px solid var(--surface2)",
                  }}
                >
                  {tc === "bullet" ? "Bullet" : tc === "blitz" ? "Blitz" : tc === "rapid" ? "Rapid" : "Unlimited"}
                </button>
              ))}
            </div>

            {/* Time slider (hidden for unlimited) */}
            {timeControl !== "unlimited" && (
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
                <span style={{ fontSize: "0.8rem", color: "var(--text-dim)", width: 120 }}>
                  Time per player:
                </span>
                <input
                  type="range"
                  min={TC_RANGES[timeControl].min}
                  max={TC_RANGES[timeControl].max}
                  step={30}
                  value={timeSecs}
                  onChange={e => setTimeSecs(Number(e.target.value))}
                  style={{ flex: 1 }}
                />
                <span style={{ fontSize: "0.9rem", fontWeight: 700, width: 48, textAlign: "right" }}>
                  {formatSecs(timeSecs)}
                </span>
              </div>
            )}

            {/* Increment slider — hidden for unlimited */}
            {timeControl !== "unlimited" && (
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
                <span style={{ fontSize: "0.8rem", color: "var(--text-dim)", width: 120 }}>
                  Increment:
                </span>
                <input
                  type="range"
                  min={0}
                  max={30}
                  value={incrementSecs}
                  onChange={e => setIncrementSecs(Number(e.target.value))}
                  style={{ flex: 1 }}
                />
                <span style={{ fontSize: "0.9rem", fontWeight: 700, width: 48, textAlign: "right" }}>
                  {incrementSecs === 0 ? "None" : `+${incrementSecs}s`}
                </span>
              </div>
            )}

            {/* Rated toggle — only for timed games */}
            {timeControl !== "unlimited" && (
              <div style={{ borderTop: "1px solid var(--surface2)", paddingTop: 16 }}>
                <div style={{ fontSize: "0.78rem", fontWeight: 700, color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 10 }}>
                  Game Type
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  {([true, false] as const).map(r => (
                    <button
                      key={String(r)}
                      onClick={() => setRated(r)}
                      style={{
                        padding: "6px 20px", borderRadius: 6, fontWeight: 600, fontSize: "0.85rem",
                        cursor: "pointer",
                        background: rated === r ? "var(--accent)" : "var(--bg)",
                        color:      rated === r ? "#fff" : "var(--text-dim)",
                        border:     rated === r ? "1.5px solid var(--accent)" : "1.5px solid var(--surface2)",
                      }}
                    >
                      {r ? "Rated" : "Unrated"}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Join by code */}
        <div style={{ marginBottom: 32 }}>
          <h3 style={{ fontSize: "0.85rem", fontWeight: 700, color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 10 }}>
            Join by Code
          </h3>
          <div style={{ display: "flex", gap: 10 }}>
            <input
              value={codeInput}
              onChange={e => setCodeInput(e.target.value.toUpperCase())}
              onKeyDown={e => e.key === "Enter" && handleJoinByCode()}
              placeholder="Enter game code (e.g. A1B2C3D4)"
              style={{
                flex: 1, padding: "10px 14px", borderRadius: 6,
                border: "1px solid var(--surface2)",
                background: "var(--surface)", color: "var(--text)", fontSize: "0.95rem",
                fontFamily: "monospace", letterSpacing: "0.05em",
              }}
            />
            <button
              onClick={handleJoinByCode}
              disabled={!codeInput.trim() || joining !== null}
              style={{ background: "var(--surface2)", color: "var(--text)", padding: "10px 22px", fontWeight: 600 }}
            >
              Join
            </button>
          </div>
        </div>

        {/* Open games list */}
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <h3 style={{ fontSize: "0.85rem", fontWeight: 700, color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
              Open Games
            </h3>
            <button
              onClick={fetchGames}
              style={{ background: "transparent", color: "var(--text-dim)", fontSize: "0.8rem", padding: "4px 10px", border: "1px solid var(--surface2)" }}
            >
              ↻ Refresh
            </button>
          </div>

          {openGames.length === 0 ? (
            <div style={{
              padding: "32px", textAlign: "center",
              background: "var(--surface)", borderRadius: 8,
              border: "1px dashed var(--surface2)",
              color: "var(--text-dim)", fontSize: "0.9rem",
            }}>
              No open games right now — create one!
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {openGames.map(g => (
                <div
                  key={g.game_id}
                  style={{
                    display: "flex", justifyContent: "space-between", alignItems: "center",
                    padding: "14px 20px", background: "var(--surface)",
                    borderRadius: 8, border: "1px solid var(--surface2)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 6 }}>
                    <span style={{ fontWeight: 600 }}>{g.creator}</span>
                    {g.creator_rating !== null && (
                      <span style={{ fontSize: "0.8rem", color: "var(--accent)", fontFamily: "monospace", fontWeight: 700 }}>
                        {formatRating(g.creator_rating, g.creator_provisional)}
                      </span>
                    )}
                    <span style={{ color: "var(--text-dim)", fontSize: "0.8rem" }}>
                      {timeAgo(g.created_at)}
                    </span>
                    <span style={{
                      fontSize: "0.75rem", fontWeight: 600,
                      color: "var(--accent)", background: "rgba(201,106,42,0.1)",
                      padding: "2px 8px", borderRadius: 4,
                    }}>
                      {g.time_label}
                    </span>
                    <span style={{
                      fontSize: "0.75rem", fontWeight: 600,
                      color: g.rated ? "#6ab04c" : "var(--text-dim)",
                      background: g.rated ? "rgba(106,176,76,0.12)" : "rgba(255,255,255,0.05)",
                      padding: "2px 8px", borderRadius: 4,
                    }}>
                      {g.rated ? "Rated" : "Unrated"}
                    </span>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <span style={{ color: "var(--text-dim)", fontSize: "0.75rem", fontFamily: "monospace" }}>
                      {g.game_id}
                    </span>
                    <button
                      onClick={() => handleJoin(g.game_id)}
                      disabled={joining !== null}
                      style={{
                        background: "var(--surface2)", color: "var(--text)",
                        padding: "6px 18px", fontWeight: 600, fontSize: "0.9rem",
                      }}
                    >
                      {joining === g.game_id ? "Joining…" : "Join"}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
