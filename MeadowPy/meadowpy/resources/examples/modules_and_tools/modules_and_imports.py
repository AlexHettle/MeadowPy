# Modules & Imports
# Modules let you organize code into reusable files.

# === Importing built-in modules ===
import math
print(f"Pi: {math.pi}")
print(f"Square root of 16: {math.sqrt(16)}")

# === Import specific things ===
from random import randint, choice
print(f"\nRandom number 1-10: {randint(1, 10)}")
print(f"Random fruit: {choice(['apple', 'banana', 'cherry'])}")

# === Import with an alias ===
import datetime as dt
now = dt.datetime.now()
print(f"\nCurrent time: {now.strftime('%H:%M')}")

# === Exploring a module ===
import os
print(f"\nCurrent directory: {os.getcwd()}")
print(f"Your username: {os.getlogin()}")

# === Using the platform module ===
import platform
print(f"\nPython version: {platform.python_version()}")
print(f"Operating system: {platform.system()}")

# === How to create your own module ===
# 1. Create a file called "mytools.py"
# 2. Put functions in it:
#    def greet(name):
#        return f"Hello, {name}!"
# 3. Import it in another file:
#    from mytools import greet
#    print(greet("Alice"))

print("\nTip: Use 'import this' to see the Zen of Python!")
