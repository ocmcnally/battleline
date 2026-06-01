"""Shared training utilities."""

from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from battleline_features import _formation_cards, _best_consistent_type


# ── Formation helpers ──────────────────────────────────────────────────────────

def _form_score(cards: list) -> float:
    """
    Map a list of formation cards to a [0, 1] quality score.

    Non-linear scale that creates a large reward gap at 3-of-a-kind and
    straight flush specifically — the formations the model was failing to
    pursue with the original linear scale (equal 0.25 gaps between all tiers).

    Linear (old):  HighSum=0.00  Straight=0.25  Flush=0.50  3OAK=0.75  SF=1.00
    Non-linear:    HighSum=0.00  Straight=0.05  Flush=0.15  3OAK=0.65  SF=1.00
    """
    if not cards:
        return 0.0
    t = _best_consistent_type(cards)
    return {1: 0.0, 2: 0.05, 3: 0.15, 4: 0.65, 5: 1.0}.get(t, 0.0)


def avg_formation_quality(game, player: int) -> float:
    """
    Average formation potential across unclaimed totem sides that have at
    least one card played.  Only unclaimed totems count — claimed ones are
    already captured by the totem-margin signal.
    """
    scores = []
    for totem in game.totems:
        if totem.claimed is not None:
            continue
        fc = _formation_cards(totem.sides[player])
        if fc:
            scores.append(_form_score(fc))
    return sum(scores) / len(scores) if scores else 0.0


def claim_formation_bonus(game, player: int, newly_claimed: set) -> float:
    """
    Reward for flags claimed on this move, weighted by the formation type
    used to claim each one.  A straight-flush claim scores 1.0; a high-sum
    claim scores 0.0.  Encourages finishing strong formations, not just any
    formation.
    """
    bonus = 0.0
    for i in newly_claimed:
        fc = _formation_cards(game.totems[i].sides[player])
        bonus += _form_score(fc)
    return bonus


# ── Value computation ──────────────────────────────────────────────────────────

def compute_value(
    winner:       int | None,
    player:       int,
    final_totems: list,
    step_bonus:   float = 0.0,
    outcome_w:    float = 0.50,
    margin_w:     float = 0.15,
    step_w:       float = 0.35,
) -> float:
    """
    Shaped value target blending four signals:

      outcome   — did this player win? (+1 / 0 / −1)
      margin    — (my_totems − opp_totems) / 9  — partial credit for claims
      step_bonus — per-move formation quality + claim bonus (avg_formation_quality
                   + claim_formation_bonus computed during game generation)

    Default weights sum to 1.0: outcome=0.50, margin=0.15, step=0.35.
    The step component dominates early training when the network needs dense
    signal; outcome remains the primary long-run objective.
    """
    outcome = 0.0 if winner is None else (1.0 if winner == player else -1.0)
    t_me    = sum(1 for t in final_totems if t.claimed == player)
    t_opp   = sum(1 for t in final_totems if t.claimed == (1 - player))
    margin  = (t_me - t_opp) / 9.0
    return outcome_w * outcome + margin_w * margin + step_w * step_bonus
