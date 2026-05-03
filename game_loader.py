"""Convert saved human-vs-AI games into training examples."""

import os
from typing import List, Tuple, Dict, Any
from game_saver import list_saved_games, load_game
from battleline import BattleLineGame, best_possible_hand
from battleline_nn import (
    encode_game_state,
    legal_troop_move_mask,
    legal_troop_moves,
    policy_index,
)

def game_to_examples(game: BattleLineGame, moves: List[Tuple], winner: int | None) -> List[Tuple]:
    """
    Convert a saved game into training examples.
    
    Each move becomes an example: (features, legal_mask, action_index, value)
    The value is 1.0 if the player won, -1.0 if they lost, 0.0 if draw.
    """
    examples = []
    
    # Replay the game to extract state at each move
    replay_game = BattleLineGame(game.names)
    
    for move_idx, (player, card, ti) in enumerate(moves):
        # Get state before the move
        features = encode_game_state(replay_game, player=player)
        legal_mask = legal_troop_move_mask(replay_game, player)
        
        # Find the action index for this move
        move_list = legal_troop_moves(replay_game, player)
        action_index = None
        for card_obj, ti_obj, idx in move_list:
            if card_obj.suit == card.suit and card_obj.value == card.value and ti_obj == ti:
                action_index = idx
                break
        
        if action_index is None:
            print(f"Warning: Could not find action index for move {player} {card} {ti}")
            continue
        
        # Compute value
        if winner is None:
            value = 0.0  # draw
        else:
            value = 1.0 if player == winner else -1.0
        
        examples.append((features, legal_mask, action_index, value))
        
        # Play the move in replay game
        replay_game.play_card(player, card, ti)
        if replay_game.deck:
            replay_game.hands[player].append(replay_game.deck.pop())
        replay_game.turn += 1
    
    return examples

def load_human_games(games_dir: str = "saved_games") -> List[Tuple]:
    """Load all saved games and convert them to training examples."""
    all_examples = []
    game_files = list_saved_games()
    
    print(f"Loading {len(game_files)} saved games from {games_dir}...")
    
    for game_file in game_files:
        try:
            filepath = os.path.join(games_dir, game_file)
            game, moves, winner = load_game(filepath)
            examples = game_to_examples(game, moves, winner)
            all_examples.extend(examples)
            print(f"  ✓ {game_file}: {len(examples)} examples")
        except Exception as e:
            print(f"  ✗ {game_file}: {e}")
    
    print(f"Total human-game examples: {len(all_examples)}")
    return all_examples

if __name__ == "__main__":
    examples = load_human_games()
    print(f"\nLoaded {len(examples)} training examples from human games")
