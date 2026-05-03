#!/usr/bin/env python3
"""Play Battle Line against the trained neural network model."""

import sys
import torch
from battleline import BattleLineGame, Card
from battleline_nn import (
    build_default_model,
    encode_game_state,
    features_to_tensor,
    legal_troop_moves,
)

def load_model(model_path: str = "battleline_model.pt"):
    """Load the trained model from a checkpoint."""
    model = build_default_model()
    model.load_state_dict(torch.load(model_path))
    model.eval()
    return model

def nn_choose_move(game: BattleLineGame, player: int, model):
    """Use the neural network to choose the best move."""
    moves = legal_troop_moves(game, player)
    if not moves:
        return None
    
    best_move = None
    best_logit = float('-inf')
    
    with torch.no_grad():
        features = encode_game_state(game, player=player)
        tensor = features_to_tensor(features)
        policy_logits, _ = model(tensor)
        logits = policy_logits.squeeze(0).cpu().numpy()
    
    # Find the highest-logit legal move
    for card, ti, action_index in moves:
        if logits[action_index] > best_logit:
            best_logit = logits[action_index]
            best_move = (card, ti, action_index)
    
    return best_move

def display_board(game: BattleLineGame):
    """Display the current game board."""
    print("\n" + "="*60)
    print(f"Turn: {game.turn}")
    print(f"Hands: {game.names[0]} has {len(game.hands[0])} cards, {game.names[1]} has {len(game.hands[1])} cards")
    print("="*60)
    
    for i, totem in enumerate(game.totems):
        p0_cards = f"  P0: {len(totem.sides[0])} cards"
        p1_cards = f"  P1: {len(totem.sides[1])} cards"
        status = ""
        if totem.claimed is not None:
            status = f" [CLAIMED by {game.names[totem.claimed]}]"
        if totem.fog:
            status += " [FOG]"
        if totem.mud:
            status += " [MUD]"
        print(f"Totem {i+1}: {p0_cards} {p1_cards}{status}")
    
    print("\nClaimed totems:")
    for i in range(2):
        claimed_count = sum(1 for t in game.totems if t.claimed == i)
        print(f"  {game.names[i]}: {claimed_count}")

def display_hand(game: BattleLineGame, player: int):
    """Display the player's hand."""
    print(f"\nYour hand ({game.names[player]}):")
    hand = game.hands[player]
    for i, card in enumerate(hand):
        print(f"  {i}: {card}")

def main():
    print("Battle Line: Play vs Neural Network Model")
    print("=========================================\n")
    
    # Load model
    print("Loading trained model...")
    try:
        model = load_model("battleline_model.pt")
        print("✓ Model loaded successfully!\n")
    except Exception as e:
        print(f"✗ Failed to load model: {e}")
        return 1
    
    # Create game
    game = BattleLineGame(["You", "AI"])
    print("Game started! You are playing as 'You', AI plays as 'AI'")
    print("Your goal: Claim 5 totems first or have the most claimed totems when the deck runs out.\n")
    
    # Main game loop
    while game.winner is None:
        player = game.turn % 2
        is_human = (player == 0)
        
        if is_human:
            display_board(game)
            display_hand(game, player)
            
            # Get human move
            while True:
                try:
                    move_input = input("\nEnter move (card_index totem_index): ").strip().split()
                    if len(move_input) != 2:
                        print("Invalid format. Use: card_index totem_index")
                        continue
                    
                    card_idx, totem_idx = int(move_input[0]), int(move_input[1])
                    
                    if card_idx < 0 or card_idx >= len(game.hands[player]):
                        print("Invalid card index")
                        continue
                    if totem_idx < 0 or totem_idx >= len(game.totems):
                        print("Invalid totem index")
                        continue
                    
                    card = game.hands[player][card_idx]
                    if not isinstance(card, Card):
                        print("Must play a troop card (not tactics)")
                        continue
                    
                    msg = game.play_card(player, card, totem_idx)
                    print(f"\n{msg}")
                    
                    # Draw card
                    if game.deck:
                        game.hands[player].append(game.deck.pop())
                    
                    game.turn += 1
                    break
                    
                except (ValueError, IndexError) as e:
                    print(f"Error: {e}")
                except Exception as e:
                    print(f"Invalid move: {e}")
        else:
            # AI move
            move = nn_choose_move(game, player, model)
            if move is None:
                print("\nAI has no legal moves - game may end based on claims.")
                break
            
            card, totem_idx, _ = move
            msg = game.play_card(player, card, totem_idx)
            print(f"\nAI's move: {msg}")
            
            # Draw card
            if game.deck:
                game.hands[player].append(game.deck.pop())
            
            game.turn += 1
    
    # Game over
    display_board(game)
    if game.winner is not None:
        print(f"\n🎉 Game Over! {game.names[game.winner]} wins!")
    else:
        # Determine winner by claimed totems
        p0_claimed = sum(1 for t in game.totems if t.claimed == 0)
        p1_claimed = sum(1 for t in game.totems if t.claimed == 1)
        if p0_claimed > p1_claimed:
            print(f"\n🎉 Game Over! {game.names[0]} wins by claiming {p0_claimed} totems!")
        elif p1_claimed > p0_claimed:
            print(f"\n🎉 Game Over! {game.names[1]} wins by claiming {p1_claimed} totems!")
        else:
            print(f"\n🤝 Game Over! It's a draw!")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
