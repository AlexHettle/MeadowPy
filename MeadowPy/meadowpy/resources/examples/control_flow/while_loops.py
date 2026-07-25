# While Loops
# A "while" loop repeats as long as a condition is true.

# Simple countdown
count = 5
print("Countdown:")
while count > 0:
    print(f"  {count}...")
    count -= 1  # Same as: count = count - 1
print("  Liftoff!")

# "break" exits the loop immediately
# "continue" skips to the next iteration
print("\nType 'quit' to exit, or a number to double it:")
while True:  # Runs forever until we break
    text = input("> ")

    if text == "quit":
        print("Goodbye!")
        break  # Exit the loop

    # Try to convert to a number
    # If it fails, "continue" skips back to the top
    if not text.lstrip("-").isdigit():
        print("That's not a number. Try again.")
        continue  # Skip the rest, go back to top

    number = int(text)
    print(f"{number} * 2 = {number * 2}")
