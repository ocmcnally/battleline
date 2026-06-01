"""Battle Line self-play training loop."""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import copy
import random
import time
from typing import List, Tuple

import numpy as np

try:
    import torch
    from torch import optim
    from torch.utils.data import DataLoader, TensorDataset
except ImportError:
    torch = None
    optim = None
    DataLoader = None
    TensorDataset = None

from battleline import BattleLineGame
from utils import compute_value, avg_formation_quality, claim_formation_bonus
from game_saver import save_game
from server.serializer import game_view
from battleline_features import (
    BattleLineNet,
    POLICY_DIM,
    encode,
    legal_mask,
    legal_troop_moves,
    to_tensor,
)


# ── Move selection ─────────────────────────────────────────────────────────────

def _sample_action(
    logits:      "torch.Tensor",
    moves:       list,
    temperature: float,
    noise_eps:   float,
    noise_alpha: float,
) -> int:
    """
    Given a 1-D logit tensor (POLICY_DIM,) and a list of legal (card, ti, idx)
    moves, return the chosen action index.

    Extracted as a helper so the same sampling logic is shared between the
    single-game path (nn_choose_move) and the batched generation path
    (generate_selfplay_dataset), avoiding code duplication.
    """
    legal_mask_t = torch.zeros(POLICY_DIM, dtype=torch.bool)
    for _, _, idx in moves:
        legal_mask_t[idx] = True
    logits = logits.masked_fill(~legal_mask_t, float("-inf"))

    if temperature < 1e-6:
        return int(logits.argmax())

    probs       = torch.softmax(logits / temperature, dim=0).numpy()
    legal_probs = probs[[idx for _, _, idx in moves]]
    legal_probs = np.clip(legal_probs, 0, None)

    if noise_eps > 0 and len(moves) > 1:
        noise       = np.random.dirichlet([noise_alpha] * len(moves))
        legal_probs = (1 - noise_eps) * legal_probs + noise_eps * noise

    legal_probs /= legal_probs.sum()
    return moves[np.random.choice(len(moves), p=legal_probs)][2]


def nn_choose_move(
    game:        BattleLineGame,
    player:      int,
    model,
    temperature: float = 1.0,
    noise_eps:   float = 0.0,
    noise_alpha: float = 0.3,
):
    """
    Single-game move selection — used by evaluate_models and sample_game.
    For bulk game generation use generate_selfplay_dataset which batches
    all active games into one forward pass per round.
    """
    moves = legal_troop_moves(game, player)
    if not moves:
        return None
    with torch.no_grad():
        logits, _ = model(to_tensor(game, player))
    action_idx = _sample_action(logits.squeeze(0), moves, temperature, noise_eps, noise_alpha)
    for card, ti, idx in moves:
        if idx == action_idx:
            return card, ti, idx
    return moves[0]


# ── Self-play data generation ──────────────────────────────────────────────────

def generate_selfplay_dataset(n_games: int, model, temperature: float = 1.0, noise_eps: float = 0.25) -> List[Tuple]:
    """
    Play n_games of the current model against itself and return training examples.

    Each position becomes: (features, legal_mask, action_taken, outcome)
    outcome: +1.0 if the player whose turn it was won, -1.0 if lost, 0.0 draw.
    """
    model.eval()
    examples = []

    for _ in range(n_games):
        game          = BattleLineGame(["P0", "P1"])
        game_examples = []

        while game.winner is None:
            player = game.turn % 2
            move   = nn_choose_move(game, player, model, temperature, noise_eps)
            if move is None:
                break

            features = encode(game, player)
            mask     = legal_mask(game, player)
            card, ti, action_index = move

            claimed_before = {i for i, t in enumerate(game.totems) if t.claimed == player}

            game.play_card(player, card, ti)
            game.draw_card(player)
            game.turn += 1

            newly_claimed = {i for i, t in enumerate(game.totems)
                             if t.claimed == player and i not in claimed_before}
            step_bonus = (avg_formation_quality(game, player)
                          + claim_formation_bonus(game, player, newly_claimed))

            game_examples.append((features, mask, action_index, player, step_bonus))

        winner = game.winner
        if winner is None:
            p0 = sum(1 for t in game.totems if t.claimed == 0)
            p1 = sum(1 for t in game.totems if t.claimed == 1)
            winner = 0 if p0 > p1 else (1 if p1 > p0 else None)

        for features, mask, action_index, sample_player, step_bonus in game_examples:
            value = compute_value(winner, sample_player, game.totems, step_bonus)
            examples.append((features, mask, action_index, value))

    return examples


