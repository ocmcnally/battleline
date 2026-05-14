import { useState } from "react";
import type { User } from "../types";
import { updateUsername } from "../lib/supabase";

interface Props {
  user:       User;
  onComplete: (displayName: string) => void;
}

const MAX_LEN = 20;
const MIN_LEN = 2;
const VALID   = /^[a-zA-Z0-9_ ]+$/;

function validate(name: string): string | null {
  const t = name.trim();
  if (t.length < MIN_LEN) return `At least ${MIN_LEN} characters required.`;
  if (t.length > MAX_LEN) return `Maximum ${MAX_LEN} characters.`;
  if (!VALID.test(t))     return "Letters, numbers, spaces, and underscores only.";
  return null;
}

export default function UsernameSetup({ user, onComplete }: Props) {
  const [name,    setName]    = useState("");
  const [error,   setError]   = useState<string | null>(null);
  const [saving,  setSaving]  = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = name.trim();
    const validErr = validate(trimmed);
    if (validErr) { setError(validErr); return; }

    setSaving(true);
    setError(null);
    const err = await updateUsername(user.token, trimmed);
    if (err) {
      setError("Couldn't save — please try again.");
      setSaving(false);
      return;
    }
    onComplete(trimmed);
  }

  return (
    <div style={{
      minHeight: "100vh", display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center",
      background: "var(--bg)", padding: "24px",
    }}>
      <div style={{
        background: "var(--surface)", borderRadius: 14,
        border: "1.5px solid var(--surface2)",
        padding: "40px 44px", maxWidth: 400, width: "100%",
        boxShadow: "0 8px 32px rgba(0,0,0,0.25)",
      }}>
        <div style={{ fontWeight: 900, fontSize: "1.5rem", color: "var(--accent)", marginBottom: 8 }}>
          Battle Line
        </div>
        <h2 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: 6 }}>
          Choose your username
        </h2>
        <p style={{ color: "var(--text-dim)", fontSize: "0.875rem", marginBottom: 28, lineHeight: 1.5 }}>
          This is how opponents will see you in-game. You can use letters, numbers, spaces, and underscores.
        </p>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ position: "relative" }}>
            <input
              autoFocus
              value={name}
              onChange={e => { setName(e.target.value); setError(null); }}
              maxLength={MAX_LEN}
              placeholder="e.g. WarriorKing"
              style={{
                width: "100%", padding: "11px 14px", boxSizing: "border-box",
                borderRadius: 7, fontSize: "1rem",
                border: `1.5px solid ${error ? "var(--claimed-opp)" : "var(--surface2)"}`,
                background: "var(--bg)", color: "var(--text)",
                outline: "none",
              }}
            />
            <span style={{
              position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)",
              fontSize: "0.7rem", color: "var(--text-dim)",
            }}>
              {name.trim().length}/{MAX_LEN}
            </span>
          </div>

          {error && (
            <div style={{ color: "var(--claimed-opp)", fontSize: "0.82rem" }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={saving || name.trim().length < MIN_LEN}
            style={{
              marginTop: 4,
              background: saving || name.trim().length < MIN_LEN ? "var(--surface2)" : "var(--accent)",
              color: saving || name.trim().length < MIN_LEN ? "var(--text-dim)" : "#fff",
              border: "none", borderRadius: 7, padding: "11px",
              fontWeight: 700, fontSize: "1rem",
              cursor: saving || name.trim().length < MIN_LEN ? "not-allowed" : "pointer",
            }}
          >
            {saving ? "Saving…" : "Continue →"}
          </button>
        </form>
      </div>
    </div>
  );
}
