"""Welcome screen shown when MeadowPy launches with no files open."""

from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from meadowpy.constants import APP_NAME, VERSION
from meadowpy.resources.resource_loader import (
    get_icon_path,
    run_button_accent_hex,
    theme_is_dark,
    theme_is_high_contrast,
)


# ── Template definitions ──────────────────────────────────────────────

TEMPLATES = [
    {
        "name": "Hello World",
        "desc": "Your first Python program",
        "icon": "\U0001F44B",
        "code": (
            '# Hello World - Your first Python program!\n'
            '# Press F5 to run this code.\n'
            '\n'
            '# print() displays text on screen\n'
            'print("Hello, World!")\n'
            'print("Welcome to Python programming!")\n'
            '\n'
            '# input() asks the user to type something\n'
            '# We store what they type in a variable called "name"\n'
            'name = input("What is your name? ")\n'
            '\n'
            '# f"..." is an f-string — it lets you put variables inside text\n'
            '# The {name} part gets replaced with whatever the user typed\n'
            'print(f"Nice to meet you, {name}!")\n'
        ),
    },
    {
        "name": "Simple Calculator",
        "desc": "Basic arithmetic with user input",
        "icon": "\U0001F522",
        "code": (
            '# Simple Calculator\n'
            '# This program asks for two numbers and shows the results\n'
            '# of adding, subtracting, multiplying, and dividing them.\n'
            '\n'
            'print("=== Simple Calculator ===")\n'
            'print()\n'
            '\n'
            '# input() always returns text, so we use float() to convert\n'
            '# it into a number that we can do math with\n'
            'num1 = float(input("Enter first number: "))\n'
            'num2 = float(input("Enter second number: "))\n'
            '\n'
            '# Show the results — Python can do math right inside f-strings\n'
            'print(f"\\n{num1} + {num2} = {num1 + num2}")\n'
            'print(f"{num1} - {num2} = {num1 - num2}")\n'
            'print(f"{num1} * {num2} = {num1 * num2}")\n'
            '\n'
            '# We need to check for zero before dividing — dividing by\n'
            '# zero is not allowed and would cause an error\n'
            'if num2 != 0:\n'
            '    print(f"{num1} / {num2} = {num1 / num2}")\n'
            'else:\n'
            '    print("Cannot divide by zero!")\n'
        ),
    },
    {
        "name": "Guessing Game",
        "desc": "Random number guessing loop",
        "icon": "\U0001F3B2",
        "code": (
            '# Number Guessing Game\n'
            '# The computer picks a random number and you try to guess it.\n'
            '# It tells you if your guess is too high or too low.\n'
            '\n'
            '# "import" loads extra tools — "random" lets us pick random numbers\n'
            'import random\n'
            '\n'
            '# Pick a random number between 1 and 100\n'
            'secret = random.randint(1, 100)\n'
            'attempts = 0\n'
            '\n'
            'print("I\'m thinking of a number between 1 and 100.")\n'
            'print()\n'
            '\n'
            '# "while True" creates a loop that runs forever\n'
            '# We use "break" to exit the loop when the guess is correct\n'
            'while True:\n'
            '    # int() converts the typed text into a whole number\n'
            '    guess = int(input("Your guess: "))\n'
            '    attempts += 1  # Same as: attempts = attempts + 1\n'
            '\n'
            '    # Compare the guess to the secret number\n'
            '    if guess < secret:\n'
            '        print("Too low! Try again.")\n'
            '    elif guess > secret:\n'
            '        print("Too high! Try again.")\n'
            '    else:\n'
            '        # If it\'s not too low and not too high, it must be correct!\n'
            '        print(f"\\nCorrect! You got it in {attempts} attempts!")\n'
            '        break  # Exit the loop\n'
        ),
    },
    {
        "name": "Todo List",
        "desc": "List operations with a menu loop",
        "icon": "\U00002705",
        "code": (
            '# Todo List Manager\n'
            '# A simple app that lets you add and remove tasks.\n'
            '# Uses a list to store items and a loop for the menu.\n'
            '\n'
            '# A list is like a container that holds multiple items\n'
            '# We start with an empty list: []\n'
            'todos = []\n'
            '\n'
            '# Main loop — keeps showing the menu until the user quits\n'
            'while True:\n'
            '    # Display all current tasks\n'
            '    print("\\n=== Todo List ===")\n'
            '    if not todos:\n'
            '        print("  (empty)")\n'
            '    else:\n'
            '        # enumerate() gives us both the number and the item\n'
            '        for i, task in enumerate(todos, 1):\n'
            '            print(f"  {i}. {task}")\n'
            '\n'
            '    # Show menu and get the user\'s choice\n'
            '    print("\\n[A]dd  [R]emove  [Q]uit")\n'
            '    # .strip() removes extra spaces, .lower() makes it lowercase\n'
            '    choice = input("> ").strip().lower()\n'
            '\n'
            '    if choice == "a":\n'
            '        task = input("New task: ")\n'
            '        todos.append(task)  # .append() adds to the end of the list\n'
            '        print(f"Added: {task}")\n'
            '    elif choice == "r":\n'
            '        num = int(input("Remove #: "))\n'
            '        # Check that the number is valid before removing\n'
            '        if 1 <= num <= len(todos):\n'
            '            removed = todos.pop(num - 1)  # .pop() removes and returns the item\n'
            '            print(f"Removed: {removed}")\n'
            '        else:\n'
            '            print("Invalid number.")\n'
            '    elif choice == "q":\n'
            '        print("Goodbye!")\n'
            '        break\n'
        ),
    },
    {
        "name": "Turtle Graphics",
        "desc": "Draw shapes with Python turtle",
        "icon": "\U0001F422",
        "code": (
            '# Turtle Graphics - Draw a colorful spiral\n'
            '# "turtle" is a built-in Python module for drawing pictures.\n'
            '# It works like a pen that moves around the screen.\n'
            '\n'
            'import turtle\n'
            '\n'
            '# Set up the drawing window\n'
            'screen = turtle.Screen()\n'
            'screen.bgcolor("white")\n'
            'screen.title("Turtle Graphics")\n'
            '\n'
            '# Create a turtle (our drawing pen)\n'
            't = turtle.Turtle()\n'
            't.speed(0)  # 0 = fastest drawing speed\n'
            '\n'
            '# A list of colors to cycle through\n'
            'colors = ["red", "orange", "yellow", "green", "blue", "purple"]\n'
            '\n'
            '# Draw 60 lines, each one a bit longer, turning slightly each time\n'
            'for i in range(60):\n'
            '    # Pick a color — the % (modulo) operator cycles through the list\n'
            '    t.pencolor(colors[i % len(colors)])\n'
            '    t.forward(i * 3)  # Move forward (longer each time)\n'
            '    t.left(61)        # Turn left 61 degrees\n'
            '\n'
            't.hideturtle()       # Hide the turtle arrow when done\n'
            'screen.mainloop()    # Keep the window open\n'
        ),
    },
    {
        "name": "Simple Quiz",
        "desc": "Question and answer game",
        "icon": "\U00002753",
        "code": (
            '# Simple Quiz Game\n'
            '# Tests your knowledge with multiple questions.\n'
            '# Uses a list of tuples to store question/answer pairs.\n'
            '\n'
            '# Each item is a tuple: (question, correct_answer)\n'
            '# A tuple is like a list but uses () instead of []\n'
            'questions = [\n'
            '    ("What is the capital of France?", "paris"),\n'
            '    ("What color is the sky?", "blue"),\n'
            '    ("How many legs does a spider have?", "8"),\n'
            '    ("What planet is closest to the sun?", "mercury"),\n'
            ']\n'
            '\n'
            'score = 0  # Track how many correct answers\n'
            '\n'
            'print("=== Python Quiz ===\\n")\n'
            '\n'
            '# Loop through each question\n'
            '# enumerate() gives us the question number (i) starting from 1\n'
            '# (question, answer) unpacks each tuple into two variables\n'
            'for i, (question, answer) in enumerate(questions, 1):\n'
            '    response = input(f"Q{i}: {question} ").strip().lower()\n'
            '    if response == answer:\n'
            '        print("Correct!\\n")\n'
            '        score += 1\n'
            '    else:\n'
            '        print(f"Wrong! The answer was: {answer}\\n")\n'
            '\n'
            '# Show final score\n'
            'print(f"You scored {score}/{len(questions)}!")\n'
            '\n'
            '# Give feedback based on how well they did\n'
            'if score == len(questions):\n'
            '    print("Perfect score!")\n'
            'elif score >= len(questions) // 2:  # // is integer division\n'
            '    print("Good job!")\n'
            'else:\n'
            '    print("Keep practicing!")\n'
        ),
    },
    {
        "name": "Temperature Converter",
        "desc": "Reusable code with functions",
        "icon": "\U0001F321",
        "code": (
            '# Temperature Converter\n'
            '# Learn how to write and use your own FUNCTIONS.\n'
            '# A function is a reusable block of code you can call by name.\n'
            '\n'
            '# "def" defines a function. It takes an input (the parameter)\n'
            '# and "return" sends a value back to whoever called it.\n'
            'def celsius_to_fahrenheit(c):\n'
            '    return c * 9 / 5 + 32\n'
            '\n'
            '\n'
            'def fahrenheit_to_celsius(f):\n'
            '    return (f - 32) * 5 / 9\n'
            '\n'
            '\n'
            '# Functions can do more than math — here one returns a label\n'
            'def describe(temp_c):\n'
            '    if temp_c < 0:\n'
            '        return "freezing"\n'
            '    elif temp_c < 15:\n'
            '        return "cold"\n'
            '    elif temp_c < 25:\n'
            '        return "mild"\n'
            '    else:\n'
            '        return "hot"\n'
            '\n'
            '\n'
            '# Main program — call the functions we defined above\n'
            'print("=== Temperature Converter ===")\n'
            'c = float(input("Enter temperature in Celsius: "))\n'
            '\n'
            '# Each call to a function gives us a fresh result to work with\n'
            'f = celsius_to_fahrenheit(c)\n'
            'label = describe(c)\n'
            '\n'
            'print(f"{c}\\u00B0C is {f:.1f}\\u00B0F  ({label})")\n'
            '\n'
            '# Functions really shine when reused — this loop calls the same\n'
            '# function over and over without rewriting the math each time\n'
            'print("\\nQuick reference table:")\n'
            'for temperature in [0, 10, 20, 30, 40]:\n'
            '    print(f"  {temperature}\\u00B0C = {celsius_to_fahrenheit(temperature):.1f}\\u00B0F")\n'
        ),
    },
    {
        "name": "Word Counter",
        "desc": "Count words using a dictionary",
        "icon": "\U0001F4D6",
        "code": (
            '# Word Counter\n'
            '# Learn about DICTIONARIES — a way to pair keys with values.\n'
            '# We will count how many times each word appears in a sentence.\n'
            '\n'
            'text = input("Type a sentence: ")\n'
            '\n'
            '# .lower() makes the text all lowercase so "The" and "the" match\n'
            '# .split() breaks the sentence into a list of words\n'
            'words = text.lower().split()\n'
            '\n'
            '# A dictionary holds key -> value pairs, written with {}\n'
            '# We start empty and fill it in as we scan the words\n'
            'counts = {}\n'
            '\n'
            'for word in words:\n'
            '    # .get(word, 0) returns the current count, or 0 if missing\n'
            '    counts[word] = counts.get(word, 0) + 1\n'
            '\n'
            'print("\\nWord counts:")\n'
            '\n'
            '# .items() lets us loop over both the key and value at once\n'
            '# sorted() with key= and reverse=True orders by highest count first\n'
            'for word, count in sorted(counts.items(), key=lambda pair: pair[1], reverse=True):\n'
            '    print(f"  {word}: {count}")\n'
            '\n'
            'print(f"\\nTotal words: {len(words)}")\n'
            'print(f"Unique words: {len(counts)}")\n'
        ),
    },
    {
        "name": "Notes Saver",
        "desc": "Read and write files on disk",
        "icon": "\U0001F4DD",
        "code": (
            '# Notes Saver\n'
            '# Learn how to READ and WRITE FILES so your data survives\n'
            '# after the program stops running.\n'
            '\n'
            '# "import os" gives us tools for checking if files exist\n'
            'import os\n'
            '\n'
            'FILENAME = "notes.txt"\n'
            '\n'
            '# Read any existing notes from the file, if it exists.\n'
            '# "with open(...) as f:" safely opens the file and closes it\n'
            '# automatically when we are done. "r" means read mode.\n'
            'if os.path.exists(FILENAME):\n'
            '    print("=== Your saved notes ===")\n'
            '    with open(FILENAME, "r", encoding="utf-8") as f:\n'
            '        print(f.read())\n'
            'else:\n'
            '    print("(No notes yet — let\'s create some!)")\n'
            '\n'
            '# Ask the user for a new note\n'
            'note = input("\\nType a new note (or press Enter to skip): ").strip()\n'
            '\n'
            'if note:\n'
            '    # "a" means append mode — add to the end without erasing\n'
            '    # the previous contents. Use "w" to overwrite instead.\n'
            '    with open(FILENAME, "a", encoding="utf-8") as f:\n'
            '        f.write(note + "\\n")\n'
            '    print(f"Saved to {FILENAME}!")\n'
            '\n'
            '    # Show the updated file so we can see what\'s inside\n'
            '    print("\\n=== Updated notes ===")\n'
            '    with open(FILENAME, "r", encoding="utf-8") as f:\n'
            '        for i, line in enumerate(f, 1):\n'
            '            # .rstrip() removes the newline at the end of each line\n'
            '            print(f"  {i}. {line.rstrip()}")\n'
        ),
    },
    {
        "name": "Bank Account",
        "desc": "Build your own class (OOP)",
        "icon": "\U0001F3E6",
        "code": (
            '# Bank Account\n'
            '# Learn OBJECT-ORIENTED PROGRAMMING by building a CLASS.\n'
            '# A class is a blueprint — you use it to create "objects"\n'
            '# that bundle data (attributes) and behavior (methods) together.\n'
            '\n'
            '# "class" defines a new type. By convention class names use\n'
            '# CapitalizedWords (CamelCase).\n'
            'class BankAccount:\n'
            '    # __init__ runs automatically when you create a new account.\n'
            '    # "self" refers to the specific account being created.\n'
            '    def __init__(self, owner, starting_balance=0):\n'
            '        self.owner = owner                # attribute\n'
            '        self.balance = starting_balance   # attribute\n'
            '        self.history = []                 # list of past actions\n'
            '\n'
            '    # Methods are functions that belong to the class\n'
            '    def deposit(self, amount):\n'
            '        self.balance += amount\n'
            '        self.history.append(f"Deposited ${amount}")\n'
            '\n'
            '    def withdraw(self, amount):\n'
            '        if amount > self.balance:\n'
            '            print("Not enough funds!")\n'
            '            return\n'
            '        self.balance -= amount\n'
            '        self.history.append(f"Withdrew ${amount}")\n'
            '\n'
            '    def show(self):\n'
            '        print(f"\\n{self.owner}\'s account — balance: ${self.balance}")\n'
            '        print("History:")\n'
            '        for entry in self.history:\n'
            '            print(f"  - {entry}")\n'
            '\n'
            '\n'
            '# Create two separate account OBJECTS from the same class.\n'
            '# Each one keeps its own balance and history.\n'
            'alice = BankAccount("Alice", 100)\n'
            'bob = BankAccount("Bob")\n'
            '\n'
            '# Call methods on each object using dot notation\n'
            'alice.deposit(50)\n'
            'alice.withdraw(30)\n'
            '\n'
            'bob.deposit(200)\n'
            'bob.withdraw(500)   # too much — the method handles this gracefully\n'
            '\n'
            'alice.show()\n'
            'bob.show()\n'
        ),
    },
    {
        "name": "Safe Input",
        "desc": "Handle errors with try/except",
        "icon": "\U0001F6E1",
        "code": (
            '# Safe Input\n'
            '# Learn ERROR HANDLING with try/except so your program can\n'
            '# recover from bad input instead of crashing.\n'
            '\n'
            '# Without try/except, int("hello") would crash the whole program.\n'
            '# With try/except, we can catch the error and ask again.\n'
            '\n'
            'def ask_for_number(prompt):\n'
            '    """Keep asking until the user types a valid whole number."""\n'
            '    while True:\n'
            '        # Code that *might* fail goes inside the "try" block\n'
            '        try:\n'
            '            value = int(input(prompt))\n'
            '            return value   # Success! Exit the loop.\n'
            '        # If int() raises a ValueError, we handle it here\n'
            '        # instead of letting the program crash.\n'
            '        except ValueError:\n'
            '            print("  That isn\'t a whole number. Try again.")\n'
            '\n'
            '\n'
            'print("=== Safe Division ===")\n'
            '\n'
            'a = ask_for_number("Numerator: ")\n'
            'b = ask_for_number("Denominator: ")\n'
            '\n'
            '# You can catch several different kinds of errors.\n'
            '# ZeroDivisionError happens when dividing by 0.\n'
            'try:\n'
            '    result = a / b\n'
            '    print(f"{a} / {b} = {result}")\n'
            'except ZeroDivisionError:\n'
            '    print("Cannot divide by zero.")\n'
            '# "finally" runs no matter what — even if there was an error.\n'
            '# It\'s useful for cleanup tasks (closing files, etc.).\n'
            'finally:\n'
            '    print("Done!")\n'
        ),
    },
    {
        "name": "Rock Paper Scissors",
        "desc": "Decision logic vs. the computer",
        "icon": "\u270A",
        "code": (
            '# Rock Paper Scissors\n'
            '# Play against the computer! Practice with random choices,\n'
            '# comparison logic, and score tracking across rounds.\n'
            '\n'
            'import random\n'
            '\n'
            '# A list of the valid moves — the computer will pick one at random\n'
            'MOVES = ["rock", "paper", "scissors"]\n'
            '\n'
            '# A dictionary that says what each move BEATS.\n'
            '# Reading it: "rock" beats "scissors", "paper" beats "rock", etc.\n'
            '# This is a neat trick that avoids a long chain of if/elif.\n'
            'BEATS = {\n'
            '    "rock": "scissors",\n'
            '    "paper": "rock",\n'
            '    "scissors": "paper",\n'
            '}\n'
            '\n'
            'player_score = 0\n'
            'computer_score = 0\n'
            '\n'
            'print("=== Rock, Paper, Scissors ===")\n'
            'print("Type q at any time to quit.\\n")\n'
            '\n'
            'while True:\n'
            '    player = input("Your move (rock/paper/scissors): ").strip().lower()\n'
            '\n'
            '    if player == "q":\n'
            '        break\n'
            '    # "not in" checks whether the value is missing from the list\n'
            '    if player not in MOVES:\n'
            '        print("  Please type rock, paper, or scissors.\\n")\n'
            '        continue   # Skip the rest of this loop and ask again\n'
            '\n'
            '    # random.choice() picks one item from a list at random\n'
            '    computer = random.choice(MOVES)\n'
            '    print(f"  Computer chose: {computer}")\n'
            '\n'
            '    # Compare the moves using our BEATS dictionary\n'
            '    if player == computer:\n'
            '        print("  It\'s a tie!\\n")\n'
            '    elif BEATS[player] == computer:\n'
            '        print("  You win this round!\\n")\n'
            '        player_score += 1\n'
            '    else:\n'
            '        print("  Computer wins this round!\\n")\n'
            '        computer_score += 1\n'
            '\n'
            'print(f"\\nFinal score — You: {player_score}  Computer: {computer_score}")\n'
        ),
    },
]


