import type { TotemData } from "../types";
import TotemColumn from "./TotemColumn";

interface Props {
  totems:        TotemData[];
  canPlayTotem:  (idx: number) => boolean;
  canDropTotem:  (idx: number) => boolean;
  isDragging:    boolean;
  onTotemClick:  (idx: number) => void;
  onTotemDrop:   (idx: number) => void;
}

export default function Board({
  totems, canPlayTotem, canDropTotem, isDragging, onTotemClick, onTotemDrop,
}: Props) {
  return (
    <div style={{
      display: "flex", gap: 8, justifyContent: "center",
      padding: "8px 16px", overflowX: "auto",
    }}>
      {totems.map((t) => (
        <TotemColumn
          key={t.index}
          totem={t}
          canPlay={canPlayTotem(t.index)}
          canDrop={canDropTotem(t.index)}
          isDragging={isDragging}
          onClick={() => onTotemClick(t.index)}
          onDrop={() => onTotemDrop(t.index)}
        />
      ))}
    </div>
  );
}
