import { useState, useEffect } from "react";
import type { User } from "./types";
import { supabase, fetchProfile } from "./lib/supabase";
import { useGameSocket } from "./hooks/useGameSocket";
import LandingPage from "./components/LandingPage";
import LobbyPage from "./components/LobbyPage";
import WaitingRoom from "./components/WaitingRoom";
import GameBoard from "./components/GameBoard";

// ── Screen state machine ───────────────────────────────────────────────────────

type Phase =
  | { screen: "loading" }
  | { screen: "landing" }
  | { screen: "lobby";   user: User }
  | { screen: "waiting"; user: User; gameId: string }
  | { screen: "game";    user: User; gameId: string };

export default function App() {
  const [phase, setPhase] = useState<Phase>({ screen: "loading" });

  // Bootstrap from existing Supabase session on mount
  useEffect(() => {
    supabase.auth.getSession().then(async ({ data: { session } }) => {
      if (!session) { setPhase({ screen: "landing" }); return; }
      const profile = await fetchProfile(session.user.id);
      if (profile) {
        setPhase({ screen: "lobby", user: { displayName: profile.display_name, token: session.user.id } });
      } else {
        setPhase({ screen: "landing" });
      }
    });

    // Handle sign-out from anywhere (other tab, session expiry, etc.)
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event) => {
      if (event === "SIGNED_OUT") setPhase({ screen: "landing" });
    });

    return () => subscription.unsubscribe();
  }, []);

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
    setPhase({ screen: "lobby", user });
  }

  async function handleSignOut() {
    await supabase.auth.signOut();
    // onAuthStateChange SIGNED_OUT fires and sets phase to landing
  }

  function handleCreateGame(gameId: string) {
    if (phase.screen !== "lobby") return;
    setPhase({ screen: "waiting", user: phase.user, gameId });
  }

  function handleJoinGame(gameId: string) {
    if (phase.screen !== "lobby") return;
    setPhase({ screen: "game", user: phase.user, gameId });
  }

  function handleCancelWaiting() {
    if (phase.screen !== "waiting") return;
    setPhase({ screen: "lobby", user: phase.user });
  }

  // ── Render ───────────────────────────────────────────────────────────────────

  switch (phase.screen) {
    case "loading":
      return (
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "center",
          height: "100vh", color: "var(--text-dim)",
        }}>
          Loading…
        </div>
      );

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
