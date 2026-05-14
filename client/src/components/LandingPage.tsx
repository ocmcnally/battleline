import { useState } from "react";
import { supabase } from "../lib/supabase";

export default function LandingPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState("");

  async function signInWithGoogle() {
    setLoading(true);
    setError("");
    const { error: err } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options:  { redirectTo: window.location.origin },
    });
    if (err) { setError(err.message); setLoading(false); }
    // On success the browser redirects — no further action needed
  }

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>

      {/* Nav */}
      <nav style={{
        padding: "16px 32px", display: "flex", justifyContent: "space-between",
        alignItems: "center", borderBottom: "1px solid var(--surface2)",
      }}>
        <span style={{ fontWeight: 800, fontSize: "1.1rem", color: "var(--accent)" }}>
          Battle Line
        </span>
        <button
          onClick={signInWithGoogle}
          disabled={loading}
          style={{
            background: "var(--accent)", color: "#fff", padding: "6px 18px",
            borderRadius: 6, border: "none", cursor: loading ? "not-allowed" : "pointer",
            fontWeight: 700, opacity: loading ? 0.7 : 1,
          }}
        >
          {loading ? "Redirecting…" : "Sign In"}
        </button>
      </nav>

      {/* Hero */}
      <main style={{
        flex: 1, display: "flex", flexDirection: "column",
        alignItems: "center", justifyContent: "center",
        padding: "48px 24px", textAlign: "center", gap: 32,
      }}>
        <div style={{ maxWidth: 560 }}>
          <h1 style={{ fontSize: "3.5rem", fontWeight: 900, lineHeight: 1.1, marginBottom: 16 }}>
            The ancient duel<br />
            <span style={{ color: "var(--accent)" }}>of formations.</span>
          </h1>
          <p style={{ fontSize: "1.15rem", color: "var(--text-dim)", lineHeight: 1.6 }}>
            Deploy troops, claim totems, outmaneuver your opponent.
            Win 5 totems or 3 in a row — first to break the line wins.
          </p>
        </div>

        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
          <button
            onClick={signInWithGoogle}
            disabled={loading}
            style={{
              display: "flex", alignItems: "center", gap: 12,
              background: "#fff", color: "#3c4043",
              padding: "12px 28px", borderRadius: 8,
              border: "1.5px solid #dadce0",
              fontWeight: 600, fontSize: "1rem",
              cursor: loading ? "not-allowed" : "pointer",
              boxShadow: "0 1px 3px rgba(0,0,0,0.12)",
              opacity: loading ? 0.7 : 1,
            }}
          >
            <GoogleIcon />
            {loading ? "Redirecting…" : "Continue with Google"}
          </button>
          {error && (
            <p style={{ color: "var(--claimed-opp)", fontSize: "0.85rem", margin: 0 }}>{error}</p>
          )}
        </div>

        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", justifyContent: "center" }}>
          {["9 totems", "60-card troop deck", "10 tactics cards", "Real-time multiplayer"].map(f => (
            <span key={f} style={{
              padding: "6px 14px", borderRadius: 20,
              background: "var(--surface)", border: "1px solid var(--surface2)",
              fontSize: "0.8rem", color: "var(--text-dim)",
            }}>
              {f}
            </span>
          ))}
        </div>
      </main>
    </div>
  );
}

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18">
      <path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.875 2.684-6.615z"/>
      <path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z"/>
      <path fill="#FBBC05" d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332z"/>
      <path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z"/>
    </svg>
  );
}
