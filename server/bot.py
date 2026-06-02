"""Neural network bot for online play."""

import os
import sys

_model = None
_tried_load = False

MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "training", "battleline_model.pt",
)


def load_model():
    global _model, _tried_load
    if _tried_load:
        return _model
    _tried_load = True
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        import torch
        from training.battleline_features import BattleLineNet
        print(f"[bot] Looking for model at: {MODEL_PATH}")
        if not os.path.exists(MODEL_PATH):
            print(f"[bot] No model found at {MODEL_PATH}")
            return None
        print(f"[bot] Model file found, loading...")
        checkpoint = torch.load(MODEL_PATH, weights_only=True, map_location="cpu")
        # Support both new format {state_dict, hidden_dim, n_blocks} and legacy state_dict-only
        if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
            hidden_dim = checkpoint.get("hidden_dim", 128)
            n_blocks   = checkpoint.get("n_blocks", 3)
            state_dict = checkpoint["state_dict"]
        else:
            hidden_dim, n_blocks, state_dict = 128, 3, checkpoint
        m = BattleLineNet(hidden_dim=hidden_dim, n_blocks=n_blocks)
        m.load_state_dict(state_dict)
        m.eval()
        _model = m
        print(f"[bot] Model loaded (hidden_dim={hidden_dim}, n_blocks={n_blocks})")
    except Exception as e:
        print(f"[bot] Failed to load model: {e}")
    return _model


def _best_card_for_formation(candidates: list, current_formation: list):
    """Return the card from candidates that maximizes formation quality when added to current_formation."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from training.battleline_features import _formation_cards, _best_consistent_type
    _SCORES = {1: 0.0, 2: 0.10, 3: 0.30, 4: 0.65, 5: 1.0}

    def score(cards):
        fc = _formation_cards(cards)
        return _SCORES.get(_best_consistent_type(fc), 0.0) if fc else 0.0

    best_card, best_score = candidates[0], -1.0
    for c in candidates:
        s = score(current_formation + [c])
        if s > best_score:
            best_score, best_card = s, c
    return best_card


def execute_move(game, player: int, move_info: tuple) -> None:
    """
    Execute a move_info tuple (move_type, data, totem_idx, policy_idx) on game.
    Handles all tactic types. Does NOT draw — caller is responsible for the draw.
    """
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from battleline import TacticsCard

    move_type, data, totem_idx, _ = move_info

    if move_type == "troop":
        card, ti = data
        game.play_card(player, card, ti)

    elif move_type == "fog":
        tactic = next(c for c in game.hands[player] if isinstance(c, TacticsCard) and c.name == "fog")
        game.play_environment(player, tactic, totem_idx)

    elif move_type == "mud":
        tactic = next(c for c in game.hands[player] if isinstance(c, TacticsCard) and c.name == "mud")
        game.play_environment(player, tactic, totem_idx)

    elif move_type == "alexander":
        tactic = next(c for c in game.hands[player] if isinstance(c, TacticsCard) and c.name == "alexander")
        game.play_unassigned_wild(player, tactic, totem_idx)

    elif move_type == "darius":
        tactic = next(c for c in game.hands[player] if isinstance(c, TacticsCard) and c.name == "darius")
        game.play_unassigned_wild(player, tactic, totem_idx)

    elif move_type == "wild8":
        tactic = next(c for c in game.hands[player] if isinstance(c, TacticsCard) and c.name == "wild8")
        game.play_unassigned_wild(player, tactic, totem_idx)

    elif move_type == "wild321":
        tactic = next(c for c in game.hands[player] if isinstance(c, TacticsCard) and c.name == "wild321")
        game.play_unassigned_wild(player, tactic, totem_idx)

    elif move_type == "deserter":
        opp_ti, = data
        tactic = next(c for c in game.hands[player] if isinstance(c, TacticsCard) and c.name == "deserter")
        opp_side = game.totems[opp_ti].sides[1 - player]
        if opp_side:
            card_to_remove = min(opp_side, key=lambda c: c.value if hasattr(c, "value") else 0)
            game.play_deserter(player, tactic, opp_ti, card_to_remove)

    elif move_type == "traitor":
        opp_src_ti, my_dst_ti = data
        tactic = next(c for c in game.hands[player] if isinstance(c, TacticsCard) and c.name == "traitor")
        opp_side = game.totems[opp_src_ti].sides[1 - player]
        if opp_side:
            card_to_steal = _best_card_for_formation(opp_side, game.totems[my_dst_ti].sides[player])
            game.play_traitor(player, tactic, opp_src_ti, card_to_steal, my_dst_ti)

    elif move_type == "redeploy":
        my_src_ti, my_dst_ti = data
        tactic = next(c for c in game.hands[player] if isinstance(c, TacticsCard) and c.name == "redeploy")
        my_side = game.totems[my_src_ti].sides[player]
        if my_side:
            card_to_move = _best_card_for_formation(my_side, game.totems[my_dst_ti].sides[player])
            game.play_redeploy(player, tactic, my_src_ti, card_to_move, my_dst_ti)

    elif move_type == "scout":
        tactic = next(c for c in game.hands[player] if isinstance(c, TacticsCard) and c.name == "scout")
        troop_available   = min(3, len(game.deck))
        tactics_available = min(3 - troop_available, len(game.tactics_deck))
        if troop_available + tactics_available >= 3:
            revealed = game.scout_reveal(player, tactic, troop_available, tactics_available)
            drawn = [(c, source) for source, c in revealed]
            sorted_by_val = sorted(drawn, key=lambda x: x[0].value if hasattr(x[0], "value") else 0)
            game.scout_return(player, [(c, src) for c, src in sorted_by_val[:2]])
        else:
            game.hands[player].remove(tactic)
            game.discarded.append(tactic)
            game.tactics_played[player] += 1


def choose_move(game, player: int):
    """
    Return move_info tuple (move_type, data, totem_idx, policy_idx) for the AI's move,
    or None if no legal moves exist.  Falls back to random if model is unavailable.
    """
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from training.battleline_features import legal_all_moves, to_tensor

    moves = legal_all_moves(game, player)
    if not moves:
        return None

    model = load_model()
    if model is None:
        import random
        return random.choice(moves)

    import torch
    with torch.no_grad():
        logits, _ = model(to_tensor(game, player))
    logits = logits.squeeze(0)

    return max(moves, key=lambda m: logits[m[-1]].item())
