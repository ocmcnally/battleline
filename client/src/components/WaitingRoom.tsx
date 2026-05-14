import { useState, useEffect } from "react";
import type { User } from "../types";

interface Props {
  user:     User;
  gameId:   string;
  onCancel: () => void;
}

export default function WaitingRoom({ user, gameId, onCancel }: Props) {
  const [copied, setCopied] = useState(false);
  const [dots, setDots]     = useState("●  ");

  // Animate the waiting dots
  useEffect(() => {
    const frames = ["●  ", "●● ", "●●●", " ●●", "  ●", "   "];
    let i = 0;
    const id = setInterval(() => {
      i = (i + 1) % frames.length;
      setDots(frames[i]);
    }, 300);
    return () => clearInterval(id);
  }, []);

  async function handleCancel() {
    try {
      await fetch(`/games/${gameId}?token=${user.token}`, { method: "DELETE" });
    } catch {
      // best-effort
    }
    onCancel();
  }

  function copyCode() {
    navigator.clipboard.writeText(gameId).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  function copyLink() {
    const url = `${location.origin}?join=${gameId}`;
    navigator.clipboard.writeText(url).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div style={{
      minHeight: "100vh", display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center", gap: 32, padding: 24,
    }}>

      {/* Header */}
      <div style={{ textAlign: "center" }}>
        <h1 style={{ fontSize: "1.8rem", fontWeight: 800 }}>Game Created</h1>
        <p style={{ color: "var(--text-dim)", marginTop: 6 }}>
          Share the code below with a friend to start playing.
        </p>
      </div>

      {/* Game code card */}
      <div style={{
        background: "var(--surface)", borderRadius: 12, padding: "32px 40px",
        border: "1px solid var(--surface2)", textAlign: "center", width: "100%", maxWidth: 400,
      }}>
        <p style={{ color: "var(--text-dim)", fontSize: "0.8rem", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 12 }}>
          Game Code
        </p>
        <div style={{
          fontSize: "2.2rem", fontWeight: 900, letterSpacing: "0.2em",
          fontFamily: "monospace", color: "var(--accent)", marginBottom: 20,
        }}>
          {gameId}
        </div>
        <div style={{ display: "flex", gap: 10, justifyContent: "center" }}>
          <button
            onClick={copyCode}
            style={{
              background: copied ? "var(--claimed-me)" : "var(--surface2)",
              color: "#fff", fontWeight: 600, padding: "8px 20px", fontSize: "0.9rem",
            }}
          >
            {copied ? "Copied!" : "Copy Code"}
          </button>
          <button
            onClick={copyLink}
            style={{
              background: "transparent", border: "1px solid var(--surface2)",
              color: "var(--text-dim)", padding: "8px 20px", fontSize: "0.9rem",
            }}
          >
            Copy Link
          </button>
        </div>
      </div>

      {/* Waiting indicator */}
      <div style={{ textAlign: "center", color: "var(--text-dim)" }}>
        <div style={{
          fontFamily: "monospace", fontSize: "1.4rem",
          color: "var(--accent)", marginBottom: 8, letterSpacing: "0.1em",
        }}>
          {dots}
        </div>
        <p>Waiting for opponent to join…</p>
      </div>

      {/* Cancel */}
      <button
        onClick={handleCancel}
        style={{
          background: "transparent", border: "1px solid var(--surface2)",
          color: "var(--text-dim)", padding: "8px 24px", fontSize: "0.9rem",
        }}
      >
        ← Cancel
      </button>
    </div>
  );
}