# ── Sample game saving ────────────────────────────────────────────────────────

def _state_snapshot(game: BattleLineGame, pov: int) -> dict:
    s = game_view(game, pov)
    s["clock"]         = None
    s["rated"]         = False
    s["category"]      = None
    s["rating_change"] = None
    return s


def sample_game(model, iteration: int) -> None:
    """Play one greedy game, capture full state sequence, and save for replay."""
    model.eval()
    game  = BattleLineGame(["Model-P0", "Model-P1"])
    moves = []

    states_p0 = [_state_snapshot(game, 0)]
    states_p1 = [_state_snapshot(game, 1)]

    while game.winner is None:
        player = game.turn % 2
        move   = nn_choose_move(game, player, model, temperature=0.0)
        if move is None:
            break
        card, ti, _ = move
        game.play_card(player, card, ti)
        moves.append((player, card, ti))
        game.draw_card(player)
        game.turn += 1
        states_p0.append(_state_snapshot(game, 0))
        states_p1.append(_state_snapshot(game, 1))

    winner = game.winner
    if winner is None:
        p0 = sum(1 for t in game.totems if t.claimed == 0)
        p1 = sum(1 for t in game.totems if t.claimed == 1)
        winner = 0 if p0 > p1 else (1 if p1 > p0 else None)

    filename = f"selfplay_iter_{iteration:04d}.json"
    path = save_game(game, moves, winner, filename, states={"p0": states_p0, "p1": states_p1})
    print(f"Sample game saved → {path}  ({len(moves)} moves)")


# ── Evaluation ─────────────────────────────────────────────────────────────────

def evaluate_models(new_model, old_model, n_games: int = 50) -> float:
    """
    Play n_games between new_model and old_model (greedy, no exploration).
    Returns new_model's win rate.
    Alternates which model plays as player 0 to remove first-move bias.
    """
    new_model.eval()
    old_model.eval()
    new_wins = 0

    for i in range(n_games):
        game       = BattleLineGame(["New", "Old"])
        new_is_p0  = (i % 2 == 0)

        while game.winner is None:
            player = game.turn % 2
            model  = new_model if ((player == 0) == new_is_p0) else old_model
            move   = nn_choose_move(game, player, model, temperature=0.0)
            if move is None:
                break
            card, ti, _ = move
            game.play_card(player, card, ti)
            game.draw_card(player)
            game.turn += 1

        winner = game.winner
        if winner is None:
            p0 = sum(1 for t in game.totems if t.claimed == 0)
            p1 = sum(1 for t in game.totems if t.claimed == 1)
            winner = 0 if p0 > p1 else (1 if p1 > p0 else None)

        if winner is not None:
            new_player = 0 if new_is_p0 else 1
            if winner == new_player:
                new_wins += 1

    return new_wins / n_games


# ── Training ───────────────────────────────────────────────────────────────────

def build_training_tensors(examples, device: str = "cpu"):
    feature_list, mask_list, action_list, value_list = [], [], [], []
    for features, mask, action_index, value in examples:
        feature_list.append(torch.tensor(features, dtype=torch.float32))
        mask_list.append(torch.tensor(mask, dtype=torch.bool))
        action_list.append(action_index)
        value_list.append(value)
    return (
        torch.stack(feature_list).to(device),
        torch.stack(mask_list).to(device),
        torch.tensor(action_list, dtype=torch.long,    device=device),
        torch.tensor(value_list,  dtype=torch.float32, device=device),
    )


