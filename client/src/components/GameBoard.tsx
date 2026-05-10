import { useEffect, useState } from "react";
import type { GameState, CardData, TacticsCard } from "../types";
import Board from "./Board";
import Hand from "./Hand";
import WildModal from "./WildModal";
import { ScoutSplitModal, ScoutReturnModal } from "./ScoutModal";

// ── Phase machine ─────────────────────────────────────────────────────────────

type BoardMode = "idle" | "redeploy_pick" | "redeploy_dest" | "traitor_pick" | "traitor_dest" | "deserter_pick";

type Phase =
  | { kind: "idle" }
  | { kind: "draw"; pendingMove: object }
  | { kind: "wild_pick"; tactic: TacticsCard; totemIdx: number }
  | { kind: "scout_split"; tactic: TacticsCard }
  | { kind: "scout_return" }
  | { kind: "redeploy_pick"; tactic: TacticsCard }
  | { kind: "redeploy_dest"; tactic: TacticsCard; fromTotem: number; boardCard: CardData }
  | { kind: "traitor_pick"; tactic: TacticsCard }
  | { kind: "traitor_dest"; tactic: TacticsCard; fromTotem: number; boardCard: CardData }
  | { kind: "deserter_pick"; tactic: TacticsCard };

const WILD_TACTICS = new Set(["alexander", "darius", "wild8", "wild321"]);
const ENV_TACTICS  = new Set(["fog", "mud"]);

// ── Component ─────────────────────────────────────────────────────────────────

interface Props {
  state:  GameState;
  gameId: string;
  onMove: (move: object) => void;
  error:  string | null;
}

