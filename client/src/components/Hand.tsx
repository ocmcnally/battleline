import type { CardData } from "../types";
import CardTile from "./CardTile";

interface Props {
  cards:       CardData[];
  selectedIdx: number | null;
  myTurn:      boolean;
  onSelect:    (idx: number) => void;
}

export default function Hand({ cards, selectedIdx, myTurn, onSelect }: Props) {
  return (
    <div style={{
      display: "flex", gap: 8, justifyContent: "center",
      flexWrap: "wrap", padding: "8px 0",
    }}>
      {cards.map((card, i) => (
        <CardTile
          key={i}
          card={card}
          selected={selectedIdx === i}
          dimmed={!myTurn}
          onClick={myTurn ? () => onSelect(i) : undefined}
        />
      ))}
    </div>
  );
}
