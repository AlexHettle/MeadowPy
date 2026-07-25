"""Beginner-friendly explanations for Python keywords and built-in functions.

Each entry has:
- explanation: A plain-English description (2-3 sentences)
- example: A short code snippet showing usage
"""

KEYWORD_HELP = {
    # ── Python Keywords ──────────────────────────────────────────────

    "False": {
        "explanation": "One of the two boolean values. It represents something that is not true. Comparisons like 3 > 5 evaluate to False.",
        "example": "is_raining = False\nif not is_raining:\n    print(\"Let's go outside!\")",
    },
    "None": {
        "explanation": "A special value that means \"nothing\" or \"no value\". Functions that don't explicitly return something return None automatically.",
        "example": "result = None\nresult = print(\"hi\")  # print returns None",
    },
    "True": {
        "explanation": "One of the two boolean values. It represents something that is true. Comparisons like 3 < 5 evaluate to True.",
        "example": "is_sunny = True\nif is_sunny:\n    print(\"Wear sunscreen!\")",
    },
    "and": {
        "explanation": "Combines two conditions. Both must be true for the whole thing to be true. If the first is false, Python doesn't even check the second.",
        "example": "age = 15\nhas_ticket = True\nif age >= 13 and has_ticket:\n    print(\"You can enter!\")",
    },
    "as": {
        "explanation": "Gives something a shorter or different name. Used with import to rename a module, or with 'with' to name what you opened.",
        "example": "import random as rnd\nprint(rnd.randint(1, 10))\n\nwith open(\"file.txt\") as f:\n    text = f.read()",
    },
    "assert": {
        "explanation": "Checks that something is true. If it's not, Python stops with an error. Used for testing and catching bugs early.",
        "example": "age = 25\nassert age > 0, \"Age must be positive\"",
    },
    "async": {
        "explanation": "Marks a function as asynchronous — it can pause and let other code run while waiting. Used for tasks like downloading web pages without freezing.",
        "example": "async def fetch_data():\n    # Can use 'await' inside here\n    pass",
    },
    "await": {
        "explanation": "Pauses an async function until a slow operation (like a network request) finishes. Can only be used inside an async function.",
        "example": "async def main():\n    result = await fetch_data()\n    print(result)",
    },
    "break": {
        "explanation": "Immediately exits a loop. The program continues with the code after the loop. Useful for stopping early when you've found what you need.",
        "example": "for num in range(100):\n    if num == 5:\n        break  # Stop the loop\nprint(\"Done!\")",
    },
    "class": {
        "explanation": "Creates a new type of object — a blueprint for bundling data and actions together. Like a cookie cutter that can make many cookies.",
        "example": "class Dog:\n    def __init__(self, name):\n        self.name = name\n    def bark(self):\n        print(f\"{self.name} says Woof!\")",
    },
    "continue": {
        "explanation": "Skips the rest of the current loop iteration and jumps back to the top. The loop keeps going with the next item.",
        "example": "for i in range(5):\n    if i == 2:\n        continue  # Skip 2\n    print(i)  # Prints 0, 1, 3, 4",
    },
    "def": {
        "explanation": "Defines a function — a reusable block of code with a name. You can call it later as many times as you want, optionally passing in values.",
        "example": "def greet(name):\n    print(f\"Hello, {name}!\")\n\ngreet(\"Alice\")\ngreet(\"Bob\")",
    },
    "del": {
        "explanation": "Deletes a variable, list item, or dictionary key. After deleting, you can't use that name or item anymore.",
        "example": "x = 10\ndel x  # x no longer exists\n\ncolors = [\"red\", \"green\", \"blue\"]\ndel colors[1]  # Removes \"green\"",
    },
    "elif": {
        "explanation": "Short for \"else if\". Checks another condition after an if (or another elif) was false. You can chain as many as you need.",
        "example": "score = 85\nif score >= 90:\n    print(\"A\")\nelif score >= 80:\n    print(\"B\")\nelif score >= 70:\n    print(\"C\")",
    },
    "else": {
        "explanation": "Runs code when none of the previous if/elif conditions were true. It's the \"if nothing else matched\" block.",
        "example": "age = 10\nif age >= 18:\n    print(\"Adult\")\nelse:\n    print(\"Minor\")",
    },
    "except": {
        "explanation": "Catches errors that happen inside a try block. Instead of crashing, your program can handle the problem gracefully.",
        "example": "try:\n    num = int(input(\"Number: \"))\nexcept ValueError:\n    print(\"That's not a valid number!\")",
    },
    "finally": {
        "explanation": "Code that always runs after a try block, whether an error happened or not. Used for cleanup like closing files.",
        "example": "try:\n    result = 10 / 0\nexcept ZeroDivisionError:\n    print(\"Can't divide by zero!\")\nfinally:\n    print(\"This always runs\")",
    },
    "for": {
        "explanation": "Repeats code once for each item in a sequence (like a list, string, or range of numbers). The loop variable takes on each value in turn.",
        "example": "fruits = [\"apple\", \"banana\", \"cherry\"]\nfor fruit in fruits:\n    print(f\"I like {fruit}!\")",
    },
    "from": {
        "explanation": "Imports specific items from a module instead of the whole thing. Lets you use the imported name directly without the module prefix.",
        "example": "from random import randint\n# Now use randint() directly instead of random.randint()\nprint(randint(1, 10))",
    },
    "global": {
        "explanation": "Lets a function modify a variable that exists outside the function. Without it, the function would create its own local copy.",
        "example": "count = 0\ndef increment():\n    global count\n    count += 1\n\nincrement()\nprint(count)  # 1",
    },
    "if": {
        "explanation": "Runs a block of code only when a condition is true. The most basic way to make decisions in your program.",
        "example": "temperature = 30\nif temperature > 25:\n    print(\"It's hot outside!\")",
    },
    "import": {
        "explanation": "Loads a module (a file of extra tools) so you can use its functions and classes. Python comes with many useful built-in modules.",
        "example": "import random\nprint(random.randint(1, 100))\n\nimport math\nprint(math.sqrt(16))  # 4.0",
    },
    "in": {
        "explanation": "Checks if something exists inside a collection (list, string, dictionary, etc.). Also used in for loops to go through each item.",
        "example": "if \"a\" in \"apple\":\n    print(\"Found it!\")\n\nfor x in [1, 2, 3]:\n    print(x)",
    },
    "is": {
        "explanation": "Checks if two variables point to the exact same object in memory (not just equal values). Most commonly used with None: 'if x is None'.",
        "example": "x = None\nif x is None:\n    print(\"x has no value\")\n\na = [1, 2]\nb = a\nprint(a is b)  # True (same object)",
    },
    "lambda": {
        "explanation": "Creates a small anonymous function in one line. Useful for simple operations you don't want to give a full name to.",
        "example": "double = lambda x: x * 2\nprint(double(5))  # 10\n\nnums = [3, 1, 2]\nsorted_nums = sorted(nums, key=lambda n: -n)  # Sort descending",
    },
    "nonlocal": {
        "explanation": "Like global, but for nested functions. Lets an inner function modify a variable from the function that contains it.",
        "example": "def outer():\n    count = 0\n    def inner():\n        nonlocal count\n        count += 1\n    inner()\n    print(count)  # 1",
    },
    "not": {
        "explanation": "Flips a boolean value: True becomes False, and False becomes True. Used to check the opposite of a condition.",
        "example": "is_raining = False\nif not is_raining:\n    print(\"No umbrella needed!\")\n\nprint(not True)   # False\nprint(not False)  # True",
    },
    "or": {
        "explanation": "Combines two conditions. At least one must be true for the whole thing to be true. If the first is true, Python doesn't check the second.",
        "example": "day = \"Saturday\"\nif day == \"Saturday\" or day == \"Sunday\":\n    print(\"It's the weekend!\")",
    },
    "pass": {
        "explanation": "Does absolutely nothing. Used as a placeholder when Python requires code but you haven't written it yet.",
        "example": "def todo_function():\n    pass  # Will implement later\n\nfor i in range(10):\n    pass  # Empty loop (placeholder)",
    },
    "raise": {
        "explanation": "Deliberately causes an error. Used when your code detects a problem and wants to signal it to the caller.",
        "example": "def set_age(age):\n    if age < 0:\n        raise ValueError(\"Age cannot be negative\")\n    return age",
    },
    "return": {
        "explanation": "Sends a value back from a function to the code that called it. The function stops running immediately after return.",
        "example": "def add(a, b):\n    return a + b\n\nresult = add(3, 5)\nprint(result)  # 8",
    },
    "try": {
        "explanation": "Wraps code that might cause an error. If an error happens inside the try block, Python jumps to the except block instead of crashing.",
        "example": "try:\n    num = int(input(\"Enter a number: \"))\n    print(f\"You entered {num}\")\nexcept ValueError:\n    print(\"That wasn't a number!\")",
    },
    "while": {
        "explanation": "Repeats code as long as a condition is true. Be careful — if the condition never becomes false, the loop runs forever!",
        "example": "count = 5\nwhile count > 0:\n    print(count)\n    count -= 1\nprint(\"Liftoff!\")",
    },
    "with": {
        "explanation": "Automatically handles setup and cleanup. Most commonly used for opening files — it closes the file for you when the block ends.",
        "example": "with open(\"data.txt\", \"r\") as f:\n    content = f.read()\n# File is automatically closed here",
    },
    "yield": {
        "explanation": "Like return, but the function pauses instead of stopping. It creates a generator — a special kind of function that produces values one at a time.",
        "example": "def countdown(n):\n    while n > 0:\n        yield n\n        n -= 1\n\nfor num in countdown(3):\n    print(num)  # 3, 2, 1",
    },

    # ── Built-in Functions ───────────────────────────────────────────

    "print": {
        "explanation": "Displays text or values on the screen. You can print multiple things separated by commas, and they'll be joined with spaces.",
        "example": "print(\"Hello!\")\nprint(\"Age:\", 25)\nprint(1, 2, 3, sep=\"-\")  # 1-2-3",
    },
    "input": {
        "explanation": "Pauses the program and waits for the user to type something. Always returns a string, so convert with int() or float() if you need a number.",
        "example": "name = input(\"What's your name? \")\nage = int(input(\"How old are you? \"))\nprint(f\"Hi {name}, you are {age}!\")",
    },
    "len": {
        "explanation": "Returns the length (number of items) of a sequence. Works on strings, lists, dictionaries, tuples, and sets.",
        "example": "print(len(\"hello\"))      # 5 characters\nprint(len([1, 2, 3]))    # 3 items\nprint(len({\"a\": 1}))     # 1 key",
    },
    "range": {
        "explanation": "Generates a sequence of numbers. range(5) gives 0-4, range(1, 6) gives 1-5, range(0, 10, 2) gives 0, 2, 4, 6, 8.",
        "example": "for i in range(5):\n    print(i)  # 0, 1, 2, 3, 4\n\nnums = list(range(1, 11))\nprint(nums)  # [1, 2, 3, ..., 10]",
    },
    "type": {
        "explanation": "Tells you what kind of data something is — str, int, float, list, etc. Helpful for debugging when a value isn't what you expected.",
        "example": "print(type(42))        # <class 'int'>\nprint(type(3.14))      # <class 'float'>\nprint(type(\"hello\"))   # <class 'str'>\nprint(type([1, 2]))    # <class 'list'>",
    },
    "int": {
        "explanation": "Converts a value to a whole number (integer). Can convert strings like \"42\" or floats like 3.7 (rounds down to 3).",
        "example": "num = int(\"42\")    # String to int\nnum = int(3.9)     # Float to int (becomes 3)\nage = int(input(\"Age: \"))",
    },
    "float": {
        "explanation": "Converts a value to a decimal number (floating-point). Can convert strings like \"3.14\" or integers like 5 (becomes 5.0).",
        "example": "pi = float(\"3.14\")   # String to float\nx = float(5)          # Int to float (5.0)\nprice = float(input(\"Price: \"))",
    },
    "str": {
        "explanation": "Converts any value to a text string. Useful for joining numbers with text, or for displaying values.",
        "example": "age = 25\nmessage = \"I am \" + str(age) + \" years old\"\nprint(str(3.14))    # \"3.14\"\nprint(str(True))    # \"True\"",
    },
    "bool": {
        "explanation": "Converts a value to True or False. Zero, empty strings, empty lists, and None are False. Everything else is True.",
        "example": "print(bool(1))       # True\nprint(bool(0))       # False\nprint(bool(\"\"))      # False (empty string)\nprint(bool(\"hi\"))    # True",
    },
    "list": {
        "explanation": "Creates a list (an ordered, changeable collection). Can convert other sequences like strings or tuples into lists.",
        "example": "letters = list(\"hello\")  # ['h', 'e', 'l', 'l', 'o']\nnums = list(range(5))    # [0, 1, 2, 3, 4]\nempty = list()            # []",
    },
    "dict": {
        "explanation": "Creates a dictionary (a collection of key-value pairs). Keys must be unique. Great for storing related data together.",
        "example": "person = dict(name=\"Alice\", age=14)\nprint(person)  # {'name': 'Alice', 'age': 14}\n\nempty = dict()  # {}",
    },
    "set": {
        "explanation": "Creates a set (a collection with no duplicates). Useful for removing duplicates from a list or checking membership quickly.",
        "example": "unique = set([1, 2, 2, 3, 3])  # {1, 2, 3}\nletters = set(\"hello\")          # {'h', 'e', 'l', 'o'}\nprint(3 in unique)              # True",
    },
    "tuple": {
        "explanation": "Creates a tuple (an ordered collection that cannot be changed). Use when you have a fixed group of values like coordinates.",
        "example": "point = tuple([3, 7])  # (3, 7)\ncoords = (10, 20)      # Also creates a tuple\nx, y = coords          # Unpack: x=10, y=20",
    },
    "abs": {
        "explanation": "Returns the absolute value of a number — how far it is from zero, always positive.",
        "example": "print(abs(-5))     # 5\nprint(abs(3))      # 3\nprint(abs(-2.7))   # 2.7",
    },
    "round": {
        "explanation": "Rounds a number to a given number of decimal places. With no second argument, rounds to the nearest whole number.",
        "example": "print(round(3.14159, 2))  # 3.14\nprint(round(3.7))         # 4\nprint(round(2.5))         # 2 (banker's rounding)",
    },
    "max": {
        "explanation": "Returns the largest value from a list or a set of arguments. Works with numbers, strings, and anything that can be compared.",
        "example": "print(max(3, 7, 2))           # 7\nprint(max([10, 5, 20, 8]))    # 20\nprint(max(\"apple\", \"banana\"))  # \"banana\"",
    },
    "min": {
        "explanation": "Returns the smallest value from a list or a set of arguments. Works with numbers, strings, and anything that can be compared.",
        "example": "print(min(3, 7, 2))           # 2\nprint(min([10, 5, 20, 8]))    # 5\nprint(min(\"apple\", \"banana\"))  # \"apple\"",
    },
    "sum": {
        "explanation": "Adds up all the numbers in a list (or other iterable). You can optionally provide a starting value.",
        "example": "print(sum([1, 2, 3, 4]))      # 10\nprint(sum(range(1, 101)))      # 5050\nprint(sum([10, 20], start=5))  # 35",
    },
    "sorted": {
        "explanation": "Returns a new sorted list from any iterable. Does not change the original. Use reverse=True to sort from largest to smallest.",
        "example": "nums = [3, 1, 4, 1, 5]\nprint(sorted(nums))                # [1, 1, 3, 4, 5]\nprint(sorted(nums, reverse=True))  # [5, 4, 3, 1, 1]",
    },
    "reversed": {
        "explanation": "Returns items in reverse order. Does not change the original. Wrap in list() if you need a list back.",
        "example": "nums = [1, 2, 3]\nfor n in reversed(nums):\n    print(n)  # 3, 2, 1\n\nprint(list(reversed(\"hello\")))  # ['o', 'l', 'l', 'e', 'h']",
    },
    "enumerate": {
        "explanation": "Gives you both the index number and the value when looping. Saves you from tracking the count yourself.",
        "example": "fruits = [\"apple\", \"banana\", \"cherry\"]\nfor i, fruit in enumerate(fruits):\n    print(f\"{i}: {fruit}\")\n# 0: apple, 1: banana, 2: cherry",
    },
    "zip": {
        "explanation": "Pairs up items from two (or more) lists, element by element. Stops when the shortest list runs out.",
        "example": "names = [\"Alice\", \"Bob\"]\nscores = [95, 87]\nfor name, score in zip(names, scores):\n    print(f\"{name}: {score}\")",
    },
    "map": {
        "explanation": "Applies a function to every item in a list. Returns a map object — wrap in list() to see the results.",
        "example": "nums = [\"1\", \"2\", \"3\"]\nints = list(map(int, nums))  # [1, 2, 3]\n\ndoubled = list(map(lambda x: x * 2, [1, 2, 3]))  # [2, 4, 6]",
    },
    "filter": {
        "explanation": "Keeps only the items where a function returns True. Returns a filter object — wrap in list() to see the results.",
        "example": "nums = [1, 2, 3, 4, 5, 6]\nevens = list(filter(lambda x: x % 2 == 0, nums))\nprint(evens)  # [2, 4, 6]",
    },
    "isinstance": {
        "explanation": "Checks if an object is a certain type (or one of several types). Returns True or False.",
        "example": "print(isinstance(42, int))        # True\nprint(isinstance(\"hi\", str))      # True\nprint(isinstance(3.14, (int, float)))  # True",
    },
    "open": {
        "explanation": "Opens a file for reading or writing. Use \"r\" for reading, \"w\" for writing (overwrites), \"a\" for appending. Best used with 'with'.",
        "example": "with open(\"notes.txt\", \"w\") as f:\n    f.write(\"Hello!\")\n\nwith open(\"notes.txt\", \"r\") as f:\n    print(f.read())",
    },
    "format": {
        "explanation": "Formats a value into a string using a format specification. Mostly replaced by f-strings, but still useful for number formatting.",
        "example": "print(format(3.14159, \".2f\"))   # \"3.14\"\nprint(format(1000000, \",\"))     # \"1,000,000\"\nprint(format(255, \"#x\"))        # \"0xff\"",
    },
    "id": {
        "explanation": "Returns a unique number identifying an object in memory. Two variables with the same id point to the exact same object.",
        "example": "x = [1, 2, 3]\ny = x\nprint(id(x) == id(y))  # True (same object)\nz = [1, 2, 3]\nprint(id(x) == id(z))  # False (different object)",
    },
    "dir": {
        "explanation": "Lists all the attributes and methods available on an object. Handy for exploring what you can do with something.",
        "example": "# See all string methods:\nprint(dir(\"\"))\n\n# See all list methods:\nprint(dir([]))",
    },
    "help": {
        "explanation": "Shows documentation for a function, method, or type. Very useful for learning what something does and how to use it.",
        "example": "help(print)       # Shows print documentation\nhelp(str.upper)   # Shows str.upper documentation\nhelp(list)        # Shows list documentation",
    },
    "any": {
        "explanation": "Returns True if at least one item in the iterable is true. Returns False for an empty list.",
        "example": "print(any([False, False, True]))   # True\nprint(any([0, 0, 0]))             # False\n\nnums = [2, 4, 7, 8]\nprint(any(n > 5 for n in nums))   # True",
    },
    "all": {
        "explanation": "Returns True only if every item in the iterable is true. Returns True for an empty list.",
        "example": "print(all([True, True, True]))    # True\nprint(all([True, False, True]))   # False\n\nnums = [2, 4, 6]\nprint(all(n % 2 == 0 for n in nums))  # True (all even)",
    },
    "chr": {
        "explanation": "Converts a number (Unicode code point) to its character. For example, 65 is 'A' and 97 is 'a'.",
        "example": "print(chr(65))    # 'A'\nprint(chr(97))    # 'a'\nprint(chr(9786))  # A smiley face",
    },
    "ord": {
        "explanation": "The opposite of chr() — converts a character to its Unicode number. Only works on a single character.",
        "example": "print(ord('A'))   # 65\nprint(ord('a'))   # 97\nprint(ord('0'))   # 48",
    },
    "hasattr": {
        "explanation": "Checks if an object has a particular attribute or method. Returns True or False without causing an error.",
        "example": "text = \"hello\"\nprint(hasattr(text, \"upper\"))    # True\nprint(hasattr(text, \"append\"))   # False (that's a list method)",
    },
    "getattr": {
        "explanation": "Gets the value of an attribute by its name (as a string). Useful when the attribute name is stored in a variable.",
        "example": "text = \"hello\"\nmethod = getattr(text, \"upper\")\nprint(method())   # \"HELLO\"",
    },
    "super": {
        "explanation": "Calls a method from the parent class. Most commonly used in __init__ to run the parent's setup code before adding your own.",
        "example": "class Animal:\n    def __init__(self, name):\n        self.name = name\n\nclass Dog(Animal):\n    def __init__(self, name, breed):\n        super().__init__(name)\n        self.breed = breed",
    },
    "self": {
        "explanation": "Refers to the current object inside a class method. It's how the object accesses its own data and methods. Always the first parameter in a method.",
        "example": "class Dog:\n    def __init__(self, name):\n        self.name = name  # Store on this object\n    def bark(self):\n        print(f\"{self.name} says Woof!\")",
    },

    # ── Common Patterns & Conventions ────────────────────────────────

    "main": {
        "explanation": "A common convention in Python. The 'main' function holds your program's main logic. The 'if __name__ == \"__main__\"' check runs it only when the file is executed directly (not when imported by another file).",
        "example": "def main():\n    print(\"Program starts here!\")\n    name = input(\"Name: \")\n    print(f\"Hello, {name}!\")\n\nif __name__ == \"__main__\":\n    main()",
    },
    "__name__": {
        "explanation": "A special variable Python sets automatically. It equals \"__main__\" when you run the file directly, but equals the module name when the file is imported. Used to control what code runs on import vs. direct execution.",
        "example": "# When you run: python myfile.py\n# __name__ is \"__main__\"\n\n# When another file does: import myfile\n# __name__ is \"myfile\"\n\nif __name__ == \"__main__\":\n    print(\"Running directly!\")",
    },
    "__init__": {
        "explanation": "A special method that runs automatically when you create a new object from a class. Use it to set up the object's initial data. The 'self' parameter refers to the new object being created.",
        "example": "class Cat:\n    def __init__(self, name, color):\n        self.name = name\n        self.color = color\n\nkitty = Cat(\"Whiskers\", \"orange\")\nprint(kitty.name)  # Whiskers",
    },
    "__str__": {
        "explanation": "A special method that controls what print() shows for your object. Without it, printing an object shows something like '<Cat object at 0x...>'. With it, you get a readable string.",
        "example": "class Cat:\n    def __init__(self, name):\n        self.name = name\n    def __str__(self):\n        return f\"Cat named {self.name}\"\n\nprint(Cat(\"Whiskers\"))  # Cat named Whiskers",
    },
}
