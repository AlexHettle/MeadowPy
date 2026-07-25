# Math Operations
# Python can do all kinds of math.

# Basic arithmetic
a, b = 17, 5
print(f"{a} + {b} = {a + b}")     # Addition
print(f"{a} - {b} = {a - b}")     # Subtraction
print(f"{a} * {b} = {a * b}")     # Multiplication
print(f"{a} / {b} = {a / b}")     # Division (gives a float)
print(f"{a} // {b} = {a // b}")   # Floor division (whole number)
print(f"{a} % {b} = {a % b}")     # Modulo (remainder)
print(f"{a} ** {b} = {a ** b}")   # Power (17 to the 5th)

# Rounding
pi = 3.14159265
print(f"\nround(pi, 2) = {round(pi, 2)}")
print(f"round(pi, 4) = {round(pi, 4)}")

# The math module has more advanced functions
import math
print(f"\nmath.sqrt(144) = {math.sqrt(144)}")   # Square root
print(f"math.floor(3.7) = {math.floor(3.7)}")  # Round down
print(f"math.ceil(3.2) = {math.ceil(3.2)}")    # Round up
print(f"math.pi = {math.pi}")                  # Pi constant
