"""Convert BattleLineGame objects to player-POV JSON dicts for WebSocket transport."""

from battleline import BattleLineGame, Card, WildCard, UnassignedWild, TacticsCard


def serialize_card(card) -> dict:
    if isinstance(card, UnassignedWild):
        return {"type": "wild", "tactic_name": card.tactic_name, "suit": None, "value": None}
    if isinstance(card, WildCard):
        return {"type": "wild", "tactic_name": card.tactic_name, "suit": card.suit, "value": card.value}
    if isinstance(card, TacticsCard):
        return {"type": "tactics", "name": card.name}
    return {"type": "troop", "suit": card.suit, "value": card.value}


def serialize_totem(totem, pov: int) -> dict:
    opp = 1 - pov
    claimed_by: str | None = None
    if totem.claimed == pov:
        claimed_by = "me"
    elif totem.claimed == (1 - pov):
        claimed_by = "opp"

    return {
        "index": totem.index,
        "my_cards": [serialize_card(c) for c in totem.sides[pov]],
        "opp_cards": [serialize_card(c) for c in totem.sides[opp]],
        "claimed_by": claimed_by,
        "fog": totem.fog,
        "mud": totem.mud,
        "cards_to_win": totem.cards_to_win,
    }


def game_view(game: BattleLineGame, pov: int) -> dict:
    """Return the game state as seen by player `pov` (0 or 1)."""
    opp = 1 - pov
    winner: str | None = None
    if game.winner == pov:
        winner = "me"
    elif game.winner == opp:
        winner = "opp"

    return {
        "my_hand": [serialize_card(c) for c in game.hands[pov]],
        "totems": [serialize_totem(t, pov) for t in game.totems],
        "my_totem_count": sum(1 for t in game.totems if t.claimed == pov),
        "opp_totem_count": sum(1 for t in game.totems if t.claimed == opp),
        "troop_deck_size": len(game.deck),
        "tactics_deck_size": len(game.tactics_deck),
        "discarded": [serialize_card(c) for c in game.discarded],
        "my_turn": game.turn % 2 == pov,
        "winner": winner,
        "my_tactics_played":  game.tactics_played[pov],
        "opp_tactics_played": game.tactics_played[opp],
        "opp_tactics_in_hand": sum(1 for c in game.hands[opp] if isinstance(c, TacticsCard)),
        "leaders_in_play": list(game.leaders_in_play[pov]),
        "names": {"me": game.names[pov], "opp": game.names[opp]},
    }
