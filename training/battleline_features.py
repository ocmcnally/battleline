"""
Battle Line feature encoder v2.

Each game state is encoded as a flat float vector of TOTAL_DIM values.

Block layout (in order):
  troop_hand   : 60   which troop cards are in hand
  tactics_hand : 10   which tactics cards are in hand
  board        : 9×2×SIDE_DIM   per-totem-side features (my side first)
  totem_meta   : 9×6  fog / mud / claimed / cards_to_win per totem
  unplayed     : 60   troop cards not yet placed on any totem
  global       :  8   deck sizes, tactics counts, turn info

Per-side block (SIDE_DIM = 73):
  card_presence : 60  which troop/assigned-wild cards are present
  n_cards       :  1  number of cards placed (0–4), normalised
  val_min       :  1  lowest value, normalised to [0,1]
  val_max       :  1  highest value, normalised to [0,1]
  val_sum       :  1  sum of values, normalised (max 27 for 3 cards)
  mono_suit     :  1  all cards same suit
  mono_value    :  1  all cards same value (3-of-a-kind seed)
  consecutive   :  1  values span exactly n-1 (straight seed)
  best_type     :  6  one-hot: [empty, sum, straight, flush, 3oak, sf]
"""

from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import List

try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    torch = None
    nn = None
    TORCH_AVAILABLE = False

from battleline import (
    BattleLineGame, Card, WildCard, UnassignedWild, TacticsCard,
    SUITS, NUM_TOTEMS,
    STRAIGHT_FLUSH, THREE_OF_A_KIND, FLUSH, STRAIGHT, HIGH_SUM,
)

# ── Constants ──────────────────────────────────────────────────────────────────

TROOP_COUNT = len(SUITS) * 10   # 60

TACTICS_NAMES = [
    "alexander", "darius", "wild8", "wild321",
    "fog", "mud", "scout", "redeploy", "traitor", "deserter",
]
TACTICS_COUNT = len(TACTICS_NAMES)   # 10

# Formation type labels (indices into the one-hot)
_F_EMPTY = 0
_F_SUM   = 1
_F_STR   = 2
_F_FLU   = 3
_F_3OAK  = 4
_F_SF    = 5
N_FORM_TYPES = 6

SIDE_DIM      = TROOP_COUNT + 4 + 3 + N_FORM_TYPES   # 73
TOTEM_META_DIM = 6

BLOCK_SIZES = {
    "troop_hand":  TROOP_COUNT,
    "tactics_hand": TACTICS_COUNT,
    "board":       NUM_TOTEMS * 2 * SIDE_DIM,
    "totem_meta":  NUM_TOTEMS * TOTEM_META_DIM,
    "unplayed":    TROOP_COUNT,
    "global":      8,
}
TOTAL_DIM = sum(BLOCK_SIZES.values())

# Policy covers every (troop-card, totem) pair
POLICY_DIM = TROOP_COUNT * NUM_TOTEMS   # 540


# ── Low-level helpers ──────────────────────────────────────────────────────────

def _card_idx(card) -> int:
    """Slot index for any card that has .suit and .value."""
    return SUITS.index(card.suit) * 10 + (card.value - 1)


def _formation_cards(side: list) -> list:
    """
    Cards on a totem side that contribute to a formation:
    regular troop cards plus assigned WildCards (which have a suit/value).
    UnassignedWild and TacticsCard (environment) are excluded.
    """
    out = []
    for c in side:
        if isinstance(c, UnassignedWild):
            continue
        if isinstance(c, TacticsCard):
            continue
        if isinstance(c, Card):   # covers WildCard subclass too
            if isinstance(c, WildCard) and (c.suit is None or c.value is None):
                continue
            out.append(c)
    return out


def _one_hot(idx: int, size: int) -> List[float]:
    v = [0.0] * size
    if 0 <= idx < size:
        v[idx] = 1.0
    return v


# ── Formation analysis ─────────────────────────────────────────────────────────

def _best_consistent_type(cards: list) -> int:
    """
    Best formation type the played cards are consistent with — i.e. could
    be completed into given the right remaining cards.  Does NOT check deck
    availability; the unplayed-cards block gives the model that context.
    """
    n = len(cards)
    if n == 0:
        return _F_EMPTY

    suits  = [c.suit  for c in cards]
    values = sorted(c.value for c in cards)

    mono_suit  = len(set(suits)) == 1
    mono_value = len(set(values)) == 1 and n >= 2
    # consecutive: all distinct and span exactly n-1
    consec     = (len(set(values)) == n) and (values[-1] - values[0] == n - 1)

    if mono_suit and consec:  return _F_SF
    if mono_value:            return _F_3OAK
    if mono_suit:             return _F_FLU
    if consec:                return _F_STR
    return _F_SUM


# ── Per-side encoder ───────────────────────────────────────────────────────────

