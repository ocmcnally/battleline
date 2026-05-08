import { useState, useEffect } from "react";
import type { User } from "./types";
import { useGameSocket } from "./hooks/useGameSocket";
import LandingPage from "./components/LandingPage";
import LobbyPage from "./components/LobbyPage";
import WaitingRoom from "./components/WaitingRoom";
import GameBoard from "./components/GameBoard";

// ── Screen state machine ───────────────────────────────────────────────────────

type Phase =
  | { screen: "landing" }
  | { screen: "lobby";   user: User }
  | { screen: "waiting"; user: User; gameId: string }
  | { screen: "game";    user: User; gameId: string };

function loadUser(): User | null {
  try {
    return JSON.parse(localStorage.getItem("battleline_user") ?? "null");
  } catch {
    return null;
  }
}

export default function App() {
  const [phase, setPhase] = useState<Phase>(() => {
    const user = loadUser();
    return user ? { screen: "lobby", user } : { screen: "landing" };
  });

  // WebSocket is only active once the player has entered a game
  const wsToken =
    phase.screen === "waiting" || phase.screen === "game"
      ? phase.user.token
      : null;

  const { status, gameState, lastError, sendMove } = useGameSocket(wsToken);

  // When creator's WS fires game_start/state, advance from waiting → game
  useEffect(() => {
    if (phase.screen === "waiting" && status === "playing") {
      setPhase(p =>
        p.screen === "waiting" ? { screen: "game", user: p.user, gameId: p.gameId } : p
      );
    }
  }, [status, phase.screen]);

  // ── Handlers ────────────────────────────────────────────────────────────────

  function handleAuth(user: User) {
    localStorage.setItem("battleline_user", JSON.stringify(user));
    setPhase({ screen: "lobby", user });
  }

  function handleSignOut() {
    localStorage.removeItem("battleline_user");
    setPhase({ screen: "landing" });
  }

  function handleCreateGame(gameId: string) {
    if (phase.screen !== "lobby") return;
    setPhase({ screen: "waiting", user: phase.user, gameId });
  }

  function handleJoinGame(gameId: string) {
    if (phase.screen !== "lobby") return;
    // Joiner goes straight to game — WS will send state on connect
    setPhase({ screen: "game", user: phase.user, gameId });
  }

  function handleCancelWaiting() {
    if (phase.screen !== "waiting") return;
    setPhase({ screen: "lobby", user: phase.user });
  }

  // ── Render ───────────────────────────────────────────────────────────────────

  switch (phase.screen) {
    case "landing":
      return <LandingPage onAuth={handleAuth} />;

    case "lobby":
      return (
        <LobbyPage
          user={phase.user}
          onCreateGame={handleCreateGame}
          onJoinGame={handleJoinGame}
          onSignOut={handleSignOut}
        />
      );

    case "waiting":
      return (
        <WaitingRoom
          user={phase.user}
          gameId={phase.gameId}
          onCancel={handleCancelWaiting}
        />
      );

    case "game":
      if (!gameState) {
        return (
          <div style={{
            display: "flex", alignItems: "center", justifyContent: "center",
            height: "100vh", color: "var(--text-dim)",
          }}>
            Connecting…
          </div>
        );
      }
      return (
        <GameBoard
          state={gameState}
          gameId={phase.gameId}
          onMove={sendMove}
          error={lastError}
        />
      );
  }
}
