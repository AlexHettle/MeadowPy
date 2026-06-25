# Hangman
# Guess the hidden word one letter at a time!

import random

words = ["python", "coding", "function", "variable", "string"]
secret = random.choice(words)
guessed = set()      # Letters the player has guessed
max_wrong = 6        # Number of wrong guesses allowed
wrong = 0

print("=== Hangman ===")
print(f"The word has {len(secret)} letters.\n")

while wrong < max_wrong:
    # Show the word with blanks for unguessed letters
    display = ""
    for letter in secret:
        if letter in guessed:
            display += letter + " "
        else:
            display += "_ "
    print(f"Word: {display}")
    print(f"Wrong guesses left: {max_wrong - wrong}")
    print(f"Guessed: {', '.join(sorted(guessed)) or 'none'}")

    # Check if the player won
    if all(letter in guessed for letter in secret):
        print(f"\nYou win! The word was \"{secret}\"!")
        break

    # Get a guess
    guess = input("\nGuess a letter: ").lower().strip()
    if len(guess) != 1 or not guess.isalpha():
        print("Please enter a single letter.")
        continue
    if guess in guessed:
        print("You already guessed that!")
        continue

    guessed.add(guess)
    if guess in secret:
        print(f"Correct! \"{guess}\" is in the word!")
    else:
        wrong += 1
        print(f"Wrong! \"{guess}\" is not in the word.")
    print()
else:
    print(f"\nGame over! The word was \"{secret}\".")
