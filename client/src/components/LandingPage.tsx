import { useState } from "react";
import type { User } from "../types";
import { supabase, fetchProfile, createProfile } from "../lib/supabase";

interface Props {
  onAuth: (user: User) => void;
}

type ModalMode = "signin" | "signup" | null;

const inputStyle: React.CSSProperties = {
  width: "100%", padding: "10px 14px", borderRadius: 6,
  background: "var(--bg)", color: "var(--text)", fontSize: "1rem",
  boxSizing: "border-box",
};

const btnPrimary: React.CSSProperties = {
  width: "100%", marginTop: 20, padding: "11px",
  background: "var(--accent)", color: "#fff",
  fontWeight: 700, fontSize: "1rem", borderRadius: 6, border: "none",
  cursor: "pointer",
};

const btnGhost: React.CSSProperties = {
  width: "100%", marginTop: 10, padding: "8px",
  background: "transparent", color: "var(--text-dim)",
  fontSize: "0.85rem", border: "none", cursor: "pointer",
};

export default function LandingPage({ onAuth }: Props) {
  const [modal, setModal]       = useState<ModalMode>(null);
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [name, setName]         = useState("");
  const [error, setError]       = useState("");
  const [loading, setLoading]   = useState(false);

  function openModal(mode: ModalMode) {
    setModal(mode);
    setEmail(""); setPassword(""); setName(""); setError("");
  }

  async function handleSignUp() {
    const trimName = name.trim();
    if (!trimName) { setError("Display name is required."); return; }
    if (trimName.length < 2) { setError("Name must be at least 2 characters."); return; }
    if (!email.includes("@")) { setError("Enter a valid email."); return; }
    if (password.length < 6) { setError("Password must be at least 6 characters."); return; }

    setLoading(true); setError("");
    const { data, error: signUpErr } = await supabase.auth.signUp({ email, password });
    if (signUpErr || !data.user) {
      setError(signUpErr?.message ?? "Sign-up failed."); setLoading(false); return;
    }
    await createProfile(data.user.id, trimName);
    onAuth({ displayName: trimName, token: data.user.id });
    setLoading(false);
  }

  async function handleSignIn() {
    if (!email) { setError("Enter your email."); return; }
    if (!password) { setError("Enter your password."); return; }

    setLoading(true); setError("");
    const { data, error: signInErr } = await supabase.auth.signInWithPassword({ email, password });
    if (signInErr || !data.user) {
      setError(signInErr?.message ?? "Sign-in failed."); setLoading(false); return;
    }
    const profile = await fetchProfile(data.user.id);
    if (!profile) {
      setError("Account found but no profile — contact support."); setLoading(false); return;
    }
    onAuth({ displayName: profile.display_name, token: data.user.id });
    setLoading(false);
  }

  const handleSubmit = modal === "signup" ? handleSignUp : handleSignIn;

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>

      {/* Nav */}
      <nav style={{
        padding: "16px 32px", display: "flex", justifyContent: "space-between",
        alignItems: "center", borderBottom: "1px solid var(--surface2)",
      }}>
        <span style={{ fontWeight: 800, fontSize: "1.1rem", color: "var(--accent)" }}>
          ⚔️ Battle Line
        </span>
        <div style={{ display: "flex", gap: 12 }}>
          <button onClick={() => openModal("signin")}
            style={{ background: "transparent", border: "1px solid var(--surface2)", color: "var(--text)", padding: "6px 18px", borderRadius: 6, cursor: "pointer" }}>
            Sign In
          </button>
          <button onClick={() => openModal("signup")}
            style={{ background: "var(--accent)", color: "#fff", padding: "6px 18px", borderRadius: 6, border: "none", cursor: "pointer" }}>
            Create Account
          </button>
        </div>
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

        <div style={{ display: "flex", gap: 14 }}>
          <button onClick={() => openModal("signup")}
            style={{ background: "var(--accent)", color: "#fff", fontWeight: 700, fontSize: "1rem", padding: "12px 32px", borderRadius: 6, border: "none", cursor: "pointer" }}>
            Play Now →
          </button>
          <button onClick={() => openModal("signin")}
            style={{ background: "transparent", border: "1px solid var(--surface2)", color: "var(--text)", fontSize: "1rem", padding: "12px 32px", borderRadius: 6, cursor: "pointer" }}>
            Sign In
          </button>
        </div>

        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", justifyContent: "center", marginTop: 8 }}>
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

      {/* Auth modal */}
      {modal && (
        <div
          style={{
            position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)",
            display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100,
          }}
          onClick={() => !loading && openModal(null)}
        >
          <div
            style={{
              background: "var(--surface)", borderRadius: 12, padding: "36px 40px",
              width: 380, boxShadow: "0 20px 60px rgba(0,0,0,0.5)",
              border: "1px solid var(--surface2)",
            }}
            onClick={e => e.stopPropagation()}
          >
            <h2 style={{ marginBottom: 24, fontSize: "1.4rem" }}>
              {modal === "signup" ? "Create Account" : "Welcome Back"}
            </h2>

            {/* Display name — signup only */}
            {modal === "signup" && (
              <div style={{ marginBottom: 14 }}>
                <label style={{ display: "block", marginBottom: 6, fontSize: "0.85rem", color: "var(--text-dim)" }}>
                  Display name
                </label>
                <input
                  autoFocus
                  value={name}
                  onChange={e => { setName(e.target.value); setError(""); }}
                  onKeyDown={e => e.key === "Enter" && handleSubmit()}
                  placeholder="e.g. Alexander"
                  style={{ ...inputStyle, border: "1px solid var(--surface2)" }}
                />
              </div>
            )}

            {/* Email */}
            <div style={{ marginBottom: 14 }}>
              <label style={{ display: "block", marginBottom: 6, fontSize: "0.85rem", color: "var(--text-dim)" }}>
                Email
              </label>
              <input
                autoFocus={modal === "signin"}
                type="email"
                value={email}
                onChange={e => { setEmail(e.target.value); setError(""); }}
                onKeyDown={e => e.key === "Enter" && handleSubmit()}
                placeholder="you@example.com"
                style={{ ...inputStyle, border: "1px solid var(--surface2)" }}
              />
            </div>

            {/* Password */}
            <div style={{ marginBottom: 4 }}>
              <label style={{ display: "block", marginBottom: 6, fontSize: "0.85rem", color: "var(--text-dim)" }}>
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={e => { setPassword(e.target.value); setError(""); }}
                onKeyDown={e => e.key === "Enter" && handleSubmit()}
                placeholder="••••••••"
                style={{ ...inputStyle, border: "1px solid var(--surface2)" }}
              />
            </div>

            {error && (
              <p style={{ color: "var(--claimed-opp)", fontSize: "0.8rem", marginTop: 8 }}>{error}</p>
            )}

            <button
              onClick={handleSubmit}
              disabled={loading}
              style={{ ...btnPrimary, opacity: loading ? 0.7 : 1, cursor: loading ? "not-allowed" : "pointer" }}
            >
              {loading ? "…" : modal === "signup" ? "Create Account" : "Sign In"}
            </button>

            <div style={{ marginTop: 16, textAlign: "center", fontSize: "0.82rem", color: "var(--text-dim)" }}>
              {modal === "signup" ? "Already have an account? " : "No account? "}
              <button
                onClick={() => openModal(modal === "signup" ? "signin" : "signup")}
                style={{ background: "none", border: "none", color: "var(--accent)", cursor: "pointer", fontWeight: 700, fontSize: "0.82rem" }}
              >
                {modal === "signup" ? "Sign in" : "Create one"}
              </button>
            </div>

            <button onClick={() => !loading && openModal(null)} style={btnGhost}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
