# User Input
# input() pauses the program and waits for the user to type.
# It always returns a string, so convert if you need a number.

# Basic input
name = input("What is your name? ")
print(f"Nice to meet you, {name}!")

# Getting a number with validation
# If the user types something that isn't a number, handle it.
while True:
    answer = input("\nPick a number between 1 and 10: ")
    if not answer.isdigit():
        print("That's not a number! Try again.")
        continue
    num = int(answer)
    if 1 <= num <= 10:
        break
    print("Out of range! Must be 1-10.")

print(f"You picked {num}!")

# Building a simple menu
print("\n--- Favorite Color ---")
print("1. Red")
print("2. Blue")
print("3. Green")
choice = input("Choose 1, 2, or 3: ")

colors = {"1": "Red", "2": "Blue", "3": "Green"}
color = colors.get(choice, "Unknown")
print(f"You chose: {color}")
