"""
Battle Line - card game with Tactics deck.

Troop deck: 60 cards (6 suits × values 1-10)
Tactics deck: 10 special cards
Win 5 totems OR 3 consecutive totems.
"""

import random
from itertools import combinations, product

# ─── Constants ────────────────────────────────────────────────────────────────

SUITS     = ["blue", "red", "orange", "yellow", "green", "purple"]
SUIT_ABBR = {"blue": "B", "red": "R", "orange": "O",
             "yellow": "Y", "green": "G", "purple": "P"}
SUIT_COLORS = {
    "blue":   "\033[94m",
    "red":    "\033[91m",
    "orange": "\033[93m",
    "yellow": "\033[33m",
    "green":  "\033[92m",
    "purple": "\033[95m",
}
RESET = "\033[0m"
BOLD  = "\033[1m"
DIM   = "\033[2m"

NUM_TOTEMS   = 9
HAND_SIZE    = 7
CARDS_TO_WIN = 3
WIN_TOTEMS   = 5
WIN_STREAK   = 3

STRAIGHT_FLUSH  = 5
THREE_OF_A_KIND = 4
FLUSH           = 3
STRAIGHT        = 2
HIGH_SUM        = 1

# Tactics card categories
LEADERS        = frozenset({"alexander", "darius"})
WILD_TACTICS   = frozenset({"alexander", "darius", "wild8", "wild321"})
ENV_TACTICS    = frozenset({"fog", "mud"})
ACTION_TACTICS = frozenset({"scout", "redeploy", "traitor", "deserter"})
TACTICS_NAMES  = list(WILD_TACTICS | ENV_TACTICS | ACTION_TACTICS)

TACTICS_DESC = {
    "alexander": "Wild — any suit & value (not with Darius)",
    "darius":    "Wild — any suit & value (not with Alexander)",
    "wild8":     "Wild — value 8, any suit",
    "wild321":   "Wild — value 1/2/3, any suit",
    "fog":       "Totem uses sum-only ranking",
    "mud":       "Totem requires 4-card formations",
    "scout":     "Draw 3, return 2 to decks",
    "redeploy":  "Move or discard one of your played cards",
    "traitor":   "Steal opponent's played card to your side",
    "deserter":  "Discard opponent's played card",
}


# ─── Card classes ─────────────────────────────────────────────────────────────

class Card:
    def __init__(self, suit: str, value: int):
        self.suit  = suit
        self.value = value

    def __repr__(self):
        color = SUIT_COLORS[self.suit]
        return f"{color}{SUIT_ABBR[self.suit]}{self.value:02d}{RESET}"

    def __eq__(self, other):
        return (isinstance(other, Card)
                and not isinstance(other, WildCard)
                and self.suit == other.suit and self.value == other.value)

    def __hash__(self):
        return hash(("card", self.suit, self.value))


class WildCard(Card):
    """A tactics wild card placed on a totem with an assigned suit/value."""
    def __init__(self, tactic_name: str, suit: str, value: int):
        super().__init__(suit, value)
        self.tactic_name = tactic_name

    def __repr__(self):
        color = SUIT_COLORS[self.suit]
        return f"{color}{SUIT_ABBR[self.suit]}{self.value:02d}*{RESET}"

    def __eq__(self, other):
        return (isinstance(other, WildCard)
                and self.tactic_name == other.tactic_name
                and self.suit == other.suit
                and self.value == other.value)

    def __hash__(self):
        return hash(("wild", self.tactic_name, self.suit, self.value))


class UnassignedWild(Card):
    """A wild tactics card on a totem whose suit/value is determined when the totem is claimed."""
    def __init__(self, tactic_name: str):
        super().__init__(SUITS[0], 0)  # placeholder; ignored for evaluation
        self.tactic_name = tactic_name

    def __repr__(self):
        return f"[{self.tactic_name.upper()[:5]}?]"

    def __eq__(self, other):
        return isinstance(other, UnassignedWild) and self.tactic_name == other.tactic_name

    def __hash__(self):
        return hash(("unassigned_wild", self.tactic_name))


class TacticsCard:
    """A tactics card held in a player's hand."""
    def __init__(self, name: str):
        self.name = name

    @property
    def is_wild(self)        -> bool: return self.name in WILD_TACTICS
    @property
    def is_environment(self) -> bool: return self.name in ENV_TACTICS
    @property
    def is_action(self)      -> bool: return self.name in ACTION_TACTICS
    @property
    def is_leader(self)      -> bool: return self.name in LEADERS

    def __repr__(self):
        return f"[{self.name.upper()[:5]}]"

    def __eq__(self, other):
        return isinstance(other, TacticsCard) and self.name == other.name

    def __hash__(self):
        return hash(("tactic", self.name))


