# For Loops
# A "for" loop repeats code for each item in a sequence.

# Loop through a list of items
fruits = ["apple", "banana", "cherry"]
for fruit in fruits:
    print(f"I like {fruit}!")

# range() generates a sequence of numbers
# range(5) gives: 0, 1, 2, 3, 4
print("\nCounting to 5:")
for i in range(1, 6):  # range(1, 6) gives: 1, 2, 3, 4, 5
    print(f"  {i}")

# enumerate() gives you both the index and the item
colors = ["red", "green", "blue"]
print("\nColors list:")
for index, color in enumerate(colors):
    print(f"  {index}: {color}")

# Nested loops (a loop inside a loop)
print("\nMultiplication table (1-5):")
for row in range(1, 6):
    for col in range(1, 6):
        # end=" " prints without a newline
        print(f"{row * col:4}", end="")
    print()  # New line after each row
