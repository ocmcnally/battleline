"""Battle Line neural-network feature extractor.

This module converts a BattleLineGame state into fixed-size numeric features
for a policy/value network. It currently focuses on troop cards and board
state, ignoring tactics card details by default.
"""

from __future__ import annotations

from typing import Dict, Iterable, List

try:
    import torch
    from torch import nn
    TORCH_AVAILABLE = True
except ImportError:  # pragma: no cover
    torch = None
    nn = None
    TORCH_AVAILABLE = False

from battleline import (
    BattleLineGame,
    Card,
    TacticsCard,
    WildCard,
    SUITS,
    NUM_TOTEMS,
    CARDS_TO_WIN,
)

CARD_COUNT = len(SUITS) * 10
TACTICS_NAMES = [
    "alexander",
    "darius",
    "wild8",
    "wild321",
    "fog",
    "mud",
    "scout",
    "redeploy",
    "traitor",
    "deserter",
]

# shape constants for convenience
FEATURE_SIZES = {
    "hand": CARD_COUNT,
    "board": NUM_TOTEMS * 2 * CARD_COUNT,
    "unplayed": CARD_COUNT,
    "totem_meta": NUM_TOTEMS * 5,
    "tactics_hand": len(TACTICS_NAMES),
    "tactics_seen": len(TACTICS_NAMES),
}


def feature_size(include_tactics_hand: bool = False) -> int:
    """Calculate the total feature dimension for the current configuration."""
    base_size = (
        FEATURE_SIZES["hand"] +  # player's hand
        FEATURE_SIZES["board"] +  # all totem sides
        FEATURE_SIZES["unplayed"] +  # unplayed cards
        FEATURE_SIZES["totem_meta"] +  # totem metadata
        5  # turn info: to_move, troop_deck_remaining, tactics_deck_remaining, hand_count[2]
    )
    if include_tactics_hand:
        base_size += FEATURE_SIZES["tactics_hand"]
    return base_size


def _card_index(card: Card) -> int:
    if isinstance(card, WildCard):
        raise ValueError("Wild cards are not part of the troop-card feature plane")
    if not isinstance(card, Card):
        raise ValueError("Only Card instances may be encoded as troop cards")
    suit_index = SUITS.index(card.suit)
    return suit_index * 10 + (card.value - 1)


def card_to_one_hot(card: Card) -> List[int]:
    """Return a 60-dimensional one-hot vector for a troop card."""
    vec = [0] * CARD_COUNT
    if isinstance(card, Card) and not isinstance(card, WildCard):
        vec[_card_index(card)] = 1
    return vec


def cards_to_vector(cards: Iterable[Card]) -> List[int]:
    """Encode a troop-card list as a 60-dimensional count vector."""
    vec = [0] * CARD_COUNT
    for card in cards:
        if isinstance(card, Card) and not isinstance(card, WildCard):
            vec[_card_index(card)] += 1
    return vec


def encode_hand(game: BattleLineGame, player: int) -> List[int]:
    """Encode the current player's troop cards in hand."""
    return cards_to_vector([card for card in game.hands[player]
                             if isinstance(card, Card) and not isinstance(card, WildCard)])


def encode_tactics_hand(game: BattleLineGame, player: int) -> List[int]:
    """Encode the current player's tactics cards as a fixed-length vector."""
    counts = [0] * len(TACTICS_NAMES)
    for card in game.hands[player]:
        if isinstance(card, TacticsCard):
            try:
                counts[TACTICS_NAMES.index(card.name)] += 1
            except ValueError:
                pass
    return counts


def encode_board(game: BattleLineGame) -> List[int]:
    """Encode the full board state as a flattened 9 × 2 × 60 vector."""
    out: List[int] = []
    for totem in game.totems:
        for side in totem.sides:
            out.extend(cards_to_vector([card for card in side
                                        if isinstance(card, Card) and not isinstance(card, WildCard)]))
    return out


def encode_totem_metadata(game: BattleLineGame, perspective_player: int) -> List[int]:
    """Encode fog/mud/claim metadata for each totem from a player's perspective."""
    out: List[int] = []
    for totem in game.totems:
        claimed = totem.claimed
        if claimed is None:
            out.extend([1, 0, 0])
        elif claimed == perspective_player:
            out.extend([0, 1, 0])
        else:
            out.extend([0, 0, 1])
        out.append(1 if totem.fog else 0)
        out.append(1 if totem.mud else 0)
    return out


def encode_unplayed(game: BattleLineGame) -> List[int]:
    """Encode the troop cards that are not on any totem and not discarded."""
    return cards_to_vector(game._unplayed_cards())


def encode_game_state(
    game: BattleLineGame,
    player: int,
    include_hand: bool = True,
    include_board: bool = True,
    include_unplayed: bool = True,
    include_totem_meta: bool = True,
    include_turn_info: bool = True,
    include_tactics_hand: bool = False,
) -> Dict[str, List[int]]:
    """Return structured feature planes for the given game state and player."""
    features: Dict[str, List[int]] = {}
    if include_hand:
        features["hand"] = encode_hand(game, player)
    if include_board:
        features["board"] = encode_board(game)
    if include_unplayed:
        features["unplayed"] = encode_unplayed(game)
    if include_totem_meta:
        features["totem_meta"] = encode_totem_metadata(game, player)
    if include_turn_info:
        features["to_move"] = [1 if game.turn % 2 == player else 0]
        features["troop_deck_remaining"] = [len(game.deck) / CARD_COUNT]
        features["tactics_deck_remaining"] = [len(game.tactics_deck) / len(TACTICS_NAMES)]
        features["hand_count"] = [len(game.hands[player]), len(game.hands[1 - player])]
    if include_tactics_hand:
        features["tactics_hand"] = encode_tactics_hand(game, player)
    return features