# ─── Hand evaluation ──────────────────────────────────────────────────────────

def evaluate_hand(cards: list[Card], fog: bool = False) -> tuple:
    """
    Evaluate a complete hand (3 or 4 cards).
    fog=True: sum-only ranking regardless of suits/values.
    """
    values    = sorted([c.value for c in cards], reverse=True)
    total     = sum(values)
    n         = len(cards)

    if fog:
        return (HIGH_SUM, total)

    suits     = [c.suit for c in cards]
    same_suit = len(set(suits)) == 1
    consec    = (max(values) - min(values) == n - 1) and len(set(values)) == n

    if same_suit and consec:   return (STRAIGHT_FLUSH, max(values))
    if len(set(values)) == 1:  return (THREE_OF_A_KIND, values[0])
    if same_suit:              return (FLUSH, *values)
    if consec:                 return (STRAIGHT, max(values))
    return (HIGH_SUM, total, *values)


def best_possible_hand(played: list[Card], available: list[Card],
                       cards_to_win: int = CARDS_TO_WIN,
                       fog: bool = False) -> tuple | None:
    """Best achievable hand rank given already-played cards and pool of available ones."""
    needed = cards_to_win - len(played)
    if needed <= 0:
        return evaluate_hand(played, fog=fog)
    candidates = [c for c in available if c not in played]
    if len(candidates) < needed:
        return None
    best = None
    for combo in combinations(candidates, needed):
        h = evaluate_hand(list(played) + list(combo), fog=fog)
        if best is None or h > best:
            best = h
    return best


def _wild_options(tactic_name: str) -> list[tuple[str, int]]:
    """Return all valid (suit, value) pairs for an UnassignedWild."""
    if tactic_name == "wild8":
        return [(s, 8) for s in SUITS]
    if tactic_name == "wild321":
        return [(s, v) for s in SUITS for v in (1, 2, 3)]
    return [(s, v) for s in SUITS for v in range(1, 11)]  # alexander, darius


def evaluate_side_best(cards: list, fog: bool = False) -> tuple[tuple, list[tuple]]:
    """
    Find best hand achievable by optimally assigning any UnassignedWilds.
    Returns (best_rank, [(suit, value), ...] one per UnassignedWild in order).
    """
    fixed = [c for c in cards if not isinstance(c, UnassignedWild)]
    wilds = [c for c in cards if isinstance(c, UnassignedWild)]
    if not wilds:
        return evaluate_hand(fixed, fog=fog), []
    best_rank, best_assign = None, []
    for combo in product(*[_wild_options(w.tactic_name) for w in wilds]):
        hand = fixed + [Card(s, v) for s, v in combo]
        rank = evaluate_hand(hand, fog=fog)
        if best_rank is None or rank > best_rank:
            best_rank, best_assign = rank, list(combo)
    return best_rank, best_assign


def best_possible_with_wilds(placed: list, available: list[Card],
                              cards_to_win: int = CARDS_TO_WIN,
                              fog: bool = False) -> tuple | None:
    """
    Best achievable rank for an incomplete side, accounting for UnassignedWilds already placed.
    """
    needed = cards_to_win - len(placed)
    if needed <= 0:
        rank, _ = evaluate_side_best(placed, fog=fog)
        return rank
    fixed = [c for c in placed if not isinstance(c, UnassignedWild)]
    wilds = [c for c in placed if isinstance(c, UnassignedWild)]
    candidates = [c for c in available if c not in fixed]
    if len(candidates) < needed:
        return None
    best = None
    if not wilds:
        for combo in combinations(candidates, needed):
            rank = evaluate_hand(fixed + list(combo), fog=fog)
            if best is None or rank > best:
                best = rank
    else:
        wild_choices = [_wild_options(w.tactic_name) for w in wilds]
        for combo in combinations(candidates, needed):
            base = fixed + list(combo)
            for wild_combo in product(*wild_choices):
                rank = evaluate_hand(base + [Card(s, v) for s, v in wild_combo], fog=fog)
                if best is None or rank > best:
                    best = rank
    return best


