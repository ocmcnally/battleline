"""Convert saved human-vs-AI games into training examples."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from typing import List, Tuple

from game_saver import list_human_games, load_game, HUMAN_GAMES_DIR
from battleline import BattleLineGame, Card
from utils import compute_value, avg_formation_quality, claim_formation_bonus
from battleline_features import (
    encode,
    legal_mask,
    legal_troop_moves,
    policy_index,
)


def game_to_examples(game: BattleLineGame, moves: List[Tuple], winner: int | None) -> List[Tuple]:
    """
    Replay a saved game and return (features, mask, action_index, value) per move.
    """
    examples    = []
    replay_game = BattleLineGame(game.names)

    for player, card, ti in moves:
        features = encode(replay_game, player)
        mask     = legal_mask(replay_game, player)

        action_index = None
        for card_obj, ti_obj, idx in legal_troop_moves(replay_game, player):
            if card_obj.suit == card.suit and card_obj.value == card.value and ti_obj == ti:
                action_index = idx
                break

        if action_index is None:
            print(f"Warning: could not find action index for {player} {card} totem {ti}")
            continue

        # play_card checks hand membership by identity, so we need the actual
        # card object from the hand rather than the reconstructed one from JSON.
        actual_card = next(
            (c for c in replay_game.hands[player]
             if isinstance(c, Card) and c.suit == card.suit and c.value == card.value),
            None
        )
        if actual_card is None:
            print(f"Warning: card {card} not found in hand for player {player}, skipping game")
            return []

        claimed_before = {i for i, t in enumerate(replay_game.totems) if t.claimed == player}

        replay_game.play_card(player, actual_card, ti)
        replay_game.draw_card(player)
        replay_game.turn += 1

        newly_claimed = {i for i, t in enumerate(replay_game.totems)
                         if t.claimed == player and i not in claimed_before}
        step_bonus = (avg_formation_quality(replay_game, player)
                      + claim_formation_bonus(replay_game, player, newly_claimed))

        value = compute_value(winner, player, game.totems, step_bonus)
        examples.append((features, mask, action_index, value))

    return examples


def load_human_games() -> List[Tuple]:
    """Load all human-created games from saved_games/human_games/ and convert to training examples."""
    all_examples = []
    game_files   = list_human_games()
    print(f"Loading {len(game_files)} human games from {HUMAN_GAMES_DIR}...")

    for game_file in game_files:
        try:
            filepath = os.path.join(HUMAN_GAMES_DIR, game_file)
            game, moves, winner = load_game(filepath)
            examples = game_to_examples(game, moves, winner)
            all_examples.extend(examples)
            print(f"  {game_file}: {len(examples)} examples")
        except Exception as e:
            print(f"  {game_file}: {e}")

    print(f"Total: {len(all_examples)} examples")
    return all_examples


if __name__ == "__main__":
    examples = load_human_games()
    print(f"\nLoaded {len(examples)} training examples from human games")
