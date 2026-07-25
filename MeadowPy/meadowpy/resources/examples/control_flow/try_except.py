# Try / Except
# Errors happen! try/except lets you handle them
# instead of crashing your program.

# Without try/except, this would crash:
#   int("hello")  -> ValueError!

# With try/except, we catch the error:
try:
    num = int(input("Enter a number: "))
    print(f"Your number doubled: {num * 2}")
except ValueError:
    print("That wasn't a valid number!")

# You can catch different error types
def safe_divide(a, b):
    try:
        result = a / b
    except ZeroDivisionError:
        print("Cannot divide by zero!")
        return None
    except TypeError:
        print("Both arguments must be numbers!")
        return None
    else:
        # Runs only if NO exception happened
        print(f"{a} / {b} = {result}")
        return result
    finally:
        # Runs ALWAYS, error or not
        print("--- division attempted ---")

print()
safe_divide(10, 3)
print()
safe_divide(10, 0)
print()
safe_divide(10, "two")