export default function GameBoard({ state, onMove, error }: Props) {
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);
  const [draggedCard, setDraggedCard] = useState<CardData | null>(null);
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });

  const selectedCard: CardData | null =
    selectedIdx !== null ? state.my_hand[selectedIdx] : null;

  // Reset phase on error
  useEffect(() => {
    if (error) { setPhase({ kind: "idle" }); setSelectedIdx(null); }
  }, [error]);

  // ── Helpers ────────────────────────────────────────────────────────────────

  function canPlayTacticsCard(): boolean {
    return state.my_tactics_played <= state.opp_tactics_played;
  }

  // Can a troop/wild/leader card be placed on a totem?
  function totemHasSpace(totemIdx: number): boolean {
    const t = state.totems[totemIdx];
    return t.claimed_by === null && t.my_cards.length < t.cards_to_win;
  }

  // Can an environment card be applied to a totem?
  function totemIsUnclaimed(totemIdx: number): boolean {
    return state.totems[totemIdx].claimed_by === null;
  }

  function canTargetTotem(totemIdx: number, card: CardData | null): boolean {
    if (!state.my_turn || state.winner !== null || card === null) return false;
    if (phase.kind !== "idle") return false;
    if (card.type === "troop" || card.type === "wild") return totemHasSpace(totemIdx);
    if (card.type === "tactics") {
      if (!canPlayTacticsCard()) return false;
      if (WILD_TACTICS.has(card.name)) return totemHasSpace(totemIdx);
      if (ENV_TACTICS.has(card.name))  return totemIsUnclaimed(totemIdx);
    }
    return false;
  }

  function canPickDest(totemIdx: number): boolean {
    if (state.winner !== null) return false;
    return totemHasSpace(totemIdx);
  }

  // ── Send helpers ───────────────────────────────────────────────────────────

  function sendMove(move: object) {
    const action = (move as any).action as string;
    const needsDraw = !["scout_reveal", "scout_return"].includes(action);
    if (!needsDraw) { onMove(move); return; }

    const { troop_deck_size, tactics_deck_size } = state;
    if (troop_deck_size === 0 && tactics_deck_size === 0) {
      onMove({ ...move, draw_from_tactics: false });
    } else if (troop_deck_size === 0) {
      onMove({ ...move, draw_from_tactics: true });
    } else if (tactics_deck_size === 0) {
      onMove({ ...move, draw_from_tactics: false });
    } else {
      setPhase({ kind: "draw", pendingMove: move });
    }
  }

  function resetSelection() {
    setSelectedIdx(null);
    setDraggedCard(null);
    setPhase({ kind: "idle" });
  }

  // ── Card-specific play dispatchers ─────────────────────────────────────────

  function playTroopOrWild(card: CardData, totemIdx: number) {
    if (card.type === "troop") {
      sendMove({ action: "play_card", card, totem: totemIdx });
    } else if (card.type === "wild") {
      sendMove({
        action: "play_wild",
        tactic: { type: "tactics", name: card.tactic_name },
        totem: totemIdx,
        suit: card.suit,
        value: card.value,
      });
    }
    resetSelection();
  }

  function playTacticsOnTotem(card: TacticsCard, totemIdx: number) {
    if (WILD_TACTICS.has(card.name)) {
      setPhase({ kind: "wild_pick", tactic: card, totemIdx });
    } else if (ENV_TACTICS.has(card.name)) {
      sendMove({
        action: "play_environment",
        tactic: { type: "tactics", name: card.name },
        totem: totemIdx,
      });
      resetSelection();
    }
  }

  // ── Totem click routing ────────────────────────────────────────────────────

  function handleTotemClick(totemIdx: number) {
    if (phase.kind === "idle") {
      if (!selectedCard) return;
      if (!canTargetTotem(totemIdx, selectedCard)) return;
      if (selectedCard.type === "tactics") playTacticsOnTotem(selectedCard, totemIdx);
      else playTroopOrWild(selectedCard, totemIdx);
    } else if (phase.kind === "redeploy_dest") {
      if (!canPickDest(totemIdx)) return;
      sendMove({
        action: "play_redeploy",
        tactic: { type: "tactics", name: phase.tactic.name },
        card: phase.boardCard,
        from_totem: phase.fromTotem,
        to_totem: totemIdx,
      });
      resetSelection();
    } else if (phase.kind === "traitor_dest") {
      if (!canPickDest(totemIdx)) return;
      sendMove({
        action: "play_traitor",
        tactic: { type: "tactics", name: phase.tactic.name },
        card: phase.boardCard,
        from_totem: phase.fromTotem,
        to_totem: totemIdx,
      });
      resetSelection();
    }
  }

  function handleTotemDrop(totemIdx: number) {
    if (draggedCard && canTargetTotem(totemIdx, draggedCard)) {
      if (draggedCard.type === "tactics") playTacticsOnTotem(draggedCard, totemIdx);
      else playTroopOrWild(draggedCard, totemIdx);
    }
  }

  // ── Hand card selection ────────────────────────────────────────────────────

  function handleCardSelect(idx: number) {
    if (phase.kind === "draw") return; // locked during draw choice

    // Deselect
    if (selectedIdx === idx) { resetSelection(); return; }

    const card = state.my_hand[idx];

    // Cancel active phase and re-select
    if (phase.kind !== "idle") setPhase({ kind: "idle" });

    setSelectedIdx(idx);

    if (card.type !== "tactics") return;
    if (!canPlayTacticsCard()) return;

    // Non-totem-targeting tactics: immediately enter phase
    if (card.name === "scout")    setPhase({ kind: "scout_split", tactic: card });
    if (card.name === "redeploy") setPhase({ kind: "redeploy_pick", tactic: card });
    if (card.name === "traitor")  setPhase({ kind: "traitor_pick", tactic: card });
    if (card.name === "deserter") setPhase({ kind: "deserter_pick", tactic: card });
  }

  // ── Board card interaction ─────────────────────────────────────────────────

  function handleMyCardClick(card: CardData, totemIdx: number) {
    if (phase.kind === "redeploy_pick") {
      setPhase({ kind: "redeploy_dest", tactic: phase.tactic, fromTotem: totemIdx, boardCard: card });
    }
  }

  function handleOppCardClick(card: CardData, totemIdx: number) {
    if (phase.kind === "traitor_pick") {
      setPhase({ kind: "traitor_dest", tactic: phase.tactic, fromTotem: totemIdx, boardCard: card });
    } else if (phase.kind === "deserter_pick") {
      sendMove({
        action: "play_deserter",
        tactic: { type: "tactics", name: phase.tactic.name },
        card,
        from_totem: totemIdx,
      });
      resetSelection();
    }
  }

  // ── canPlay/canDrop for Board ──────────────────────────────────────────────

  function canPlayTotemForBoard(idx: number): boolean {
    if (phase.kind === "redeploy_dest" || phase.kind === "traitor_dest") return canPickDest(idx);
    return canTargetTotem(idx, selectedCard);
  }

  function canDropTotemForBoard(idx: number): boolean {
    if (phase.kind !== "idle") return false;
    return canTargetTotem(idx, draggedCard);
  }

  const boardMode: BoardMode =
    phase.kind === "redeploy_pick" ? "redeploy_pick" :
    phase.kind === "redeploy_dest" ? "redeploy_dest" :
    phase.kind === "traitor_pick"  ? "traitor_pick"  :
    phase.kind === "traitor_dest"  ? "traitor_dest"  :
    phase.kind === "deserter_pick" ? "deserter_pick" :
    "idle";

  // ── Hint text ──────────────────────────────────────────────────────────────

  function buildHint(): string {
    if (!state.my_turn || state.winner !== null) return "Waiting for opponent…";
    switch (phase.kind) {
      case "draw":          return "Draw a card — click Troops or Tactics deck";
      case "wild_pick":     return "Assign suit & value";
      case "scout_split":   return "Scout: choose how many to draw from each deck";
      case "scout_return":  return "Scout: return 2 cards from your hand";
      case "redeploy_pick": return "Redeploy: click one of your board cards to move";
      case "redeploy_dest": return "Redeploy: click a destination totem (or Discard)";
      case "traitor_pick":  return "Traitor: click an opponent card to steal";
      case "traitor_dest":  return "Traitor: click a totem to place the stolen card";
      case "deserter_pick": return "Deserter: click an opponent card to discard";
    }
    if (draggedCard || selectedCard) {
      const c = draggedCard ?? selectedCard!;
      if (c.type === "tactics" && ENV_TACTICS.has(c.name))  return "Drop on a totem to apply";
      if (c.type === "tactics" && WILD_TACTICS.has(c.name)) return "Drop on a totem, then assign suit & value";
      return "Drop on a totem to play";
    }
    return "Select or drag a card, then drop on a totem";
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  const { names, my_totem_count, opp_totem_count, troop_deck_size, tactics_deck_size,
          my_turn, winner, my_tactics_played, opp_tactics_played } = state;

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

  const tacticsBlocked = my_turn && !canPlayTacticsCard() && winner === null;

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

        <div style={{ fontSize: "0.8rem", color: "var(--text-dim)", textAlign: "right" }}>
          Tactics: me {my_tactics_played} / opp {opp_tactics_played}
          {tacticsBlocked && (
            <span style={{ color: "var(--claimed-opp)", marginLeft: 8, fontWeight: 700 }}>
              (tactics locked)
            </span>
          )}
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
          troopDeckSize={troop_deck_size}
          tacticsDeckSize={tactics_deck_size}
          canPlayTotem={canPlayTotemForBoard}
          canDropTotem={canDropTotemForBoard}
          isDragging={draggedCard !== null}
          isDrawPhase={phase.kind === "draw"}
          boardMode={boardMode}
          onTotemClick={handleTotemClick}
          onTotemDrop={handleTotemDrop}
          onDrawTroop={() => {
            if (phase.kind === "draw") {
              onMove({ ...phase.pendingMove, draw_from_tactics: false });
              setPhase({ kind: "idle" });
            }
          }}
          onDrawTactics={() => {
            if (phase.kind === "draw") {
              onMove({ ...phase.pendingMove, draw_from_tactics: true });
              setPhase({ kind: "idle" });
            }
          }}
          onMyCardClick={handleMyCardClick}
          onOppCardClick={handleOppCardClick}
        />
      </div>

      {/* Redeploy discard button */}
      {phase.kind === "redeploy_dest" && (
        <div style={{
          display: "flex", justifyContent: "center", padding: "6px 0",
          background: "var(--surface)", borderTop: "1px solid var(--surface2)",
          flexShrink: 0,
        }}>
          <button
            onClick={() => {
              sendMove({
                action: "play_redeploy",
                tactic: { type: "tactics", name: phase.tactic.name },
                card: phase.boardCard,
                from_totem: phase.fromTotem,
                to_totem: null,
              });
              resetSelection();
            }}
            style={{
              borderRadius: 6, fontWeight: 700, padding: "5px 16px", fontSize: "0.8rem",
              background: "#7a2020", color: "#ffd0d0", border: "none", cursor: "pointer",
            }}
          >
            Discard instead
          </button>
        </div>
      )}

      {/* Hand */}
      <div style={{
        padding: "8px 16px 20px",
        background: "var(--surface)",
        borderTop: "1.5px solid var(--surface2)",
        flexShrink: 0,
      }}>
        <div style={{
          color: phase.kind === "draw" ? "var(--accent)" : "var(--text-dim)",
          fontSize: "0.75rem", marginBottom: 8, paddingLeft: 2,
          fontWeight: phase.kind === "draw" ? 700 : 400,
        }}>
          {buildHint()}
          {phase.kind === "idle" && tacticsBlocked && selectedCard?.type === "tactics" && (
            <span style={{ color: "var(--claimed-opp)", marginLeft: 8 }}>
              (opponent must play a tactic first)
            </span>
          )}
        </div>
        <Hand
          cards={state.my_hand}
          selectedIdx={selectedIdx}
          myTurn={my_turn && winner === null && phase.kind !== "draw" && phase.kind !== "scout_return"}
          onSelect={handleCardSelect}
          onCardDragStart={(card) => {
            if (phase.kind !== "idle") return;
            setDraggedCard(card);
            setSelectedIdx(null);
          }}
          onDragEnd={() => setDraggedCard(null)}
        />
      </div>

      {/* Wild card modal */}
      {phase.kind === "wild_pick" && (
        <WildModal
          tactic={phase.tactic}
          onConfirm={(suit, value) => {
            sendMove({
              action: "play_wild",
              tactic: { type: "tactics", name: phase.tactic.name },
              totem: phase.totemIdx,
              suit,
              value,
            });
            resetSelection();
          }}
          onCancel={resetSelection}
        />
      )}

      {/* Scout split modal */}
      {phase.kind === "scout_split" && (
        <ScoutSplitModal
          troopDeckSize={troop_deck_size}
          tacticsDeckSize={tactics_deck_size}
          onConfirm={(troop_count, tactics_count) => {
            onMove({
              action: "scout_reveal",
              tactic: { type: "tactics", name: "scout" },
              troop_count,
              tactics_count,
            });
            setPhase({ kind: "scout_return" });
            setSelectedIdx(null);
          }}
          onCancel={resetSelection}
        />
      )}

      {/* Scout return modal */}
      {phase.kind === "scout_return" && (
        <ScoutReturnModal
          hand={state.my_hand}
          onConfirm={(returns) => {
            onMove({ action: "scout_return", returns });
            resetSelection();
          }}
          onCancel={resetSelection}
        />
      )}
    </div>
  );
}
