import { useState } from "react";
import type { CardData } from "../types";
import CardTile from "./CardTile";

// ── Phase 1: choose how many cards to draw ────────────────────────────────────

interface SplitProps {
  troopDeckSize:   number;
  tacticsDeckSize: number;
  onConfirm:       (troop_count: number, tactics_count: number) => void;
  onCancel:        () => void;
}

export function ScoutSplitModal({ troopDeckSize, tacticsDeckSize, onConfirm, onCancel }: SplitProps) {
  const maxTroop   = Math.min(3, troopDeckSize);
  const [troop, setTroop] = useState(Math.min(3, troopDeckSize));
  const tactics = 3 - troop;
  const valid = troop + tactics === 3 && troop <= troopDeckSize && tactics <= tacticsDeckSize;

  const btn: React.CSSProperties = {
    borderRadius: 6, fontWeight: 700, cursor: "pointer",
    border: "1.5px solid var(--surface2)", background: "var(--surface)",
    color: "var(--text)", width: 36, height: 36, padding: 0, fontSize: "0.9rem",
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
        minWidth: 260,
      }}>
        <div style={{ fontWeight: 800, fontSize: "1rem", marginBottom: 16, color: "var(--accent)" }}>
          SCOUT — Draw 3 Cards
        </div>

        <div style={{ fontSize: "0.8rem", color: "var(--text-dim)", marginBottom: 12 }}>
          Troop deck: {troopDeckSize} · Tactics deck: {tacticsDeckSize}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
          <span style={{ width: 80, fontSize: "0.85rem" }}>From Troops</span>
          <div style={{ display: "flex", gap: 6 }}>
            {Array.from({ length: 4 }, (_, i) => (
              <button
                key={i}
                onClick={() => setTroop(i)}
                disabled={i > maxTroop || (3 - i) > tacticsDeckSize}
                style={{
                  ...btn,
                  border: troop === i ? "2px solid var(--accent)" : btn.border,
                  background: troop === i ? "rgba(201,106,42,0.15)" : btn.background,
                  opacity: (i > maxTroop || (3 - i) > tacticsDeckSize) ? 0.35 : 1,
                  cursor: (i > maxTroop || (3 - i) > tacticsDeckSize) ? "not-allowed" : "pointer",
                }}
              >
                {i}
              </button>
            ))}
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
          <span style={{ width: 80, fontSize: "0.85rem" }}>From Tactics</span>
          <span style={{
            width: 36, height: 36, display: "flex", alignItems: "center", justifyContent: "center",
            borderRadius: 6, background: "var(--bg)", border: "1.5px solid var(--surface2)",
            fontWeight: 700, fontSize: "0.9rem", color: tactics < 0 ? "var(--claimed-opp)" : "var(--text)",
          }}>
            {tactics < 0 ? "!" : tactics}
          </span>
        </div>

        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button onClick={onCancel} style={{
            borderRadius: 6, fontWeight: 700, cursor: "pointer",
            border: "1.5px solid var(--surface2)", background: "var(--surface)",
            color: "var(--text-dim)", padding: "6px 14px", fontSize: "0.85rem",
          }}>
            Cancel
          </button>
          <button
            disabled={!valid}
            onClick={() => valid && onConfirm(troop, tactics)}
            style={{
              borderRadius: 6, fontWeight: 700, padding: "6px 14px", fontSize: "0.85rem",
              background: valid ? "var(--accent)" : "var(--surface2)",
              color: valid ? "#fff" : "var(--text-dim)",
              border: "none", cursor: valid ? "pointer" : "not-allowed", opacity: valid ? 1 : 0.6,
            }}
          >
            Draw
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Phase 2: return 2 cards to decks ──────────────────────────────────────────

interface ReturnEntry { card: CardData; dest: "troop" | "tactics" }

interface ReturnProps {
  hand:      CardData[];
  onConfirm: (returns: ReturnEntry[]) => void;
  onCancel:  () => void;
}

export function ScoutReturnModal({ hand, onConfirm, onCancel }: ReturnProps) {
  const [selections, setSelections] = useState<ReturnEntry[]>([]);

  function toggleCard(card: CardData, dest: "troop" | "tactics") {
    const idx = selections.findIndex(s => s.card === card && s.dest === dest);
    if (idx >= 0) {
      setSelections(prev => prev.filter((_, i) => i !== idx));
    } else if (selections.length < 2) {
      setSelections(prev => [...prev, { card, dest }]);
    }
  }

  function isSelected(card: CardData, dest: "troop" | "tactics") {
    return selections.some(s => s.card === card && s.dest === dest);
  }

  const ready = selections.length === 2;

  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)", zIndex: 100,
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      <div style={{
        background: "var(--surface)", borderRadius: 12, padding: "22px 28px",
        border: "1.5px solid var(--surface2)", boxShadow: "0 8px 32px rgba(0,0,0,0.25)",
        maxWidth: 480,
      }}>
        <div style={{ fontWeight: 800, fontSize: "1rem", marginBottom: 6, color: "var(--accent)" }}>
          SCOUT — Return 2 Cards
        </div>
        <div style={{ fontSize: "0.78rem", color: "var(--text-dim)", marginBottom: 16 }}>
          Click a card then choose where to return it. Select {2 - selections.length} more.
        </div>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginBottom: 16 }}>
          {hand.map((card, i) => {
            const troopSel    = isSelected(card, "troop");
            const tacticsSel  = isSelected(card, "tactics");
            const anySel      = troopSel || tacticsSel;
            return (
              <div key={i} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
                <CardTile card={card} selected={anySel} />
                <div style={{ display: "flex", gap: 4 }}>
                  <button
                    onClick={() => toggleCard(card, "troop")}
                    style={{
                      fontSize: "0.6rem", fontWeight: 700, padding: "2px 5px", borderRadius: 4,
                      border: troopSel ? "2px solid var(--accent)" : "1.5px solid var(--surface2)",
                      background: troopSel ? "rgba(201,106,42,0.15)" : "var(--bg)",
                      cursor: "pointer", color: "var(--text)",
                    }}
                  >
                    Troop
                  </button>
                  <button
                    onClick={() => toggleCard(card, "tactics")}
                    style={{
                      fontSize: "0.6rem", fontWeight: 700, padding: "2px 5px", borderRadius: 4,
                      border: tacticsSel ? "2px solid var(--accent)" : "1.5px solid var(--surface2)",
                      background: tacticsSel ? "rgba(201,106,42,0.15)" : "var(--bg)",
                      cursor: "pointer", color: "var(--text)",
                    }}
                  >
                    Tactics
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button onClick={onCancel} style={{
            borderRadius: 6, fontWeight: 700, cursor: "pointer",
            border: "1.5px solid var(--surface2)", background: "var(--surface)",
            color: "var(--text-dim)", padding: "6px 14px", fontSize: "0.85rem",
          }}>
            Cancel
          </button>
          <button
            disabled={!ready}
            onClick={() => ready && onConfirm(selections)}
            style={{
              borderRadius: 6, fontWeight: 700, padding: "6px 14px", fontSize: "0.85rem",
              background: ready ? "var(--accent)" : "var(--surface2)",
              color: ready ? "#fff" : "var(--text-dim)",
              border: "none", cursor: ready ? "pointer" : "not-allowed", opacity: ready ? 1 : 0.6,
            }}
          >
            Confirm
          </button>
        </div>
      </div>
    </div>
  );
}
