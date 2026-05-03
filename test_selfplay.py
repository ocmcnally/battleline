#!/usr/bin/env python3
"""Test self-play generation with updated claiming logic."""

from battleline import BattleLineGame
from battleline_nn import legal_troop_moves
from battleline import evaluate_hand, best_possible_hand

def choose_expert_troop_move(game: BattleLineGame, player: int):
    """Choose the best troop-card placement move from the current state."""
    unplayed = game._unplayed_cards()
    best_move = None
    best_score = ((-1,), -1, -1)

    for card, ti, action_index in legal_troop_moves(game, player):
        totem = game.totems[ti]
        played = totem.sides[player] + [card]
        avail = [c for c in unplayed if c != card]
        rank = best_possible_hand(played, avail,
                                  cards_to_win=totem.cards_to_win,
                                  fog=totem.fog) or (0,)
        score = (rank, len(played), -ti)
        if score > best_score:
            best_score = score
            best_move = (card, ti, action_index)
    return best_move

def generate_game():
    """Generate a single self-play game."""
    game = BattleLineGame(["Player1", "Player2"])
    moves = []
    turn = 0

    while game.winner is None:
        player = turn % 2
        move = choose_expert_troop_move(game, player)
        if move is None:
            print(f"No legal moves for player {player} at turn {turn}")
            print(f"Game state: {game}")
            return None  # Error

        card, ti, action_index = move
        try:
            msg = game.play_card(player, card, ti)
            moves.append((player, card, ti, action_index))
            # Draw new card
            if game.deck:
                game.hands[player].append(game.deck.pop())
        except Exception as e:
            print(f"Error playing move: {e}")
            return None

        turn += 1
        if turn > 1000:  # Safety
            print("Game too long")
            return None

    return moves, game.winner

if __name__ == "__main__":
    print("Testing self-play generation...")
    for i in range(5):
        result = generate_game()
        if result is None:
            print(f"Game {i+1} failed")
            break
        else:
            moves, winner = result
            print(f"Game {i+1} completed: {len(moves)} moves, winner: {winner}")
    else:
        print("All test games completed successfully!")