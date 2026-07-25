# Password Generator
# Creates random passwords of any length.

import random
import string

# string module gives us character sets
# string.ascii_letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
# string.digits = "0123456789"
# string.punctuation = "!@#$%^&*()..." etc.

def generate_password(length=12, use_symbols=True):
    """Generate a random password of the given length."""
    characters = string.ascii_letters + string.digits
    if use_symbols:
        characters += string.punctuation

    # random.choices() picks random items from a sequence
    password = "".join(random.choices(characters, k=length))
    return password


print("=== Password Generator ===")
print()

length = int(input("Password length (default 12): ") or "12")
count = int(input("How many passwords? (default 5): ") or "5")
symbols = input("Include symbols? (y/n, default y): ").strip().lower()
use_symbols = symbols != "n"

print(f"\nGenerated passwords ({length} chars):")
for i in range(count):
    pwd = generate_password(length, use_symbols)
    print(f"  {i + 1}. {pwd}")
