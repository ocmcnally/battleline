"""Load human game files and return pre-computed training examples."""

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from typing import List, Tuple

from game_saver import list_human_games, HUMAN_GAMES_DIR


def load_human_games() -> List[Tuple]:
    """
    Load training examples from human game files.

    Training data is captured in-line during the GUI game (no replay needed),
    so this simply deserialises the pre-computed features/mask/action/value
    from each JSON file.
    """
    all_examples = []
    game_files   = list_human_games()
    print(f"Loading {len(game_files)} human games from {HUMAN_GAMES_DIR}...")

    for game_file in game_files:
        filepath = os.path.join(HUMAN_GAMES_DIR, game_file)
        try:
            with open(filepath) as f:
                data = json.load(f)

            rows = data.get("training_examples")
            if not rows:
                print(f"  {game_file}: no training_examples (old format, skipping)")
                continue

            examples = [
                (row["features"], row["mask"], row["action_idx"], row["value"])
                for row in rows
            ]
            all_examples.extend(examples)
            print(f"  {game_file}: {len(examples)} examples")
        except Exception as e:
            print(f"  {game_file}: {e}")

    print(f"Total: {len(all_examples)} examples")
    return all_examples


if __name__ == "__main__":
    examples = load_human_games()
    print(f"\nLoaded {len(examples)} training examples from human games")
