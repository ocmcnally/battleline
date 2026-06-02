"""Game saving and loading utilities for Battle Line."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from pathlib import Path
from typing import List, Dict, Any
from battleline import BattleLineGame, Card, SUITS

_PROJECT_ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAMES_DIR       = os.path.join(_PROJECT_ROOT, "saved_games")
HUMAN_GAMES_DIR = os.path.join(GAMES_DIR, "human_games")

def ensure_games_dir():
    """Create the saved_games and human_games directories if they don't exist."""
    Path(GAMES_DIR).mkdir(exist_ok=True)
    Path(HUMAN_GAMES_DIR).mkdir(exist_ok=True)

def save_game(
    game:          BattleLineGame,
    moves:         List[tuple],
    winner:        int | None,
    filename:      str  | None = None,
    states:        dict | None = None,
    human:         bool = True,
    initial_hands:    list | None = None,
    initial_deck:     list | None = None,
    training_moves:   list | None = None,
) -> str:
    """
    Save a completed game to JSON.

    moves:         list of (player, Card, totem_index) tuples
    winner:        0, 1, or None for draw
    states:        optional dict with keys "p0" and "p1" for client-side replay
    human:         if True, save to saved_games/human_games/; if False, saved_games/
    initial_hands: the two players' hands at game start — required for accurate replay
    initial_deck:  the remaining deck at game start — required for accurate replay
    """
    ensure_games_dir()

    if filename is None:
        import time
        filename = f"game_{int(time.time())}.json"

    save_dir = HUMAN_GAMES_DIR if human else GAMES_DIR
    filepath = os.path.join(save_dir, filename)

    def _move_dict(m):
        player, card, ti = m[0], m[1], m[2]
        drew_tactics = m[3] if len(m) > 3 else False
        return {"player": player, "card": {"suit": card.suit, "value": card.value},
                "totem_index": ti, "drew_from_tactics": drew_tactics}

    data: Dict[str, Any] = {
        "players": game.names,
        "winner":  winner,
        "moves":   [_move_dict(m) for m in moves],
    }
    if initial_hands is not None:
        data["initial_hands"] = [
            [{"suit": c.suit, "value": c.value} for c in hand]
            for hand in initial_hands
        ]
    if initial_deck is not None:
        data["initial_deck"] = [{"suit": c.suit, "value": c.value} for c in initial_deck]
    if training_moves is not None and len(training_moves) > 0:
        # Compute value for each move now that we know the winner and final totems.
        # Import here to avoid circular dependency at module load time.
        from utils import compute_value
        t_me  = [sum(1 for t in game.totems if t.claimed == p) for p in (0, 1)]
        t_opp = [t_me[1], t_me[0]]
        margin = [(t_me[p] - t_opp[p]) / 9.0 for p in (0, 1)]
        outcome = {0: [1.0, -1.0], 1: [-1.0, 1.0], None: [0.0, 0.0]}[winner]
        rows = []
        for feats, msk, act_idx, player, step_bonus in training_moves:
            value = compute_value(winner, player, game.totems, step_bonus)
            rows.append({
                "features":   feats,
                "mask":       msk,
                "action_idx": act_idx,
                "player":     player,
                "value":      value,
            })
        data["training_examples"] = rows
    if states is not None:
        data["states_p0"] = states["p0"]
        data["states_p1"] = states["p1"]

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

    return filepath

def load_game(filepath: str) -> tuple[BattleLineGame, List[tuple], int | None]:
    """
    Load a saved game and return (initial_game, moves, winner).

    initial_game has hands and deck set to the start-of-game state — no moves
    played yet.  Callers that need to replay the game should step through moves
    themselves using the initial_game as the starting point.

    moves is a list of (player, Card, totem_index, drew_from_tactics).
    """
    with open(filepath, 'r') as f:
        data = json.load(f)

    if "initial_hands" not in data or "initial_deck" not in data:
        raise ValueError(
            "Game file is missing initial_hands/initial_deck — "
            "it was saved before accurate replay was supported and cannot be loaded."
        )

    # Build the initial game state with the saved deck/hand order.
    game = BattleLineGame(data["players"])
    game.hands[0] = [Card(c["suit"], c["value"]) for c in data["initial_hands"][0]]
    game.hands[1] = [Card(c["suit"], c["value"]) for c in data["initial_hands"][1]]
    game.deck      = [Card(c["suit"], c["value"]) for c in data["initial_deck"]]

    # Parse moves — include drew_from_tactics so callers can replay draws correctly.
    moves = []
    for move_data in data["moves"]:
        card_dict    = move_data["card"]
        drew_tactics = move_data.get("drew_from_tactics", False)
        moves.append((
            move_data["player"],
            Card(card_dict["suit"], card_dict["value"]),
            move_data["totem_index"],
            drew_tactics,
        ))

    return game, moves, data["winner"]

def list_saved_games() -> List[str]:
    """List all saved game files."""
    ensure_games_dir()
    return sorted([f for f in os.listdir(GAMES_DIR) if f.endswith('.json')])

def list_human_games() -> List[str]:
    """List all manually-created human game files from saved_games/human_games/."""
    ensure_games_dir()
    return sorted([f for f in os.listdir(HUMAN_GAMES_DIR) if f.endswith('.json')])

def get_game_count() -> int:
    """Get the total number of saved games."""
    return len(list_saved_games())
