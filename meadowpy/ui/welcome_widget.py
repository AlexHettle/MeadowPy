"""Welcome screen shown when MeadowPy launches with no files open."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from meadowpy.constants import APP_NAME, VERSION
from meadowpy.resources.resource_loader import get_icon_path


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
]


# ── Welcome widget ────────────────────────────────────────────────────

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

    def __init__(self, is_dark: bool = False, parent=None):
        super().__init__(parent)
        self._is_dark = is_dark
        self.setObjectName("WelcomeWidget")
        self._setup_ui()

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Scrollable center column
        center = QWidget()
        center.setMaximumWidth(720)
        center.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(center)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(12)

        # ── Title area ────────────────────────────────────────────
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_path = get_icon_path("meadowpy_256")
        if icon_path:
            pixmap = QPixmap(icon_path).scaled(
                64, 64,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            icon_label.setPixmap(pixmap)
        layout.addWidget(icon_label)

        title = QLabel(APP_NAME)
        title.setObjectName("welcomeTitle")
        title_font = QFont()
        title_font.setPointSize(28)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel(f"A beginner-friendly Python IDE  ·  v{VERSION}")
        subtitle.setObjectName("welcomeSubtitle")
        sub_font = QFont()
        sub_font.setPointSize(11)
        subtitle.setFont(sub_font)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

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

        grid = QGridLayout()
        grid.setSpacing(12)

        for idx, tmpl in enumerate(TEMPLATES):
            card = self._make_template_card(tmpl)
            row, col = divmod(idx, 3)
            grid.addWidget(card, row, col)

        layout.addLayout(grid)

        layout.addStretch(1)

        # Center the column horizontally
        outer.addStretch(1)
        h_box = QHBoxLayout()
        h_box.addStretch(1)
        h_box.addWidget(center)
        h_box.addStretch(1)
        outer.addLayout(h_box)
        outer.addStretch(1)

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
        card.setMinimumHeight(90)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(4)

        header = QLabel(f"{tmpl['icon']}  {tmpl['name']}")
        header.setObjectName("welcomeCardTitle")
        header_font = QFont()
        header_font.setPointSize(11)
        header_font.setBold(True)
        header.setFont(header_font)
        card_layout.addWidget(header)

        desc = QLabel(tmpl["desc"])
        desc.setObjectName("welcomeCardDesc")
        desc.setWordWrap(True)
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
