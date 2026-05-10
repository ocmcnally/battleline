import { useState } from "react";
import type { GameState, CardData } from "../types";
import Board from "./Board";
import Hand from "./Hand";

interface Props {
  state:  GameState;
  gameId: string;
  onMove: (move: object) => void;
  error:  string | null;
}

export default function GameBoard({ state, onMove, error }: Props) {
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);
  const [draggedCard, setDraggedCard] = useState<CardData | null>(null);

  const selectedCard: CardData | null =
    selectedIdx !== null ? state.my_hand[selectedIdx] : null;

  // ── Validity checks ──────────────────────────────────────────────────────────

  function canPlayTotem(totemIdx: number, withCard: CardData | null = selectedCard): boolean {
    if (!state.my_turn || state.winner !== null || withCard === null) return false;
    const totem = state.totems[totemIdx];
    if (totem.claimed_by !== null) return false;
    if (totem.my_cards.length >= totem.cards_to_win) return false;
    if (withCard.type === "tactics") return false;  // needs extra UI
    return true;
  }

  // ── Unified play action ──────────────────────────────────────────────────────

  function playCard(card: CardData, totemIdx: number) {
    if (!canPlayTotem(totemIdx, card)) return;

    if (card.type === "troop") {
      onMove({ action: "play_card", card, totem: totemIdx });
    } else if (card.type === "wild") {
      onMove({
        action: "play_wild",
        tactic: { type: "tactics", name: card.tactic_name },
        totem: totemIdx,
        suit: card.suit,
        value: card.value,
      });
    }
    setSelectedIdx(null);
    setDraggedCard(null);
  }

  // ── Event handlers ───────────────────────────────────────────────────────────

  function handleTotemClick(totemIdx: number) {
    if (selectedCard) playCard(selectedCard, totemIdx);
  }

  function handleTotemDrop(totemIdx: number) {
    if (draggedCard) playCard(draggedCard, totemIdx);
  }

  // ── Render ───────────────────────────────────────────────────────────────────

  const { names, my_totem_count, opp_totem_count, troop_deck_size, tactics_deck_size, my_turn, winner } = state;

  const turnLabel =
    winner === "me"  ? "You won!"        :
    winner === "opp" ? "You lost"        :
    my_turn          ? "Your turn"       :
    `${names.opp}'s turn…`;

  const turnColor =
    winner === "me"  ? "var(--claimed-me)"  :
    winner === "opp" ? "var(--claimed-opp)" :
    my_turn          ? "var(--claimed-me)"  :
    "var(--text-dim)";

  const hintText = !my_turn
    ? "Waiting for opponent…"
    : draggedCard || selectedCard
      ? "Drop on a totem to play"
      : "Select or drag a card, then drop on a totem";

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: "var(--bg)" }}>

      {/* Header */}
      <div style={{
        padding: "10px 20px", background: "var(--surface)",
        borderBottom: "1.5px solid var(--surface2)",
        display: "flex", justifyContent: "space-between", alignItems: "center",
        flexShrink: 0, gap: 16,
      }}>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <span style={{ fontWeight: 700, color: "var(--claimed-opp)", fontSize: "0.95rem" }}>
            {names.opp} — {opp_totem_count}
          </span>
          <span style={{ color: "var(--text-dim)" }}>vs</span>
          <span style={{ fontWeight: 700, color: "var(--claimed-me)", fontSize: "0.95rem" }}>
            {my_totem_count} — {names.me}
          </span>
        </div>

        <span style={{ fontWeight: 700, color: turnColor }}>{turnLabel}</span>

        <div style={{ color: "var(--text-dim)", fontSize: "0.8rem", textAlign: "right" }}>
          Troop {troop_deck_size} · Tactics {tactics_deck_size}
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div style={{
          padding: "6px 20px", background: "#7a2020",
          color: "#ffd0d0", fontSize: "0.85rem", flexShrink: 0,
        }}>
          {error}
        </div>
      )}

      {/* Board */}
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", overflow: "auto" }}>
        <Board
          totems={state.totems}
          canPlayTotem={(idx) => canPlayTotem(idx, selectedCard)}
          canDropTotem={(idx) => canPlayTotem(idx, draggedCard)}
          isDragging={draggedCard !== null}
          onTotemClick={handleTotemClick}
          onTotemDrop={handleTotemDrop}
        />
      </div>

      {/* Hand */}
      <div style={{
        padding: "8px 16px 20px",
        background: "var(--surface)",
        borderTop: "1.5px solid var(--surface2)",
        flexShrink: 0,
      }}>
        <div style={{ color: "var(--text-dim)", fontSize: "0.75rem", marginBottom: 8, paddingLeft: 2 }}>
          {hintText}
          {selectedCard?.type === "tactics" && my_turn && (
            <span style={{ color: "var(--accent)", marginLeft: 8 }}>
              (tactics UI coming soon — click again to deselect)
            </span>
          )}
        </div>
        <Hand
          cards={state.my_hand}
          selectedIdx={selectedIdx}
          myTurn={my_turn && winner === null}
          onSelect={(idx) => setSelectedIdx(prev => prev === idx ? null : idx)}
          onCardDragStart={(card) => { setDraggedCard(card); setSelectedIdx(null); }}
          onDragEnd={() => setDraggedCard(null)}
        />
      </div>

    </div>
  );
}
