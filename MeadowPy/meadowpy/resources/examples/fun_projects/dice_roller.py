# Dice Roller
# Roll dice and see the statistics!

import random

def roll_dice(num_dice=2, sides=6):
    """Roll some dice and return the results."""
    rolls = [random.randint(1, sides) for _ in range(num_dice)]
    return rolls

# Roll a pair of dice
print("=== Dice Roller ===")
dice = roll_dice(2, 6)
print(f"You rolled: {dice[0]} and {dice[1]}")
print(f"Total: {sum(dice)}")

# Roll many times and track the results
num_rolls = 1000
totals = {}
for _ in range(num_rolls):
    total = sum(roll_dice(2, 6))
    totals[total] = totals.get(total, 0) + 1

print(f"\nRolling 2 dice {num_rolls} times:")
print(f"{'Total':>6} {'Count':>6} {'Pct':>6}  Distribution")
print("-" * 50)
for value in range(2, 13):
    count = totals.get(value, 0)
    pct = count / num_rolls * 100
    bar = "#" * int(pct)
    print(f"{value:>6} {count:>6} {pct:>5.1f}%  {bar}")

print(f"\n7 is the most common total because there")
print(f"are the most ways to make it (1+6, 2+5, 3+4, etc.)")
