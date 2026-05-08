import { useState } from "react";
import type { User } from "../types";

interface Props {
  onAuth: (user: User) => void;
}

type ModalMode = "signin" | "signup" | null;

export default function LandingPage({ onAuth }: Props) {
  const [modal, setModal]       = useState<ModalMode>(null);
  const [name, setName]         = useState("");
  const [nameError, setNameError] = useState("");

  function handleSubmit() {
    const trimmed = name.trim();
    if (!trimmed) { setNameError("Please enter a display name."); return; }
    if (trimmed.length < 2) { setNameError("Name must be at least 2 characters."); return; }
    const token = crypto.randomUUID().replace(/-/g, "");
    onAuth({ displayName: trimmed, token });
  }

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
          <button
            onClick={() => { setModal("signin"); setName(""); setNameError(""); }}
            style={{ background: "transparent", border: "1px solid var(--surface2)", color: "var(--text)", padding: "6px 18px" }}
          >
            Sign In
          </button>
          <button
            onClick={() => { setModal("signup"); setName(""); setNameError(""); }}
            style={{ background: "var(--accent)", color: "#fff", padding: "6px 18px" }}
          >
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
          <button
            onClick={() => { setModal("signup"); setName(""); setNameError(""); }}
            style={{ background: "var(--accent)", color: "#fff", fontWeight: 700, fontSize: "1rem", padding: "12px 32px" }}
          >
            Play Now →
          </button>
          <button
            onClick={() => { setModal("signin"); setName(""); setNameError(""); }}
            style={{ background: "transparent", border: "1px solid var(--surface2)", color: "var(--text)", fontSize: "1rem", padding: "12px 32px" }}
          >
            Sign In
          </button>
        </div>

        {/* Feature chips */}
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
            display: "flex", alignItems: "center", justifyContent: "center",
            zIndex: 100,
          }}
          onClick={() => setModal(null)}
        >
          <div
            style={{
              background: "var(--surface)", borderRadius: 12, padding: "36px 40px",
              width: 380, boxShadow: "0 20px 60px rgba(0,0,0,0.5)",
              border: "1px solid var(--surface2)",
            }}
            onClick={e => e.stopPropagation()}
          >
            <h2 style={{ marginBottom: 8, fontSize: "1.4rem" }}>
              {modal === "signup" ? "Create Account" : "Welcome Back"}
            </h2>
            <p style={{ color: "var(--text-dim)", fontSize: "0.85rem", marginBottom: 24 }}>
              Enter a display name to get started. Full accounts coming soon.
            </p>

            <label style={{ display: "block", marginBottom: 6, fontSize: "0.85rem", color: "var(--text-dim)" }}>
              Display name
            </label>
            <input
              autoFocus
              value={name}
              onChange={e => { setName(e.target.value); setNameError(""); }}
              onKeyDown={e => e.key === "Enter" && handleSubmit()}
              placeholder="e.g. Alexander"
              style={{
                width: "100%", padding: "10px 14px", borderRadius: 6,
                border: nameError ? "1px solid var(--claimed-opp)" : "1px solid var(--surface2)",
                background: "var(--bg)", color: "var(--text)", fontSize: "1rem",
              }}
            />
            {nameError && (
              <p style={{ color: "var(--claimed-opp)", fontSize: "0.8rem", marginTop: 6 }}>{nameError}</p>
            )}

            <button
              onClick={handleSubmit}
              disabled={!name.trim()}
              style={{
                width: "100%", marginTop: 20, padding: "11px",
                background: "var(--accent)", color: "#fff",
                fontWeight: 700, fontSize: "1rem", borderRadius: 6,
              }}
            >
              Continue →
            </button>

            <button
              onClick={() => setModal(null)}
              style={{
                width: "100%", marginTop: 10, padding: "8px",
                background: "transparent", color: "var(--text-dim)", fontSize: "0.85rem",
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