def display_rank(rank_tuple: tuple) -> str:
    r = rank_tuple[0]
    if r == STRAIGHT_FLUSH:  return f"Straight Flush (high {rank_tuple[1]})"
    if r == THREE_OF_A_KIND: return f"Three of a Kind ({rank_tuple[1]}s)"
    if r == FLUSH:           return f"Flush ({'+'.join(str(x) for x in rank_tuple[1:])})"
    if r == STRAIGHT:        return f"Straight (high {rank_tuple[1]})"
    return f"High Sum ({rank_tuple[1]})"


# ─── Totem ────────────────────────────────────────────────────────────────────

class Totem:
    def __init__(self, index: int):
        self.index   = index
        self.sides   = [[], []]   # sides[0]=player0, sides[1]=player1
        self.claimed = None       # None, 0, or 1
        self.fog     = False      # Fog environment active
        self.mud     = False      # Mud environment active

    @property
    def cards_to_win(self) -> int:
        return CARDS_TO_WIN + (1 if self.mud else 0)

    def is_full(self, side: int) -> bool:
        return len(self.sides[side]) == self.cards_to_win

    def play_card(self, side: int, card: Card):
        if self.claimed is not None:
            raise ValueError("Totem already claimed")
        if self.is_full(side):
            raise ValueError("Side already full")
        self.sides[side].append(card)

    def try_claim(self, available_cards: list[Card], last_player: int) -> bool:
        if self.claimed is not None:
            return False
        ctw = self.cards_to_win
        rank   = [None, None]
        assign = [None, None]
        for p in range(2):
            if len(self.sides[p]) == ctw:
                rank[p], assign[p] = evaluate_side_best(self.sides[p], fog=self.fog)

        if rank[0] is None and rank[1] is None:
            return False

        if rank[0] is not None and rank[1] is not None:
            if rank[0] > rank[1]:   winner = 0
            elif rank[1] > rank[0]: winner = 1
            else:                   winner = last_player
            self._apply_wild_assignments(0, assign[0])
            self._apply_wild_assignments(1, assign[1])
            self.claimed = winner
            return True

        full_p  = 0 if rank[0] is not None else 1
        other_p = 1 - full_p
        best_other = best_possible_with_wilds(self.sides[other_p], available_cards,
                                              cards_to_win=ctw, fog=self.fog)
        can_claim = rank[full_p] >= best_other 
        if best_other is None or can_claim:
            self._apply_wild_assignments(full_p, assign[full_p])
            self.claimed = full_p
            return True
        return False

    def _apply_wild_assignments(self, player: int, assignments: list[tuple] | None):
        if not assignments:
            return
        j = 0
        for i, card in enumerate(self.sides[player]):
            if isinstance(card, UnassignedWild):
                suit, value = assignments[j]
                self.sides[player][i] = WildCard(card.tactic_name, suit, value)
                j += 1


# ─── Game ─────────────────────────────────────────────────────────────────────

