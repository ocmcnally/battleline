import { useState, useEffect } from "react";
import type { User } from "./types";
import { supabase, getOrCreateProfile } from "./lib/supabase";
import { useGameSocket } from "./hooks/useGameSocket";
import LandingPage from "./components/LandingPage";
import LobbyPage from "./components/LobbyPage";
import WaitingRoom from "./components/WaitingRoom";
import GameBoard from "./components/GameBoard";
import UsernameSetup from "./components/UsernameSetup";

// ── Screen state machine ───────────────────────────────────────────────────────

type Phase =
  | { screen: "loading" }
  | { screen: "landing" }
  | { screen: "username_setup"; user: User }
  | { screen: "lobby";          user: User }
  | { screen: "waiting";        user: User; gameId: string }
  | { screen: "game";           user: User; gameId: string };

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

          const user: User = { displayName, token: session.user.id, rating: null, provisional: true };

          setPhase(prev =>
            prev.screen === "loading" || prev.screen === "landing"
              ? { screen: "lobby", user }
              : prev
          );

          // Apply saved profile data (display name + rating) and redirect to setup if needed
          getOrCreateProfile(session).then(profile => {
            if (!profile) return;
            const PROVISIONAL_THRESHOLD = 10;
            const updatedUser: User = {
              token:       session.user.id,
              displayName: profile.username_customized ? profile.display_name : displayName,
              rating:      profile.rating ?? null,
              provisional: (profile.games_played ?? 0) < PROVISIONAL_THRESHOLD,
            };
            if (!profile.username_customized) {
              setPhase(prev =>
                prev.screen === "lobby"
                  ? { screen: "username_setup", user: updatedUser }
                  : prev
              );
            } else {
              setPhase(prev => {
                if (prev.screen === "lobby" || prev.screen === "waiting" || prev.screen === "game") {
                  return { ...prev, user: updatedUser } as Phase;
                }
                return prev;
              });
            }
          }).catch(console.error);
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

    case "username_setup":
      return (
        <UsernameSetup
          user={phase.user}
          onComplete={(displayName) =>
            setPhase({ screen: "lobby", user: { ...phase.user, displayName, rating: 1500, provisional: true } })
          }
        />
      );

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
          onLeave={() => setPhase({ screen: "lobby", user: phase.user })}
        />
      );
  }
}
