import type { TotemData } from "../types";
import TotemColumn from "./TotemColumn";

interface Props {
  totems:        TotemData[];
  canPlayTotem:  (idx: number) => boolean;
  onTotemClick:  (idx: number) => void;
}

export default function Board({ totems, canPlayTotem, onTotemClick }: Props) {
  return (
    <div style={{
      display: "flex", gap: 6, justifyContent: "center",
      padding: "8px 12px", overflowX: "auto",
    }}>
      {totems.map((t) => (
        <TotemColumn
          key={t.index}
          totem={t}
          canPlay={canPlayTotem(t.index)}
          onClick={() => onTotemClick(t.index)}
        />
      ))}
    </div>
  );
}
