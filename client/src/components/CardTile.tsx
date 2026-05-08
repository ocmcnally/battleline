import type { CardData } from "../types";

const SUIT_COLOR: Record<string, string> = {
  blue:   "var(--suit-blue)",
  red:    "var(--suit-red)",
  orange: "var(--suit-orange)",
  yellow: "var(--suit-yellow)",
  green:  "var(--suit-green)",
  purple: "var(--suit-purple)",
};

const SUIT_SYMBOL: Record<string, string> = {
  blue: "●", red: "♦", orange: "▲", yellow: "★", green: "♣", purple: "♠",
};

const TACTIC_COLOR: Record<string, string> = {
  alexander: "#ffd700", darius:   "#c0a000",
  wild8:     "#4a90d9", wild321:  "#9b59b6",
  fog:       "#aaaaaa", mud:      "#8b6914",
  scout:     "#4caf50", redeploy: "#f5a623",
  traitor:   "#e84040", deserter: "#555555",
};

interface Props {
  card:      CardData;
  selected?: boolean;
  dimmed?:   boolean;
  onClick?:  () => void;
  small?:    boolean;
}

export default function CardTile({ card, selected, dimmed, onClick, small }: Props) {
  const w = small ? 36 : 44;
  const h = small ? 52 : 62;

  const base: React.CSSProperties = {
    width: w, height: h,
    borderRadius: 6,
    display: "flex", flexDirection: "column",
    alignItems: "center", justifyContent: "center",
    cursor: onClick ? "pointer" : "default",
    userSelect: "none",
    flexShrink: 0,
    opacity: dimmed ? 0.35 : 1,
    transition: "transform 0.1s, box-shadow 0.1s",
    transform: selected ? "translateY(-8px)" : "none",
    boxShadow: selected ? "0 6px 16px rgba(255,255,255,0.25)" : "none",
    background: "var(--surface2)",
  };

  if (card.type === "troop") {
    const color  = SUIT_COLOR[card.suit]  ?? "#aaa";
    const symbol = SUIT_SYMBOL[card.suit] ?? "?";
    return (
      <div style={{ ...base, border: selected ? "2px solid #fff" : "1px solid #444" }} onClick={onClick}>
        <span style={{ color, fontSize: small ? "0.9rem" : "1.1rem" }}>{symbol}</span>
        <span style={{ color, fontSize: small ? "0.65rem" : "0.75rem", fontWeight: 700, marginTop: 2 }}>
          {card.value}
        </span>
      </div>
    );
  }

  if (card.type === "wild") {
    const color  = SUIT_COLOR[card.suit]  ?? "#aaa";
    const symbol = SUIT_SYMBOL[card.suit] ?? "?";
    return (
      <div style={{ ...base, border: selected ? "2px solid #fff" : "1px solid gold" }} onClick={onClick}>
        <span style={{ color, fontSize: small ? "0.9rem" : "1rem" }}>{symbol}</span>
        <span style={{ color, fontSize: small ? "0.6rem" : "0.7rem", fontWeight: 700 }}>{card.value}</span>
        <span style={{ color: "gold", fontSize: "0.5rem" }}>★</span>
      </div>
    );
  }

  // Tactics card
  const tacColor = TACTIC_COLOR[card.name] ?? "#888";
  return (
    <div
      style={{ ...base, background: "#111827", border: selected ? "2px solid #fff" : `1px solid ${tacColor}` }}
      onClick={onClick}
    >
      <span style={{
        color: tacColor, fontSize: small ? "0.48rem" : "0.54rem",
        textAlign: "center", lineHeight: 1.3, padding: "0 2px", fontWeight: 700,
      }}>
        {card.name.toUpperCase()}
      </span>
    </div>
  );
}
