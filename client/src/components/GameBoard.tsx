import { useState } from "react";
import type { GameState, CardData } from "../types";
import Board from "./Board";
import Hand from "./Hand";

interface Props {
  state:   GameState;
  gameId:  string;
  onMove:  (move: object) => void;
  error:   string | null;
}

export default function GameBoard({ state, onMove, error }: Props) {
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);

  const selectedCard: CardData | null =
    selectedIdx !== null ? state.my_hand[selectedIdx] : null;

  function handleCardSelect(idx: number) {
    setSelectedIdx(prev => prev === idx ? null : idx);
  }

  function canPlayTotem(totemIdx: number): boolean {
    if (!state.my_turn || state.winner !== null) return false;
    if (selectedCard === null) return false;
    const totem = state.totems[totemIdx];
    if (totem.claimed_by !== null) return false;
    if (totem.my_cards.length >= totem.cards_to_win) return false;
    // Tactics cards need additional input — not yet wired up
    if (selectedCard.type === "tactics") return false;
    return true;
  }

  function handleTotemClick(totemIdx: number) {
    if (!selectedCard || !canPlayTotem(totemIdx)) return;

    if (selectedCard.type === "troop") {
      onMove({ action: "play_card", card: selectedCard, totem: totemIdx });
      setSelectedIdx(null);
      return;
    }

    if (selectedCard.type === "wild") {
      onMove({
        action: "play_wild",
        tactic: { type: "tactics", name: selectedCard.tactic_name },
        totem: totemIdx,
        suit: selectedCard.suit,
        value: selectedCard.value,
      });
      setSelectedIdx(null);
    }
  }

  const { names, my_totem_count, opp_totem_count, troop_deck_size, tactics_deck_size, my_turn, winner } = state;

  const turnLabel =
    winner === "me"  ? "🎉 You won!" :
    winner === "opp" ? "💀 You lost" :
    my_turn          ? "Your turn"   :
    `${names.opp}'s turn…`;

  const turnColor =
    winner === "me"  ? "var(--claimed-me)"  :
    winner === "opp" ? "var(--claimed-opp)" :
    my_turn          ? "var(--claimed-me)"  :
    "var(--text-dim)";

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: "var(--bg)" }}>

      {/* ── Header bar ── */}
      <div style={{
        padding: "10px 20px", background: "var(--surface)",
        display: "flex", justifyContent: "space-between", alignItems: "center",
        flexShrink: 0, gap: 16,
      }}>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <span style={{ fontWeight: 700, color: "var(--claimed-opp)" }}>
            {names.opp} {opp_totem_count}
          </span>
          <span style={{ color: "var(--text-dim)" }}>vs</span>
          <span style={{ fontWeight: 700, color: "var(--claimed-me)" }}>
            {my_totem_count} {names.me}
          </span>
        </div>

        <span style={{ fontWeight: 700, color: turnColor }}>{turnLabel}</span>

        <div style={{ color: "var(--text-dim)", fontSize: "0.8rem", textAlign: "right" }}>
          <span>Troop {troop_deck_size}</span>
          <span style={{ margin: "0 6px" }}>·</span>
          <span>Tactics {tactics_deck_size}</span>
        </div>
      </div>

      {/* ── Error banner ── */}
      {error && (
        <div style={{
          padding: "6px 20px", background: "#5c1a1a",
          color: "#ff9999", fontSize: "0.85rem", flexShrink: 0,
        }}>
          {error}
        </div>
      )}

      {/* ── Board ── */}
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", overflow: "auto" }}>
        <Board
          totems={state.totems}
          canPlayTotem={canPlayTotem}
          onTotemClick={handleTotemClick}
        />
      </div>

      {/* ── Hand ── */}
      <div style={{ padding: "8px 16px 20px", background: "var(--surface)", flexShrink: 0 }}>
        <div style={{ color: "var(--text-dim)", fontSize: "0.75rem", marginBottom: 6, paddingLeft: 2 }}>
          {my_turn ? "Select a card, then click a totem" : "Waiting for opponent…"}
          {selectedCard?.type === "tactics" && my_turn && (
            <span style={{ color: "var(--suit-yellow)", marginLeft: 8 }}>
              (tactics UI coming soon — click again to deselect)
            </span>
          )}
        </div>
        <Hand
          cards={state.my_hand}
          selectedIdx={selectedIdx}
          myTurn={my_turn && winner === null}
          onSelect={handleCardSelect}
        />
      </div>

    </div>
  );
}