class BattleLineGame:
    def __init__(self, player_names: list[str]):
        self.names         = player_names
        self.deck          = [Card(s, v) for s in SUITS for v in range(1, 11)]
        random.shuffle(self.deck)
        self.tactics_deck  = [TacticsCard(n) for n in TACTICS_NAMES]
        random.shuffle(self.tactics_deck)
        self.hands         = [[], []]
        self.totems        = [Totem(i) for i in range(NUM_TOTEMS)]
        self.turn          = 0
        self.winner        = None
        self.tactics_played  = [0, 0]   # tactics cards played by each player
        self.leaders_in_play = set()    # "alexander" and/or "darius"
        self.discarded       = []       # public discard pile

        for _ in range(HAND_SIZE):
            for p in range(2):
                self._draw(p)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _draw(self, player: int, from_tactics: bool = False):
        deck = self.tactics_deck if from_tactics else self.deck
        if deck:
            self.hands[player].append(deck.pop())

    def draw_card(self, player: int, from_tactics: bool = False) -> bool:
        """Public: draw one card after a turn. Returns True if successful."""
        deck = self.tactics_deck if from_tactics else self.deck
        if deck:
            self.hands[player].append(deck.pop())
            return True
        return False

    def _all_played_cards(self) -> list:
        out = []
        for t in self.totems:
            for side in t.sides:
                out.extend(side)
        return out

    def _unplayed_cards(self) -> list[Card]:
        """Troop cards not on any totem and not discarded (used for claim evaluation)."""
        played_troop  = {c for c in self._all_played_cards()
                         if isinstance(c, Card) and not isinstance(c, (WildCard, UnassignedWild))}
        disc_troop    = {c for c in self.discarded
                         if isinstance(c, Card) and not isinstance(c, (WildCard, UnassignedWild))}
        excluded      = played_troop | disc_troop
        return [Card(s, v) for s in SUITS for v in range(1, 11)
                if Card(s, v) not in excluded]

    def _check_claims(self, last_player: int) -> list[int]:
        unplayed = self._unplayed_cards()
        newly = []
        for t in self.totems:
            if t.claimed is None and t.try_claim(unplayed, last_player):
                newly.append(t.index + 1)
        return newly

    def _claim_msg(self, newly: list[int]) -> str:
        out = ""
        for ti in newly:
            c = self.totems[ti - 1].claimed
            out += f"\n  >> Totem {ti} claimed by {self.names[c]}!"
        return out

    def get_winner(self) -> int | None:
        claimed = [t.claimed for t in self.totems]
        for p in range(2):
            if claimed.count(p) >= WIN_TOTEMS:
                return p
            streak = best = 0
            for c in claimed:
                if c == p: streak += 1; best = max(best, streak)
                else:      streak = 0
            if best >= WIN_STREAK:
                return p
        return None

    def can_play_tactics(self, player: int) -> bool:
        """True if player hasn't played one more tactics card than their opponent."""
        return self.tactics_played[player] <= self.tactics_played[1 - player]

    # ── Regular card ──────────────────────────────────────────────────────────

    def play_card(self, player: int, card: Card, totem_index: int) -> str:
        """Play a troop card to a totem. Draw separately via draw_card()."""
        totem = self.totems[totem_index]
        if totem.claimed is not None:
            raise ValueError(f"Totem {totem_index + 1} is already claimed.")
        if totem.is_full(player):
            raise ValueError(f"Your side of totem {totem_index + 1} is already full.")
        if card not in self.hands[player]:
            raise ValueError("You don't have that card.")

        self.hands[player].remove(card)
        totem.play_card(player, card)
        newly = self._check_claims(player)
        self.winner = self.get_winner()
        return f"{self.names[player]} played {card} on totem {totem_index + 1}." + self._claim_msg(newly)

    # ── Wild tactics ──────────────────────────────────────────────────────────

    def play_wild(self, player: int, tactic: TacticsCard, totem_index: int,
                  suit: str, value: int) -> str:
        """Play a wild tactics card assigned to a specific suit/value."""
        if tactic not in self.hands[player]:
            raise ValueError("Card not in hand.")
        if not self.can_play_tactics(player):
            raise ValueError("Can't play tactics: you're already 1 ahead of opponent.")
        if tactic.is_leader:
            other = LEADERS - {tactic.name}
            if any(l in self.leaders_in_play for l in other):
                raise ValueError("Cannot play both Alexander and Darius.")
        if tactic.name == "wild8" and value != 8:
            raise ValueError("Wild 8 must have value 8.")
        if tactic.name == "wild321" and value not in (1, 2, 3):
            raise ValueError("Wild 321 must have value 1, 2, or 3.")

        totem = self.totems[totem_index]
        if totem.claimed is not None:
            raise ValueError(f"Totem {totem_index + 1} is already claimed.")
        if totem.is_full(player):
            raise ValueError(f"Your side of totem {totem_index + 1} is full.")

        self.hands[player].remove(tactic)
        totem.play_card(player, WildCard(tactic.name, suit, value))
        self.tactics_played[player] += 1
        if tactic.is_leader:
            self.leaders_in_play.add(tactic.name)

        newly = self._check_claims(player)
        self.winner = self.get_winner()
        name = tactic.name.capitalize()
        return (f"{self.names[player]} played {name} as {suit} {value} "
                f"on totem {totem_index + 1}." + self._claim_msg(newly))

    def play_unassigned_wild(self, player: int, tactic: TacticsCard, totem_index: int) -> str:
        """Play a wild tactics card without declaring suit/value (resolved at claim time)."""
        if tactic not in self.hands[player]:
            raise ValueError("Card not in hand.")
        if not self.can_play_tactics(player):
            raise ValueError("Can't play tactics: you're already 1 ahead of opponent.")
        if tactic.is_leader:
            other = LEADERS - {tactic.name}
            if any(l in self.leaders_in_play for l in other):
                raise ValueError("Cannot play both Alexander and Darius.")
        totem = self.totems[totem_index]
        if totem.claimed is not None:
            raise ValueError(f"Totem {totem_index + 1} is already claimed.")
        if totem.is_full(player):
            raise ValueError(f"Your side of totem {totem_index + 1} is full.")

        self.hands[player].remove(tactic)
        totem.play_card(player, UnassignedWild(tactic.name))
        self.tactics_played[player] += 1
        if tactic.is_leader:
            self.leaders_in_play.add(tactic.name)

        newly = self._check_claims(player)
        self.winner = self.get_winner()
        name = tactic.name.capitalize()
        return (f"{self.names[player]} played {name} (undeclared) "
                f"on totem {totem_index + 1}." + self._claim_msg(newly))

    # ── Environment tactics ───────────────────────────────────────────────────

    def play_environment(self, player: int, tactic: TacticsCard,
                         totem_index: int) -> str:
        """Play Fog or Mud on a totem."""
        if tactic not in self.hands[player]:
            raise ValueError("Card not in hand.")
        if not self.can_play_tactics(player):
            raise ValueError("Can't play tactics: you're already 1 ahead of opponent.")
        totem = self.totems[totem_index]
        if totem.claimed is not None:
            raise ValueError(f"Totem {totem_index + 1} is already claimed.")
        if tactic.name == "fog" and totem.fog:
            raise ValueError(f"Totem {totem_index + 1} already has Fog.")
        if tactic.name == "mud" and totem.mud:
            raise ValueError(f"Totem {totem_index + 1} already has Mud.")

        self.hands[player].remove(tactic)
        if tactic.name == "fog": totem.fog = True
        if tactic.name == "mud": totem.mud = True
        self.tactics_played[player] += 1

        newly = self._check_claims(player)
        self.winner = self.get_winner()
        name = tactic.name.capitalize()
        return (f"{self.names[player]} played {name} on totem {totem_index + 1}."
                + self._claim_msg(newly))

    # ── Scout ─────────────────────────────────────────────────────────────────

    def scout_reveal(self, player: int, tactic: TacticsCard,
                     troop_count: int, tactics_count: int) -> list:
        """
        Phase 1: reveal top cards from decks into hand.
        Returns list of ("troop"|"tactics", card) pairs revealed.
        No draw_card() needed afterward — scout replaces the normal draw.
        """
        if tactic not in self.hands[player]:
            raise ValueError("Card not in hand.")
        if not self.can_play_tactics(player):
            raise ValueError("Can't play tactics: you're already 1 ahead of opponent.")
        if troop_count + tactics_count != 3:
            raise ValueError("Must reveal exactly 3 cards total.")
        if troop_count > len(self.deck):
            raise ValueError(f"Only {len(self.deck)} troop cards left.")
        if tactics_count > len(self.tactics_deck):
            raise ValueError(f"Only {len(self.tactics_deck)} tactics cards left.")

        self.hands[player].remove(tactic)
        self.discarded.append(tactic)
        self.tactics_played[player] += 1

        revealed = []
        for _ in range(troop_count):
            c = self.deck.pop()
            self.hands[player].append(c)
            revealed.append(("troop", c))
        for _ in range(tactics_count):
            c = self.tactics_deck.pop()
            self.hands[player].append(c)
            revealed.append(("tactics", c))
        return revealed

    def scout_return(self, player: int, returns: list[tuple]) -> str:
        """
        Phase 2: return 2 cards from hand back to tops of decks.
        returns: [(card, "troop"|"tactics"), ...] — 2 items, last item ends up on top.
        """
        if len(returns) != 2:
            raise ValueError("Must return exactly 2 cards.")
        for card, _ in returns:
            if card not in self.hands[player]:
                raise ValueError(f"{card} is not in hand.")
        for card, dest in reversed(returns):
            self.hands[player].remove(card)
            if dest == "troop":   self.deck.append(card)
            else:                 self.tactics_deck.append(card)
        return f"{self.names[player]} played Scout."

    # ── Redeploy ──────────────────────────────────────────────────────────────

    def play_redeploy(self, player: int, tactic: TacticsCard,
                      from_totem: int, card,
                      to_totem: int | None) -> str:
        """Move your card from from_totem to to_totem, or discard if to_totem=None."""
        if tactic not in self.hands[player]:
            raise ValueError("Card not in hand.")
        if not self.can_play_tactics(player):
            raise ValueError("Can't play tactics: you're already 1 ahead of opponent.")
        src = self.totems[from_totem]
        if src.claimed is not None:
            raise ValueError(f"Totem {from_totem + 1} is already claimed.")
        if card not in src.sides[player]:
            raise ValueError("Card not on your side of that totem.")
        if to_totem is not None:
            dst = self.totems[to_totem]
            if dst.claimed is not None:
                raise ValueError(f"Destination totem {to_totem + 1} is already claimed.")
            if dst.is_full(player):
                raise ValueError(f"Your side of totem {to_totem + 1} is full.")

        self.hands[player].remove(tactic)
        self.discarded.append(tactic)
        src.sides[player].remove(card)
        self.tactics_played[player] += 1

        if to_totem is not None:
            self.totems[to_totem].sides[player].append(card)
            desc = f"moved card from totem {from_totem+1} to totem {to_totem+1}"
        else:
            self.discarded.append(card)
            desc = f"discarded card from totem {from_totem+1}"

        newly = self._check_claims(player)
        self.winner = self.get_winner()
        return f"{self.names[player]} played Redeploy ({desc})." + self._claim_msg(newly)

    # ── Traitor ───────────────────────────────────────────────────────────────

    def play_traitor(self, player: int, tactic: TacticsCard,
                     from_totem: int, card, to_totem: int) -> str:
        """Steal opponent's card from from_totem to your side of to_totem."""
        if tactic not in self.hands[player]:
            raise ValueError("Card not in hand.")
        if not self.can_play_tactics(player):
            raise ValueError("Can't play tactics: you're already 1 ahead of opponent.")
        opp = 1 - player
        src = self.totems[from_totem]
        if src.claimed is not None:
            raise ValueError(f"Totem {from_totem+1} is already claimed.")
        if card not in src.sides[opp]:
            raise ValueError("Card not on opponent's side of that totem.")
        dst = self.totems[to_totem]
        if dst.claimed is not None:
            raise ValueError(f"Destination totem {to_totem+1} is already claimed.")
        if dst.is_full(player):
            raise ValueError(f"Your side of totem {to_totem+1} is full.")

        self.hands[player].remove(tactic)
        self.discarded.append(tactic)
        src.sides[opp].remove(card)
        dst.sides[player].append(card)
        self.tactics_played[player] += 1

        newly = self._check_claims(player)
        self.winner = self.get_winner()
        return (f"{self.names[player]} played Traitor "
                f"(stole from totem {from_totem+1} → totem {to_totem+1})."
                + self._claim_msg(newly))

    # ── Deserter ──────────────────────────────────────────────────────────────

    def play_deserter(self, player: int, tactic: TacticsCard,
                      from_totem: int, card) -> str:
        """Discard opponent's card from from_totem (card stays public info in discard)."""
        if tactic not in self.hands[player]:
            raise ValueError("Card not in hand.")
        if not self.can_play_tactics(player):
            raise ValueError("Can't play tactics: you're already 1 ahead of opponent.")
        opp = 1 - player
        src = self.totems[from_totem]
        if src.claimed is not None:
            raise ValueError(f"Totem {from_totem+1} is already claimed.")
        if card not in src.sides[opp]:
            raise ValueError("Card not on opponent's side of that totem.")

        self.hands[player].remove(tactic)
        self.discarded.append(tactic)
        src.sides[opp].remove(card)
        self.discarded.append(card)   # still public
        self.tactics_played[player] += 1

        newly = self._check_claims(player)
        self.winner = self.get_winner()
        return (f"{self.names[player]} played Deserter "
                f"(removed card from totem {from_totem+1})." + self._claim_msg(newly))