def encode_side(side: list) -> List[float]:
    """Return a SIDE_DIM-length float vector for one side of a totem."""
    fc = _formation_cards(side)
    n  = len(fc)

    # card presence (60)
    presence = [0.0] * TROOP_COUNT
    for c in fc:
        presence[_card_idx(c)] = 1.0

    # scalars (4)
    if n == 0:
        scalars = [0.0, 0.0, 0.0, 0.0]
    else:
        vals    = sorted(c.value for c in fc)
        scalars = [
            n / 4.0,               # n_cards  (max 4 with mud)
            vals[0]  / 10.0,       # val_min
            vals[-1] / 10.0,       # val_max
            sum(vals) / 27.0,      # val_sum  (10+9+8 = 27 is natural max for 3 cards)
        ]

    # flags (3)
    if n == 0:
        flags = [0.0, 0.0, 0.0]
    else:
        suits = [c.suit for c in fc]
        vals  = sorted(c.value for c in fc)
        flags = [
            1.0 if len(set(suits)) == 1 else 0.0,
            1.0 if (len(set(vals)) == 1 and n >= 2) else 0.0,
            1.0 if (len(set(vals)) == n and vals[-1] - vals[0] == n - 1) else 0.0,
        ]

    # best formation type one-hot (6)
    form = _one_hot(_best_consistent_type(fc), N_FORM_TYPES)

    return presence + scalars + flags + form


# ── Block encoders ─────────────────────────────────────────────────────────────

def encode_troop_hand(game: BattleLineGame, player: int) -> List[float]:
    vec = [0.0] * TROOP_COUNT
    for c in game.hands[player]:
        if isinstance(c, Card) and not isinstance(c, (WildCard, UnassignedWild, TacticsCard)):
            vec[_card_idx(c)] = 1.0
    return vec


def encode_tactics_hand(game: BattleLineGame, player: int) -> List[float]:
    vec = [0.0] * TACTICS_COUNT
    for c in game.hands[player]:
        if isinstance(c, TacticsCard):
            try:
                vec[TACTICS_NAMES.index(c.name)] = 1.0
            except ValueError:
                pass
    return vec


def encode_board(game: BattleLineGame, pov: int) -> List[float]:
    """All totem sides from pov's perspective. Own side always comes first."""
    out: List[float] = []
    opp = 1 - pov
    for totem in game.totems:
        out.extend(encode_side(totem.sides[pov]))
        out.extend(encode_side(totem.sides[opp]))
    return out


def encode_totem_meta(game: BattleLineGame, pov: int) -> List[float]:
    out: List[float] = []
    for totem in game.totems:
        if totem.claimed is None:
            out.extend([1.0, 0.0, 0.0])
        elif totem.claimed == pov:
            out.extend([0.0, 1.0, 0.0])
        else:
            out.extend([0.0, 0.0, 1.0])
        out.append(1.0 if totem.fog else 0.0)
        out.append(1.0 if totem.mud else 0.0)
        out.append(totem.cards_to_win / 4.0)
    return out


def encode_unplayed(game: BattleLineGame) -> List[float]:
    """Troop cards not on any totem (in deck or in a hand — unknown to us but needed for training)."""
    vec = [0.0] * TROOP_COUNT
    for c in game._unplayed_cards():
        if isinstance(c, Card) and not isinstance(c, (WildCard, UnassignedWild)):
            vec[_card_idx(c)] = 1.0
    return vec


