"""Shared training utilities."""

from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def compute_value(
    winner:         int | None,
    player:         int,
    totems:         list,
    outcome_weight: float = 0.7,
) -> float:
    """
    Shaped value target for a training example.

    Blends the binary game outcome with the totem margin so that claiming
    flags in a losing game is still rewarded slightly, and winning by more
    totems produces a stronger positive signal than a narrow win.

    outcome_weight=1.0  →  pure win/loss (original behaviour)
    outcome_weight=0.0  →  pure totem differential
    """
    outcome = 0.0 if winner is None else (1.0 if winner == player else -1.0)
    t_me    = sum(1 for t in totems if t.claimed == player)
    t_opp   = sum(1 for t in totems if t.claimed == (1 - player))
    margin  = (t_me - t_opp) / 9.0          # normalised to [-1, 1]
    return outcome_weight * outcome + (1.0 - outcome_weight) * margin
