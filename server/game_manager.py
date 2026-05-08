"""In-memory game sessions, matchmaking queue, and move dispatch."""

import uuid
from battleline import (
    BattleLineGame, Card, WildCard, TacticsCard, SUITS,
)


class GameSession:
    def __init__(self, game: BattleLineGame, tokens: list[str], game_id: str):
        self.game = game
        self.tokens = tokens          # [token_p0, token_p1]
        self.id = game_id
        # player index waiting to resolve scout_return, or None
        self.pending_scout: int | None = None


class GameManager:
    def __init__(self):
        self.sessions: dict[str, GameSession] = {}      # game_id → session
        self.token_to_game: dict[str, str] = {}          # token → game_id
        self.token_to_player: dict[str, int] = {}        # token → player index
        self._queue: list[tuple[str, str]] = []          # [(token, username), ...]

    # ── Matchmaking ───────────────────────────────────────────────────────────

    def enqueue(self, token: str, username: str) -> str | None:
        """
        Add player to the matchmaking queue.
        Returns game_id immediately if another player was waiting, else None.
        """
        if self._queue:
            other_token, other_name = self._queue.pop(0)
            game_id = str(uuid.uuid4())[:8]
            game = BattleLineGame([other_name, username])
            session = GameSession(game, [other_token, token], game_id)
            self.sessions[game_id] = session
            self.token_to_game[other_token] = game_id
            self.token_to_game[token] = game_id
            self.token_to_player[other_token] = 0
            self.token_to_player[token] = 1
            return game_id

        self._queue.append((token, username))
        return None

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
        """
        Apply a player move.  Returns (message, success).
        On success, game state has already been mutated.
        """
        result = self.get_session(token)
        if not result:
            return "Not in a game.", False

        session, player_idx = result
        game = session.game

        if game.winner is not None:
            return "Game is already over.", False

        # Scout return is an out-of-turn action for the same player
        is_scout_return = move.get("action") == "scout_return"
        if is_scout_return:
            if session.pending_scout != player_idx:
                return "Not waiting for a scout return from you.", False
        else:
            if game.turn % 2 != player_idx:
                return "Not your turn.", False

        try:
            msg, needs_draw = self._dispatch(session, player_idx, move)
            if needs_draw:
                from_tactics = move.get("draw_from_tactics", False)
                game.draw_card(player_idx, from_tactics)
                game.turn += 1
            return msg, True
        except (ValueError, KeyError, IndexError) as e:
            return str(e), False

    def _dispatch(self, session: GameSession, player: int, move: dict) -> tuple[str, bool]:
        """Route move to the correct game method. Returns (message, needs_draw)."""
        game = session.game
        action = move.get("action")

        if action == "play_card":
            card = self._card_from_hand(move["card"], game, player)
            msg = game.play_card(player, card, move["totem"])
            return msg, True

        if action == "play_wild":
            tactic = self._tactic_from_hand(move["tactic"], game, player)
            msg = game.play_wild(player, tactic, move["totem"], move["suit"], move["value"])
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
            # Scout replaces the normal draw; turn advances after scout_return
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
