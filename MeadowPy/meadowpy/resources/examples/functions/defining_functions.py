# Defining Functions
# A function is a reusable block of code.
# Use "def" to define one.

# A simple function with no parameters
def say_hello():
    print("Hello there!")

say_hello()  # Call the function

# A function with parameters (inputs)
def greet(name):
    print(f"Hello, {name}!")

greet("Alice")
greet("Bob")

# A function that returns a value
def add(a, b):
    return a + b

result = add(3, 5)
print(f"\n3 + 5 = {result}")

# Default parameter values
def power(base, exponent=2):
    """Raise base to exponent. Defaults to squaring."""
    return base ** exponent

print(f"\npower(4) = {power(4)}")        # Uses default: 4^2
print(f"power(2, 10) = {power(2, 10)}")  # Override: 2^10

# Functions can return multiple values (as a tuple)
def min_max(numbers):
    return min(numbers), max(numbers)

lowest, highest = min_max([4, 7, 1, 9, 3])
print(f"\nMin: {lowest}, Max: {highest}")
