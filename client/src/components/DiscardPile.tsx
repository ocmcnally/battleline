import { useState } from "react";
import type { CardData } from "../types";
import CardTile from "./CardTile";

interface Props {
  cards: CardData[];
}

export default function DiscardPile({ cards }: Props) {
  const [open, setOpen] = useState(false);
  const top = cards[cards.length - 1] ?? null;

  return (
    <>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6, flexShrink: 0 }}>
        {/* Stack */}
        <div
          onClick={() => cards.length > 0 && setOpen(true)}
          style={{
            position: "relative",
            width: 44, height: 62,
            cursor: cards.length > 0 ? "pointer" : "default",
          }}
        >
          {/* Ghost cards behind */}
          {cards.length >= 3 && (
            <div style={{
              position: "absolute", top: -4, left: 4,
              width: 44, height: 62, borderRadius: 7,
              background: "#e8e0d0", border: "1.5px solid var(--surface2)",
              opacity: 0.6,
            }} />
          )}
          {cards.length >= 2 && (
            <div style={{
              position: "absolute", top: -2, left: 2,
              width: 44, height: 62, borderRadius: 7,
              background: "#ede6d8", border: "1.5px solid var(--surface2)",
              opacity: 0.8,
            }} />
          )}

          {top
            ? <div style={{ position: "absolute", inset: 0 }}>
                <CardTile card={top} />
              </div>
            : <div style={{
                width: 44, height: 62, borderRadius: 7,
                border: "1.5px dashed var(--surface2)",
                opacity: 0.4,
              }} />
          }

          {/* Count badge */}
          {cards.length > 0 && (
            <div style={{
              position: "absolute", top: -6, right: -6,
              background: "var(--text-dim)", color: "#fff",
              fontSize: "0.6rem", fontWeight: 800,
              width: 18, height: 18, borderRadius: "50%",
              display: "flex", alignItems: "center", justifyContent: "center",
              border: "1.5px solid var(--surface)",
            }}>
              {cards.length}
            </div>
          )}
        </div>
        <span style={{ fontSize: "0.62rem", color: "var(--text-dim)", fontWeight: 600 }}>Discard</span>
      </div>

      {/* Expanded modal */}
      {open && (
        <div
          style={{
            position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)", zIndex: 100,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}
          onClick={() => setOpen(false)}
        >
          <div
            style={{
              background: "var(--surface)", borderRadius: 12, padding: "20px 24px",
              border: "1.5px solid var(--surface2)", boxShadow: "0 8px 32px rgba(0,0,0,0.25)",
              maxWidth: 520, maxHeight: "70vh", overflow: "auto",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ fontWeight: 800, fontSize: "0.9rem", marginBottom: 14, color: "var(--text-dim)" }}>
              Discard pile — {cards.length} card{cards.length !== 1 ? "s" : ""}
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {cards.map((card, i) => (
                <CardTile key={i} card={card} />
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
