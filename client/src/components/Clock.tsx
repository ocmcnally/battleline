import { useEffect, useRef, useState } from "react";
import type { ClockState } from "../types";

function formatTime(ms: number): string {
  const totalSecs = Math.max(0, Math.ceil(ms / 1000));
  const m = Math.floor(totalSecs / 60);
  const s = totalSecs % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

interface PlayerClockProps {
  remainingMs:     number;
  lastTurnStartMs: number;
  isActive:        boolean;
  label:           string;
}

function PlayerClock({ remainingMs, lastTurnStartMs, isActive, label }: PlayerClockProps) {
  const [, setTick] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!isActive) {
      if (intervalRef.current) clearInterval(intervalRef.current);
      return;
    }
    intervalRef.current = setInterval(() => setTick(t => t + 1), 100);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [isActive]);

  const displayed = isActive
    ? Math.max(0, remainingMs - (Date.now() - lastTurnStartMs))
    : remainingMs;

  const flagged = displayed <= 0;
  const low     = displayed < 30_000 && !flagged;

  const color = flagged ? "var(--claimed-opp)"
              : low     ? "#e07000"
              : isActive ? "var(--text)"
              : "var(--text-dim)";

  return (
    <div style={{
      display: "flex", flexDirection: "column", alignItems: "center",
      background: isActive ? "var(--bg)" : "transparent",
      border: isActive ? "1.5px solid var(--surface2)" : "1.5px solid transparent",
      borderRadius: 8, padding: "4px 12px", minWidth: 80,
      transition: "background 0.2s, border-color 0.2s",
    }}>
      <span style={{ fontSize: "0.6rem", color: "var(--text-dim)", fontWeight: 600, marginBottom: 1 }}>
        {label}
      </span>
      <span style={{
        fontFamily: "monospace", fontWeight: 800,
        fontSize: flagged || isActive ? "1.15rem" : "1rem",
        color,
        transition: "color 0.3s",
      }}>
        {flagged ? "🚩" : formatTime(displayed)}
      </span>
    </div>
  );
}

interface Props {
  clock:  ClockState;
  myTurn: boolean;
}

export default function Clock({ clock, myTurn }: Props) {
  const { my_remaining_ms, opp_remaining_ms, last_turn_start_ms, increment_ms } = clock;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <PlayerClock
        remainingMs={opp_remaining_ms}
        lastTurnStartMs={last_turn_start_ms}
        isActive={!myTurn}
        label="Opp"
      />
      {increment_ms > 0 && (
        <span style={{ fontSize: "0.65rem", color: "var(--text-dim)" }}>
          +{increment_ms / 1000}s
        </span>
      )}
      <PlayerClock
        remainingMs={my_remaining_ms}
        lastTurnStartMs={last_turn_start_ms}
        isActive={myTurn}
        label="You"
      />
    </div>
  );
}
