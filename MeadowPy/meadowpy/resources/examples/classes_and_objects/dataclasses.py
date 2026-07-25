# Dataclasses
# The @dataclass decorator auto-generates __init__,
# __repr__, __eq__, and more — less typing!

from dataclasses import dataclass, field

# === Without dataclass (lots of boilerplate) ===
# class Point:
#     def __init__(self, x, y):
#         self.x = x
#         self.y = y
#     def __repr__(self): ...
#     def __eq__(self, other): ...

# === With dataclass (clean and simple!) ===
@dataclass
class Point:
    x: float
    y: float

p1 = Point(3, 4)
p2 = Point(3, 4)
p3 = Point(1, 2)

print(f"p1 = {p1}")           # Auto __repr__
print(f"p1 == p2: {p1 == p2}") # Auto __eq__
print(f"p1 == p3: {p1 == p3}")

# === Default values and fields ===
@dataclass
class Student:
    name: str
    age: int
    grade: str = "N/A"              # Default value
    courses: list = field(default_factory=list)  # Mutable default

    def is_passing(self):
        return self.grade not in ("F", "N/A")

alice = Student("Alice", 15, "A")
bob = Student("Bob", 14)  # Uses defaults

alice.courses.append("Math")
alice.courses.append("Science")

print(f"\n{alice}")
print(f"Passing: {alice.is_passing()}")
print(f"Courses: {alice.courses}")

print(f"\n{bob}")
print(f"Passing: {bob.is_passing()}")
print(f"Courses: {bob.courses}")  # Empty — not shared!
