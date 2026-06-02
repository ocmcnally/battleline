import { useState, useEffect, useCallback } from "react";
import type { GameState } from "../types";
import Board from "./Board";
import Hand from "./Hand";

interface MoveData {
  player:      number;
  card:        { suit: string; value: number };
  totem_index: number;
}

interface ReplayData {
  players:   string[];
  winner:    number | null;
  moves:     MoveData[];
  states_p0: GameState[];
  states_p1: GameState[];
}

interface Props {
  onBack: () => void;
}

const SUIT_SYMBOL: Record<string, string> = {
  blue: "♦", red: "●", orange: "▲", yellow: "★", green: "♣", purple: "♠",
};

const SUIT_COLOR: Record<string, string> = {
  blue: "var(--suit-blue)", red: "var(--suit-red)", orange: "var(--suit-orange)",
  yellow: "var(--suit-yellow)", green: "var(--suit-green)", purple: "var(--suit-purple)",
};

function MoveLabel({ move, players }: { move: MoveData; players: string[] }) {
  const sym   = SUIT_SYMBOL[move.card.suit] ?? "?";
  const color = SUIT_COLOR[move.card.suit]  ?? "#999";
  return (
    <span>
      <strong>{players[move.player]}</strong> played{" "}
      <span style={{ fontFamily: "monospace", fontWeight: 700, color }}>
        {sym}{move.card.value}
      </span>
      {" "}→ Totem {move.totem_index + 1}
    </span>
  );
}

