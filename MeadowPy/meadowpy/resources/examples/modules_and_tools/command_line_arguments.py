# Command-Line Arguments
# Scripts can accept input when run from the terminal.

import sys

# === sys.argv — the simplest approach ===
# sys.argv is a list of strings passed to the script
# sys.argv[0] is always the script name
print(f"Script name: {sys.argv[0]}")
print(f"All arguments: {sys.argv}")
print(f"Number of args: {len(sys.argv) - 1}")

# === argparse — the professional approach ===
import argparse

# Create a parser
parser = argparse.ArgumentParser(
    description="A demo script that greets you."
)

# Add arguments
parser.add_argument("name", help="Your name")
parser.add_argument(
    "-c", "--count",
    type=int,
    default=1,
    help="How many times to greet (default: 1)"
)
parser.add_argument(
    "-l", "--loud",
    action="store_true",
    help="Greet in uppercase"
)

# Parse (using demo args so this example runs without CLI)
args = parser.parse_args(["Alice", "--count", "3", "--loud"])

print(f"\nParsed arguments:")
print(f"  Name:  {args.name}")
print(f"  Count: {args.count}")
print(f"  Loud:  {args.loud}")

# Use the arguments
print()
for i in range(args.count):
    greeting = f"Hello, {args.name}!"
    if args.loud:
        greeting = greeting.upper()
    print(greeting)

# Try running from terminal:
#   python script.py Alice --count 3 --loud
#   python script.py --help
