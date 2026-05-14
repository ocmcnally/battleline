import { useState } from "react";

interface Props {
  onJoin: (token: string) => void;
}

export default function LobbyScreen({ onJoin }: Props) {
  const [username, setUsername] = useState("");
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState<string | null>(null);

  async function handleJoin() {
    const name = username.trim();
    if (!name) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/join", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: name }),
      });
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const data = await res.json() as { token: string };
      onJoin(data.token);
    } catch (e) {
      setError(String(e));
      setLoading(false);
    }
  }

  return (
    <div style={{
      display: "flex", flexDirection: "column", alignItems: "center",
      justifyContent: "center", height: "100vh", gap: 28,
    }}>
      <div style={{ textAlign: "center" }}>
        <h1 style={{ fontSize: "2.2rem", color: "var(--accent)", fontWeight: 800 }}>
          Battle Line
        </h1>
        <p style={{ color: "var(--text-dim)", marginTop: 4 }}>
          Clash of formations — 9 totems, 2 players
        </p>
      </div>

      <div style={{ display: "flex", gap: 10 }}>
        <input
          value={username}
          onChange={e => setUsername(e.target.value)}
          onKeyDown={e => e.key === "Enter" && handleJoin()}
          placeholder="Your name"
          autoFocus
          style={{
            padding: "10px 16px", borderRadius: 6,
            border: "1px solid var(--surface2)",
            background: "var(--surface)", color: "var(--text)",
            fontSize: "1rem", width: 200,
          }}
        />
        <button
          onClick={handleJoin}
          disabled={loading || !username.trim()}
          style={{ background: "var(--accent)", color: "#fff", fontWeight: 600 }}
        >
          {loading ? "Joining…" : "Join Queue"}
        </button>
      </div>

      {error && (
        <p style={{ color: "var(--claimed-opp)", fontSize: "0.9rem" }}>{error}</p>
      )}
    </div>
  );
}
