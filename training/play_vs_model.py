#!/usr/bin/env python3
"""Play Battle Line against the trained neural network model."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch
from battleline import BattleLineGame, Card
from battleline_features import (
    BattleLineNet,
    legal_troop_moves,
    to_tensor,
)


def load_model(model_path: str = "battleline_model.pt"):
    model = BattleLineNet()
    model.load_state_dict(torch.load(model_path, weights_only=True))
    model.eval()
    return model


def nn_choose_move(game: BattleLineGame, player: int, model):
    moves = legal_troop_moves(game, player)
    if not moves:
        return None
    with torch.no_grad():
        logits, _ = model(to_tensor(game, player))
        logits = logits.squeeze(0).cpu().numpy()
    return max(moves, key=lambda m: logits[m[2]])


def display_board(game: BattleLineGame):
    print("\n" + "=" * 60)
    print(f"Turn: {game.turn}")
    print(f"Hands: {game.names[0]} has {len(game.hands[0])} cards, "
          f"{game.names[1]} has {len(game.hands[1])} cards")
    print("=" * 60)
    for i, totem in enumerate(game.totems):
        status = ""
        if totem.claimed is not None:
            status = f" [CLAIMED by {game.names[totem.claimed]}]"
        if totem.fog:
            status += " [FOG]"
        if totem.mud:
            status += " [MUD]"
        print(f"Totem {i+1}:  P0: {len(totem.sides[0])} cards  "
              f"P1: {len(totem.sides[1])} cards{status}")
    print("\nClaimed totems:")
    for i in range(2):
        print(f"  {game.names[i]}: {sum(1 for t in game.totems if t.claimed == i)}")


def display_hand(game: BattleLineGame, player: int):
    print(f"\nYour hand ({game.names[player]}):")
    for i, card in enumerate(game.hands[player]):
        print(f"  {i}: {card}")


def main():
    print("Battle Line: Play vs Neural Network Model")
    print("=========================================\n")

    try:
        model = load_model("battleline_model.pt")
        print("Model loaded.\n")
    except Exception as e:
        print(f"Failed to load model: {e}")
        return 1

    game = BattleLineGame(["You", "AI"])
    print("You are Player 0. Goal: claim 5 totems, or 3 consecutive.\n")

    while game.winner is None:
        player   = game.turn % 2
        is_human = (player == 0)

        if is_human:
            display_board(game)
            display_hand(game, player)
            while True:
                try:
                    parts = input("\nEnter move (card_idx totem_idx): ").strip().split()
                    if len(parts) != 2:
                        print("Use: card_idx totem_idx")
                        continue
                    card_idx, totem_idx = int(parts[0]), int(parts[1])
                    card = game.hands[player][card_idx]
                    if not isinstance(card, Card):
                        print("Must play a troop card.")
                        continue
                    print(game.play_card(player, card, totem_idx))
                    game.draw_card(player)
                    game.turn += 1
                    break
                except (ValueError, IndexError, Exception) as e:
                    print(f"Error: {e}")
        else:
            move = nn_choose_move(game, player, model)
            if move is None:
                print("AI has no legal moves.")
                break
            card, totem_idx, _ = move
            print(f"\nAI plays: {game.play_card(player, card, totem_idx)}")
            game.draw_card(player)
            game.turn += 1

    display_board(game)
    if game.winner is not None:
        print(f"\nGame Over! {game.names[game.winner]} wins!")
    else:
        p0 = sum(1 for t in game.totems if t.claimed == 0)
        p1 = sum(1 for t in game.totems if t.claimed == 1)
        if p0 > p1:
            print(f"\nGame Over! {game.names[0]} wins by totem count!")
        elif p1 > p0:
            print(f"\nGame Over! {game.names[1]} wins by totem count!")
        else:
            print("\nGame Over! Draw.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
