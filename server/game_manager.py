"""In-memory game sessions, pending games, and move dispatch."""

import time
import uuid
from battleline import (
    BattleLineGame, Card, WildCard, UnassignedWild, TacticsCard, SUITS,
)


class PendingGame:
    def __init__(self, game_id: str, token: str, username: str,
                 time_ms: int | None = None, increment_ms: int = 0,
                 rated: bool = True, creator_rating: dict | None = None):
        self.game_id        = game_id
        self.token          = token
        self.username       = username
        self.created_at     = time.time()
        self.time_ms        = time_ms
        self.increment_ms   = increment_ms
        self.rated          = rated
        self.creator_rating = creator_rating  # {"rating": int, "provisional": bool} | None


class GameSession:
    def __init__(self, game: BattleLineGame, tokens: list[str], game_id: str,
                 time_ms: int | None = None, increment_ms: int = 0, rated: bool = True):
        self.game = game
        self.tokens = tokens          # [token_p0, token_p1]
        self.id = game_id
        self.pending_scout: int | None = None
        self.time_remaining_ms: list[int] | None = [time_ms, time_ms] if time_ms else None
        self.increment_ms     = increment_ms
        self.last_turn_start: float = time.time()
        self.rated            = rated
        self.ratings_settled  = False

    def clock_state(self, pov: int) -> dict | None:
        if self.time_remaining_ms is None:
            return None
        opp = 1 - pov
        return {
            "my_remaining_ms":    self.time_remaining_ms[pov],
            "opp_remaining_ms":   self.time_remaining_ms[opp],
            "last_turn_start_ms": int(self.last_turn_start * 1000),
            "increment_ms":       self.increment_ms,
        }


