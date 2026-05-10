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
  alexander: "#9a7000", darius:   "#7a5800",
  wild8:     "#1e5fa0", wild321:  "#5828a0",
  fog:       "#7a6650", mud:      "#7a5010",
  scout:     "#1e7020", redeploy: "#c05810",
  traitor:   "#b02828", deserter: "#7a6650",
};

const W = 44;
const H = 62;

interface Props {
  card:          CardData;
  selected?:     boolean;
  highlighted?:  boolean;
  dimmed?:       boolean;
  onClick?:      () => void;
  draggable?:    boolean;
  onDragStart?:  (e: React.DragEvent) => void;
  onDragEnd?:    (e: React.DragEvent) => void;
}

export default function CardTile({
  card, selected, highlighted, dimmed, onClick,
  draggable: isDraggable, onDragStart, onDragEnd,
}: Props) {
  const base: React.CSSProperties = {
    width: W, height: H,
    borderRadius: 7,
    display: "flex", flexDirection: "column",
    alignItems: "center", justifyContent: "center",
    cursor: isDraggable ? "grab" : onClick ? "pointer" : "default",
    userSelect: "none",
    flexShrink: 0,
    opacity: dimmed ? 0.35 : 1,
    transition: "transform 0.1s, box-shadow 0.1s, opacity 0.15s",
    transform: selected ? "translateY(-10px)" : "none",
    boxShadow: selected
      ? "0 6px 18px rgba(74,140,64,0.45)"
      : highlighted
        ? "0 0 10px rgba(201,106,42,0.55)"
        : "0 1px 3px rgba(0,0,0,0.12)",
    background: "#fdf8f0",
  };

  if (card.type === "troop") {
    const color  = SUIT_COLOR[card.suit]  ?? "#555";
    const symbol = SUIT_SYMBOL[card.suit] ?? "?";
    return (
      <div
        style={{
          ...base,
          border: selected
            ? "2px solid var(--claimed-me)"
            : highlighted
              ? "2px solid var(--accent)"
              : "1.5px solid var(--surface2)",
        }}
        onClick={onClick}
        draggable={isDraggable}
        onDragStart={onDragStart}
        onDragEnd={onDragEnd}
      >
        <span style={{ color, fontSize: "1.1rem", lineHeight: 1 }}>{symbol}</span>
        <span style={{ color, fontSize: "0.85rem", fontWeight: 800, marginTop: 3 }}>
          {card.value}
        </span>
      </div>
    );
  }

  if (card.type === "wild") {
    const color  = SUIT_COLOR[card.suit]  ?? "#555";
    const symbol = SUIT_SYMBOL[card.suit] ?? "?";
    return (
      <div
        style={{
          ...base,
          border: selected ? "2px solid var(--claimed-me)" : highlighted ? "2px solid var(--accent)" : "1.5px solid #9a7000",
          background: "#fffbf0",
        }}
        onClick={onClick}
        draggable={isDraggable}
        onDragStart={onDragStart}
        onDragEnd={onDragEnd}
      >
        <span style={{ color, fontSize: "1rem", lineHeight: 1 }}>{symbol}</span>
        <span style={{ color, fontSize: "0.82rem", fontWeight: 800 }}>{card.value}</span>
        <span style={{ color: "#9a7000", fontSize: "0.6rem", marginTop: 2 }}>wild</span>
      </div>
    );
  }

  // Tactics card
  const tacColor = TACTIC_COLOR[card.name] ?? "#666";
  return (
    <div
      style={{
        ...base,
        background: "#f5f0e4",
        border: selected ? "2px solid var(--claimed-me)" : highlighted ? "2px solid var(--accent)" : `1.5px solid ${tacColor}`,
      }}
      onClick={onClick}
      draggable={isDraggable}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
    >
      <span style={{
        color: tacColor, fontSize: "0.62rem",
        textAlign: "center", lineHeight: 1.3,
        padding: "0 4px", fontWeight: 800,
        textTransform: "uppercase",
      }}>
        {card.name}
      </span>
    </div>
  );
}
