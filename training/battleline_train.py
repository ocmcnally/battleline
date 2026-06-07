"""Battle Line self-play training loop."""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import copy
import multiprocessing as mp
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

from battleline import BattleLineGame, TacticsCard
from game_loader import load_human_games
from game_saver import save_game
from server.serializer import game_view
from battleline_features import (
    BattleLineNet,
    POLICY_DIM,
    legal_troop_moves,
    to_tensor,
)


# ── Move execution helpers ────────────────────────────────────────────────────────

def _best_card_for_formation(candidates: list, current_formation: list):
    """Return the card from candidates that maximizes formation quality when added to current_formation."""
    from battleline_features import _formation_cards, _best_consistent_type
    _SCORES = {1: 0.0, 2: 0.10, 3: 0.30, 4: 0.65, 5: 1.0}

    def score(cards):
        fc = _formation_cards(cards)
        return _SCORES.get(_best_consistent_type(fc), 0.0) if fc else 0.0

    best_card = candidates[0]
    best_score = -1.0
    for c in candidates:
        s = score(current_formation + [c])
        if s > best_score:
            best_score = s
            best_card = c
    return best_card


# ── Move execution ────────────────────────────────────────────────────────────────

def play_move(game, player, move_info):
    """
    Execute a move returned from legal_all_moves.
    move_info = (move_type, data, totem_idx, policy_idx)
    """
    move_type, data, totem_idx, policy_idx = move_info
    tactic = None

    if move_type == "troop":
        card, ti = data
        game.play_card(player, card, ti)

    elif move_type == "fog":
        tactic = next(c for c in game.hands[player]
                     if isinstance(c, TacticsCard) and c.name == "fog")
        game.play_environment(player, tactic, totem_idx)

    elif move_type == "mud":
        tactic = next(c for c in game.hands[player]
                     if isinstance(c, TacticsCard) and c.name == "mud")
        game.play_environment(player, tactic, totem_idx)

    elif move_type == "alexander":
        tactic = next(c for c in game.hands[player]
                     if isinstance(c, TacticsCard) and c.name == "alexander")
        game.play_unassigned_wild(player, tactic, totem_idx)

    elif move_type == "darius":
        tactic = next(c for c in game.hands[player]
                     if isinstance(c, TacticsCard) and c.name == "darius")
        game.play_unassigned_wild(player, tactic, totem_idx)

    elif move_type == "wild8":
        tactic = next(c for c in game.hands[player]
                     if isinstance(c, TacticsCard) and c.name == "wild8")
        game.play_unassigned_wild(player, tactic, totem_idx)

    elif move_type == "wild321":
        tactic = next(c for c in game.hands[player]
                     if isinstance(c, TacticsCard) and c.name == "wild321")
        game.play_unassigned_wild(player, tactic, totem_idx)

    elif move_type == "deserter":
        opp_ti, = data
        tactic = next(c for c in game.hands[player]
                     if isinstance(c, TacticsCard) and c.name == "deserter")
        opp = 1 - player
        opp_side = game.totems[opp_ti].sides[opp]
        if opp_side:
            card_to_remove = min(opp_side, key=lambda c: c.value if hasattr(c, 'value') else 0)
            game.play_deserter(player, tactic, opp_ti, card_to_remove)

    elif move_type == "traitor":
        opp_src_ti, my_dst_ti = data
        tactic = next(c for c in game.hands[player]
                     if isinstance(c, TacticsCard) and c.name == "traitor")
        opp = 1 - player
        opp_side = game.totems[opp_src_ti].sides[opp]
        if opp_side:
            # Pick the opponent card that maximizes our destination formation quality
            card_to_steal = _best_card_for_formation(opp_side, game.totems[my_dst_ti].sides[player])
            game.play_traitor(player, tactic, opp_src_ti, card_to_steal, my_dst_ti)

    elif move_type == "redeploy":
        my_src_ti, my_dst_ti = data
        tactic = next(c for c in game.hands[player]
                     if isinstance(c, TacticsCard) and c.name == "redeploy")
        my_side = game.totems[my_src_ti].sides[player]
        if my_side:
            # Pick the card that most improves the destination formation when moved
            card_to_move = _best_card_for_formation(my_side, game.totems[my_dst_ti].sides[player])
            game.play_redeploy(player, tactic, my_src_ti, card_to_move, my_dst_ti)

    elif move_type == "scout":
        tactic = next(c for c in game.hands[player]
                     if isinstance(c, TacticsCard) and c.name == "scout")
        troop_available = min(3, len(game.deck))
        tactics_needed = 3 - troop_available
        tactics_available = min(tactics_needed, len(game.tactics_deck))

        if troop_available + tactics_available >= 3:
            revealed = game.scout_reveal(player, tactic, troop_available, tactics_available)
            # Scout: reveal 3, return 2 (keep 1)
            # Strategy: keep highest-value card, return lowest two
            drawn = [(c, source) for source, c in revealed]
            sorted_by_val = sorted(drawn, key=lambda x: x[0].value if hasattr(x[0], 'value') else 0)
            to_return = sorted_by_val[:2]  # Return 2 lowest-value cards
            returns = [(c, source) for c, source in to_return]
            game.scout_return(player, returns)
        else:
            game.hands[player].remove(tactic)
            game.discarded.append(tactic)
            game.tactics_played[player] += 1


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
    Single-game move selection — used by evaluate_vs_greedy and sample_game.
    Includes both troop plays and tactics. Returns full move_info tuple.
    For bulk game generation use generate_selfplay_dataset which batches
    all active games into one forward pass per round.
    """
    from battleline_features import legal_all_moves

    moves = legal_all_moves(game, player)
    if not moves:
        return None
    with torch.no_grad():
        logits, _ = model(to_tensor(game, player))
    logits = logits.squeeze(0)  # Remove batch dimension if present

    # Get policy logits for legal moves
    policy_idxs = [move[-1] for move in moves]
    lp = np.array([logits[idx].item() for idx in policy_idxs], dtype=np.float64)

    # Sample from policy (with optional temperature + noise)
    lp = np.exp(lp - lp.max())
    if temperature > 1e-6:
        lp = lp ** (1.0 / temperature)
    lp /= lp.sum()
    if noise_eps > 0 and len(moves) > 1:
        noise = np.random.dirichlet([noise_alpha] * len(moves))
        lp = (1 - noise_eps) * lp + noise_eps * noise
        lp /= lp.sum()

    # Pick move
    best_idx = np.argmax(lp)
    return moves[best_idx]


# ── Greedy game generation ────────────────────────────────────────────────────

def _run_greedy_games(n_games: int) -> List[Tuple]:
    """
    Generate training examples from greedy-vs-greedy self-play.

    Uses the hand-crafted greedy AI (ai_choose_move) instead of the neural
    network.  Greedy games are much higher quality than random self-play,
    making them useful for warming up the replay buffer before NN training
    begins.  No model needed — runs fast.
    """
    import sys, os, random
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import numpy as np
    from battleline import BattleLineGame, TacticsCard, ai_choose_move
    from battleline_features import encode, legal_mask, legal_troop_moves, legal_all_moves
    from utils import compute_value, avg_formation_quality, claim_formation_bonus, opponent_claim_penalty

    examples = []
    for game_num in range(n_games):
        if game_num % 10 == 0:
            print(f"  [greedy] game {game_num}/{n_games}...", flush=True)
        game = BattleLineGame(["P0", "P1"])
        game_examples = []

        while game.winner is None:
            player = game.turn % 2

            # With 10% probability draw a tactics card, but only if hand has none already
            # (cap at 1 to prevent ai_choose_move from becoming slow evaluating wilds)
            has_tactic = any(isinstance(c, TacticsCard) for c in game.hands[player])
            if not has_tactic and np.random.random() < 0.10 and len(game.tactics_deck) > 0:
                game.tactics_deck  # draw happens after play below — flag for later
                draw_from_tactics = True
            else:
                draw_from_tactics = False

            # Tactics play logic:
            #   - Non-scout tactics: always play if they immediately claim a flag
            #   - Scout: play with 30% probability (value is card-draw, not flag-winning)
            winning_tactic_moves = []
            scout_moves = []
            if has_tactic and game.can_play_tactics(player):
                import copy as _copy
                all_moves = legal_all_moves(game, player)
                for m in all_moves:
                    if m[0] == "troop":
                        continue
                    if m[0] == "scout":
                        scout_moves.append(m)
                    else:
                        g = _copy.deepcopy(game)
                        claimed_before_sim = {i for i, t in enumerate(g.totems) if t.claimed == player}
                        play_move(g, player, m)
                        claimed_after_sim = {i for i, t in enumerate(g.totems) if t.claimed == player}
                        if len(claimed_after_sim) > len(claimed_before_sim):
                            winning_tactic_moves.append(m)

            tactic_move_to_play = None
            if winning_tactic_moves:
                tactic_move_to_play = random.choice(winning_tactic_moves)
            elif scout_moves and np.random.random() < 0.30:
                tactic_move_to_play = random.choice(scout_moves)

            if tactic_move_to_play is not None:
                move_info = tactic_move_to_play
                features   = encode(game, player)
                mask       = legal_mask(game, player)
                action_idx = move_info[-1]

                opp = 1 - player
                claimed_before     = {i for i, t in enumerate(game.totems) if t.claimed == player}
                opp_claimed_before = {i for i, t in enumerate(game.totems) if t.claimed == opp}
                play_move(game, player, move_info)
                if move_info[0] != "scout":
                    game.draw_card(player, from_tactics=draw_from_tactics)
                game.turn += 1

                newly_claimed     = {i for i, t in enumerate(game.totems)
                                     if t.claimed == player and i not in claimed_before}
                opp_newly_claimed = {i for i, t in enumerate(game.totems)
                                     if t.claimed == opp and i not in opp_claimed_before}
                step_bonus = (avg_formation_quality(game, player)
                              + claim_formation_bonus(game, player, newly_claimed)
                              - opponent_claim_penalty(game, player, opp_newly_claimed))
                game_examples.append((features, mask, action_idx, player, step_bonus))
                continue

            # Normal greedy troop play
            move = ai_choose_move(game, player)
            if move is None or move[0] != "card":
                troop_moves = legal_troop_moves(game, player)
                if not troop_moves:
                    break
                best = max(troop_moves, key=lambda m: m[0].value)
                move = ("card", best[0], best[1])

            _, card, ti = move
            features = encode(game, player)
            mask     = legal_mask(game, player)

            action_idx = next(
                (idx for c, t, idx in legal_troop_moves(game, player)
                 if c.suit == card.suit and c.value == card.value and t == ti),
                None,
            )
            if action_idx is None:
                break

            opp = 1 - player
            claimed_before     = {i for i, t in enumerate(game.totems) if t.claimed == player}
            opp_claimed_before = {i for i, t in enumerate(game.totems) if t.claimed == opp}
            game.play_card(player, card, ti)

            game.draw_card(player, from_tactics=draw_from_tactics)
            game.turn += 1

            newly_claimed     = {i for i, t in enumerate(game.totems)
                                  if t.claimed == player and i not in claimed_before}
            opp_newly_claimed = {i for i, t in enumerate(game.totems)
                                  if t.claimed == opp and i not in opp_claimed_before}
            step_bonus = (avg_formation_quality(game, player)
                          + claim_formation_bonus(game, player, newly_claimed)
                          - opponent_claim_penalty(game, player, opp_newly_claimed))
            game_examples.append((features, mask, action_idx, player, step_bonus))

        winner = game.winner
        if winner is None:
            p0 = sum(1 for t in game.totems if t.claimed == 0)
            p1 = sum(1 for t in game.totems if t.claimed == 1)
            winner = 0 if p0 >= p1 else 1

        game_len = game.turn
        for features, mask, action_idx, sample_player, step_bonus in game_examples:
            value = compute_value(winner, sample_player, game.totems, step_bonus, game_len)
            examples.append((features, mask, action_idx, value))

    return examples


def generate_greedy_dataset(n_games: int) -> List[Tuple]:
    """Run greedy game generation in parallel across CPU cores."""
    n_workers = min(mp.cpu_count(), n_games)
    base, rem = divmod(n_games, n_workers)
    split     = [base + (1 if i < rem else 0) for i in range(n_workers)]
    ctx       = mp.get_context("spawn")
    with ctx.Pool(n_workers) as pool:
        results = pool.map(_run_greedy_games, split)
    return [ex for batch in results for ex in batch]


# ── Self-play data generation ──────────────────────────────────────────────────

def _run_games(args: tuple) -> List[Tuple]:
    """
    Worker for multiprocessing game generation.

    Move selection uses top-K policy filtering + value-guided selection:
      1. Apply Dirichlet noise + temperature to get a noisy policy distribution.
      2. Take the top_k moves by noisy policy score as candidates.
      3. Simulate each candidate move on a game copy and evaluate the resulting
         position with the value head (batched into one forward pass).
      4. Play the candidate with the highest value estimate.

    This breaks the self-play echo chamber: pure policy sampling trains the
    network to imitate its own (bad) moves.  Selecting among top_k candidates
    by value means even a mediocre value head guides self-play toward better
    positions, and better games produce better training signal.
    """
    state_dict, n_games, temperature, noise_eps, noise_alpha, hidden_dim, n_blocks, top_k = args

    import sys, os, copy
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import torch
    import numpy as np
    from battleline import BattleLineGame, TacticsCard, SUITS
    from battleline_features import BattleLineNet, POLICY_DIM, encode, legal_mask, legal_all_moves, legal_draw_moves, to_tensor
    from utils import compute_value, avg_formation_quality, claim_formation_bonus, opponent_claim_penalty, tactics_draw_penalty

    model = BattleLineNet(hidden_dim=hidden_dim, n_blocks=n_blocks)
    model.load_state_dict(state_dict)
    model.eval()

    # Track tactics usage for debugging
    tactics_played_total = 0
    tactics_drawn_total = 0

    # Use module-level play_move (no draw_card calls — draw handled separately below)

    def pick_move_draw(game, player, moves):
        """
        Pick a draw move. Since there are only 2 options (troop vs tactics),
        just use policy logits without value simulation.

        If troop deck is empty, force tactics draw (if available).

        Bias: ~85% explore troop, ~15% explore tactics. This gives the model
        occasional exposure to tactics without over-drawing them early.
        """
        if len(moves) == 1:
            return moves[0]

        # Force tactics draw if troop deck is empty
        if len(game.deck) == 0:
            for move_info in moves:
                if move_info[2] == "tactics":  # draw_source is at index 2
                    return move_info
            # If no tactics move available either, take what we have
            return moves[0]

        with torch.no_grad():
            logits, _ = model(to_tensor(game, player))
        logits = logits.squeeze(0)

        # Pick draw move with highest policy logit + biased noise
        policy_idxs = [move[-1] for move in moves]
        lp = np.array([logits[idx].item() for idx in policy_idxs], dtype=np.float64)

        # Pick draw move with strong bias toward troop (95% troop, 5% tactics)
        # Minimal tactics exploration since they're rarely played anyway
        if len(moves) > 1:
            lp = np.exp(lp - lp.max())
            # With 5% probability, occasionally explore tactics draws
            if noise_eps > 0 and np.random.random() < 0.05:
                # Occasionally explore tactics draws
                best = 1  # Index 1 is tactics draw
            else:
                # Default to policy (which should learn to prefer troop draws early)
                best = np.argmax(lp)
        else:
            best = int(np.argmax(lp))

        return moves[best]

    def pick_move(game, player, moves):
        """Select a move via top-k policy + 2-ply minimax value.

        1. Select top-K candidates by noisy policy.
        2. Simulate each candidate + troop draw.
        3. Batch-evaluate opponent's policy on all K resulting states.
        4. For each, simulate opponent's greedy best response + draw.
        5. Batch-evaluate final states from our perspective; pick best.
        """
        opp = 1 - player

        with torch.no_grad():
            logits, _ = model(to_tensor(game, player))
        logits = logits.squeeze(0)

        policy_idxs = [move[-1] for move in moves]
        lp = np.array([logits[idx].item() for idx in policy_idxs], dtype=np.float64)
        lp = np.exp(lp - lp.max())
        if temperature > 1e-6:
            lp = lp ** (1.0 / temperature)
        lp /= lp.sum()
        if noise_eps > 0 and len(moves) > 1:
            noise = np.random.dirichlet([noise_alpha] * len(moves))
            lp = (1 - noise_eps) * lp + noise_eps * noise
            lp /= lp.sum()

        k = min(top_k, len(moves))
        top_indices = np.argpartition(lp, -k)[-k:]
        candidates  = [moves[i] for i in top_indices]

        if k == 1:
            return candidates[0]

        # Step 1: simulate our top-K moves + draw.
        after_our_move = []
        for move_info in candidates:
            g = copy.deepcopy(game)
            play_move(g, player, move_info)
            if move_info[0] != "scout":
                g.draw_card(player)
            g.turn += 1
            after_our_move.append(g)

        # Step 2: batch-evaluate opponent's policy on all K states.
        opp_encoded = [encode(g, opp) for g in after_our_move]
        opp_batch   = torch.tensor(opp_encoded, dtype=torch.float32)
        with torch.no_grad():
            opp_logits_batch, _ = model(opp_batch)   # (K, POLICY_DIM)

        # Step 3: simulate opponent's greedy best response + draw.
        after_opp_move = []
        for i, g in enumerate(after_our_move):
            if g.winner is None:
                opp_moves = legal_all_moves(g, opp)
                if opp_moves:
                    opp_lp = opp_logits_batch[i]
                    best_opp = opp_moves[int(
                        np.argmax([opp_lp[m[-1]].item() for m in opp_moves])
                    )]
                    play_move(g, opp, best_opp)
                    if best_opp[0] != "scout":
                        g.draw_card(opp)
                    g.turn += 1
            after_opp_move.append(g)

        # Step 4: batch-evaluate final states from our perspective.
        final_encoded = [encode(g, player) for g in after_opp_move]
        feat_batch    = torch.tensor(final_encoded, dtype=torch.float32)
        with torch.no_grad():
            _, values = model(feat_batch)

        best = int(values.flatten().argmax().item())
        return candidates[best]

    examples = []
    for _ in range(n_games):
        game = BattleLineGame(["P0", "P1"])
        game_examples = []

        while game.winner is None:
            player = game.turn % 2

            # 1. Play a card
            play_moves = legal_all_moves(game, player)
            if not play_moves:
                break

            play_features = encode(game, player)
            play_mask     = legal_mask(game, player)
            play_move_info = pick_move(game, player, play_moves)
            play_type, play_data, totem_idx, play_action_idx = play_move_info

            opp = 1 - player
            claimed_before     = {i for i, t in enumerate(game.totems) if t.claimed == player}
            opp_claimed_before = {i for i, t in enumerate(game.totems) if t.claimed == opp}
            play_move(game, player, play_move_info)

            # Track if a tactic was played
            if play_type != "troop":
                tactics_played_total += 1

            newly_claimed     = {i for i, t in enumerate(game.totems)
                                  if t.claimed == player and i not in claimed_before}
            opp_newly_claimed = {i for i, t in enumerate(game.totems)
                                  if t.claimed == opp and i not in opp_claimed_before}
            step_bonus = (avg_formation_quality(game, player)
                          + claim_formation_bonus(game, player, newly_claimed)
                          - opponent_claim_penalty(game, player, opp_newly_claimed))

            # Capture play decision example (value will be set later)
            game_examples.append((play_features, play_mask, play_action_idx, player, step_bonus))

            # 2. Choose draw source and draw
            # Scout already draws internally (reveal 3, return 2), so skip the normal draw
            if play_type != "scout":
                draw_moves = legal_draw_moves(game, player)
                draw_features = encode(game, player)  # Features after play but before draw
                draw_mask = [0] * POLICY_DIM
                for _, _, _, draw_action_idx in draw_moves:
                    draw_mask[draw_action_idx] = 1

                draw_move_info = pick_move_draw(game, player, draw_moves)
                _, _, draw_source, draw_action_idx = draw_move_info

                tactics_in_hand = sum(1 for c in game.hands[player] if isinstance(c, TacticsCard))
                tactics_locked  = game.tactics_played[player] > game.tactics_played[1 - player]
                if draw_source == "tactics":
                    game.draw_card(player, from_tactics=True)
                    tactics_drawn_total += 1
                    draw_step_bonus = tactics_draw_penalty(tactics_in_hand, tactics_locked)
                else:
                    game.draw_card(player, from_tactics=False)
                    draw_step_bonus = 0.0

                game_examples.append((draw_features, draw_mask, draw_action_idx, player, draw_step_bonus))

            game.turn += 1

        winner = game.winner
        if winner is None:
            p0 = sum(1 for t in game.totems if t.claimed == 0)
            p1 = sum(1 for t in game.totems if t.claimed == 1)
            winner = 0 if p0 >= p1 else 1

        game_len = game.turn
        for features, mask, action_idx, sample_player, step_bonus in game_examples:
            value = compute_value(winner, sample_player, game.totems, step_bonus, game_len)
            examples.append((features, mask, action_idx, value))

    # Debug: print tactics usage stats
    if n_games > 0:
        print(f"  [Worker] Tactics: {tactics_played_total} played, {tactics_drawn_total} drawn across {n_games} games", flush=True)

    return examples


def generate_selfplay_dataset(
    n_games:     int,
    model,
    temperature: float = 1.0,
    noise_eps:   float = 0.25,
    device:      str   = "cpu",
    hidden_dim:  int   = 128,
    n_blocks:    int   = 3,
    noise_alpha: float = 0.3,
    top_k:       int   = 5,
) -> List[Tuple]:
    n_workers = min(mp.cpu_count(), n_games)
    base, rem = divmod(n_games, n_workers)
    split = [base + (1 if i < rem else 0) for i in range(n_workers)]
    state_dict = {k: v.cpu() for k, v in model.state_dict().items()}
    worker_args = [
        (state_dict, g, temperature, noise_eps, noise_alpha, hidden_dim, n_blocks, top_k)
        for g in split
    ]
    ctx = mp.get_context("spawn")
    with ctx.Pool(n_workers) as pool:
        results = pool.map(_run_games, worker_args)
    return [ex for batch in results for ex in batch]


# ── Sample game saving ────────────────────────────────────────────────────────

def _state_snapshot(game: BattleLineGame, pov: int) -> dict:
    s = game_view(game, pov)
    s["clock"]         = None
    s["rated"]         = False
    s["category"]      = None
    s["rating_change"] = None
    return s


def sample_game(model, iteration: int) -> None:
    """Play one sample game, capture full state sequence, and save for replay."""
    from battleline_features import legal_troop_moves, legal_draw_moves

    model.eval()
    game  = BattleLineGame(["Model-P0", "Model-P1"])
    moves = []

    states_p0 = [_state_snapshot(game, 0)]
    states_p1 = [_state_snapshot(game, 1)]

    while game.winner is None:
        player = game.turn % 2

        # Use all legal moves (troops + tactics) to match self-play behavior
        from battleline_features import legal_all_moves

        all_moves = legal_all_moves(game, player)
        if not all_moves:
            break

        # Pick best move by policy
        with torch.no_grad():
            logits, _ = model(to_tensor(game, player))
        logits = logits.squeeze(0)

        policy_idxs = [move[-1] for move in all_moves]
        lp = np.array([logits[idx].item() for idx in policy_idxs], dtype=np.float64)
        lp = np.exp(lp - lp.max())
        lp /= lp.sum()
        best_idx = np.argmax(lp)

        move_info = all_moves[best_idx]
        play_move(game, player, move_info)

        # Only record troop moves in moves list (for save_game compatibility)
        move_type, move_data, _, _ = move_info
        if move_type == "troop":
            card, ti = move_data
            moves.append((player, card, ti))

        # Choose draw source (greedy value-based)
        draw_moves = legal_draw_moves(game, player)
        if draw_moves:
            with torch.no_grad():
                logits, _ = model(to_tensor(game, player))
            logits = logits.squeeze(0)

            # Evaluate both draw options and pick the one with highest value
            best_draw_move = None
            best_value = float('-inf')
            for move_info in draw_moves:
                g = copy.deepcopy(game)
                _, _, draw_source, _ = move_info
                g.draw_card(player, from_tactics=(draw_source == "tactics"))
                g.turn += 1
                with torch.no_grad():
                    _, value = model(to_tensor(g, player))
                value = value.item()
                if value > best_value:
                    best_value = value
                    best_draw_move = move_info

            # Execute best draw move
            if best_draw_move:
                _, _, draw_source, _ = best_draw_move
                game.draw_card(player, from_tactics=(draw_source == "tactics"))
        else:
            game.draw_card(player)  # Fallback

        game.turn += 1
        states_p0.append(_state_snapshot(game, 0))
        states_p1.append(_state_snapshot(game, 1))

    winner = game.winner
    if winner is None:
        p0 = sum(1 for t in game.totems if t.claimed == 0)
        p1 = sum(1 for t in game.totems if t.claimed == 1)
        winner = 0 if p0 > p1 else (1 if p1 > p0 else None)

    filename = f"selfplay_iter_{iteration:04d}.json"
    path = save_game(game, moves, winner, filename, states={"p0": states_p0, "p1": states_p1}, human=False)
    print(f"Sample game saved → {path}  ({len(moves)} moves)")


# ── Evaluation ─────────────────────────────────────────────────────────────────

def evaluate_models(new_model, old_model, n_games: int = 50) -> float:
    """
    Play n_games between new_model and old_model (greedy, no exploration).
    Returns new_model's win rate. Alternates sides to remove first-move bias.

    Kept as an alternative to evaluate_vs_greedy — useful if you want to
    switch back to direct model-vs-model promotion.
    """
    new_model.eval()
    old_model.eval()
    new_wins = 0

    from battleline_features import legal_draw_moves

    for i in range(n_games):
        game      = BattleLineGame(["New", "Old"])
        new_is_p0 = (i % 2 == 0)

        while game.winner is None:
            player = game.turn % 2
            model  = new_model if ((player == 0) == new_is_p0) else old_model

            # 1. Get move (troop or tactic)
            move_info = nn_choose_move(game, player, model, temperature=0.0)
            if move_info is None:
                break

            # 2. Play move (supports all move types)
            play_move(game, player, move_info)

            # 3. Draw (force 5% exploration of tactics, else use value head)
            # Note: tactics are drawn but rarely played; full tactical play requires
            # additional training signals (formation bonuses, or warm-start tactical games)
            draw_moves = legal_draw_moves(game, player)
            if draw_moves:
                # Force 5% of draws to be from tactics (minimal exploration)
                if np.random.random() < 0.05 and len(draw_moves) > 1:
                    # Force tactics draw
                    for move in draw_moves:
                        if move[2] == "tactics":
                            game.draw_card(player, from_tactics=True)
                            break
                else:
                    # Otherwise, use value head to pick best draw source
                    with torch.no_grad():
                        logits, _ = model(to_tensor(game, player))
                    logits = logits.squeeze(0)

                    best_draw = None
                    best_value = float('-inf')
                    for draw_move in draw_moves:
                        g = copy.deepcopy(game)
                        _, _, draw_source, _ = draw_move
                        g.draw_card(player, from_tactics=(draw_source == "tactics"))
                        g.turn += 1
                        with torch.no_grad():
                            _, value = model(to_tensor(g, player))
                        if value.item() > best_value:
                            best_value = value.item()
                            best_draw = draw_move

                    if best_draw:
                        _, _, draw_source, _ = best_draw
                        game.draw_card(player, from_tactics=(draw_source == "tactics"))
            else:
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


def evaluate_vs_greedy(model, n_games: int = 100) -> float:
    """
    Measure a model's win rate against the greedy AI over n_games.

    Using a fixed external reference (greedy) rather than comparing models
    against each other avoids the echo-chamber problem where two mediocre
    models flip-flop at ~52% and the system thinks it's making progress.
    A model that beats greedy more often is objectively better at the game.

    Alternates sides to remove first-move bias.
    """
    from battleline import ai_choose_move

    model.eval()
    wins = 0

    for i in range(n_games):
        game        = BattleLineGame(["NN", "Greedy"])
        nn_is_p0    = (i % 2 == 0)

        while game.winner is None:
            player    = game.turn % 2
            nn_turn   = (player == 0) == nn_is_p0

            if nn_turn:
                move = nn_choose_move(game, player, model, temperature=0.0)
                if move is None:
                    break
                card, ti, _ = move
            else:
                greedy = ai_choose_move(game, player)
                if greedy is None or greedy[0] != "card":
                    break
                _, card, ti = greedy

            game.play_card(player, card, ti)
            game.draw_card(player)
            game.turn += 1

        winner = game.winner
        if winner is None:
            p0 = sum(1 for t in game.totems if t.claimed == 0)
            p1 = sum(1 for t in game.totems if t.claimed == 1)
            winner = 0 if p0 > p1 else (1 if p1 > p0 else None)

        if winner is not None:
            nn_player = 0 if nn_is_p0 else 1
            if winner == nn_player:
                wins += 1

    return wins / n_games


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
    parser.add_argument("--epochs",            type=int,   default=5,    help="Training epochs per iteration. Keep low to avoid catastrophic forgetting of incumbent weights.")
    parser.add_argument("--batch-size",        type=int,   default=64)
    parser.add_argument("--lr",                type=float, default=3e-4)
    parser.add_argument("--value-weight",      type=float, default=10.0)
    parser.add_argument("--temperature",       type=float, default=0.5,  help="Move sampling temperature during self-play.")
    parser.add_argument("--noise-eps",         type=float, default=0.15, help="Dirichlet noise fraction mixed into policy during self-play (0 = off).")
    parser.add_argument("--noise-alpha",       type=float, default=0.3,  help="Dirichlet alpha — lower = more extreme noise.")
    parser.add_argument("--buffer-iters",      type=int,   default=10,   help="Keep examples from this many past iterations in the replay buffer.")
    parser.add_argument("--eval-games",        type=int,   default=50,   help="Games to evaluate new vs old model.")
    parser.add_argument("--promote-threshold", type=float, default=0.55, help="Win rate required to promote candidate.")
    parser.add_argument("--step-weight",       type=float, default=0.35, help="Weight of per-move formation/claim bonus in value target.")
    parser.add_argument("--hidden-dim",        type=int,   default=128,  help="Hidden layer size. Smaller = faster training on limited data.")
    parser.add_argument("--n-blocks",          type=int,   default=3,    help="Number of residual blocks.")
    parser.add_argument("--top-k",             type=int,   default=5,    help="Policy top-K: evaluate this many policy-candidate moves with the value head and pick the best.")
    parser.add_argument("--checkpoint-dir",    type=str,   default=os.path.join(os.path.dirname(__file__), "checkpoints"))
    parser.add_argument("--device",            type=str,   default="cpu")
    parser.add_argument("--fresh",             action="store_true", help="Ignore existing model and start from scratch.")
    parser.add_argument("--include-human",     action="store_true", help="Include manually-created games from saved_games/ in the replay buffer.")
    parser.add_argument("--greedy-games",      type=int, default=0, help="Generate this many greedy-vs-greedy games and add to the replay buffer as a warm-start.")
    args = parser.parse_args()

    os.makedirs(args.checkpoint_dir, exist_ok=True)

    # Load or initialise model.
    # Track whether we started truly fresh so we know whether iteration 1
    # has a valid baseline to evaluate against.
    model = BattleLineNet(hidden_dim=args.hidden_dim, n_blocks=args.n_blocks)
    started_fresh = args.fresh or not os.path.exists(_MODEL_PATH)
    if not started_fresh:
        checkpoint = torch.load(_MODEL_PATH, weights_only=True)
        if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
            model.load_state_dict(checkpoint["state_dict"])
        else:
            model.load_state_dict(checkpoint)
        print(f"Loaded existing model from {_MODEL_PATH}")
    else:
        print("Starting with fresh model.")
    print(f"Parameters: {sum(p.numel() for p in model.parameters()):,}\n")

    win_history: List[float] = []

    # Load human games if requested.
    # High-quality manually-created games help bootstrap the model and prevent
    # it from getting stuck in a self-play echo chamber early on. These are
    # treated as one "pseudo-iteration" in the replay buffer.
    human_examples: List[Tuple] = []
    if args.include_human:
        print("Loading human games from saved_games/...")
        human_examples = load_human_games()
        print(f"Loaded {len(human_examples)} examples from human games.\n")

    # Replay buffer: stores example batches from recent iterations.
    # Training on a mix of old and new data prevents the model from
    # memorising a single batch (which caused value loss → 0.02 quickly
    # without any real improvement in play quality — the echo chamber problem).
    # We keep the last `buffer_iters` iterations rather than a fixed example
    # count so the buffer naturally scales with --games.
    replay_buffer: List[List] = []

    # Anchor pool: high-quality examples that are ALWAYS included in every
    # training batch regardless of how many self-play iterations have passed.
    # Unlike the rolling buffer, the anchor is never evicted.
    # Human games and greedy games go here — not into the rolling buffer —
    # so they permanently anchor the training signal and prevent the model
    # from drifting as self-play data accumulates.
    anchor_examples: List[Tuple] = []
    if human_examples:
        anchor_examples.extend(human_examples)
        print(f"Anchor: {len(human_examples)} human game examples.")

    if args.greedy_games > 0:
        print(f"Generating {args.greedy_games} greedy anchor games...")
        greedy_examples = generate_greedy_dataset(args.greedy_games)
        anchor_examples.extend(greedy_examples)
        print(f"Anchor: added {len(greedy_examples)} greedy examples "
              f"({len(anchor_examples)} total anchor).\n")

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
            args.games, model, args.temperature, args.noise_eps,
            args.device, args.hidden_dim, args.n_blocks, args.noise_alpha,
            args.top_k,
        )
        print(f"Generated {len(new_examples)} new examples.")

        # 2. Update replay buffer.
        # Pop the oldest iteration batch when the buffer is full so we never
        # train on data from more than `buffer_iters` iterations ago.
        replay_buffer.append(new_examples)
        if len(replay_buffer) > args.buffer_iters:
            replay_buffer.pop(0)

        # Combine anchor (always-present) + rolling buffer for training.
        all_examples = list(anchor_examples) + [ex for batch in replay_buffer for ex in batch]
        random.shuffle(all_examples)
        print(f"Training on {len(all_examples)} examples "
              f"({len(anchor_examples)} anchor + "
              f"{len(all_examples) - len(anchor_examples)} buffer "
              f"[{len(replay_buffer)}/{args.buffer_iters} iters]).")

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
            print(f"Evaluating candidate vs current ({args.eval_games} games)...")
            win_rate = evaluate_models(candidate, model, args.eval_games)
            win_history.append(win_rate)
            print(f"  Candidate vs current: {win_rate:.1%}  (threshold {args.promote_threshold:.1%})")

        # 5. Promote or discard.
        if win_rate >= args.promote_threshold:
            model = candidate
            _checkpoint = {"state_dict": model.state_dict(),
                           "hidden_dim": args.hidden_dim, "n_blocks": args.n_blocks}
            torch.save(_checkpoint, _MODEL_PATH)
            ckpt = os.path.join(args.checkpoint_dir, f"iter_{iteration:04d}.pt")
            torch.save(_checkpoint, ckpt)
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
