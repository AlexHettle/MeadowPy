# String Formatting
# Strings are text — you can combine and format them.

first = "Ada"
last = "Lovelace"

# Method 1: Concatenation (joining with +)
full_name = first + " " + last
print("Concatenation:", full_name)

# Method 2: f-strings (recommended!) — put variables inside {}
print(f"f-string: {first} {last}")

# f-strings can contain expressions too
price = 9.99
quantity = 3
print(f"Total: ${price * quantity:.2f}")  # :.2f means 2 decimal places

# Useful string methods
message = "  Hello, World!  "
print(f"Upper: {message.upper()}")       # ALL CAPS
print(f"Lower: {message.lower()}")       # all lowercase
print(f"Strip: '{message.strip()}'")     # remove extra spaces
print(f"Replace: {message.replace('World', 'Python')}")
print(f"Length: {len(message)} characters")
