# Type Hints
# Type hints make your code easier to read and catch bugs early.
# Python doesn't enforce them — they're documentation for humans and tools.

# === Basic variable annotations ===
name: str = "Alice"
age: int = 30
height: float = 5.6
is_active: bool = True

# === Function annotations ===
def greet(name: str, excited: bool = False) -> str:
    """Return a greeting message."""
    if excited:
        return f"HI {name.upper()}!!!"
    return f"Hello, {name}."

print(greet("Alice"))
print(greet("Bob", excited=True))

# === Collection types ===
scores: list[int] = [95, 87, 92]
config: dict[str, str] = {"theme": "dark", "lang": "en"}
coordinates: tuple[float, float] = (3.14, 2.72)
unique_ids: set[int] = {1, 2, 3}

# === Optional values (might be None) ===
def find_user(user_id: int) -> str | None:
    """Find a user by ID. Returns None if not found."""
    users = {1: "Alice", 2: "Bob"}
    return users.get(user_id)

result = find_user(1)
print(f"\nFound: {result}")
result = find_user(99)
print(f"Found: {result}")

# === A practical example ===
def average(numbers: list[float]) -> float:
    """Calculate the average of a list of numbers."""
    if not numbers:
        return 0.0
    return sum(numbers) / len(numbers)

grades: list[float] = [85.5, 92.0, 78.5, 96.0]
print(f"\nAverage grade: {average(grades):.1f}")
