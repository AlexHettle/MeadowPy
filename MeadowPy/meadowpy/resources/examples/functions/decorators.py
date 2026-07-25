# Decorators
# A decorator wraps a function to add extra behavior
# without changing the original function's code.

import time

# === Building a decorator step by step ===
# A decorator is just a function that takes a function
# and returns a new function.

def timer(func):
    """Measure how long a function takes to run."""
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        print(f"  {func.__name__} took {elapsed:.4f} seconds")
        return result
    return wrapper

# Apply it with the @ symbol
@timer
def slow_add(a, b):
    time.sleep(0.1)  # Simulate slow work
    return a + b

print(f"Result: {slow_add(3, 5)}")

# === Another example: a repeat decorator ===
def repeat(n):
    """Run a function n times."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            for i in range(n):
                result = func(*args, **kwargs)
            return result
        return wrapper
    return decorator

@repeat(3)
def say_hello(name):
    print(f"Hello, {name}!")

print()
say_hello("Alice")  # Prints 3 times!
