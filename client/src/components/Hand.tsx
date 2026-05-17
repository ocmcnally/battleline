import { useState, useEffect } from "react";
import type { CardData } from "../types";
import CardTile from "./CardTile";

interface Props {
  cards:            CardData[];
  selectedIdx:      number | null;
  myTurn:           boolean;
  onSelect:         (idx: number) => void;
  onCardDragStart?: (card: CardData) => void;
  onDragEnd?:       () => void;
}

export default function Hand({
  cards, selectedIdx, myTurn, onSelect, onCardDragStart, onDragEnd,
}: Props) {
  const [draggingIdx, setDraggingIdx] = useState<number | null>(null);

  useEffect(() => {
    setDraggingIdx(null);
  }, [cards.length]);

  return (
    <div style={{
      display: "flex", gap: 10, justifyContent: "center",
      flexWrap: "wrap", padding: "8px 0",
    }}>
      {cards.map((card, i) => (
        <CardTile
          key={i}
          card={card}
          selected={selectedIdx === i}
          dimmed={!myTurn || draggingIdx === i}
          draggable={myTurn}
          onClick={myTurn ? () => onSelect(i) : undefined}
          onDragStart={(e) => {
            e.dataTransfer.effectAllowed = "move";
            setDraggingIdx(i);
            onCardDragStart?.(card);
          }}
          onDragEnd={() => {
            setDraggingIdx(null);
            onDragEnd?.();
          }}
        />
      ))}
    </div>
  );
}
