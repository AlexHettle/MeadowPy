# Pattern Matching (Python 3.10+)
# match/case is like a powerful "switch" statement.

# === Basic value matching ===
command = "quit"

match command:
    case "start":
        print("Starting...")
    case "stop":
        print("Stopping...")
    case "quit" | "exit":  # match multiple values with |
        print("Goodbye!")
    case _:  # _ is the wildcard / default
        print(f"Unknown command: {command}")

# === Matching with variables (capture patterns) ===
point = (3, 7)

match point:
    case (0, 0):
        print("Origin")
    case (x, 0):
        print(f"On the x-axis at {x}")
    case (0, y):
        print(f"On the y-axis at {y}")
    case (x, y):
        print(f"Point at ({x}, {y})")

# === Matching with guards (if conditions) ===
age = 25

match age:
    case n if n < 0:
        print("Invalid age")
    case n if n < 18:
        print(f"Minor ({n} years old)")
    case n if n < 65:
        print(f"Adult ({n} years old)")
    case n:
        print(f"Senior ({n} years old)")

# === Matching dictionaries ===
action = {"type": "move", "direction": "north", "steps": 3}

match action:
    case {"type": "move", "direction": d, "steps": s}:
        print(f"Moving {d} for {s} steps")
    case {"type": "attack", "target": t}:
        print(f"Attacking {t}")
    case _:
        print("Unknown action")
