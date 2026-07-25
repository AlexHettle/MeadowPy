# Tuples & Sets
# Two more useful data structures in Python.

# === TUPLES ===
# A tuple is like a list but cannot be changed (immutable).
# Tuples use parentheses: ()
point = (3, 7)
print(f"Point: {point}")
print(f"X: {point[0]}, Y: {point[1]}")

# Tuple unpacking — assign each item to a variable
x, y = point
print(f"Unpacked: x={x}, y={y}")

# Tuples are great for returning multiple values
rgb = ("red", "green", "blue")
for color in rgb:
    print(f"  Color: {color}")

# === SETS ===
# A set holds unique items (no duplicates).
# Sets use curly braces: {} (but no key:value pairs)
fruits = {"apple", "banana", "cherry", "apple"}  # Duplicate removed!
print(f"\nFruits set: {fruits}")

# Add and remove
fruits.add("mango")
fruits.discard("banana")  # Safe remove (no error if missing)
print(f"Updated: {fruits}")

# Set operations
a = {1, 2, 3, 4}
b = {3, 4, 5, 6}
print(f"\na = {a}")
print(f"b = {b}")
print(f"Union (a | b): {a | b}")          # All items
print(f"Intersection (a & b): {a & b}")    # Common items
print(f"Difference (a - b): {a - b}")      # In a but not b
