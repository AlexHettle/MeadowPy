# Recursion
# A recursive function calls itself to solve smaller
# pieces of the same problem.

# === Factorial ===
# 5! = 5 * 4 * 3 * 2 * 1 = 120
def factorial(n):
    # Base case: stop recursing
    if n <= 1:
        return 1
    # Recursive case: n! = n * (n-1)!
    return n * factorial(n - 1)

print(f"5! = {factorial(5)}")
print(f"10! = {factorial(10)}")

# === Fibonacci ===
# Each number is the sum of the two before it
# 0, 1, 1, 2, 3, 5, 8, 13, 21, ...
def fibonacci(n):
    if n <= 0:
        return 0
    if n == 1:
        return 1
    return fibonacci(n - 1) + fibonacci(n - 2)

print("\nFibonacci sequence:")
for i in range(10):
    print(f"  fib({i}) = {fibonacci(i)}")

# === Countdown with recursion ===
def countdown(n):
    if n <= 0:
        print("Liftoff!")
        return
    print(f"  {n}...")
    countdown(n - 1)

print("\nCountdown:")
countdown(5)
