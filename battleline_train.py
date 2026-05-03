"""Train a simple Battle Line policy/value network with self-play data."""

from __future__ import annotations

import argparse
import random
import sys
import time
from typing import List, Tuple

try:
    import torch
    from torch import optim
    from torch.utils.data import DataLoader, TensorDataset
except ImportError:
    torch = None
    optim = None
    DataLoader = None
    TensorDataset = None

from battleline import BattleLineGame, Card, best_possible_hand
from battleline_nn import (
    build_default_model,
    encode_game_state,
    feature_size,
    features_to_tensor,
    legal_troop_move_mask,
    legal_troop_moves,
    policy_index,
    POLICY_DIM,
)
from game_loader import load_human_games


def choose_expert_troop_move(game: BattleLineGame, player: int) -> Tuple[Card, int, int]:
    """Choose the best troop-card placement move from the current state."""
    unplayed = game._unplayed_cards()
    best_move = None
    best_score = ((-1,), -1, -1)

    for card, ti, action_index in legal_troop_moves(game, player):
        totem = game.totems[ti]
        played = totem.sides[player] + [card]
        avail = [c for c in unplayed if c != card]
        rank = best_possible_hand(played, avail,
                                  cards_to_win=totem.cards_to_win,
                                  fog=totem.fog) or (0,)
        score = (rank, len(played), -ti)
        if score > best_score:
            best_score = score
            best_move = (card, ti, action_index)

    if best_move is None:
        # Fallback to any legal move if heuristic fails.
        moves = legal_troop_moves(game, player)
        if not moves:
            raise RuntimeError("No legal troop moves available.")
        best_move = moves[0]

    return best_move


def generate_selfplay_dataset(n_games: int, include_tactics_hand: bool = False):
    """Generate supervised training examples using a greedy troop-only expert."""
    examples = []

    for game_index in range(n_games):
        game = BattleLineGame(["Player 1", "Player 2"])
        game_examples = []
        winner = None
        while game.winner is None:
            player = game.turn % 2
            moves = legal_troop_moves(game, player)
            if not moves:
                # No legal moves, game ends in draw or based on claimed totems
                winner = None
                break
            features = encode_game_state(
                game,
                player=player,
                include_tactics_hand=include_tactics_hand,
            )
            legal_mask = legal_troop_move_mask(game, player)
            card, ti, action_index = choose_expert_troop_move(game, player)
            game_examples.append((features, legal_mask, action_index, player))
            game.play_card(player, card, ti)
            game.draw_card(player)
            game.turn += 1

        if winner is None:
            winner = game.winner
            if winner is None:
                # Count claimed totems
                p0_claimed = sum(1 for t in game.totems if t.claimed == 0)
                p1_claimed = sum(1 for t in game.totems if t.claimed == 1)
                if p0_claimed > p1_claimed:
                    winner = 0
                elif p1_claimed > p0_claimed:
                    winner = 1
                else:
                    winner = None  # true draw

        for features, legal_mask, action_index, sample_player in game_examples:
            if winner is None:
                value = 0.0  # draw
            else:
                value = 1.0 if sample_player == winner else -1.0
            examples.append((features, legal_mask, action_index, value))

    return examples


def build_training_tensors(examples, include_tactics_hand: bool = False, device: str = "cpu"):
    feature_list = []
    mask_list = []
    action_indices = []
    value_targets = []

    for features, legal_mask, action_index, value in examples:
        tensor = features_to_tensor(features).squeeze(0)
        feature_list.append(tensor)
        mask_list.append(torch.tensor(legal_mask, dtype=torch.bool, device=device))
        action_indices.append(action_index)
        value_targets.append(value)

    feature_tensor = torch.stack(feature_list)
    mask_tensor = torch.stack(mask_list)
    action_tensor = torch.tensor(action_indices, dtype=torch.long, device=device)
    value_tensor = torch.tensor(value_targets, dtype=torch.float32, device=device)
    return feature_tensor, mask_tensor, action_tensor, value_tensor


def train_model(
    model,
    dataset,
    epochs: int = 10,
    batch_size: int = 32,
    lr: float = 1e-3,
    value_weight: float = 1.0,
    device: str = "cpu",
):
    model.to(device)
    model.train()
    optimizer = optim.Adam(model.parameters(), lr=lr)
    data_loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    for epoch in range(1, epochs + 1):
        total_loss = 0.0
        total_policy = 0.0
        total_value = 0.0
        count = 0

        for features, legal_mask, actions, values in data_loader:
            features = features.to(device)
            legal_mask = legal_mask.to(device)
            actions = actions.to(device)
            values = values.to(device)

            optimizer.zero_grad()
            policy_logits, value_pred = model(features)
            masked_logits = policy_logits.masked_fill(~legal_mask, torch.finfo(policy_logits.dtype).min / 2)
            policy_loss = torch.nn.functional.cross_entropy(masked_logits, actions)
            value_loss = torch.nn.functional.mse_loss(value_pred, values)
            loss = policy_loss + value_weight * value_loss
            loss.backward()
            optimizer.step()

            total_loss += loss.item() * features.size(0)
            total_policy += policy_loss.item() * features.size(0)
            total_value += value_loss.item() * features.size(0)
            count += features.size(0)

        print(
            f"Epoch {epoch}/{epochs}: loss={total_loss / count:.4f} "
            f"policy={total_policy / count:.4f} value={total_value / count:.4f}"
        )


def main() -> int:
    if torch is None:
        print("PyTorch is required to run training. Install torch first.")
        return 1

    parser = argparse.ArgumentParser(description="Train Battle Line policy/value network.")
    parser.add_argument("--games", type=int, default=100, help="Number of self-play games to generate.")
    parser.add_argument("--epochs", type=int, default=10, help="Training epochs.")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size.")
    parser.add_argument("--lr", type=float, default=1e-3, help="Learning rate.")
    parser.add_argument("--value-weight", type=float, default=1.0, help="Weight for value loss.")
    parser.add_argument("--device", type=str, default="cpu", help="Torch device.")
    parser.add_argument("--save", type=str, default=None, help="Save model state dict to this file.")
    args = parser.parse_args()

    print(f"Generating {args.games} self-play games...")
    examples = generate_selfplay_dataset(args.games)
    random.shuffle(examples)
    print(f"Generated {len(examples)} examples.")

    feature_tensor, mask_tensor, action_tensor, value_tensor = build_training_tensors(
        examples, device=args.device
    )
    dataset = TensorDataset(feature_tensor, mask_tensor, action_tensor, value_tensor)
    model = build_default_model()

    start = time.time()
    train_model(
        model,
        dataset,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        value_weight=args.value_weight,
        device=args.device,
    )
    duration = time.time() - start
    print(f"Training complete in {duration:.1f}s")

    if args.save:
        torch.save(model.state_dict(), args.save)
        print(f"Saved model parameters to {args.save}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
