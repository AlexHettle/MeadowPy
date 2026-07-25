# Variables & Types
# A variable is a name that stores a value.
# Python figures out the type automatically.

# Text is called a "string" (str)
name = "Alice"

# Whole numbers are "integers" (int)
age = 14

# Numbers with decimals are "floats" (float)
height = 5.6

# True/False values are "booleans" (bool)
likes_python = True

# type() tells you what kind of data a variable holds
print(f"name = {name} (type: {type(name).__name__})")
print(f"age = {age} (type: {type(age).__name__})")
print(f"height = {height} (type: {type(height).__name__})")
print(f"likes_python = {likes_python} (type: {type(likes_python).__name__})")

# You can change a variable's value at any time
age = age + 1
print(f"\nHappy birthday! Now age = {age}")
