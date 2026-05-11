import { useState, useEffect } from "react";
import type { User } from "./types";
import { supabase, getOrCreateProfile } from "./lib/supabase";
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

  useEffect(() => {
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (event, session) => {
        if (event === "SIGNED_OUT" || !session) {
          setPhase({ screen: "landing" });
          return;
        }

        if (event === "SIGNED_IN" || event === "INITIAL_SESSION" || event === "TOKEN_REFRESHED") {
          // Use Google metadata directly — no DB query blocking the UI
          const displayName =
            (session.user.user_metadata?.full_name as string | undefined) ??
            (session.user.user_metadata?.name    as string | undefined) ??
            session.user.email?.split("@")[0] ??
            "Player";

          setPhase(prev =>
            prev.screen === "loading" || prev.screen === "landing"
              ? { screen: "lobby", user: { displayName, token: session.user.id } }
              : prev
          );

          // Sync the profiles table in the background — never blocks the UI
          getOrCreateProfile(session).catch(console.error);
        }
      }
    );

    return () => subscription.unsubscribe();
  }, []);

  // WebSocket is only active once the player is in a game
  const wsToken =
    phase.screen === "waiting" || phase.screen === "game"
      ? phase.user.token
      : null;

  const { status, gameState, lastError, sendMove } = useGameSocket(wsToken);

  // Advance creator from waiting → game once opponent joins
  useEffect(() => {
    if (phase.screen === "waiting" && status === "playing") {
      setPhase(p =>
        p.screen === "waiting" ? { screen: "game", user: p.user, gameId: p.gameId } : p
      );
    }
  }, [status, phase.screen]);

  // ── Handlers ────────────────────────────────────────────────────────────────

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
      return <LandingPage />;

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
