import { useState } from "react";
import type { CardData } from "../types";
import CardTile from "./CardTile";

// ── Helpers ───────────────────────────────────────────────────────────────────

function cardKey(c: CardData): string {
  if (c.type === "troop")  return `troop:${c.suit}:${c.value}`;
  if (c.type === "wild")   return `wild:${c.tactic_name}:${c.suit}:${c.value}`;
  return `tactics:${c.name}`;
}

// Returns cards in `after` that are not present in `before` (bag-style diff).
export function diffHands(before: CardData[], after: CardData[]): CardData[] {
  const pool = new Map<string, number>();
  for (const c of before) {
    const k = cardKey(c);
    pool.set(k, (pool.get(k) ?? 0) + 1);
  }
  const result: CardData[] = [];
  for (const c of after) {
    const k = cardKey(c);
    const n = pool.get(k) ?? 0;
    if (n > 0) { pool.set(k, n - 1); }
    else        { result.push(c); }
  }
  return result;
}

function autoDest(c: CardData): "troop" | "tactics" {
  return c.type === "troop" ? "troop" : "tactics";
}

const MODAL: React.CSSProperties = {
  position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)", zIndex: 100,
  display: "flex", alignItems: "center", justifyContent: "center",
};
const PANEL: React.CSSProperties = {
  background: "var(--surface)", borderRadius: 12, padding: "22px 28px",
  border: "1.5px solid var(--surface2)", boxShadow: "0 8px 32px rgba(0,0,0,0.25)",
};
const BTN_CANCEL: React.CSSProperties = {
  borderRadius: 6, fontWeight: 700, cursor: "pointer",
  border: "1.5px solid var(--surface2)", background: "var(--surface)",
  color: "var(--text-dim)", padding: "6px 14px", fontSize: "0.85rem",
};
function btnConfirm(enabled: boolean): React.CSSProperties {
  return {
    borderRadius: 6, fontWeight: 700, padding: "6px 14px", fontSize: "0.85rem",
    background: enabled ? "var(--accent)" : "var(--surface2)",
    color: enabled ? "#fff" : "var(--text-dim)",
    border: "none", cursor: enabled ? "pointer" : "not-allowed", opacity: enabled ? 1 : 0.6,
  };
}

// ── Phase 1: choose split ────────────────────────────────────────────────────

interface SplitProps {
  troopDeckSize:   number;
  tacticsDeckSize: number;
  onConfirm:       (troop_count: number, tactics_count: number) => void;
  onCancel:        () => void;
}

export function ScoutSplitModal({ troopDeckSize, tacticsDeckSize, onConfirm, onCancel }: SplitProps) {
  const [selected, setSelected] = useState<[number, number] | null>(null);

  const options: [number, number][] = [
    [3, 0], [2, 1], [1, 2], [0, 3],
  ].filter(([t, k]) => t <= troopDeckSize && k <= tacticsDeckSize) as [number, number][];

  return (
    <div style={MODAL}>
      <div style={{ ...PANEL, minWidth: 280 }}>
        <div style={{ fontWeight: 800, fontSize: "1rem", marginBottom: 6, color: "var(--accent)" }}>
          SCOUT — Draw 3 Cards
        </div>
        <div style={{ fontSize: "0.8rem", color: "var(--text-dim)", marginBottom: 16 }}>
          Troop deck: {troopDeckSize} · Tactics deck: {tacticsDeckSize}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 20 }}>
          {options.map(([t, k]) => {
            const active = selected?.[0] === t && selected?.[1] === k;
            return (
              <button
                key={`${t}-${k}`}
                onClick={() => setSelected([t, k])}
                style={{
                  borderRadius: 8, padding: "10px 14px", fontWeight: 600, fontSize: "0.88rem",
                  textAlign: "left", cursor: "pointer",
                  border: active ? "2px solid var(--accent)" : "1.5px solid var(--surface2)",
                  background: active ? "rgba(201,106,42,0.12)" : "var(--bg)",
                  color: "var(--text)",
                }}
              >
                <span style={{ fontWeight: 800 }}>{t}</span>
                <span style={{ color: "var(--text-dim)" }}> from troops · </span>
                <span style={{ fontWeight: 800 }}>{k}</span>
                <span style={{ color: "var(--text-dim)" }}> from tactics</span>
              </button>
            );
          })}
          {options.length === 0 && (
            <div style={{ color: "var(--claimed-opp)", fontSize: "0.85rem" }}>
              Not enough cards in either deck to scout.
            </div>
          )}
        </div>

        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button onClick={onCancel} style={BTN_CANCEL}>Cancel</button>
          <button
            disabled={!selected}
            onClick={() => selected && onConfirm(selected[0], selected[1])}
            style={btnConfirm(!!selected)}
          >
            Draw
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Phase 2: return 2 cards (inline panel, no overlay) ───────────────────────

