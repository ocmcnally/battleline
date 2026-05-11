import type { TotemData, CardData } from "../types";
import TotemColumn from "./TotemColumn";
import DiscardPile from "./DiscardPile";

type BoardMode = "idle" | "redeploy_pick" | "redeploy_dest" | "traitor_pick" | "traitor_dest" | "deserter_pick";

// ── Deck pile ─────────────────────────────────────────────────────────────────

interface DeckPileProps {
  count:       number;
  label:       string;
  isDrawPhase: boolean;
  onClick?:    () => void;
}

function DeckPile({ count, label, isDrawPhase, onClick }: DeckPileProps) {
  const active = isDrawPhase && count > 0;
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6, flexShrink: 0 }}>
      <div
        onClick={active ? onClick : undefined}
        style={{
          width: 44, height: 62,
          borderRadius: 7,
          display: "flex", alignItems: "center", justifyContent: "center",
          flexDirection: "column", gap: 2,
          cursor: active ? "pointer" : "default",
          userSelect: "none",
          background: active ? "var(--accent)" : "var(--surface2)",
          border: active
            ? "2.5px solid var(--claimed-me)"
            : `1.5px solid ${count === 0 ? "transparent" : "var(--surface2)"}`,
          boxShadow: active ? "0 0 10px rgba(74,140,64,0.35)" : "none",
          opacity: count === 0 ? 0.35 : 1,
          transition: "background 0.15s, box-shadow 0.15s",
        }}
      >
        <span style={{ color: active ? "#fff" : "var(--text-dim)", fontSize: "1.2rem", fontWeight: 800, lineHeight: 1 }}>
          {count}
        </span>
        {active && (
          <span style={{ color: "#fff", fontSize: "0.55rem", fontWeight: 700, opacity: 0.85 }}>DRAW</span>
        )}
      </div>
      <span style={{ fontSize: "0.62rem", color: "var(--text-dim)", fontWeight: 600, textAlign: "center" }}>
        {label}
      </span>
    </div>
  );
}

// ── Board ─────────────────────────────────────────────────────────────────────

interface Props {
  totems:          TotemData[];
  troopDeckSize:   number;
  tacticsDeckSize: number;
  discarded:       CardData[];
  canPlayTotem:    (idx: number) => boolean;
  canDropTotem:    (idx: number) => boolean;
  isDragging:      boolean;
  isDrawPhase:     boolean;
  boardMode:       BoardMode;
  onTotemClick:    (idx: number) => void;
  onTotemDrop:     (idx: number) => void;
  onDrawTroop:     () => void;
  onDrawTactics:   () => void;
  onMyCardClick:   (card: CardData, totemIdx: number) => void;
  onOppCardClick:  (card: CardData, totemIdx: number) => void;
}

export default function Board({
  totems, troopDeckSize, tacticsDeckSize, discarded,
  canPlayTotem, canDropTotem, isDragging,
  isDrawPhase, boardMode,
  onTotemClick, onTotemDrop,
  onDrawTroop, onDrawTactics,
  onMyCardClick, onOppCardClick,
}: Props) {
  return (
    <div style={{
      display: "flex", gap: 12, justifyContent: "center", alignItems: "center",
      padding: "8px 16px", overflowX: "auto",
    }}>
      <DeckPile
        count={tacticsDeckSize}
        label="Tactics"
        isDrawPhase={isDrawPhase}
        onClick={onDrawTactics}
      />

      <DiscardPile cards={discarded} />

      {totems.map((t) => (
        <TotemColumn
          key={t.index}
          totem={t}
          canPlay={canPlayTotem(t.index)}
          canDrop={canDropTotem(t.index)}
          isDragging={isDragging}
          boardMode={boardMode}
          onClick={() => onTotemClick(t.index)}
          onDrop={() => onTotemDrop(t.index)}
          onMyCardClick={(card) => onMyCardClick(card, t.index)}
          onOppCardClick={(card) => onOppCardClick(card, t.index)}
        />
      ))}

      <DeckPile
        count={troopDeckSize}
        label="Troops"
        isDrawPhase={isDrawPhase}
        onClick={onDrawTroop}
      />
    </div>
  );
}
