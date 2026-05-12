import { useRef, useState } from "react";
import type { TotemData, CardData } from "../types";
import CardTile from "./CardTile";

const CARD_W = 44;
const CARD_H = 62;
const POLE_H = 48; // height reserved for every totem slot (top/center/bottom)

// ── Totem pole SVG ─────────────────────────────────────────────────────────────

interface PoleProps {
  canPlay?:   boolean;
  isHovered?: boolean;
  envLabel?:  string;
}

function TotemPole({ canPlay, isHovered, envLabel }: PoleProps) {
  const ringColor = isHovered ? "var(--claimed-me)" : "var(--accent)";
  return (
    <div style={{ position: "relative", width: CARD_W, height: POLE_H, flexShrink: 0 }}>
      <svg viewBox="0 0 56 72" width={CARD_W} height={POLE_H}>
        {/* Flat wooden base */}
        <rect x="17" y="59" width="22" height="10" rx="3" fill="#6b3d14" />
        {/* Pole */}
        <rect x="25" y="6" width="6" height="57" rx="3" fill="#b06030" />
        {/* Pole grain shadow */}
        <rect x="27" y="6" width="2.5" height="57" rx="1.5" fill="#7a4020" opacity="0.45" />
        {/* Red pennant */}
        <polygon points="31,4 55,16 31,28" fill="#c83020" />
        {/* Pennant highlight (upper triangle lighter) */}
        <polygon points="31,4 55,16 31,16" fill="#e04030" opacity="0.35" />
      </svg>

      {/* Highlight ring — shown when card is selected (canPlay) or drag-hovering */}
      {(canPlay || isHovered) && (
        <div style={{
          position: "absolute", inset: -3, borderRadius: 8, pointerEvents: "none",
          border: `2.5px solid ${ringColor}`,
          boxShadow: `0 0 8px ${ringColor}55`,
        }} />
      )}

      {/* Fog / Mud badge */}
      {envLabel && (
        <div style={{
          position: "absolute", bottom: 2, left: "50%", transform: "translateX(-50%)",
          background: envLabel.includes("FOG") ? "#667788" : "#7a5010",
          color: "#fff", fontSize: "0.45rem", fontWeight: 800,
          padding: "1px 5px", borderRadius: 3, whiteSpace: "nowrap",
        }}>
          {envLabel}
        </div>
      )}
    </div>
  );
}

// Invisible spacer that reserves the same height as a TotemPole
function PoleSpacer() {
  return <div style={{ width: CARD_W, height: POLE_H, flexShrink: 0 }} />;
}

// ── Empty card slot ────────────────────────────────────────────────────────────

const emptySlot = (highlight: boolean): React.CSSProperties => ({
  width: CARD_W, height: CARD_H,
  borderRadius: 7, flexShrink: 0,
  border: highlight ? "2.5px solid var(--claimed-me)" : "1.5px dashed var(--surface2)",
  background: highlight ? "rgba(74,140,64,0.12)" : "transparent",
  boxShadow: highlight ? "0 0 10px rgba(74,140,64,0.3)" : "none",
  transition: "border 0.1s, background 0.1s, box-shadow 0.1s",
});

// ── TotemColumn ────────────────────────────────────────────────────────────────

type BoardMode = "idle" | "redeploy_pick" | "redeploy_dest" | "traitor_pick" | "traitor_dest" | "deserter_pick";

interface Props {
  totem:          TotemData;
  canPlay:        boolean;
  canDrop:        boolean;
  isDragging:     boolean;
  boardMode:      BoardMode;
  onClick:        () => void;
  onDrop:         () => void;
  onMyCardClick?: (card: CardData) => void;
  onOppCardClick?:(card: CardData) => void;
}

export default function TotemColumn({
  totem, canPlay, canDrop, isDragging, boardMode,
  onClick, onDrop, onMyCardClick, onOppCardClick,
}: Props) {
  const { my_cards, opp_cards, claimed_by, fog, mud, cards_to_win } = totem;
  const [isHovered, setIsHovered] = useState(false);
  const enterCount = useRef(0);

  // Opponent slots: furthest-from-totem rendered at top
  const oppSlots: (CardData | null)[] = Array.from({ length: cards_to_win }, (_, i) =>
    opp_cards[cards_to_win - 1 - i] ?? null
  );

  // My slots: nearest-to-totem first (upward)
  const mySlots: (CardData | null)[] = Array.from({ length: cards_to_win }, (_, i) =>
    my_cards[i] ?? null
  );

  const dropTargetSlot = my_cards.length;
  const envLabel = [fog && "FOG", mud && "MUD"].filter(Boolean).join(" · ") || undefined;
  const showRing  = isHovered && canDrop;

  const myCardsClickable  = boardMode === "redeploy_pick" && claimed_by === null;
  const oppCardsClickable = (boardMode === "traitor_pick" || boardMode === "deserter_pick") && claimed_by === null;

  // Fade columns that can't accept this drag
  const columnOpacity = isDragging && !canDrop && claimed_by === null ? 0.4 : 1;

  return (
    <div
      style={{
        display: "flex", flexDirection: "column", alignItems: "center", gap: 3,
        cursor: canPlay ? "pointer" : "default",
        opacity: columnOpacity,
        transition: "opacity 0.15s",
      }}
      onClick={canPlay && !isDragging ? onClick : undefined}
      onDragOver={(e) => { if (canDrop) { e.preventDefault(); e.dataTransfer.dropEffect = "move"; } }}
      onDragEnter={() => { enterCount.current++; if (canDrop) setIsHovered(true); }}
      onDragLeave={() => { enterCount.current--; if (enterCount.current === 0) setIsHovered(false); }}
      onDrop={(e) => { e.preventDefault(); enterCount.current = 0; setIsHovered(false); if (canDrop) onDrop(); }}
    >
      {/* ── Zone 1: top slot — totem appears here when claimed by opponent ── */}
      {claimed_by === "opp"
        ? <TotemPole />
        : <PoleSpacer />}

      {/* ── Zone 2: opponent's cards ── */}
      {oppSlots.map((card, i) =>
        card
          ? <CardTile
              key={`opp-${i}`} card={card}
              highlighted={oppCardsClickable}
              onClick={oppCardsClickable ? () => onOppCardClick?.(card) : undefined}
            />
          : <div key={`opp-e-${i}`} style={emptySlot(false)} />
      )}

      {/* ── Zone 3: center slot — totem lives here when unclaimed ── */}
      {claimed_by === null
        ? <TotemPole canPlay={canPlay} isHovered={showRing} envLabel={envLabel} />
        : <PoleSpacer />}

      {/* ── Zone 4: my cards ── */}
      {mySlots.map((card, i) => {
        const isDropSlot = i === dropTargetSlot && showRing;
        return card
          ? <CardTile
              key={`my-${i}`} card={card}
              highlighted={myCardsClickable}
              onClick={myCardsClickable ? () => onMyCardClick?.(card) : undefined}
            />
          : <div key={`my-e-${i}`} style={emptySlot(isDropSlot)} />;
      })}

      {/* ── Zone 5: bottom slot — totem moves here when claimed by me ── */}
      {claimed_by === "me"
        ? <TotemPole />
        : <PoleSpacer />}
    </div>
  );
}
