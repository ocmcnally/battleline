"""Game saving and loading utilities for Battle Line."""

import json
import os
from pathlib import Path
from typing import List, Dict, Any
from battleline import BattleLineGame, Card, SUITS

GAMES_DIR = "saved_games"

def ensure_games_dir():
    """Create the saved_games directory if it doesn't exist."""
    Path(GAMES_DIR).mkdir(exist_ok=True)

def save_game(game: BattleLineGame, moves: List[tuple], winner: int | None, filename: str = None) -> str:
    """
    Save a completed game to JSON.
    
    moves: list of (player, card_suit, card_value, totem_index) tuples
    winner: 0, 1, or None for draw
    returns: path to saved file
    """
    ensure_games_dir()
    
    if filename is None:
        import time
        filename = f"game_{int(time.time())}.json"
    
    filepath = os.path.join(GAMES_DIR, filename)
    
    data = {
        "players": game.names,
        "winner": winner,
        "moves": [
            {
                "player": player,
                "card": {"suit": card.suit, "value": card.value},
                "totem_index": ti
            }
            for player, card, ti in moves
        ]
    }
    
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    
    return filepath

def load_game(filepath: str) -> tuple[BattleLineGame, List[tuple], int | None]:
    """
    Load a saved game and return the final game state, moves, and winner.
    
    returns: (game, moves, winner)
    """
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    game = BattleLineGame(data["players"])
    moves = []
    
    for move_data in data["moves"]:
        player = move_data["player"]
        card_dict = move_data["card"]
        ti = move_data["totem_index"]
        
        # Reconstruct the card
        card = Card(card_dict["suit"], card_dict["value"])
        
        # Play the move
        game.play_card(player, card, ti)
        moves.append((player, card, ti))
        
        # Draw a card
        if game.deck:
            game.hands[player].append(game.deck.pop())
        
        game.turn += 1
    
    winner = data["winner"]
    return game, moves, winner

def list_saved_games() -> List[str]:
    """List all saved game files."""
    ensure_games_dir()
    return sorted([f for f in os.listdir(GAMES_DIR) if f.endswith('.json')])

def get_game_count() -> int:
    """Get the total number of saved games."""
    return len(list_saved_games())
