import { useState, useEffect, useCallback } from "react";
import type { User, OpenGame } from "../types";

interface Props {
  user:          User;
  onCreateGame:  (gameId: string) => void;
  onJoinGame:    (gameId: string) => void;
  onSignOut:     () => void;
}

function timeAgo(ts: number): string {
  const secs = Math.floor(Date.now() / 1000 - ts);
  if (secs < 5)  return "just now";
  if (secs < 60) return `${secs}s ago`;
  return `${Math.floor(secs / 60)}m ago`;
}

export default function LobbyPage({ user, onCreateGame, onJoinGame, onSignOut }: Props) {
  const [openGames, setOpenGames] = useState<OpenGame[]>([]);
  const [codeInput, setCodeInput] = useState("");
  const [creating, setCreating]   = useState(false);
  const [joining, setJoining]     = useState<string | null>(null); // game_id being joined
  const [error, setError]         = useState<string | null>(null);

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

  async function handleCreate() {
    setCreating(true);
    setError(null);
    try {
      const res = await fetch("/games", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: user.token, username: user.displayName }),
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
          ⚔️ Battle Line
        </span>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <span style={{ color: "var(--text-dim)", fontSize: "0.9rem" }}>
            {user.displayName}
          </span>
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
          display: "flex", justifyContent: "space-between", alignItems: "center", gap: 24,
        }}>
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
                  <div>
                    <span style={{ fontWeight: 600 }}>{g.creator}</span>
                    <span style={{ color: "var(--text-dim)", fontSize: "0.8rem", marginLeft: 12 }}>
                      {timeAgo(g.created_at)}
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