def train_model(
    model,
    dataset,
    epochs:       int   = 10,
    batch_size:   int   = 64,
    lr:           float = 1e-3,
    value_weight: float = 1.0,
    device:       str   = "cpu",
):
    model.to(device)
    model.train()
    optimizer   = optim.Adam(model.parameters(), lr=lr)
    data_loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    for epoch in range(1, epochs + 1):
        total_loss = total_policy = total_value = 0.0
        count = 0

        for features, mask, actions, values in data_loader:
            features = features.to(device)
            mask     = mask.to(device)
            actions  = actions.to(device)
            values   = values.to(device)

            optimizer.zero_grad()
            policy_logits, value_pred = model(features)
            masked_logits = policy_logits.masked_fill(
                ~mask, torch.finfo(policy_logits.dtype).min / 2
            )
            policy_loss = torch.nn.functional.cross_entropy(masked_logits, actions)
            value_loss  = torch.nn.functional.mse_loss(value_pred, values)
            batch_loss  = policy_loss + value_weight * value_loss
            batch_loss.backward()
            optimizer.step()

            n             = features.size(0)
            total_loss   += batch_loss.item()  * n
            total_policy += policy_loss.item() * n
            total_value  += value_loss.item()  * n
            count        += n

        print(
            f"  Epoch {epoch}/{epochs}: "
            f"loss={total_loss/count:.4f}  "
            f"policy={total_policy/count:.4f}  "
            f"value={total_value/count:.4f}"
        )


# ── Main loop ──────────────────────────────────────────────────────────────────

_MODEL_PATH = os.path.join(os.path.dirname(__file__), "battleline_model.pt")