# ── Welcome widget ────────────────────────────────────────────────────

def _rounded_pixmap(pixmap: QPixmap, size: int, radius: float) -> QPixmap:
    """Return ``pixmap`` scaled and clipped to a rounded square."""
    scaled = pixmap.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    rounded = QPixmap(size, size)
    rounded.fill(Qt.GlobalColor.transparent)

    painter = QPainter(rounded)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    clip_path = QPainterPath()
    clip_path.addRoundedRect(0, 0, size, size, radius, radius)
    painter.setClipPath(clip_path)
    painter.drawPixmap(0, 0, scaled)
    painter.end()

    return rounded


class _WelcomeHeroWidget(QWidget):
    """Paint the welcome-page brand block as a single stable hero widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_dark = False
        self._is_high_contrast = False
        self._palette = {
            "background": "#FFFFFF",
            "text": "#273026",
            "muted": "#7D857F",
            "accent": "#4CAF50",
        }
        self._icon_size = 92
        self._icon_radius = 22
        self._icon = QPixmap()

        icon_path = get_icon_path("meadowpy_256") or get_icon_path("meadowpy")
        if icon_path:
            self._icon = _rounded_pixmap(
                QPixmap(icon_path),
                self._icon_size,
                self._icon_radius,
            )

        self._title_font = QFont("Segoe UI", 1)
        self._title_font.setPixelSize(40)
        self._title_font.setBold(True)

        self._subtitle_font = QFont("Segoe UI", 1)
        self._subtitle_font.setPixelSize(15)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(238)

    def apply_theme(
        self,
        theme_name: str,
        custom_base: str = "dark",
        custom_accent: str | None = None,
    ) -> None:
        """Refresh the hero colors to match the active MeadowPy theme."""
        self._is_dark = theme_is_dark(theme_name, custom_base)
        self._is_high_contrast = theme_is_high_contrast(theme_name)
        accent = run_button_accent_hex(theme_name, custom_accent)

        if self._is_high_contrast:
            self._palette = {
                "background": "#000000",
                "text": "#FFFFFF",
                "muted": "#D7D7D7",
                "accent": "#FFFFFF",
            }
        elif self._is_dark:
            self._palette = {
                "background": "#1E1E1E",
                "text": "#F6FAF5",
                "muted": "#98A39B",
                "accent": accent,
            }
        else:
            self._palette = {
                "background": "#FFFFFF",
                "text": "#273026",
                "muted": "#7D857F",
                "accent": accent,
            }

        self.update()

    def paintEvent(self, event) -> None:
        """Paint the icon halo, split-color title, and subtitle."""
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        painter.fillRect(self.rect(), QColor(self._palette["background"]))
        icon_rect = self._paint_icon(painter)
        title_bottom = self._paint_title(painter, int(icon_rect.bottom()) + 30)
        self._paint_subtitle(painter, title_bottom + 12)
        painter.end()

    def _paint_icon(self, painter: QPainter) -> QRectF:
        """Paint the welcome icon with the same halo language as About."""
        icon_left = (self.width() - self._icon_size) / 2
        icon_top = 18 if self._is_high_contrast else 20
        icon_rect = QRectF(icon_left, icon_top, self._icon_size, self._icon_size)

        glow_color = QColor(self._palette["accent"])
        max_expand = 10 if self._is_high_contrast else 16
        glow_steps = 8 if self._is_high_contrast else 12
        max_alpha = 10 if self._is_high_contrast else 18

        for step in range(glow_steps, 0, -1):
            distance = step / glow_steps
            expand = 2 + (max_expand * distance)
            alpha = max(1, round(3 + (max_alpha * (1.0 - distance))))
            layer_color = QColor(glow_color)
            layer_color.setAlpha(alpha)
            layer_rect = icon_rect.adjusted(-expand, -expand, expand, expand)
            layer_radius = self._icon_radius + expand
            layer_path = QPainterPath()
            layer_path.addRoundedRect(layer_rect, layer_radius, layer_radius)
            painter.fillPath(layer_path, layer_color)

        inner_glow = QColor(glow_color)
        inner_glow.setAlpha(14 if self._is_high_contrast else 24)
        inner_rect = icon_rect.adjusted(-3, -3, 3, 3)
        inner_path = QPainterPath()
        inner_path.addRoundedRect(
            inner_rect,
            self._icon_radius + 3,
            self._icon_radius + 3,
        )
        painter.fillPath(inner_path, inner_glow)

        if not self._icon.isNull():
            painter.drawPixmap(int(icon_rect.x()), int(icon_rect.y()), self._icon)

        return icon_rect

    def _paint_title(self, painter: QPainter, top: int) -> int:
        """Paint a MeadowPy title with an accent-colored ``Py`` suffix."""
        base = APP_NAME[:-2] if APP_NAME.endswith("Py") else APP_NAME
        suffix = APP_NAME[-2:] if APP_NAME.endswith("Py") else ""

        painter.setFont(self._title_font)
        fm = QFontMetrics(self._title_font)
        total_width = fm.horizontalAdvance(base + suffix)
        base_width = fm.horizontalAdvance(base)
        baseline = top + fm.ascent()
        start_x = int((self.width() - total_width) / 2)

        painter.setPen(QColor(self._palette["text"]))
        painter.drawText(start_x, baseline, base)
        painter.setPen(QColor(self._palette["accent"]))
        painter.drawText(start_x + base_width, baseline, suffix)
        return top + fm.height()

    def _paint_subtitle(self, painter: QPainter, top: int) -> None:
        """Paint the welcome subtitle and current version."""
        painter.setFont(self._subtitle_font)
        painter.setPen(QColor(self._palette["muted"]))
        rect = QRectF(48, top, self.width() - 96, 28)
        painter.drawText(
            rect,
            int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter),
            f"A beginner-friendly Python IDE  ·  v{VERSION}",
        )


class WelcomeWidget(QWidget):
    """Welcome screen displayed as a tab when no files are open.

    Signals
    -------
    action_new_file()
        User clicked the New File button.
    action_open_file()
        User clicked the Open File button.
    action_open_folder()
        User clicked the Open Folder button.
    template_selected(str, str)
        User clicked a template.  Arguments: (tab_name, code).
    """

    action_new_file = pyqtSignal()
    action_open_file = pyqtSignal()
    action_open_folder = pyqtSignal()
    template_selected = pyqtSignal(str, str)   # (tab_name, code)

    def __init__(
        self,
        theme_name: str = "default_light",
        custom_base: str = "dark",
        custom_accent: str | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("WelcomeWidget")
        self._setup_ui()
        self.apply_theme(theme_name, custom_base, custom_accent)

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Scroll area so the welcome page can be viewed even when the
        # window is shorter than the content (e.g. with tabs open).
        scroll = QScrollArea()
        scroll.setObjectName("welcomeScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Let the theme background (light or dark) show through instead of
        # the scroll area's default opaque viewport colour.
        scroll.setStyleSheet(
            "QScrollArea#welcomeScrollArea, "
            "QScrollArea#welcomeScrollArea > QWidget > QWidget "
            "{ background: transparent; }"
        )
        outer.addWidget(scroll)

        scroll_content = QWidget()
        scroll_content.setObjectName("welcomeScrollContent")
        scroll_content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        scroll.setWidget(scroll_content)
        scroll_outer = QVBoxLayout(scroll_content)
        scroll_outer.setContentsMargins(0, 0, 0, 0)

        # Scrollable center column
        center = QWidget()
        center.setMinimumWidth(640)
        center.setMaximumWidth(720)
        center.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(center)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(12)

        # ── Title area ────────────────────────────────────────────
        self._hero_widget = _WelcomeHeroWidget(self)
        layout.addWidget(self._hero_widget)

        layout.addSpacing(24)

        # ── Quick actions row ─────────────────────────────────────
        actions_label = QLabel("Get Started")
        actions_label.setObjectName("welcomeSectionLabel")
        section_font = QFont()
        section_font.setPointSize(12)
        section_font.setBold(True)
        actions_label.setFont(section_font)
        layout.addWidget(actions_label)

        actions_row = QHBoxLayout()
        actions_row.setSpacing(12)

        new_btn = self._make_action_btn("New File", "Create a blank Python file")
        new_btn.clicked.connect(self.action_new_file.emit)
        actions_row.addWidget(new_btn)

        open_btn = self._make_action_btn("Open File", "Open an existing file")
        open_btn.clicked.connect(self.action_open_file.emit)
        actions_row.addWidget(open_btn)

        folder_btn = self._make_action_btn("Open Folder", "Open a project folder")
        folder_btn.clicked.connect(self.action_open_folder.emit)
        actions_row.addWidget(folder_btn)

        layout.addLayout(actions_row)

        layout.addSpacing(24)

        # ── Templates grid ────────────────────────────────────────
        templates_label = QLabel("Quick-Start Templates")
        templates_label.setObjectName("welcomeSectionLabel")
        templates_label.setFont(section_font)
        layout.addWidget(templates_label)

        # Build the grid as stacked HBox rows inside a VBox.
        # We use setSpacing(0) plus explicit addSpacing(...) between rows
        # so the gap is a hard guarantee — previous spacing values were
        # being visually collapsed somewhere in the layout tree.
        grid_wrap = QVBoxLayout()
        grid_wrap.setSpacing(0)
        grid_wrap.setContentsMargins(0, 0, 0, 0)

        COLS = 3
        H_GAP = 14   # horizontal gap between cards in a row
        V_GAP = 22   # vertical gap between rows — tuned so it visually
                     # matches the horizontal gap (Qt's addSpacing is exact
                     # pixels; HBox setSpacing renders slightly larger due
                     # to card borders/radius)
        current_row = None
        for idx, tmpl in enumerate(TEMPLATES):
            if idx % COLS == 0:
                if idx != 0:
                    grid_wrap.addSpacing(V_GAP)
                current_row = QHBoxLayout()
                current_row.setSpacing(H_GAP)
                grid_wrap.addLayout(current_row)
            current_row.addWidget(self._make_template_card(tmpl), 1)

        # If the last row is short, pad with invisible placeholders so
        # remaining cards keep their 1/3 width (don't stretch to fill).
        remainder = len(TEMPLATES) % COLS
        if remainder and current_row is not None:
            for _ in range(COLS - remainder):
                spacer = QWidget()
                spacer.setSizePolicy(
                    QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
                )
                current_row.addWidget(spacer, 1)

        layout.addLayout(grid_wrap)

        layout.addStretch(1)

        # Center the column horizontally inside the scroll area
        scroll_outer.addStretch(1)
        h_box = QHBoxLayout()
        h_box.addStretch(1)
        h_box.addWidget(center)
        h_box.addStretch(1)
        scroll_outer.addLayout(h_box)
        scroll_outer.addStretch(1)

    def apply_theme(
        self,
        theme_name: str,
        custom_base: str = "dark",
        custom_accent: str | None = None,
    ) -> None:
        """Refresh the welcome hero styling for the current theme."""
        self._hero_widget.apply_theme(theme_name, custom_base, custom_accent)

    # ── Widget builders ───────────────────────────────────────────

    def _make_action_btn(self, text: str, tooltip: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("welcomeActionBtn")
        btn.setToolTip(tooltip)
        btn.setMinimumHeight(40)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return btn

    def _make_template_card(self, tmpl: dict) -> QFrame:
        card = QFrame()
        card.setObjectName("welcomeTemplateCard")
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setFrameShape(QFrame.Shape.StyledPanel)
        # Lock the card to a uniform size so every row looks identical,
        # regardless of whether the description wraps to 1 or 2 lines.
        card.setFixedHeight(110)
        card.setMinimumWidth(180)
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(4)

        header = QLabel(f"{tmpl['icon']}  {tmpl['name']}")
        header.setObjectName("welcomeCardTitle")
        header_font = QFont()
        header_font.setPointSize(11)
        header_font.setBold(True)
        header.setFont(header_font)
        # Allow the title to wrap and ignore its own size hint so one long
        # name (e.g. "Temperature Converter") doesn't force its column wider
        # than the others.
        header.setWordWrap(True)
        header.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        card_layout.addWidget(header)

        desc = QLabel(tmpl["desc"])
        desc.setObjectName("welcomeCardDesc")
        desc.setWordWrap(True)
        # Same trick as the title — don't let description minWidth push
        # the column wider than the stretch allocation.
        desc.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        desc_font = QFont()
        desc_font.setPointSize(9)
        desc.setFont(desc_font)
        card_layout.addWidget(desc)

        card_layout.addStretch()

        # Make the whole card clickable
        card.mousePressEvent = lambda ev, t=tmpl: self._on_template_clicked(t)
        return card

    def _on_template_clicked(self, tmpl: dict) -> None:
        self.template_selected.emit(tmpl["name"], tmpl["code"])