def encode_global(game: BattleLineGame, pov: int) -> List[float]:
    opp = 1 - pov
    return [
        1.0 if game.turn % 2 == pov else 0.0,
        len(game.deck)         / TROOP_COUNT,
        len(game.tactics_deck) / TACTICS_COUNT,
        game.tactics_played[pov] / TACTICS_COUNT,
        game.tactics_played[opp] / TACTICS_COUNT,
        len(game.hands[pov]) / 8.0,
        len(game.hands[opp]) / 8.0,
        (game.turn // 2)     / 60.0,   # game progress
    ]


# ── Top-level encode ───────────────────────────────────────────────────────────

def encode(game: BattleLineGame, pov: int) -> List[float]:
    """Return a flat TOTAL_DIM-length float vector for the given player's POV."""
    return (
        encode_troop_hand(game, pov)
        + encode_tactics_hand(game, pov)
        + encode_board(game, pov)
        + encode_totem_meta(game, pov)
        + encode_unplayed(game)
        + encode_global(game, pov)
    )


# ── Policy helpers ─────────────────────────────────────────────────────────────

def policy_index(card: Card, totem_idx: int) -> int:
    return totem_idx * TROOP_COUNT + _card_idx(card)


def policy_from_index(idx: int):
    return idx // TROOP_COUNT, idx % TROOP_COUNT   # totem_idx, card_slot


def legal_troop_moves(game: BattleLineGame, player: int) -> List[tuple]:
    """Return list of (card, totem_idx, policy_idx) for every legal troop placement."""
    moves = []
    for card in game.hands[player]:
        if not isinstance(card, Card) or isinstance(card, (WildCard, UnassignedWild, TacticsCard)):
            continue
        for ti, totem in enumerate(game.totems):
            if totem.claimed is None and not totem.is_full(player):
                moves.append((card, ti, policy_index(card, ti)))
    return moves


def legal_mask(game: BattleLineGame, player: int) -> List[int]:
    mask = [0] * POLICY_DIM
    for card in game.hands[player]:
        if not isinstance(card, Card) or isinstance(card, (WildCard, UnassignedWild, TacticsCard)):
            continue
        for ti, totem in enumerate(game.totems):
            if totem.claimed is None and not totem.is_full(player):
                mask[policy_index(card, ti)] = 1
    return mask


# ── Network ────────────────────────────────────────────────────────────────────

if TORCH_AVAILABLE:

    class ResidualBlock(nn.Module):
        def __init__(self, dim: int, dropout: float = 0.1):
            super().__init__()
            self.block = nn.Sequential(
                nn.Linear(dim, dim),
                nn.LayerNorm(dim),
                nn.ReLU(inplace=True),
                nn.Dropout(dropout),
                nn.Linear(dim, dim),
                nn.LayerNorm(dim),
            )
            self.act = nn.ReLU(inplace=True)

        def forward(self, x):
            return self.act(x + self.block(x))


    class BattleLineNet(nn.Module):
        """
        AlphaZero-style policy/value network.

        Architecture:
          input → projection → N residual blocks → policy head + value head

        Policy head : logits over POLICY_DIM (troop-card × totem) actions
        Value head  : scalar in (-1, 1) estimating win probability from pov
        """

        def __init__(
            self,
            input_dim:   int   = TOTAL_DIM,
            hidden_dim:  int   = 512,
            n_blocks:    int   = 6,
            policy_dim:  int   = POLICY_DIM,
            dropout:     float = 0.1,
        ):
            super().__init__()

            self.projection = nn.Sequential(
                nn.Linear(input_dim, hidden_dim),
                nn.LayerNorm(hidden_dim),
                nn.ReLU(inplace=True),
            )

            self.residual_tower = nn.Sequential(
                *[ResidualBlock(hidden_dim, dropout) for _ in range(n_blocks)]
            )

            self.policy_head = nn.Sequential(
                nn.Linear(hidden_dim, hidden_dim // 2),
                nn.ReLU(inplace=True),
                nn.Linear(hidden_dim // 2, policy_dim),
            )

            self.value_head = nn.Sequential(
                nn.Linear(hidden_dim, hidden_dim // 4),
                nn.ReLU(inplace=True),
                nn.Linear(hidden_dim // 4, 1),
                nn.Tanh(),
            )

        def forward(self, x: "torch.Tensor"):
            h = self.projection(x)
            h = self.residual_tower(h)
            policy_logits = self.policy_head(h)
            value         = self.value_head(h).squeeze(-1)
            return policy_logits, value


    def to_tensor(
        game: BattleLineGame,
        pov:  int,
        device: str = "cpu",
    ) -> "torch.Tensor":
        flat = encode(game, pov)
        return torch.tensor(flat, dtype=torch.float32, device=device).unsqueeze(0)


    def masked_policy(logits: "torch.Tensor", mask: "torch.Tensor") -> "torch.Tensor":
        neg_inf = torch.finfo(logits.dtype).min / 2
        return logits.masked_fill(~mask.bool(), neg_inf)


    def loss(
        policy_logits:  "torch.Tensor",
        values:         "torch.Tensor",
        target_actions: "torch.Tensor",
        legal_mask_t:   "torch.Tensor",
        value_targets:  "torch.Tensor",
        value_weight:   float = 1.0,
    ) -> "torch.Tensor":
        masked  = masked_policy(policy_logits, legal_mask_t)
        p_loss  = nn.functional.cross_entropy(masked, target_actions)
        v_loss  = nn.functional.mse_loss(values, value_targets)
        return p_loss + value_weight * v_loss


# ── Smoke test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    game = BattleLineGame(["P1", "P2"])
    vec  = encode(game, pov=0)

    print("Block sizes:")
    for name, size in BLOCK_SIZES.items():
        print(f"  {name:12s}: {size}")
    print(f"  {'TOTAL':12s}: {TOTAL_DIM}")
    print(f"Encoded length : {len(vec)}  (expected {TOTAL_DIM})")
    assert len(vec) == TOTAL_DIM, "Dimension mismatch!"

    if TORCH_AVAILABLE:
        net = BattleLineNet()
        t   = to_tensor(game, pov=0)
        pl, v = net(t)
        print(f"Policy logits  : {pl.shape}")
        print(f"Value          : {v.item():.4f}")
        total_params = sum(p.numel() for p in net.parameters())
        print(f"Parameters     : {total_params:,}")
