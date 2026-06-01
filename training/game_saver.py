"""Game saving and loading utilities for Battle Line."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from pathlib import Path
from typing import List, Dict, Any
from battleline import BattleLineGame, Card, SUITS

GAMES_DIR = "saved_games"
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
    initial_hands: list | None = None,
    initial_deck:  list | None = None,
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

    data: Dict[str, Any] = {
        "players": game.names,
        "winner":  winner,
        "moves": [
            {"player": player, "card": {"suit": card.suit, "value": card.value}, "totem_index": ti}
            for player, card, ti in moves
        ],
    }
    if initial_hands is not None:
        data["initial_hands"] = [
            [{"suit": c.suit, "value": c.value} for c in hand]
            for hand in initial_hands
        ]
    if initial_deck is not None:
        data["initial_deck"] = [{"suit": c.suit, "value": c.value} for c in initial_deck]
    if states is not None:
        data["states_p0"] = states["p0"]
        data["states_p1"] = states["p1"]

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

    return filepath

def load_game(filepath: str) -> tuple[BattleLineGame, List[tuple], int | None]:
    """
    Load a saved game and return (game, moves, winner).
    Requires initial_hands and initial_deck to be present in the JSON —
    games saved before those fields were added cannot be replayed accurately.
    """
    with open(filepath, 'r') as f:
        data = json.load(f)

    if "initial_hands" not in data or "initial_deck" not in data:
        raise ValueError(
            "Game file is missing initial_hands/initial_deck — "
            "it was saved before accurate replay was supported and cannot be loaded."
        )

    game = BattleLineGame(data["players"])

    # Override the randomly-dealt hands and deck with the saved initial state
    # so that replay follows the exact same card sequence as the original game.
    game.hands[0] = [Card(c["suit"], c["value"]) for c in data["initial_hands"][0]]
    game.hands[1] = [Card(c["suit"], c["value"]) for c in data["initial_hands"][1]]
    game.deck      = [Card(c["suit"], c["value"]) for c in data["initial_deck"]]

    moves = []
    for move_data in data["moves"]:
        player    = move_data["player"]
        card_dict = move_data["card"]
        ti        = move_data["totem_index"]

        card = next(
            (c for c in game.hands[player]
             if c.suit == card_dict["suit"] and c.value == card_dict["value"]),
            None
        )
        if card is None:
            raise ValueError(f"Card {card_dict} not found in player {player}'s hand")

        game.play_card(player, card, ti)
        moves.append((player, card, ti))

        if game.deck:
            game.hands[player].append(game.deck.pop())

        game.turn += 1

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