# ─── AI ───────────────────────────────────────────────────────────────────────

def ai_choose_move(game: BattleLineGame, player: int):
    """
    Greedy AI. Returns a move tuple:
      ("card",  card, totem_idx)
      ("wild",  tactic, totem_idx, suit, value)
    Skips action tactics (too complex for greedy AI).
    """
    hand     = game.hands[player]
    unplayed = game._unplayed_cards()

    best_move  = None
    best_score = ((-1,), -1, -1)

    # ── Regular troop cards ───────────────────────────────────────────────────
    for card in hand:
        if isinstance(card, TacticsCard):
            continue
        for ti, totem in enumerate(game.totems):
            if totem.claimed is not None or totem.is_full(player):
                continue
            played = totem.sides[player] + [card]
            avail  = [c for c in unplayed if c != card]
            rank   = best_possible_hand(played, avail,
                                        cards_to_win=totem.cards_to_win,
                                        fog=totem.fog) or (0,)
            score  = (rank, len(played), -ti)
            if score > best_score:
                best_score = score
                best_move  = ("card", card, ti)

    # ── Wild tactics cards ────────────────────────────────────────────────────
    if game.can_play_tactics(player):
        for tac in hand:
            if not isinstance(tac, TacticsCard) or not tac.is_wild:
                continue
            if tac.is_leader:
                other = LEADERS - {tac.name}
                if any(l in game.leaders_in_play for l in other):
                    continue
            if tac.name == "wild8":
                combos = [(s, 8) for s in SUITS]
            elif tac.name == "wild321":
                combos = [(s, v) for s in SUITS for v in (1, 2, 3)]
            else:
                combos = [(s, v) for s in SUITS for v in range(1, 11)]

            for ti, totem in enumerate(game.totems):
                if totem.claimed is not None or totem.is_full(player):
                    continue
                for suit, val in combos:
                    w      = WildCard(tac.name, suit, val)
                    played = totem.sides[player] + [w]
                    rank   = best_possible_hand(played, unplayed,
                                                cards_to_win=totem.cards_to_win,
                                                fog=totem.fog) or (0,)
                    score  = (rank, len(played), -ti)
                    if score > best_score:
                        best_score = score
                        best_move  = ("wild", tac, ti, suit, val)

    # ── Fallback ──────────────────────────────────────────────────────────────
    if best_move is None:
        for card in hand:
            if isinstance(card, TacticsCard):
                continue
            for ti, totem in enumerate(game.totems):
                if totem.claimed is None and not totem.is_full(player):
                    return ("card", card, ti)
        # Only tactics left — play first wild if possible
        for tac in hand:
            if isinstance(tac, TacticsCard) and tac.is_wild and game.can_play_tactics(player):
                if tac.is_leader and any(l in game.leaders_in_play
                                         for l in LEADERS - {tac.name}):
                    continue
                for ti, totem in enumerate(game.totems):
                    if totem.claimed is None and not totem.is_full(player):
                        suit = SUITS[0]
                        val  = 8 if tac.name == "wild8" else (1 if tac.name == "wild321" else 7)
                        return ("wild", tac, ti, suit, val)

    return best_move


