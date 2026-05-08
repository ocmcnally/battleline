import type { TotemData, CardData } from "../types";
import CardTile from "./CardTile";

const EMPTY: React.CSSProperties = {
  width: 44, height: 62, borderRadius: 6,
  border: "1px dashed #2a2a4a", flexShrink: 0,
};

interface Props {
  totem:    TotemData;
  canPlay:  boolean;
  onClick:  () => void;
}

export default function TotemColumn({ totem, canPlay, onClick }: Props) {
  const { my_cards, opp_cards, claimed_by, fog, mud, cards_to_win, index } = totem;

  // Opponent's row: slot nearest the totem is shown closest to the center
  const oppSlots: (CardData | null)[] = Array.from({ length: cards_to_win }, (_, i) =>
    opp_cards[cards_to_win - 1 - i] ?? null
  );

  // My row: slot 0 nearest the totem
  const mySlots: (CardData | null)[] = Array.from({ length: cards_to_win }, (_, i) =>
    my_cards[i] ?? null
  );

  const markerBg =
    claimed_by === "me"  ? "var(--claimed-me)"  :
    claimed_by === "opp" ? "var(--claimed-opp)" :
    "var(--surface2)";

  const markerLabel =
    claimed_by === "me"  ? "YOU" :
    claimed_by === "opp" ? "OPP" :
    [fog && "F", mud && "M"].filter(Boolean).join("") || String(index + 1);

  return (
    <div
      style={{
        display: "flex", flexDirection: "column", alignItems: "center", gap: 3,
        cursor: canPlay ? "pointer" : "default",
      }}
      onClick={canPlay ? onClick : undefined}
    >
      {/* Opponent cards (far → near) */}
      {oppSlots.map((card, i) =>
        card
          ? <CardTile key={`opp-${i}`} card={card} small />
          : <div key={`opp-e-${i}`} style={{ ...EMPTY, width: 36, height: 52 }} />
      )}

      {/* Totem marker */}
      <div style={{
        width: 44, height: 26,
        borderRadius: 4,
        background: markerBg,
        border: canPlay ? "2px solid rgba(255,255,255,0.7)" : "1px solid transparent",
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: "0.6rem", fontWeight: 800, color: "#fff",
        transition: "border 0.1s",
        flexShrink: 0,
      }}>
        {markerLabel}
      </div>

      {/* My cards (near → far) */}
      {mySlots.map((card, i) =>
        card
          ? <CardTile key={`my-${i}`} card={card} />
          : <div key={`my-e-${i}`} style={EMPTY} />
      )}
    </div>
  );
}