def flatten_features(features: Dict[str, List[int]]) -> List[int]:
    """Flatten a feature dictionary into a single flat list in sorted key order."""
    out: List[int] = []
    for key in sorted(features):
        out.extend(features[key])
    return out


POLICY_DIM = NUM_TOTEMS * CARD_COUNT


def policy_index(card: Card, totem_index: int) -> int:
    """Convert a troop card + totem into a flat policy action index."""
    return totem_index * CARD_COUNT + _card_index(card)


def policy_move_from_index(index: int) -> tuple[int, int]:
    """Convert a flat policy index into (card_index, totem_index)."""
    totem_index = index // CARD_COUNT
    card_index = index % CARD_COUNT
    return card_index, totem_index


def legal_troop_move_mask(game: BattleLineGame, player: int) -> List[int]:
    """Return a binary mask for legal troop-card placement actions."""
    mask = [0] * POLICY_DIM
    for card in game.hands[player]:
        if not isinstance(card, Card) or isinstance(card, WildCard):
            continue
        for ti, totem in enumerate(game.totems):
            if totem.claimed is None and not totem.is_full(player):
                mask[policy_index(card, ti)] = 1
    return mask


def legal_troop_moves(game: BattleLineGame, player: int) -> List[tuple[Card, int, int]]:
    """List all legal troop-card placement moves for the current player."""
    moves: List[tuple[Card, int, int]] = []
    for card in game.hands[player]:
        if not isinstance(card, Card) or isinstance(card, WildCard):
            continue
        for ti, totem in enumerate(game.totems):
            if totem.claimed is None and not totem.is_full(player):
                moves.append((card, ti, policy_index(card, ti)))
    return moves


def policy_target_from_move(card: Card, totem_index: int) -> List[int]:
    """Return a one-hot policy target vector for a troop-card move."""
    target = [0] * POLICY_DIM
    target[policy_index(card, totem_index)] = 1
    return target


def features_to_tensor(
    features: Dict[str, List[int]],
    dtype: "torch.dtype" = torch.float32 if TORCH_AVAILABLE else None,
    device: str | "torch.device" = "cpu",
) -> "torch.Tensor":
    """Convert flattened Battle Line features to a PyTorch tensor."""
    if not TORCH_AVAILABLE:
        raise ImportError("PyTorch is required for features_to_tensor(). Install torch and retry.")
    flat = flatten_features(features)
    return torch.tensor(flat, dtype=dtype, device=device).unsqueeze(0)


if TORCH_AVAILABLE:
    class BattleLineNet(nn.Module):
        """Simple MLP for Battle Line policy and value prediction."""

        def __init__(self,
                     input_dim: int,
                     hidden_dims: tuple[int, ...] = (1024, 512, 256),
                     policy_dim: int = POLICY_DIM,
        ):
            super().__init__()
            layers = []
            prev_dim = input_dim
            for dim in hidden_dims:
                layers.append(nn.Linear(prev_dim, dim))
                layers.append(nn.ReLU(inplace=True))
                prev_dim = dim
            self.body = nn.Sequential(*layers)
            self.policy_head = nn.Linear(prev_dim, policy_dim)
            self.value_head = nn.Linear(prev_dim, 1)

        def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
            """Return (policy_logits, value) for a batch of feature vectors."""
            hidden = self.body(x)
            policy_logits = self.policy_head(hidden)
            value = torch.tanh(self.value_head(hidden)).squeeze(-1)
            return policy_logits, value

    def mask_policy_logits(policy_logits: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        """Apply a legal-action mask to policy logits."""
        neg_inf = torch.finfo(policy_logits.dtype).min / 2
        return policy_logits.masked_fill(~mask, neg_inf)


    def policy_value_loss(
        policy_logits: torch.Tensor,
        values: torch.Tensor,
        target_actions: torch.Tensor,
        legal_mask: torch.Tensor,
        value_targets: torch.Tensor,
        value_weight: float = 1.0,
    ) -> torch.Tensor:
        """Compute combined policy and value loss for a batch."""
        masked_logits = mask_policy_logits(policy_logits, legal_mask)
        policy_loss = torch.nn.functional.cross_entropy(masked_logits, target_actions)
        value_loss = torch.nn.functional.mse_loss(values, value_targets)
        return policy_loss + value_weight * value_loss


    def build_default_model(include_tactics_hand: bool = False) -> BattleLineNet:
        """Create a default BattleLineNet using the current feature dimensions."""
        return BattleLineNet(input_dim=feature_size(include_tactics_hand))
else:  # pragma: no cover
    def build_default_model(include_tactics_hand: bool = False):
        raise ImportError("PyTorch is not installed. Install torch to create a BattleLineNet.")


if __name__ == "__main__":
    game = BattleLineGame(["Player 1", "Player 2"])
    features = encode_game_state(game, player=0, include_tactics_hand=True)
    tensor = None
    if TORCH_AVAILABLE:
        tensor = features_to_tensor(features)
    flat = flatten_features(features)
    print("Encoded features:")
    for name, value_list in features.items():
        print(f"  {name}: {len(value_list)}")
    print(f"Total flattened feature length: {len(flat)}")
    if TORCH_AVAILABLE:
        model = build_default_model(include_tactics_hand=True)
        policy_logits, value = model(tensor)
        print(f"Policy logits shape: {policy_logits.shape}")
        print(f"Value shape: {value.shape}")
