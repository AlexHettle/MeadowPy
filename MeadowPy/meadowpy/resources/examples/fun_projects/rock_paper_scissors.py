# Rock Paper Scissors
# Play against the computer!

import random

choices = ["rock", "paper", "scissors"]
wins = 0
losses = 0

print("=== Rock Paper Scissors ===")
print("Type rock, paper, or scissors (or quit to stop)\n")

while True:
    player = input("Your choice: ").strip().lower()

    if player == "quit":
        break

    if player not in choices:
        print("Invalid choice! Try rock, paper, or scissors.")
        continue

    computer = random.choice(choices)
    print(f"Computer chose: {computer}")

    if player == computer:
        print("It's a tie!\n")
    elif (
        (player == "rock" and computer == "scissors") or
        (player == "paper" and computer == "rock") or
        (player == "scissors" and computer == "paper")
    ):
        print("You win!\n")
        wins += 1
    else:
        print("You lose!\n")
        losses += 1

print(f"\nFinal score: {wins} wins, {losses} losses")
