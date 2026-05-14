import { useState, useEffect } from "react";
import type { RatingCategory } from "../types";
import { fetchLeaderboard, type LeaderboardEntry } from "../lib/supabase";

interface Props {
  onBack: () => void;
}

const CATEGORIES: { key: RatingCategory; label: string }[] = [
  { key: "bullet", label: "Bullet" },
  { key: "blitz",  label: "Blitz"  },
  { key: "rapid",  label: "Rapid"  },
];

export default function LeaderboardPage({ onBack }: Props) {
  const [category, setCategory] = useState<RatingCategory>("blitz");
  const [entries, setEntries]   = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading]   = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchLeaderboard(category).then(rows => {
      setEntries(rows);
      setLoading(false);
    });
  }, [category]);

  const firstProvisionalIdx = entries.findIndex(e => e.provisional);
  const hasProvisional = firstProvisionalIdx !== -1;
  const established = hasProvisional ? entries.slice(0, firstProvisionalIdx) : entries;

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <nav style={{
        padding: "14px 32px", display: "flex", justifyContent: "space-between",
        alignItems: "center", borderBottom: "1px solid var(--surface2)",
        background: "var(--surface)",
      }}>
        <span style={{ fontWeight: 800, fontSize: "1.1rem", color: "var(--accent)" }}>
          Battle Line
        </span>
        <button
          onClick={onBack}
          style={{
            background: "transparent", border: "1px solid var(--surface2)",
            color: "var(--text-dim)", padding: "5px 14px", fontSize: "0.85rem",
          }}
        >
          ← Back to Lobby
        </button>
      </nav>

      <main style={{ flex: 1, maxWidth: 600, margin: "0 auto", width: "100%", padding: "40px 24px" }}>
        <h1 style={{ fontSize: "1.6rem", fontWeight: 800, marginBottom: 24 }}>Leaderboard</h1>

        {/* Category tabs */}
        <div style={{ display: "flex", gap: 8, marginBottom: 24 }}>
          {CATEGORIES.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setCategory(key)}
              style={{
                padding: "6px 20px", borderRadius: 6, fontWeight: 600, fontSize: "0.9rem",
                cursor: "pointer",
                background: category === key ? "var(--accent)" : "var(--bg)",
                color:      category === key ? "#fff" : "var(--text-dim)",
                border:     category === key ? "1.5px solid var(--accent)" : "1.5px solid var(--surface2)",
              }}
            >
              {label}
            </button>
          ))}
        </div>

        <div style={{
          background: "var(--surface)", borderRadius: 12,
          border: "1px solid var(--surface2)", overflow: "hidden",
        }}>
          {loading ? (
            <div style={{ padding: "40px", textAlign: "center", color: "var(--text-dim)", fontSize: "0.9rem" }}>
              Loading…
            </div>
          ) : entries.length === 0 ? (
            <div style={{ padding: "40px", textAlign: "center", color: "var(--text-dim)", fontSize: "0.9rem" }}>
              No rated games played yet.
            </div>
          ) : (
            <>
              <RankTable entries={established} startRank={1} />
              {hasProvisional && (
                <>
                  <div style={{
                    padding: "8px 20px", fontSize: "0.75rem", fontWeight: 700,
                    color: "var(--text-dim)", textTransform: "uppercase",
                    letterSpacing: "0.07em", borderTop: "1px solid var(--surface2)",
                    background: "rgba(255,255,255,0.02)",
                  }}>
                    Provisional
                  </div>
                  <RankTable entries={entries.slice(firstProvisionalIdx)} startRank={null} />
                </>
              )}
            </>
          )}
        </div>
      </main>
    </div>
  );
}

function RankTable({ entries, startRank }: { entries: LeaderboardEntry[]; startRank: number | null }) {
  return (
    <>
      {entries.map((e, i) => (
        <div
          key={`${e.display_name}-${i}`}
          style={{
            display: "grid",
            gridTemplateColumns: "40px 1fr 80px 60px",
            alignItems: "center",
            padding: "12px 20px",
            borderTop: i === 0 ? "none" : "1px solid var(--surface2)",
          }}
        >
          <span style={{ color: "var(--text-dim)", fontSize: "0.85rem", fontFamily: "monospace" }}>
            {startRank !== null ? `#${startRank + i}` : "—"}
          </span>
          <span style={{ fontWeight: 600, fontSize: "0.95rem" }}>{e.display_name}</span>
          <span style={{
            fontFamily: "monospace", fontWeight: 800, fontSize: "1rem",
            color: "var(--accent)", textAlign: "right",
          }}>
            {e.provisional ? `${e.rating}?` : `${e.rating}`}
          </span>
          <span style={{
            color: "var(--text-dim)", fontSize: "0.78rem",
            textAlign: "right", paddingRight: 4,
          }}>
            {e.games_played}g
          </span>
        </div>
      ))}
    </>
  );
}
