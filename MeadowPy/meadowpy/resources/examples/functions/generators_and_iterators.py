# Generators & Iterators
# Generators produce values one at a time, saving memory.

# === A simple generator function uses "yield" ===
def countdown(n):
    """Count down from n to 1."""
    while n > 0:
        yield n  # Pauses here, returns n, resumes on next()
        n -= 1

print("Countdown:")
for num in countdown(5):
    print(f"  {num}...")
print("  Go!")

# === Generators are lazy — they don't compute everything upfront ===
def fibonacci():
    """Generate Fibonacci numbers forever."""
    a, b = 0, 1
    while True:
        yield a
        a, b = b, a + b

# Take just the first 10 Fibonacci numbers
fib = fibonacci()
first_10 = [next(fib) for _ in range(10)]
print(f"\nFirst 10 Fibonacci: {first_10}")

# === Generator expressions (like list comprehensions, but lazy) ===
# List comprehension — creates all values in memory
squares_list = [x**2 for x in range(1000000)]

# Generator expression — creates values on demand
squares_gen = (x**2 for x in range(1000000))

print(f"\nList size: {squares_list.__sizeof__()} bytes")
print(f"Generator size: {squares_gen.__sizeof__()} bytes")

# === Practical example: reading large data ===
def even_numbers(limit):
    """Generate even numbers up to limit."""
    for n in range(0, limit + 1, 2):
        yield n

total = sum(even_numbers(100))
print(f"\nSum of even numbers 0-100: {total}")