export default function ReplayPage({ onBack }: Props) {
  const [data,    setData]    = useState<ReplayData | null>(null);
  const [moveIdx, setMoveIdx] = useState(0);
  const [pov,     setPov]     = useState(0);
  const [error,   setError]   = useState<string | null>(null);

  const states     = data ? (pov === 0 ? data.states_p0 : data.states_p1) : null;
  const totalMoves = states ? states.length - 1 : 0;  // one state per turn including initial
  const state      = states?.[moveIdx] ?? null;
  const atEnd      = moveIdx === totalMoves;

  const navigate = useCallback((delta: number) => {
    if (!data) return;
    setMoveIdx(i => Math.max(0, Math.min(totalMoves, i + delta)));
  }, [data, totalMoves]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight" || e.key === "ArrowDown") navigate(1);
      if (e.key === "ArrowLeft"  || e.key === "ArrowUp")   navigate(-1);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [navigate]);

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        const parsed = JSON.parse(ev.target?.result as string) as ReplayData;
        if (!parsed.states_p0 || !parsed.states_p1) {
          setError("This save file has no replay states. Re-run training to generate a compatible file.");
          return;
        }
        setData(parsed);
        setMoveIdx(0);
        setPov(0);
        setError(null);
      } catch {
        setError("Could not parse file — make sure it's a valid save JSON.");
      }
    };
    reader.readAsText(file);
  }

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>

      {/* Nav */}
      <nav style={{
        padding: "14px 32px", display: "flex", justifyContent: "space-between",
        alignItems: "center", borderBottom: "1px solid var(--surface2)",
        background: "var(--surface)",
      }}>
        <span style={{ fontWeight: 800, fontSize: "1.1rem", color: "var(--accent)" }}>
          Battle Line — Replay
        </span>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {data && (
            <label style={{
              background: "var(--bg)", border: "1px solid var(--surface2)",
              color: "var(--text-dim)", padding: "5px 14px", fontSize: "0.85rem",
              cursor: "pointer", borderRadius: 6,
            }}>
              Load another
              <input type="file" accept=".json" onChange={handleFile} style={{ display: "none" }} />
            </label>
          )}
          <button onClick={onBack} style={{
            background: "transparent", border: "1px solid var(--surface2)",
            color: "var(--text-dim)", padding: "5px 14px", fontSize: "0.85rem",
          }}>
            ← Back
          </button>
        </div>
      </nav>

      <main style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>

        {/* No file loaded */}
        {!data && (
          <div style={{
            flex: 1, display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center", gap: 20,
          }}>
            {error && (
              <div style={{
                padding: "10px 20px", background: "#5c1a1a", color: "#ff9999",
                borderRadius: 8, fontSize: "0.9rem", maxWidth: 480, textAlign: "center",
              }}>
                {error}
              </div>
            )}
            <label style={{
              display: "flex", flexDirection: "column", alignItems: "center", gap: 12,
              padding: "48px 64px", cursor: "pointer",
              background: "var(--surface)", borderRadius: 12,
              border: "2px dashed var(--surface2)",
            }}>
              <span style={{ fontSize: "2rem" }}>📂</span>
              <span style={{ fontWeight: 700, fontSize: "1.1rem" }}>Load a saved game</span>
              <span style={{ color: "var(--text-dim)", fontSize: "0.85rem" }}>
                Select a <code>selfplay_iter_*.json</code> from <code>saved_games/</code>
              </span>
              <input type="file" accept=".json" onChange={handleFile} style={{ display: "none" }} />
            </label>
          </div>
        )}

        {/* Game loaded */}
        {data && state && (
          <>
            {/* Info bar */}
            <div style={{
              display: "flex", alignItems: "center", justifyContent: "space-between",
              padding: "10px 24px", background: "var(--surface)",
              borderBottom: "1px solid var(--surface2)", flexWrap: "wrap", gap: 12,
            }}>
              {/* Move annotation */}
              <div style={{ fontSize: "0.9rem", minWidth: 240 }}>
                {moveIdx === 0
                  ? <span style={{ color: "var(--text-dim)" }}>Game start</span>
                  : atEnd
                    ? <span style={{ fontWeight: 700 }}>
                        Game over —{" "}
                        {data.winner !== null
                          ? <span style={{ color: "var(--claimed-me)" }}>{data.players[data.winner]} wins</span>
                          : "Draw"}
                      </span>
                    // moves[] only has troop plays; tactics turns have no entry
                  : data.moves[moveIdx - 1]
                    ? <MoveLabel move={data.moves[moveIdx - 1]} players={data.players} />
                    : <span style={{ color: "var(--text-dim)" }}>Tactics move</span>
                }
              </div>

              {/* POV toggle */}
              <div style={{ display: "flex", gap: 6 }}>
                {[0, 1].map(p => (
                  <button
                    key={p}
                    onClick={() => setPov(p)}
                    style={{
                      padding: "4px 14px", borderRadius: 6, fontSize: "0.82rem",
                      fontWeight: 600, cursor: "pointer",
                      background: pov === p ? "var(--accent)" : "var(--bg)",
                      color:      pov === p ? "#fff" : "var(--text-dim)",
                      border:     pov === p ? "1.5px solid var(--accent)" : "1.5px solid var(--surface2)",
                    }}
                  >
                    {data.players[p]}
                  </button>
                ))}
              </div>

              {/* Step counter */}
              <span style={{ color: "var(--text-dim)", fontSize: "0.85rem", fontFamily: "monospace" }}>
                Move {moveIdx} / {totalMoves}
              </span>
            </div>

            {/* Board */}
            <div style={{ flex: 1, overflow: "auto" }}>
              <Board
                totems={state.totems}
                troopDeckSize={state.troop_deck_size}
                tacticsDeckSize={state.tactics_deck_size}
                discarded={state.discarded}
                canPlayTotem={() => false}
                canDropTotem={() => false}
                isDragging={false}
                isDrawPhase={false}
                boardMode="idle"
                onTotemClick={() => {}}
                onTotemDrop={() => {}}
                onDrawTroop={() => {}}
                onDrawTactics={() => {}}
                onMyCardClick={() => {}}
                onOppCardClick={() => {}}
              />
            </div>

            {/* Hand */}
            <div style={{
              borderTop: "1px solid var(--surface2)",
              padding: "8px 16px",
              background: "var(--surface)",
            }}>
              <div style={{ fontSize: "0.72rem", color: "var(--text-dim)", textAlign: "center",
                            fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em",
                            marginBottom: 6 }}>
                {data.players[pov]}'s hand
              </div>
              <Hand
                cards={state.my_hand}
                selectedIdx={null}
                myTurn={false}
                onSelect={() => {}}
              />
            </div>

            {/* Navigation controls */}
            <div style={{
              display: "flex", alignItems: "center", justifyContent: "center",
              gap: 12, padding: "16px", borderTop: "1px solid var(--surface2)",
              background: "var(--surface)",
            }}>
              <button onClick={() => setMoveIdx(0)} disabled={moveIdx === 0}
                style={navBtn(moveIdx === 0)}>⟪</button>
              <button onClick={() => navigate(-1)} disabled={moveIdx === 0}
                style={navBtn(moveIdx === 0)}>‹ Prev</button>

              {/* Scrubber */}
              <input
                type="range" min={0} max={totalMoves} value={moveIdx}
                onChange={e => setMoveIdx(Number(e.target.value))}
                style={{ width: 220 }}
              />

              <button onClick={() => navigate(1)} disabled={atEnd}
                style={navBtn(atEnd)}>Next ›</button>
              <button onClick={() => setMoveIdx(totalMoves)} disabled={atEnd}
                style={navBtn(atEnd)}>⟫</button>
            </div>
          </>
        )}
      </main>
    </div>
  );
}

function navBtn(disabled: boolean): React.CSSProperties {
  return {
    padding: "6px 16px", borderRadius: 6, fontWeight: 600, fontSize: "0.9rem",
    cursor: disabled ? "default" : "pointer",
    opacity: disabled ? 0.35 : 1,
    background: "var(--surface2)", color: "var(--text)", border: "none",
  };
}
