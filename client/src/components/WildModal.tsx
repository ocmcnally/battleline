import { useState } from "react";
import type { TacticsCard } from "../types";

const SUITS = ["blue", "red", "orange", "yellow", "green", "purple"];
const SUIT_LABEL: Record<string, string> = {
  blue: "●", red: "♦", orange: "▲", yellow: "★", green: "♣", purple: "♠",
};
const SUIT_COLOR: Record<string, string> = {
  blue: "var(--suit-blue)", red: "var(--suit-red)", orange: "var(--suit-orange)",
  yellow: "var(--suit-yellow)", green: "var(--suit-green)", purple: "var(--suit-purple)",
};

function allowedValues(name: string): number[] {
  if (name === "wild8")   return [8];
  if (name === "wild321") return [1, 2, 3];
  return [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
}

interface Props {
  tactic:    TacticsCard;
  onConfirm: (suit: string, value: number) => void;
  onCancel:  () => void;
}

export default function WildModal({ tactic, onConfirm, onCancel }: Props) {
  const values = allowedValues(tactic.name);
  const [suit,  setSuit]  = useState<string | null>(null);
  const [value, setValue] = useState<number | null>(values.length === 1 ? values[0] : null);

  const btn: React.CSSProperties = {
    borderRadius: 6, fontWeight: 700, cursor: "pointer",
    border: "1.5px solid var(--surface2)", background: "var(--surface)",
    color: "var(--text)", padding: "6px 10px", fontSize: "0.85rem",
    transition: "border 0.1s, background 0.1s",
  };

  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)", zIndex: 100,
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      <div style={{
        background: "var(--surface)", borderRadius: 12, padding: "22px 28px",
        border: "1.5px solid var(--surface2)", boxShadow: "0 8px 32px rgba(0,0,0,0.25)",
        minWidth: 280,
      }}>
        <div style={{ fontWeight: 800, fontSize: "1rem", marginBottom: 16, color: "var(--accent)" }}>
          Assign {tactic.name.toUpperCase()}
        </div>

        {/* Suit picker */}
        <div style={{ fontSize: "0.75rem", color: "var(--text-dim)", marginBottom: 8 }}>Suit</div>
        <div style={{ display: "flex", gap: 8, marginBottom: 18, flexWrap: "wrap" }}>
          {SUITS.map(s => (
            <button
              key={s}
              onClick={() => setSuit(s)}
              style={{
                ...btn,
                color: SUIT_COLOR[s],
                border: suit === s ? `2px solid ${SUIT_COLOR[s]}` : btn.border,
                background: suit === s ? `${SUIT_COLOR[s]}22` : btn.background,
                width: 40, height: 40, padding: 0, fontSize: "1.2rem",
              }}
            >
              {SUIT_LABEL[s]}
            </button>
          ))}
        </div>

        {/* Value picker */}
        {values.length > 1 && (
          <>
            <div style={{ fontSize: "0.75rem", color: "var(--text-dim)", marginBottom: 8 }}>Value</div>
            <div style={{ display: "flex", gap: 6, marginBottom: 18, flexWrap: "wrap" }}>
              {values.map(v => (
                <button
                  key={v}
                  onClick={() => setValue(v)}
                  style={{
                    ...btn,
                    border: value === v ? "2px solid var(--accent)" : btn.border,
                    background: value === v ? "rgba(201,106,42,0.15)" : btn.background,
                    width: 36, height: 36, padding: 0,
                  }}
                >
                  {v}
                </button>
              ))}
            </div>
          </>
        )}

        {/* Actions */}
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button onClick={onCancel} style={{ ...btn, color: "var(--text-dim)" }}>Cancel</button>
          <button
            onClick={() => suit && value !== null && onConfirm(suit, value)}
            disabled={!suit || value === null}
            style={{
              ...btn,
              background: suit && value !== null ? "var(--accent)" : "var(--surface2)",
              color: suit && value !== null ? "#fff" : "var(--text-dim)",
              border: "none",
              opacity: suit && value !== null ? 1 : 0.6,
              cursor: suit && value !== null ? "pointer" : "not-allowed",
            }}
          >
            Play
          </button>
        </div>
      </div>
    </div>
  );
}
