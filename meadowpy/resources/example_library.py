"""Built-in Python example library for beginners.

Organized by category, each example has a title, description,
and fully-commented source code.
"""

EXAMPLE_CATEGORIES = [
    {
        "name": "Basics",
        "icon": "\U0001F331",
        "examples": [
            {
                "name": "Variables & Types",
                "desc": "Storing data in variables and checking types",
                "code": (
                    '# Variables & Types\n'
                    '# A variable is a name that stores a value.\n'
                    '# Python figures out the type automatically.\n'
                    '\n'
                    '# Text is called a "string" (str)\n'
                    'name = "Alice"\n'
                    '\n'
                    '# Whole numbers are "integers" (int)\n'
                    'age = 14\n'
                    '\n'
                    '# Numbers with decimals are "floats" (float)\n'
                    'height = 5.6\n'
                    '\n'
                    '# True/False values are "booleans" (bool)\n'
                    'likes_python = True\n'
                    '\n'
                    '# type() tells you what kind of data a variable holds\n'
                    'print(f"name = {name} (type: {type(name).__name__})")\n'
                    'print(f"age = {age} (type: {type(age).__name__})")\n'
                    'print(f"height = {height} (type: {type(height).__name__})")\n'
                    'print(f"likes_python = {likes_python} (type: {type(likes_python).__name__})")\n'
                    '\n'
                    '# You can change a variable\'s value at any time\n'
                    'age = age + 1\n'
                    'print(f"\\nHappy birthday! Now age = {age}")\n'
                ),
            },
            {
                "name": "String Formatting",
                "desc": "Different ways to build and format text",
                "code": (
                    '# String Formatting\n'
                    '# Strings are text — you can combine and format them.\n'
                    '\n'
                    'first = "Ada"\n'
                    'last = "Lovelace"\n'
                    '\n'
                    '# Method 1: Concatenation (joining with +)\n'
                    'full_name = first + " " + last\n'
                    'print("Concatenation:", full_name)\n'
                    '\n'
                    '# Method 2: f-strings (recommended!) — put variables inside {}\n'
                    'print(f"f-string: {first} {last}")\n'
                    '\n'
                    '# f-strings can contain expressions too\n'
                    'price = 9.99\n'
                    'quantity = 3\n'
                    'print(f"Total: ${price * quantity:.2f}")  # :.2f means 2 decimal places\n'
                    '\n'
                    '# Useful string methods\n'
                    'message = "  Hello, World!  "\n'
                    'print(f"Upper: {message.upper()}")       # ALL CAPS\n'
                    'print(f"Lower: {message.lower()}")       # all lowercase\n'
                    'print(f"Strip: \'{message.strip()}\'")     # remove extra spaces\n'
                    'print(f"Replace: {message.replace(\'World\', \'Python\')}")\n'
                    'print(f"Length: {len(message)} characters")\n'
                ),
            },
            {
                "name": "Type Conversion",
                "desc": "Converting between numbers, strings, and more",
                "code": (
                    '# Type Conversion\n'
                    '# Sometimes you need to convert data from one type to another.\n'
                    '\n'
                    '# input() always gives you a string, even if you type a number\n'
                    'text = input("Enter a number: ")\n'
                    'print(f"You typed: {text} (type: {type(text).__name__})")\n'
                    '\n'
                    '# int() converts to a whole number\n'
                    'number = int(text)\n'
                    'print(f"As integer: {number} (type: {type(number).__name__})")\n'
                    '\n'
                    '# float() converts to a decimal number\n'
                    'decimal = float(text)\n'
                    'print(f"As float: {decimal} (type: {type(decimal).__name__})")\n'
                    '\n'
                    '# str() converts anything to a string\n'
                    'age = 25\n'
                    'age_text = str(age)\n'
                    'print(f"As string: \'{age_text}\' (type: {type(age_text).__name__})")\n'
                    '\n'
                    '# bool() converts to True/False\n'
                    '# 0, empty string, None, and empty lists are False\n'
                    '# Everything else is True\n'
                    'print(f"\\nbool(1) = {bool(1)}")\n'
                    'print(f"bool(0) = {bool(0)}")\n'
                    'print(f\'bool("hello") = {bool("hello")}\')\n'
                    'print(f\'bool("") = {bool("")}\')\n'
                ),
            },
            {
                "name": "Math Operations",
                "desc": "Arithmetic, rounding, and the math module",
                "code": (
                    '# Math Operations\n'
                    '# Python can do all kinds of math.\n'
                    '\n'
                    '# Basic arithmetic\n'
                    'a, b = 17, 5\n'
                    'print(f"{a} + {b} = {a + b}")     # Addition\n'
                    'print(f"{a} - {b} = {a - b}")     # Subtraction\n'
                    'print(f"{a} * {b} = {a * b}")     # Multiplication\n'
                    'print(f"{a} / {b} = {a / b}")     # Division (gives a float)\n'
                    'print(f"{a} // {b} = {a // b}")   # Floor division (whole number)\n'
                    'print(f"{a} % {b} = {a % b}")     # Modulo (remainder)\n'
                    'print(f"{a} ** {b} = {a ** b}")   # Power (17 to the 5th)\n'
                    '\n'
                    '# Rounding\n'
                    'pi = 3.14159265\n'
                    'print(f"\\nround(pi, 2) = {round(pi, 2)}")\n'
                    'print(f"round(pi, 4) = {round(pi, 4)}")\n'
                    '\n'
                    '# The math module has more advanced functions\n'
                    'import math\n'
                    'print(f"\\nmath.sqrt(144) = {math.sqrt(144)}")   # Square root\n'
                    'print(f"math.floor(3.7) = {math.floor(3.7)}")  # Round down\n'
                    'print(f"math.ceil(3.2) = {math.ceil(3.2)}")    # Round up\n'
                    'print(f"math.pi = {math.pi}")                  # Pi constant\n'
                ),
            },
        ],
    },
    {
        "name": "Control Flow",
        "icon": "\U0001F500",
        "examples": [
            {
                "name": "If / Elif / Else",
                "desc": "Making decisions in your code",
                "code": (
                    '# If / Elif / Else\n'
                    '# Use "if" to run code only when a condition is true.\n'
                    '\n'
                    'age = int(input("Enter your age: "))\n'
                    '\n'
                    '# "if" checks the first condition\n'
                    '# "elif" (else if) checks another condition if the first was false\n'
                    '# "else" runs if nothing above was true\n'
                    'if age < 0:\n'
                    '    print("That\'s not a valid age!")\n'
                    'elif age < 13:\n'
                    '    print("You\'re a child.")\n'
                    'elif age < 18:\n'
                    '    print("You\'re a teenager.")\n'
                    'elif age < 65:\n'
                    '    print("You\'re an adult.")\n'
                    'else:\n'
                    '    print("You\'re a senior.")\n'
                    '\n'
                    '# Comparison operators:\n'
                    '#   ==  equal to          !=  not equal to\n'
                    '#   <   less than          >   greater than\n'
                    '#   <=  less or equal      >=  greater or equal\n'
                    '\n'
                    '# You can combine conditions with "and", "or", "not"\n'
                    'has_ticket = True\n'
                    'if age >= 13 and has_ticket:\n'
                    '    print("\\nYou can enter the movie!")\n'
                    'elif not has_ticket:\n'
                    '    print("\\nYou need a ticket first.")\n'
                    'else:\n'
                    '    print("\\nSorry, you\'re too young for this movie.")\n'
                ),
            },
            {
                "name": "For Loops",
                "desc": "Repeating code a set number of times",
                "code": (
                    '# For Loops\n'
                    '# A "for" loop repeats code for each item in a sequence.\n'
                    '\n'
                    '# Loop through a list of items\n'
                    'fruits = ["apple", "banana", "cherry"]\n'
                    'for fruit in fruits:\n'
                    '    print(f"I like {fruit}!")\n'
                    '\n'
                    '# range() generates a sequence of numbers\n'
                    '# range(5) gives: 0, 1, 2, 3, 4\n'
                    'print("\\nCounting to 5:")\n'
                    'for i in range(1, 6):  # range(1, 6) gives: 1, 2, 3, 4, 5\n'
                    '    print(f"  {i}")\n'
                    '\n'
                    '# enumerate() gives you both the index and the item\n'
                    'colors = ["red", "green", "blue"]\n'
                    'print("\\nColors list:")\n'
                    'for index, color in enumerate(colors):\n'
                    '    print(f"  {index}: {color}")\n'
                    '\n'
                    '# Nested loops (a loop inside a loop)\n'
                    'print("\\nMultiplication table (1-5):")\n'
                    'for row in range(1, 6):\n'
                    '    for col in range(1, 6):\n'
                    '        # end=" " prints without a newline\n'
                    '        print(f"{row * col:4}", end="")\n'
                    '    print()  # New line after each row\n'
                ),
            },
            {
                "name": "While Loops",
                "desc": "Repeating code until a condition is met",
                "code": (
                    '# While Loops\n'
                    '# A "while" loop repeats as long as a condition is true.\n'
                    '\n'
                    '# Simple countdown\n'
                    'count = 5\n'
                    'print("Countdown:")\n'
                    'while count > 0:\n'
                    '    print(f"  {count}...")\n'
                    '    count -= 1  # Same as: count = count - 1\n'
                    'print("  Liftoff!")\n'
                    '\n'
                    '# "break" exits the loop immediately\n'
                    '# "continue" skips to the next iteration\n'
                    'print("\\nType \'quit\' to exit, or a number to double it:")\n'
                    'while True:  # Runs forever until we break\n'
                    '    text = input("> ")\n'
                    '\n'
                    '    if text == "quit":\n'
                    '        print("Goodbye!")\n'
                    '        break  # Exit the loop\n'
                    '\n'
                    '    # Try to convert to a number\n'
                    '    # If it fails, "continue" skips back to the top\n'
                    '    if not text.lstrip("-").isdigit():\n'
                    '        print("That\'s not a number. Try again.")\n'
                    '        continue  # Skip the rest, go back to top\n'
                    '\n'
                    '    number = int(text)\n'
                    '    print(f"{number} * 2 = {number * 2}")\n'
                ),
            },
        ],
    },
    {
        "name": "Data Structures",
        "icon": "\U0001F4E6",
        "examples": [
            {
                "name": "Lists",
                "desc": "Ordered collections you can change",
                "code": (
                    '# Lists\n'
                    '# A list holds multiple items in order.\n'
                    '# Lists use square brackets: []\n'
                    '\n'
                    '# Create a list\n'
                    'colors = ["red", "green", "blue"]\n'
                    'print("Original:", colors)\n'
                    '\n'
                    '# Access items by index (starts at 0)\n'
                    'print(f"First: {colors[0]}")   # red\n'
                    'print(f"Last: {colors[-1]}")    # blue (-1 = last item)\n'
                    '\n'
                    '# Add items\n'
                    'colors.append("yellow")          # Add to end\n'
                    'colors.insert(1, "orange")        # Insert at position 1\n'
                    'print(f"After adding: {colors}")\n'
                    '\n'
                    '# Remove items\n'
                    'colors.remove("green")            # Remove by value\n'
                    'popped = colors.pop()             # Remove and return last item\n'
                    'print(f"Popped: {popped}")\n'
                    'print(f"After removing: {colors}")\n'
                    '\n'
                    '# Slicing — get a sub-list\n'
                    'numbers = [0, 1, 2, 3, 4, 5]\n'
                    'print(f"\\nnumbers[1:4] = {numbers[1:4]}")  # [1, 2, 3]\n'
                    'print(f"numbers[:3] = {numbers[:3]}")      # [0, 1, 2]\n'
                    'print(f"numbers[3:] = {numbers[3:]}")      # [3, 4, 5]\n'
                    '\n'
                    '# Useful list functions\n'
                    'nums = [3, 1, 4, 1, 5, 9, 2]\n'
                    'print(f"\\nLength: {len(nums)}")\n'
                    'print(f"Sorted: {sorted(nums)}")\n'
                    'print(f"Sum: {sum(nums)}")\n'
                    'print(f"Min: {min(nums)}, Max: {max(nums)}")\n'
                ),
            },
            {
                "name": "Dictionaries",
                "desc": "Key-value pairs for organizing data",
                "code": (
                    '# Dictionaries\n'
                    '# A dictionary stores key-value pairs.\n'
                    '# Think of it like a real dictionary: word -> definition.\n'
                    '# Dictionaries use curly braces: {}\n'
                    '\n'
                    '# Create a dictionary\n'
                    'student = {\n'
                    '    "name": "Alice",\n'
                    '    "age": 14,\n'
                    '    "grade": "A",\n'
                    '    "hobbies": ["reading", "coding"]\n'
                    '}\n'
                    '\n'
                    '# Access values by key\n'
                    'print(f"Name: {student[\'name\']}")\n'
                    'print(f"Age: {student[\'age\']}")\n'
                    '\n'
                    '# .get() is safer — returns None if key doesn\'t exist\n'
                    'print(f"Email: {student.get(\'email\', \'not set\')}")\n'
                    '\n'
                    '# Add or change values\n'
                    'student["email"] = "alice@example.com"  # Add new key\n'
                    'student["age"] = 15                      # Update existing key\n'
                    '\n'
                    '# Loop through a dictionary\n'
                    'print("\\nAll student info:")\n'
                    'for key, value in student.items():\n'
                    '    print(f"  {key}: {value}")\n'
                    '\n'
                    '# Check if a key exists\n'
                    'if "name" in student:\n'
                    '    print(f"\\nStudent name is {student[\'name\']}")\n'
                    '\n'
                    '# Useful dictionary methods\n'
                    'print(f"\\nKeys: {list(student.keys())}")\n'
                    'print(f"Values: {list(student.values())}")\n'
                ),
            },
            {
                "name": "Tuples & Sets",
                "desc": "Immutable sequences and unique collections",
                "code": (
                    '# Tuples & Sets\n'
                    '# Two more useful data structures in Python.\n'
                    '\n'
                    '# === TUPLES ===\n'
                    '# A tuple is like a list but cannot be changed (immutable).\n'
                    '# Tuples use parentheses: ()\n'
                    'point = (3, 7)\n'
                    'print(f"Point: {point}")\n'
                    'print(f"X: {point[0]}, Y: {point[1]}")\n'
                    '\n'
                    '# Tuple unpacking — assign each item to a variable\n'
                    'x, y = point\n'
                    'print(f"Unpacked: x={x}, y={y}")\n'
                    '\n'
                    '# Tuples are great for returning multiple values\n'
                    'rgb = ("red", "green", "blue")\n'
                    'for color in rgb:\n'
                    '    print(f"  Color: {color}")\n'
                    '\n'
                    '# === SETS ===\n'
                    '# A set holds unique items (no duplicates).\n'
                    '# Sets use curly braces: {} (but no key:value pairs)\n'
                    'fruits = {"apple", "banana", "cherry", "apple"}  # Duplicate removed!\n'
                    'print(f"\\nFruits set: {fruits}")\n'
                    '\n'
                    '# Add and remove\n'
                    'fruits.add("mango")\n'
                    'fruits.discard("banana")  # Safe remove (no error if missing)\n'
                    'print(f"Updated: {fruits}")\n'
                    '\n'
                    '# Set operations\n'
                    'a = {1, 2, 3, 4}\n'
                    'b = {3, 4, 5, 6}\n'
                    'print(f"\\na = {a}")\n'
                    'print(f"b = {b}")\n'
                    'print(f"Union (a | b): {a | b}")          # All items\n'
                    'print(f"Intersection (a & b): {a & b}")    # Common items\n'
                    'print(f"Difference (a - b): {a - b}")      # In a but not b\n'
                ),
            },
        ],
    },
    {
        "name": "Functions",
        "icon": "\U00002699",
        "examples": [
            {
                "name": "Defining Functions",
                "desc": "Creating reusable blocks of code",
                "code": (
                    '# Defining Functions\n'
                    '# A function is a reusable block of code.\n'
                    '# Use "def" to define one.\n'
                    '\n'
                    '# A simple function with no parameters\n'
                    'def say_hello():\n'
                    '    print("Hello there!")\n'
                    '\n'
                    'say_hello()  # Call the function\n'
                    '\n'
                    '# A function with parameters (inputs)\n'
                    'def greet(name):\n'
                    '    print(f"Hello, {name}!")\n'
                    '\n'
                    'greet("Alice")\n'
                    'greet("Bob")\n'
                    '\n'
                    '# A function that returns a value\n'
                    'def add(a, b):\n'
                    '    return a + b\n'
                    '\n'
                    'result = add(3, 5)\n'
                    'print(f"\\n3 + 5 = {result}")\n'
                    '\n'
                    '# Default parameter values\n'
                    'def power(base, exponent=2):\n'
                    '    """Raise base to exponent. Defaults to squaring."""\n'
                    '    return base ** exponent\n'
                    '\n'
                    'print(f"\\npower(4) = {power(4)}")        # Uses default: 4^2\n'
                    'print(f"power(2, 10) = {power(2, 10)}")  # Override: 2^10\n'
                    '\n'
                    '# Functions can return multiple values (as a tuple)\n'
                    'def min_max(numbers):\n'
                    '    return min(numbers), max(numbers)\n'
                    '\n'
                    'lowest, highest = min_max([4, 7, 1, 9, 3])\n'
                    'print(f"\\nMin: {lowest}, Max: {highest}")\n'
                ),
            },
            {
                "name": "List Comprehensions",
                "desc": "Building lists in a single line",
                "code": (
                    '# List Comprehensions\n'
                    '# A compact way to create lists from other lists.\n'
                    '\n'
                    '# The long way — using a for loop:\n'
                    'squares = []\n'
                    'for x in range(1, 6):\n'
                    '    squares.append(x ** 2)\n'
                    'print(f"Squares (loop): {squares}")\n'
                    '\n'
                    '# The short way — list comprehension:\n'
                    '# [expression for item in iterable]\n'
                    'squares = [x ** 2 for x in range(1, 6)]\n'
                    'print(f"Squares (comp): {squares}")\n'
                    '\n'
                    '# With a condition — only include even numbers\n'
                    'evens = [x for x in range(1, 11) if x % 2 == 0]\n'
                    'print(f"\\nEvens 1-10: {evens}")\n'
                    '\n'
                    '# Transform strings\n'
                    'words = ["hello", "world", "python"]\n'
                    'upper_words = [w.upper() for w in words]\n'
                    'print(f"Uppercased: {upper_words}")\n'
                    '\n'
                    '# Practical example: Fahrenheit to Celsius\n'
                    'fahrenheit = [32, 68, 77, 100, 212]\n'
                    'celsius = [round((f - 32) * 5 / 9, 1) for f in fahrenheit]\n'
                    'print(f"\\nFahrenheit: {fahrenheit}")\n'
                    'print(f"Celsius:    {celsius}")\n'
                ),
            },
        ],
    },
    {
        "name": "File I/O",
        "icon": "\U0001F4C4",
        "examples": [
            {
                "name": "Reading & Writing Files",
                "desc": "Saving and loading text files",
                "code": (
                    '# Reading & Writing Files\n'
                    '# Python can create, write to, and read text files.\n'
                    '\n'
                    '# === Writing a file ===\n'
                    '# "w" mode creates/overwrites the file\n'
                    '# "with" automatically closes the file when done\n'
                    'with open("example.txt", "w") as f:\n'
                    '    f.write("Hello, file!\\n")\n'
                    '    f.write("This is line 2.\\n")\n'
                    '    f.write("Python is fun!\\n")\n'
                    '\n'
                    'print("File written!")\n'
                    '\n'
                    '# === Reading the whole file ===\n'
                    'with open("example.txt", "r") as f:\n'
                    '    content = f.read()\n'
                    'print("\\n--- Full content ---")\n'
                    'print(content)\n'
                    '\n'
                    '# === Reading line by line ===\n'
                    'print("--- Line by line ---")\n'
                    'with open("example.txt", "r") as f:\n'
                    '    for line_num, line in enumerate(f, 1):\n'
                    '        # .strip() removes the newline at the end\n'
                    '        print(f"Line {line_num}: {line.strip()}")\n'
                    '\n'
                    '# === Appending to a file ===\n'
                    '# "a" mode adds to the end without erasing\n'
                    'with open("example.txt", "a") as f:\n'
                    '    f.write("This line was appended!\\n")\n'
                    '\n'
                    '# Read again to confirm\n'
                    'with open("example.txt", "r") as f:\n'
                    '    lines = f.readlines()  # Returns a list of lines\n'
                    'print(f"\\nFile now has {len(lines)} lines.")\n'
                ),
            },
        ],
    },
    {
        "name": "Classes & Objects",
        "icon": "\U0001F3D7",
        "examples": [
            {
                "name": "Basic Classes",
                "desc": "Creating your own types with classes",
                "code": (
                    '# Basic Classes\n'
                    '# A class is a blueprint for creating objects.\n'
                    '# Objects bundle data (attributes) and actions (methods).\n'
                    '\n'
                    'class Dog:\n'
                    '    # __init__ runs when you create a new Dog\n'
                    '    # "self" refers to the specific dog being created\n'
                    '    def __init__(self, name, breed):\n'
                    '        self.name = name      # Store the name\n'
                    '        self.breed = breed    # Store the breed\n'
                    '        self.tricks = []      # Start with no tricks\n'
                    '\n'
                    '    def learn_trick(self, trick):\n'
                    '        """Teach the dog a new trick."""\n'
                    '        self.tricks.append(trick)\n'
                    '        print(f"{self.name} learned {trick}!")\n'
                    '\n'
                    '    def show_tricks(self):\n'
                    '        """Display all tricks the dog knows."""\n'
                    '        if self.tricks:\n'
                    '            tricks_str = ", ".join(self.tricks)\n'
                    '            print(f"{self.name} knows: {tricks_str}")\n'
                    '        else:\n'
                    '            print(f"{self.name} doesn\'t know any tricks yet.")\n'
                    '\n'
                    '    def __str__(self):\n'
                    '        """This controls what print() shows."""\n'
                    '        return f"{self.name} the {self.breed}"\n'
                    '\n'
                    '\n'
                    '# Create Dog objects\n'
                    'buddy = Dog("Buddy", "Golden Retriever")\n'
                    'max_dog = Dog("Max", "Beagle")\n'
                    '\n'
                    'print(buddy)  # Uses __str__\n'
                    'print(max_dog)\n'
                    '\n'
                    '# Teach some tricks\n'
                    'buddy.learn_trick("sit")\n'
                    'buddy.learn_trick("shake")\n'
                    'max_dog.learn_trick("roll over")\n'
                    '\n'
                    'print()\n'
                    'buddy.show_tricks()\n'
                    'max_dog.show_tricks()\n'
                ),
            },
            {
                "name": "Inheritance",
                "desc": "Building new classes from existing ones",
                "code": (
                    '# Inheritance\n'
                    '# A child class can inherit from a parent class,\n'
                    '# reusing its code and adding new features.\n'
                    '\n'
                    '# Parent class\n'
                    'class Animal:\n'
                    '    def __init__(self, name, sound):\n'
                    '        self.name = name\n'
                    '        self.sound = sound\n'
                    '\n'
                    '    def speak(self):\n'
                    '        print(f"{self.name} says {self.sound}!")\n'
                    '\n'
                    '    def __str__(self):\n'
                    '        return self.name\n'
                    '\n'
                    '\n'
                    '# Child class — inherits from Animal\n'
                    'class Cat(Animal):\n'
                    '    def __init__(self, name, indoor=True):\n'
                    '        # super() calls the parent\'s __init__\n'
                    '        super().__init__(name, "Meow")\n'
                    '        self.indoor = indoor\n'
                    '\n'
                    '    def purr(self):\n'
                    '        """Only cats can purr — this is a new method."""\n'
                    '        print(f"{self.name} purrs softly...")\n'
                    '\n'
                    '\n'
                    'class Dog(Animal):\n'
                    '    def __init__(self, name, breed):\n'
                    '        super().__init__(name, "Woof")\n'
                    '        self.breed = breed\n'
                    '\n'
                    '    def fetch(self, item):\n'
                    '        print(f"{self.name} fetches the {item}!")\n'
                    '\n'
                    '\n'
                    '# Create animals\n'
                    'whiskers = Cat("Whiskers", indoor=True)\n'
                    'rex = Dog("Rex", "German Shepherd")\n'
                    '\n'
                    '# Both can use the parent\'s speak() method\n'
                    'whiskers.speak()  # Whiskers says Meow!\n'
                    'rex.speak()       # Rex says Woof!\n'
                    '\n'
                    '# Each has its own special methods\n'
                    'whiskers.purr()\n'
                    'rex.fetch("ball")\n'
                    '\n'
                    '# isinstance() checks if an object is a certain type\n'
                    'print(f"\\nIs whiskers a Cat? {isinstance(whiskers, Cat)}")\n'
                    'print(f"Is whiskers an Animal? {isinstance(whiskers, Animal)}")\n'
                    'print(f"Is rex a Cat? {isinstance(rex, Cat)}")\n'
                ),
            },
        ],
    },
    {
        "name": "Fun Projects",
        "icon": "\U0001F3AE",
        "examples": [
            {
                "name": "Rock Paper Scissors",
                "desc": "A classic game against the computer",
                "code": (
                    '# Rock Paper Scissors\n'
                    '# Play against the computer!\n'
                    '\n'
                    'import random\n'
                    '\n'
                    'choices = ["rock", "paper", "scissors"]\n'
                    'wins = 0\n'
                    'losses = 0\n'
                    '\n'
                    'print("=== Rock Paper Scissors ===")\n'
                    'print("Type rock, paper, or scissors (or quit to stop)\\n")\n'
                    '\n'
                    'while True:\n'
                    '    player = input("Your choice: ").strip().lower()\n'
                    '\n'
                    '    if player == "quit":\n'
                    '        break\n'
                    '\n'
                    '    if player not in choices:\n'
                    '        print("Invalid choice! Try rock, paper, or scissors.")\n'
                    '        continue\n'
                    '\n'
                    '    computer = random.choice(choices)\n'
                    '    print(f"Computer chose: {computer}")\n'
                    '\n'
                    '    if player == computer:\n'
                    '        print("It\'s a tie!\\n")\n'
                    '    elif (\n'
                    '        (player == "rock" and computer == "scissors") or\n'
                    '        (player == "paper" and computer == "rock") or\n'
                    '        (player == "scissors" and computer == "paper")\n'
                    '    ):\n'
                    '        print("You win!\\n")\n'
                    '        wins += 1\n'
                    '    else:\n'
                    '        print("You lose!\\n")\n'
                    '        losses += 1\n'
                    '\n'
                    'print(f"\\nFinal score: {wins} wins, {losses} losses")\n'
                ),
            },
            {
                "name": "Password Generator",
                "desc": "Generate secure random passwords",
                "code": (
                    '# Password Generator\n'
                    '# Creates random passwords of any length.\n'
                    '\n'
                    'import random\n'
                    'import string\n'
                    '\n'
                    '# string module gives us character sets\n'
                    '# string.ascii_letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"\n'
                    '# string.digits = "0123456789"\n'
                    '# string.punctuation = "!@#$%^&*()..." etc.\n'
                    '\n'
                    'def generate_password(length=12, use_symbols=True):\n'
                    '    """Generate a random password of the given length."""\n'
                    '    characters = string.ascii_letters + string.digits\n'
                    '    if use_symbols:\n'
                    '        characters += string.punctuation\n'
                    '\n'
                    '    # random.choices() picks random items from a sequence\n'
                    '    password = "".join(random.choices(characters, k=length))\n'
                    '    return password\n'
                    '\n'
                    '\n'
                    'print("=== Password Generator ===")\n'
                    'print()\n'
                    '\n'
                    'length = int(input("Password length (default 12): ") or "12")\n'
                    'count = int(input("How many passwords? (default 5): ") or "5")\n'
                    'symbols = input("Include symbols? (y/n, default y): ").strip().lower()\n'
                    'use_symbols = symbols != "n"\n'
                    '\n'
                    'print(f"\\nGenerated passwords ({length} chars):")\n'
                    'for i in range(count):\n'
                    '    pwd = generate_password(length, use_symbols)\n'
                    '    print(f"  {i + 1}. {pwd}")\n'
                ),
            },
            {
                "name": "Word Counter",
                "desc": "Analyze text and count word frequency",
                "code": (
                    '# Word Counter\n'
                    '# Counts how often each word appears in text.\n'
                    '\n'
                    'text = """\n'
                    'Python is a great programming language.\n'
                    'Python is easy to learn and fun to use.\n'
                    'Many people love Python because it is simple.\n'
                    '"""\n'
                    '\n'
                    '# Clean up the text\n'
                    '# .lower() makes everything lowercase\n'
                    '# .split() breaks text into a list of words\n'
                    'words = text.lower().split()\n'
                    '\n'
                    '# Remove punctuation from each word\n'
                    'clean_words = []\n'
                    'for word in words:\n'
                    '    # .strip() removes characters from the edges\n'
                    "    cleaned = word.strip('.,!?;:\\'\"')\n"
                    '    if cleaned:  # Skip empty strings\n'
                    '        clean_words.append(cleaned)\n'
                    '\n'
                    '# Count each word using a dictionary\n'
                    'word_counts = {}\n'
                    'for word in clean_words:\n'
                    '    if word in word_counts:\n'
                    '        word_counts[word] += 1\n'
                    '    else:\n'
                    '        word_counts[word] = 1\n'
                    '\n'
                    '# Sort by count (most common first)\n'
                    '# sorted() with key= tells Python how to sort\n'
                    'sorted_words = sorted(word_counts.items(),\n'
                    '                      key=lambda pair: pair[1],\n'
                    '                      reverse=True)\n'
                    '\n'
                    'print(f"Total words: {len(clean_words)}")\n'
                    'print(f"Unique words: {len(word_counts)}")\n'
                    'print("\\nWord frequencies:")\n'
                    'for word, count in sorted_words:\n'
                    '    bar = "#" * count  # Visual bar\n'
                    '    print(f"  {word:12} {count:2} {bar}")\n'
                ),
            },
        ],
    },
]
