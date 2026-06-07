"""Shared training utilities."""

from __future__ import annotations
import sys, os
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))  # project root (for battleline.py etc.)
sys.path.insert(0, _HERE)                   # training/ (for battleline_features.py)

from battleline_features import _formation_cards, _best_consistent_type


# ── Formation helpers ──────────────────────────────────────────────────────────

def _form_score(cards: list) -> float:
    """
    Map a list of formation cards to a [0, 1] quality score.

    Non-linear scale that creates a large reward gap at 3-of-a-kind and
    straight flush specifically — the formations the model was failing to
    pursue with the original linear scale (equal 0.25 gaps between all tiers).

    Linear (old):  HighSum=0.00  Straight=0.25  Flush=0.50  3OAK=0.75  SF=1.00
    Non-linear:    HighSum=0.00  Straight=0.05  Flush=0.15  3OAK=0.80  SF=2.00
    SF is doubled relative to 3OAK to push the model toward holding SF-capable cards.
    """
    if not cards:
        return 0.0
    t = _best_consistent_type(cards)
    return {1: 0.0, 2: 0.10, 3: 0.30, 4: 0.80, 5: 2.0}.get(t, 0.0)


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


# Separate score table for claim bonuses — identical to _form_score except SF
# gets a small extra bump (1.2 vs 1.0) to push the model toward finishing
# straight flushes rather than settling for 3OAK or flush.
_CLAIM_SCORES = {1: 0.0, 2: 0.10, 3: 0.30, 4: 1.0, 5: 3.0}

def claim_formation_bonus(game, player: int, newly_claimed: set) -> float:
    """
    Reward for flags claimed on this move, weighted by the formation type
    used to claim each one.
    """
    bonus = 0.0
    for i in newly_claimed:
        fc = _formation_cards(game.totems[i].sides[player])
        t  = _best_consistent_type(fc)
        bonus += _CLAIM_SCORES.get(t, 0.0)
    return bonus


def opponent_claim_penalty(game, player: int, opp_newly_claimed: set) -> float:
    """
    Penalty for flags claimed by the opponent on this move, weighted by their
    formation type.  Mirrors claim_formation_bonus to give the model an
    immediate negative signal when a move gifts the opponent a flag.
    """
    opp = 1 - player
    penalty = 0.0
    for i in opp_newly_claimed:
        fc = _formation_cards(game.totems[i].sides[opp])
        t  = _best_consistent_type(fc)
        penalty += _CLAIM_SCORES.get(t, 0.0)
    return penalty


# ── Value computation ──────────────────────────────────────────────────────────

_MAX_GAME_LEN = 120  # ~60 troop cards + tactics buffer; used to normalise tempo

def compute_value(
    winner:       int | None,
    player:       int,
    final_totems: list,
    step_bonus:   float = 0.0,
    game_length:  int   = 0,
    outcome_w:    float = 0.50,
    margin_w:     float = 0.15,
    step_w:       float = 0.35,
    tempo_w:      float = 0.08,
) -> float:
    """
    Shaped value target blending four signals:

      outcome   — did this player win? (+1 / 0 / −1)
      margin    — (my_totems − opp_totems) / 9  — partial credit for claims
      step_bonus — per-move formation quality + claim bonus
      tempo     — outcome × (1 − game_length / MAX) — small bonus for fast wins,
                  small penalty for fast losses

    Weights: outcome=0.50, margin=0.15, step=0.35, tempo=0.08 (additive).
    """
    outcome = 0.0 if winner is None else (1.0 if winner == player else -1.0)
    t_me    = sum(1 for t in final_totems if t.claimed == player)
    t_opp   = sum(1 for t in final_totems if t.claimed == (1 - player))
    margin  = (t_me - t_opp) / 9.0
    tempo   = outcome * max(0.0, 1.0 - game_length / _MAX_GAME_LEN)
    return outcome_w * outcome + margin_w * margin + step_w * step_bonus + tempo_w * tempo