interface ReturnProps {
  hand:      CardData[];
  preHand:   CardData[];   // hand snapshot before scout_reveal was sent
  onConfirm: (cards: CardData[]) => void;
}

export function ScoutReturnPanel({ hand, preHand, onConfirm }: ReturnProps) {
  const [selected, setSelected] = useState<CardData[]>([]);

  const newCards = preHand.length > 0 ? diffHands(preHand, hand) : [];
  const waiting  = preHand.length > 0 && newCards.length === 0;

  function toggle(card: CardData) {
    setSelected(prev => {
      const already = prev.includes(card);
      if (already) return prev.filter(c => c !== card);
      if (prev.length >= 2) return prev;
      return [...prev, card];
    });
  }

  const ready = selected.length === 2;

  if (waiting) {
    return (
      <div style={{ padding: "10px 16px", color: "var(--text-dim)", fontSize: "0.85rem" }}>
        Drawing cards…
      </div>
    );
  }

  return (
    <div style={{ padding: "10px 16px 18px" }}>
      {/* Header row */}
      <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 10 }}>
        <span style={{ fontWeight: 800, fontSize: "0.9rem", color: "var(--accent)" }}>
          SCOUT — return 2 cards
        </span>

        {/* Newly drawn cards inline */}
        {newCards.length > 0 && (
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ fontSize: "0.7rem", fontWeight: 700, color: "var(--claimed-me)" }}>
              Drew:
            </span>
            <div style={{ display: "flex", gap: 4 }}>
              {newCards.map((card, i) => <CardTile key={i} card={card} />)}
            </div>
          </div>
        )}

        <span style={{ fontSize: "0.75rem", color: "var(--text-dim)", marginLeft: "auto" }}>
          {selected.length < 2
            ? `Select ${2 - selected.length} more to return`
            : "Ready to return"}
        </span>

        <button
          disabled={!ready}
          onClick={() => ready && onConfirm(selected)}
          style={btnConfirm(ready)}
        >
          Return
        </button>
      </div>

      {/* Hand cards */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        {hand.map((card, i) => {
          const isSel = selected.includes(card);
          const isNew = newCards.includes(card);
          const dest  = autoDest(card);
          return (
            <div key={i} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 3 }}>
              <div style={{ position: "relative" }}>
                <CardTile
                  card={card}
                  selected={isSel}
                  highlighted={isNew && !isSel}
                  onClick={() => toggle(card)}
                />
                {isNew && !isSel && (
                  <div style={{
                    position: "absolute", top: -6, right: -6,
                    background: "var(--claimed-me)", color: "#fff",
                    fontSize: "0.5rem", fontWeight: 800, padding: "1px 4px", borderRadius: 3,
                  }}>
                    NEW
                  </div>
                )}
              </div>
              {isSel && (
                <div style={{
                  fontSize: "0.6rem", fontWeight: 700,
                  color: dest === "troop" ? "var(--suit-blue)" : "var(--accent)",
                  background: dest === "troop" ? "rgba(30,95,160,0.1)" : "rgba(201,106,42,0.1)",
                  padding: "2px 6px", borderRadius: 4, whiteSpace: "nowrap",
                }}>
                  → {dest === "troop" ? "Troop" : "Tactics"}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