def ai_make_move(game: BattleLineGame, player: int) -> tuple[str, bool]:
    """
    Execute AI's chosen move. Returns (message, needs_draw).
    needs_draw=False for Scout (scout manages its own cards).
    """
    move = ai_choose_move(game, player)
    if move is None:
        return ("AI skipped (no valid moves).", False)

    mtype = move[0]
    if mtype == "card":
        _, card, ti = move
        return (game.play_card(player, card, ti), True)
    elif mtype == "wild":
        _, tac, ti, suit, val = move
        return (game.play_wild(player, tac, ti, suit, val), True)

    return ("AI skipped.", False)


# ─── CLI display (unchanged) ──────────────────────────────────────────────────

def render_row(cards, max_cards: int = 3) -> list[str]:
    row = []
    for i in range(max_cards):
        if i < len(cards):
            row.append(f"[{cards[i]}]")
        else:
            row.append(DIM + "[   ]" + RESET)
    return row

def display_board(game, pov: int):
    opponent = 1 - pov
    print()
    print(BOLD + f"  {'═' * 70}" + RESET)
    totem_nums = "   ".join(f"  {BOLD}{i+1}{RESET}  " for i in range(NUM_TOTEMS))
    print(f"  Totems:  {totem_nums}")
    print()
    opp_rows = [render_row(game.totems[i].sides[opponent]) for i in range(NUM_TOTEMS)]
    for slot in range(CARDS_TO_WIN - 1, -1, -1):
        line   = "  ".join(row[slot] for row in opp_rows)
        prefix = f"  {game.names[opponent][:4]:4s}" if slot == CARDS_TO_WIN - 1 else "       "
        print(f"  {prefix}  {line}")
    print()
    totem_status = []
    for t in game.totems:
        if t.claimed == pov:
            totem_status.append(BOLD + "\033[92m[YOU]\033[0m" + RESET)
        elif t.claimed == opponent:
            totem_status.append(BOLD + "\033[91m[OPP]\033[0m" + RESET)
        else:
            lbl = ""
            if t.fog: lbl += "F"
            if t.mud: lbl += "M"
            totem_status.append(DIM + f"[{lbl:^4}]" + RESET)
    print("  Claim:   " + "  ".join(totem_status))
    print()
    my_rows = [render_row(game.totems[i].sides[pov]) for i in range(NUM_TOTEMS)]
    for slot in range(CARDS_TO_WIN):
        line   = "  ".join(row[slot] for row in my_rows)
        prefix = f"  {game.names[pov][:4]:4s}" if slot == 0 else "       "
        print(f"  {prefix}  {line}")
    print()
    print(BOLD + f"  {'═' * 70}" + RESET)
    p0c = sum(1 for t in game.totems if t.claimed == 0)
    p1c = sum(1 for t in game.totems if t.claimed == 1)
    print(f"  Score: {game.names[0]}: {p0c}  |  {game.names[1]}: {p1c}  "
          f"(need {WIN_TOTEMS} or {WIN_STREAK} in a row)")
    print()

