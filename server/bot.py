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
        if not os.path.exists(MODEL_PATH):
            print(f"[bot] No model found at {MODEL_PATH}")
            return None
        m = BattleLineNet()
        m.load_state_dict(torch.load(MODEL_PATH, weights_only=True, map_location="cpu"))
        m.eval()
        _model = m
        print(f"[bot] Model loaded from {MODEL_PATH}")
    except Exception as e:
        print(f"[bot] Failed to load model: {e}")
    return _model


def choose_move(game, player: int):
    """Return (card, totem_idx, policy_idx) for the AI's move, or None."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from training.battleline_features import legal_troop_moves, to_tensor

    moves = legal_troop_moves(game, player)
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

    return max(moves, key=lambda m: logits[m[2]].item())
