# Lambda & Map/Filter
# Lambda creates small one-line functions.
# map() and filter() apply functions to sequences.

# A lambda is a function without a name
# Normal function:
def double(x):
    return x * 2

# Same thing as a lambda:
double_lambda = lambda x: x * 2

print(f"double(5) = {double(5)}")
print(f"lambda(5) = {double_lambda(5)}")

# === map() — apply a function to every item ===
numbers = [1, 2, 3, 4, 5]
doubled = list(map(lambda x: x * 2, numbers))
print(f"\nOriginal: {numbers}")
print(f"Doubled:  {doubled}")

# === filter() — keep only items that pass a test ===
numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
evens = list(filter(lambda x: x % 2 == 0, numbers))
print(f"\nAll:   {numbers}")
print(f"Evens: {evens}")

# === Sorting with lambda ===
# Sort a list of tuples by the second element
scores = [("Alice", 92), ("Bob", 85), ("Charlie", 95)]
by_score = sorted(scores, key=lambda pair: pair[1], reverse=True)
print("\nRanked by score:")
for name, score in by_score:
    print(f"  {name}: {score}")