def display_hand(game, player: int):
    hand = game.hands[player]
    print(f"  Your hand ({len(hand)} cards):")
    for i, card in enumerate(hand):
        if isinstance(card, TacticsCard):
            print(f"    {i+1}. [TACTICS] {card.name}  — {TACTICS_DESC[card.name]}")
        else:
            print(f"    {i+1}. {card}  ({card.suit} {card.value})")
    print()


# ─── CLI main ─────────────────────────────────────────────────────────────────

def clear():
    print("\033[2J\033[H", end="")

def get_int(prompt: str, lo: int, hi: int) -> int:
    while True:
        try:
            v = int(input(prompt).strip())
            if lo <= v <= hi:
                return v
            print(f"  Please enter {lo}–{hi}.")
        except ValueError:
            print("  Invalid input.")

def main():
    clear()
    print(BOLD + "\n  ╔══════════════════════════════╗" + RESET)
    print(BOLD + "  ║     BATTLE LINE              ║" + RESET)
    print(BOLD + "  ╚══════════════════════════════╝" + RESET)
    print()
    mode    = get_int("  Play against: (1) Human  (2) AI  → ", 1, 2)
    p0_name = input("  Player 1 name: ").strip() or "Player 1"
    p1_name = "AI" if mode == 2 else (input("  Player 2 name: ").strip() or "Player 2")
    game    = BattleLineGame([p0_name, p1_name])
    is_ai   = [False, mode == 2]

    while game.winner is None:
        p          = game.turn % 2
        is_ai_turn = is_ai[p]

        if is_ai_turn:
            msg, needs_draw = ai_make_move(game, p)
            if needs_draw:
                game.draw_card(p)
            game.turn += 1
            clear()
            display_board(game, 0)
            print(f"\n  {msg}")
            input("\n  [Press Enter to continue]")
        else:
            while True:
                clear()
                display_board(game, p)
                display_hand(game, p)
                print(f"  {BOLD}{game.names[p]}'s turn{RESET}  "
                      f"(troop deck: {len(game.deck)}  tactics deck: {len(game.tactics_deck)})")
                print()
                print("  Commands: <card#> <totem#>  |  q = quit")
                cmd = input("  > ").strip().lower()
                if cmd == "q":
                    return
                parts = cmd.split()
                if len(parts) != 2:
                    print("  Enter: <card number> <totem number>")
                    input("  [Press Enter]"); continue
                try:
                    ci = int(parts[0]) - 1
                    ti = int(parts[1]) - 1
                    if not (0 <= ci < len(game.hands[p])):
                        raise ValueError("Card index out of range")
                    if not (0 <= ti < NUM_TOTEMS):
                        raise ValueError("Totem index out of range")
                    card = game.hands[p][ci]
                    if isinstance(card, TacticsCard):
                        print("  Tactics cards not supported in CLI mode. Use the GUI.")
                        input("  [Press Enter]"); continue
                    msg = game.play_card(p, card, ti)
                    game.draw_card(p)
                    game.turn += 1
                    clear()
                    display_board(game, p)
                    print(f"\n  {msg}")
                    input("\n  [Press Enter to continue]")
                    break
                except (ValueError, IndexError) as e:
                    print(f"  Error: {e}")
                    input("  [Press Enter]")

    clear()
    display_board(game, 0)
    print(BOLD + f"\n  *** {game.names[game.winner]} wins! ***\n" + RESET)


if __name__ == "__main__":
    main()
