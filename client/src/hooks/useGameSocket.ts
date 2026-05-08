import { useState, useEffect, useRef, useCallback } from "react";
import type { GameState, WsMessage } from "../types";

export type ConnectionStatus = "idle" | "connecting" | "waiting" | "playing";

export function useGameSocket(token: string | null) {
  const [status, setStatus]       = useState<ConnectionStatus>("idle");
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [lastError, setLastError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!token) {
      setStatus("idle");
      setGameState(null);
      return;
    }

    const ws = new WebSocket(`ws://${location.host}/ws?token=${token}`);
    wsRef.current = ws;
    setStatus("connecting");

    ws.onmessage = (evt) => {
      const msg: WsMessage = JSON.parse(evt.data as string);
      if (msg.type === "waiting") {
        setStatus("waiting");
      } else if (msg.type === "game_start" || msg.type === "state") {
        setGameState(msg.state);
        setStatus("playing");
        setLastError(null);
      } else if (msg.type === "error") {
        setLastError(msg.message);
      }
    };

    ws.onclose = () => {
      setStatus("idle");
      wsRef.current = null;
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [token]);

  const sendMove = useCallback((move: object) => {
    setLastError(null);
    wsRef.current?.send(JSON.stringify({ action: "move", move }));
  }, []);

  return { status, gameState, lastError, sendMove };
}
