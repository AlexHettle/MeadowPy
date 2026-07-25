# Regular Expressions
# The "re" module lets you search for patterns in text.

import re

# === Finding patterns ===
text = "Call me at 555-1234 or 555-5678"

# \d means "any digit", {3} means "exactly 3 times"
phones = re.findall(r"\d{3}-\d{4}", text)
print(f"Phone numbers found: {phones}")

# === Common patterns ===
email_text = "Contact alice@example.com or bob@test.org"
emails = re.findall(r"[\w.]+@[\w.]+", email_text)
print(f"Emails found: {emails}")

# === Checking if a string matches ===
def is_valid_username(name):
    """Username must be 3-16 letters, numbers, or underscores."""
    return bool(re.match(r"^[a-zA-Z0-9_]{3,16}$", name))

usernames = ["alice_99", "ab", "good-name", "valid_user"]
print("\nUsername validation:")
for name in usernames:
    status = "valid" if is_valid_username(name) else "invalid"
    print(f"  {name:15} -> {status}")

# === Search and replace ===
messy = "too    many     spaces    here"
clean = re.sub(r"\s+", " ", messy)
print(f"\nCleaned: \"{clean}\"")

# === Splitting with a pattern ===
data = "apple, banana;  cherry,  date"
items = re.split(r"[,;]\s*", data)
print(f"\nSplit items: {items}")

# === Quick reference ===
# \d = digit    \w = word char    \s = whitespace
# .  = any char   *  = 0 or more   +  = 1 or more
# ^  = start      $  = end         [] = character set