class GameManager:
    def __init__(self):
        self.sessions: dict[str, GameSession] = {}       # game_id → session
        self.token_to_game: dict[str, str] = {}           # token → game_id
        self.token_to_player: dict[str, int] = {}         # token → player index

        self._pending: dict[str, PendingGame] = {}        # game_id → pending
        self._token_pending: dict[str, str] = {}          # token → game_id

    # ── Lobby / game creation ─────────────────────────────────────────────────

    def create_game(self, token: str, username: str,
                    time_ms: int | None = None, increment_ms: int = 0,
                    rated: bool = True, creator_rating: dict | None = None) -> str:
        self.cancel_pending(token)
        game_id = str(uuid.uuid4())[:8].upper()
        self._pending[game_id] = PendingGame(
            game_id, token, username, time_ms, increment_ms, rated, creator_rating,
        )
        self._token_pending[token] = game_id
        return game_id

    def join_game(self, token: str, username: str, game_id: str) -> tuple[bool, str]:
        pending = self._pending.get(game_id)
        if not pending:
            return False, "Game not found or already started."
        if pending.token == token:
            return False, "You cannot join your own game."

        self._pending.pop(game_id)
        self._token_pending.pop(pending.token, None)

        game = BattleLineGame([pending.username, username])
        session = GameSession(game, [pending.token, token], game_id,
                              pending.time_ms, pending.increment_ms, pending.rated)
        self.sessions[game_id] = session
        self.token_to_game[pending.token] = game_id
        self.token_to_game[token] = game_id
        self.token_to_player[pending.token] = 0
        self.token_to_player[token] = 1
        return True, ""

    def list_open_games(self) -> list[dict]:
        def time_label(p: PendingGame) -> str:
            if p.time_ms is None:
                return "Unlimited"
            total_secs = p.time_ms // 1000
            m, s = divmod(total_secs, 60)
            label = f"{m}:{s:02d}"
            if p.increment_ms > 0:
                label += f" +{p.increment_ms // 1000}s"
            return label

        return sorted(
            [
                {
                    "game_id":            p.game_id,
                    "creator":            p.username,
                    "created_at":         p.created_at,
                    "time_label":         time_label(p),
                    "rated":              p.rated,
                    "creator_rating":     p.creator_rating["rating"]      if p.creator_rating else None,
                    "creator_provisional": p.creator_rating["provisional"] if p.creator_rating else None,
                }
                for p in self._pending.values()
            ],
            key=lambda x: x["created_at"],
        )

    def is_pending(self, token: str) -> str | None:
        return self._token_pending.get(token)

    def cancel_pending(self, token: str) -> bool:
        game_id = self._token_pending.pop(token, None)
        if not game_id:
            return False
        self._pending.pop(game_id, None)
        return True

    # ── Session lookup ────────────────────────────────────────────────────────

    def get_session(self, token: str) -> tuple[GameSession, int] | None:
        game_id = self.token_to_game.get(token)
        if not game_id:
            return None
        session = self.sessions.get(game_id)
        if not session:
            return None
        return session, self.token_to_player[token]

    # ── Move application ──────────────────────────────────────────────────────

    def apply_move(self, token: str, move: dict) -> tuple[str, bool]:
        result = self.get_session(token)
        if not result:
            return "Not in a game.", False

        session, player_idx = result
        game = session.game

        if game.winner is not None:
            return "Game is already over.", False

        is_scout_return = move.get("action") == "scout_return"
        is_scout_reveal = move.get("action") == "scout_reveal"
        turn_completing  = not is_scout_reveal

        if is_scout_return:
            if session.pending_scout != player_idx:
                return "Not waiting for a scout return from you.", False
        else:
            if game.turn % 2 != player_idx:
                return "Not your turn.", False

        # Enforce clock for turn-completing moves (scout_reveal is part 1; clock ticks on return)
        if session.time_remaining_ms is not None and turn_completing:
            elapsed_ms = int((time.time() - session.last_turn_start) * 1000)
            if elapsed_ms >= session.time_remaining_ms[player_idx]:
                session.time_remaining_ms[player_idx] = 0
                game.winner = 1 - player_idx
                return "Time's up!", True

        try:
            msg, needs_draw = self._dispatch(session, player_idx, move)
            if needs_draw:
                from_tactics = move.get("draw_from_tactics", False)
                game.draw_card(player_idx, from_tactics)
                game.turn += 1

            # Deduct time and add increment after a successful turn-completing move
            if session.time_remaining_ms is not None and turn_completing:
                elapsed_ms = int((time.time() - session.last_turn_start) * 1000)
                remaining = session.time_remaining_ms[player_idx] - elapsed_ms
                session.time_remaining_ms[player_idx] = max(0, remaining + session.increment_ms)
                session.last_turn_start = time.time()

            return msg, True
        except (ValueError, KeyError, IndexError) as e:
            return str(e), False

    def _dispatch(self, session: GameSession, player: int, move: dict) -> tuple[str, bool]:
        game = session.game
        action = move.get("action")

        if action == "play_card":
            card = self._card_from_hand(move["card"], game, player)
            msg = game.play_card(player, card, move["totem"])
            return msg, True

        if action == "play_wild":
            tactic = self._tactic_from_hand(move["tactic"], game, player)
            msg = game.play_unassigned_wild(player, tactic, move["totem"])
            return msg, True

        if action == "play_environment":
            tactic = self._tactic_from_hand(move["tactic"], game, player)
            msg = game.play_environment(player, tactic, move["totem"])
            return msg, True

        if action == "scout_reveal":
            tactic = self._tactic_from_hand(move["tactic"], game, player)
            revealed = game.scout_reveal(
                player, tactic, move["troop_count"], move["tactics_count"]
            )
            session.pending_scout = player
            return f"Scout: revealed {len(revealed)} cards.", False

        if action == "scout_return":
            returns = [
                (self._card_from_hand(r["card"], game, player), r["dest"])
                for r in move["returns"]
            ]
            msg = game.scout_return(player, returns)
            session.pending_scout = None
            game.turn += 1
            return msg, False

        if action == "play_redeploy":
            tactic = self._tactic_from_hand(move["tactic"], game, player)
            card = self._card_from_totem(move["card"], game, player, move["from_totem"])
            msg = game.play_redeploy(player, tactic, move["from_totem"], card, move.get("to_totem"))
            return msg, True

        if action == "play_traitor":
            tactic = self._tactic_from_hand(move["tactic"], game, player)
            opp = 1 - player
            card = self._card_from_totem(move["card"], game, opp, move["from_totem"])
            msg = game.play_traitor(player, tactic, move["from_totem"], card, move["to_totem"])
            return msg, True

        if action == "play_deserter":
            tactic = self._tactic_from_hand(move["tactic"], game, player)
            opp = 1 - player
            card = self._card_from_totem(move["card"], game, opp, move["from_totem"])
            msg = game.play_deserter(player, tactic, move["from_totem"], card)
            return msg, True

        raise ValueError(f"Unknown action: {action!r}")

    # ── Card resolution helpers ───────────────────────────────────────────────

    def _card_from_hand(self, data: dict, game: BattleLineGame, player: int):
        for card in game.hands[player]:
            if self._matches(card, data):
                return card
        raise ValueError(f"Card {data} not found in hand.")

    def _tactic_from_hand(self, data: dict, game: BattleLineGame, player: int) -> TacticsCard:
        for card in game.hands[player]:
            if isinstance(card, TacticsCard) and card.name == data.get("name"):
                return card
        raise ValueError(f"Tactics card {data!r} not found in hand.")

    def _card_from_totem(self, data: dict, game: BattleLineGame, player: int, totem_idx: int):
        for card in game.totems[totem_idx].sides[player]:
            if self._matches(card, data):
                return card
        raise ValueError(f"Card {data} not found on totem {totem_idx}.")

    @staticmethod
    def _matches(card, data: dict) -> bool:
        if isinstance(card, UnassignedWild):
            return (
                data.get("type") == "wild"
                and card.tactic_name == data.get("tactic_name")
                and data.get("suit") is None
                and data.get("value") is None
            )
        if isinstance(card, WildCard):
            return (
                data.get("type") == "wild"
                and card.tactic_name == data.get("tactic_name")
                and card.suit == data.get("suit")
                and card.value == data.get("value")
            )
        if isinstance(card, TacticsCard):
            return data.get("type") == "tactics" and card.name == data.get("name")
        return (
            data.get("type") == "troop"
            and card.suit == data.get("suit")
            and card.value == data.get("value")
        )
