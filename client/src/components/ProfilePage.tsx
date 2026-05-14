import { useState, useEffect } from "react";
import type { User, RatingCategory } from "../types";
import { fetchProfile, profileRatings } from "../lib/supabase";

interface Props {
  user:     User;
  onBack:   () => void;
}

const CATEGORIES: { key: RatingCategory; label: string }[] = [
  { key: "bullet", label: "Bullet"  },
  { key: "blitz",  label: "Blitz"   },
  { key: "rapid",  label: "Rapid"   },
];

function formatRating(rating: number, provisional: boolean): string {
  return provisional ? `${rating}?` : `${rating}`;
}

export default function ProfilePage({ user, onBack }: Props) {
  const [ratings, setRatings] = useState(user.ratings);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchProfile(user.token).then(profile => {
      if (profile) setRatings(profileRatings(profile));
      setLoading(false);
    });
  }, [user.token]);

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

      <main style={{ flex: 1, maxWidth: 560, margin: "0 auto", width: "100%", padding: "40px 24px" }}>
        <div style={{ marginBottom: 32 }}>
          <h1 style={{ fontSize: "1.6rem", fontWeight: 800, marginBottom: 4 }}>
            {user.displayName}
          </h1>
          <p style={{ color: "var(--text-dim)", fontSize: "0.9rem" }}>Player profile</p>
        </div>

        <div style={{
          background: "var(--surface)", borderRadius: 12, padding: "24px 28px",
          border: "1px solid var(--surface2)",
        }}>
          <div style={{
            fontSize: "0.78rem", fontWeight: 700, color: "var(--text-dim)",
            textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 20,
          }}>
            Ratings
          </div>

          {loading ? (
            <div style={{ color: "var(--text-dim)", fontSize: "0.9rem" }}>Loading…</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
              {CATEGORIES.map(({ key, label }, i) => {
                const cr = ratings[key];
                return (
                  <div
                    key={key}
                    style={{
                      display: "flex", justifyContent: "space-between", alignItems: "center",
                      padding: "14px 0",
                      borderBottom: i < CATEGORIES.length - 1 ? "1px solid var(--surface2)" : "none",
                    }}
                  >
                    <span style={{ fontWeight: 600, fontSize: "1rem" }}>{label}</span>
                    {cr ? (
                      <div style={{ textAlign: "right" }}>
                        <span style={{
                          fontFamily: "monospace", fontWeight: 800, fontSize: "1.2rem",
                          color: "var(--accent)",
                        }}>
                          {formatRating(cr.rating, cr.provisional)}
                        </span>
                        {cr.provisional && (
                          <span style={{
                            display: "block", fontSize: "0.72rem",
                            color: "var(--text-dim)", marginTop: 2,
                          }}>
                            provisional
                          </span>
                        )}
                      </div>
                    ) : (
                      <span style={{ color: "var(--text-dim)", fontSize: "0.9rem" }}>
                        No games yet
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