def main() -> int:
    if torch is None:
        print("PyTorch is required. Install torch first.")
        return 1

    parser = argparse.ArgumentParser(description="Battle Line self-play training loop.")
    parser.add_argument("--iterations",        type=int,   default=20,   help="Number of self-play/train iterations.")
    parser.add_argument("--games",             type=int,   default=200,  help="Self-play games per iteration.")
    parser.add_argument("--epochs",            type=int,   default=5,    help="Training epochs per iteration. Lower than before because the replay buffer already provides diversity — more epochs just overfits the current batch.")
    parser.add_argument("--batch-size",        type=int,   default=64)
    parser.add_argument("--lr",                type=float, default=1e-3)
    parser.add_argument("--value-weight",      type=float, default=1.0)
    parser.add_argument("--temperature",       type=float, default=1.0,  help="Move sampling temperature during self-play.")
    parser.add_argument("--noise-eps",         type=float, default=0.25, help="Dirichlet noise fraction mixed into policy during self-play (0 = off).")
    parser.add_argument("--noise-alpha",       type=float, default=0.3,  help="Dirichlet alpha — lower = more extreme noise.")
    parser.add_argument("--buffer-iters",      type=int,   default=10,   help="Keep examples from this many past iterations in the replay buffer.")
    parser.add_argument("--eval-games",        type=int,   default=50,   help="Games to evaluate new vs old model.")
    parser.add_argument("--promote-threshold", type=float, default=0.52, help="Win rate required to promote candidate.")
    parser.add_argument("--step-weight",       type=float, default=0.35, help="Weight of per-move formation/claim bonus in value target.")
    parser.add_argument("--hidden-dim",        type=int,   default=512)
    parser.add_argument("--n-blocks",          type=int,   default=6)
    parser.add_argument("--checkpoint-dir",    type=str,   default=os.path.join(os.path.dirname(__file__), "checkpoints"))
    parser.add_argument("--device",            type=str,   default="cpu")
    parser.add_argument("--fresh",             action="store_true", help="Ignore existing model and start from scratch.")
    args = parser.parse_args()

    os.makedirs(args.checkpoint_dir, exist_ok=True)

    # Load or initialise model.
    # Track whether we started truly fresh so we know whether iteration 1
    # has a valid baseline to evaluate against.
    model = BattleLineNet(hidden_dim=args.hidden_dim, n_blocks=args.n_blocks)
    started_fresh = args.fresh or not os.path.exists(_MODEL_PATH)
    if not started_fresh:
        model.load_state_dict(torch.load(_MODEL_PATH, weights_only=True))
        print(f"Loaded existing model from {_MODEL_PATH}")
    else:
        print("Starting with fresh model.")
    print(f"Parameters: {sum(p.numel() for p in model.parameters()):,}\n")

    win_history: List[float] = []

    # Replay buffer: stores example batches from recent iterations.
    # Training on a mix of old and new data prevents the model from
    # memorising a single batch (which caused value loss → 0.02 quickly
    # without any real improvement in play quality — the echo chamber problem).
    # We keep the last `buffer_iters` iterations rather than a fixed example
    # count so the buffer naturally scales with --games.
    replay_buffer: List[List] = []

    for iteration in range(1, args.iterations + 1):
        iter_start = time.time()
        print(f"{'='*54}")
        print(f"Iteration {iteration}/{args.iterations}")
        print(f"{'='*54}")

        # 1. Generate self-play games with current model.
        # Dirichlet noise (noise_eps) is mixed into the policy at every move
        # so the model is forced to occasionally try moves it would normally
        # underweight.  This prevents the games from all looking identical and
        # gives the replay buffer genuine diversity across iterations.
        # noise_eps=0 during evaluation and sample_game so those stay greedy.
        print(f"Generating {args.games} games "
              f"(temp={args.temperature}, noise={args.noise_eps})...")
        new_examples = generate_selfplay_dataset(
            args.games, model, args.temperature, args.noise_eps
        )
        print(f"Generated {len(new_examples)} new examples.")

        # 2. Update replay buffer.
        # Pop the oldest iteration batch when the buffer is full so we never
        # train on data from more than `buffer_iters` iterations ago.
        replay_buffer.append(new_examples)
        if len(replay_buffer) > args.buffer_iters:
            replay_buffer.pop(0)

        # Flatten and shuffle all buffered examples for training.
        all_examples = [ex for batch in replay_buffer for ex in batch]
        random.shuffle(all_examples)
        print(f"Replay buffer: {len(all_examples)} examples "
              f"({len(replay_buffer)}/{args.buffer_iters} iterations).")

        # 3. Train a candidate starting from the current model's weights.
        # Training on the full buffer (not just new examples) means each
        # gradient step sees a diverse mix of positions from different model
        # versions, reducing overfitting to the current play style.
        candidate = copy.deepcopy(model)
        tensors   = build_training_tensors(all_examples, args.device)
        dataset   = TensorDataset(*tensors)
        print("Training candidate...")
        train_model(
            candidate, dataset,
            epochs=args.epochs,
            batch_size=args.batch_size,
            lr=args.lr,
            value_weight=args.value_weight,
            device=args.device,
        )

        # 4. Evaluate candidate vs current model.
        # Skip evaluation only on iteration 1 of a truly fresh run — in that
        # case there is no meaningful baseline to compare against.
        # When continuing from a saved model, evaluate every iteration so the
        # existing model is always the bar to beat.
        if iteration == 1 and started_fresh:
            win_rate = 1.0
            print("Iteration 1 (fresh start): promoting without evaluation.")
        else:
            print(f"Evaluating ({args.eval_games} games)...")
            win_rate = evaluate_models(candidate, model, args.eval_games)
            win_history.append(win_rate)
            print(f"Candidate win rate: {win_rate:.1%}  "
                  f"(threshold {args.promote_threshold:.1%})")

        # 5. Promote or discard.
        if win_rate >= args.promote_threshold:
            model = candidate
            torch.save(model.state_dict(), _MODEL_PATH)
            ckpt = os.path.join(args.checkpoint_dir, f"iter_{iteration:04d}.pt")
            torch.save(model.state_dict(), ckpt)
            print(f"Promoted.  Saved to {ckpt}")
        else:
            print("Candidate rejected — keeping current model.")

        sample_game(model, iteration)
        elapsed = time.time() - iter_start
        print(f"Iteration time: {elapsed:.1f}s")

    print(f"\n{'='*54}")
    print("Training complete.")
    if win_history:
        print(f"Win rates by iteration: {[f'{r:.0%}' for r in win_history]}")
    print(f"Final model: {_MODEL_PATH}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
