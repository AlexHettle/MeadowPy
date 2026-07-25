# List Comprehensions
# A compact way to create lists from other lists.

# The long way — using a for loop:
squares = []
for x in range(1, 6):
    squares.append(x ** 2)
print(f"Squares (loop): {squares}")

# The short way — list comprehension:
# [expression for item in iterable]
squares = [x ** 2 for x in range(1, 6)]
print(f"Squares (comp): {squares}")

# With a condition — only include even numbers
evens = [x for x in range(1, 11) if x % 2 == 0]
print(f"\nEvens 1-10: {evens}")

# Transform strings
words = ["hello", "world", "python"]
upper_words = [w.upper() for w in words]
print(f"Uppercased: {upper_words}")

# Practical example: Fahrenheit to Celsius
fahrenheit = [32, 68, 77, 100, 212]
celsius = [round((f - 32) * 5 / 9, 1) for f in fahrenheit]
print(f"\nFahrenheit: {fahrenheit}")
print(f"Celsius:    {celsius}")
