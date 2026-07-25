# Magic Methods (Dunder Methods)
# Special methods like __add__, __len__, __eq__ let you
# control how your objects work with Python operators.

class Vector:
    """A 2D vector with x and y components."""

    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __repr__(self):
        """How the vector looks when printed."""
        return f"Vector({self.x}, {self.y})"

    def __add__(self, other):
        """v1 + v2 adds the components."""
        return Vector(self.x + other.x, self.y + other.y)

    def __mul__(self, scalar):
        """v * 3 scales the vector."""
        return Vector(self.x * scalar, self.y * scalar)

    def __eq__(self, other):
        """v1 == v2 checks if components match."""
        return self.x == other.x and self.y == other.y

    def __abs__(self):
        """abs(v) returns the length of the vector."""
        return (self.x ** 2 + self.y ** 2) ** 0.5


# Now we can use +, *, ==, abs() with Vectors!
a = Vector(3, 4)
b = Vector(1, 2)

print(f"a = {a}")
print(f"b = {b}")
print(f"a + b = {a + b}")
print(f"a * 3 = {a * 3}")
print(f"a == b: {a == b}")
print(f"a == Vector(3, 4): {a == Vector(3, 4)}")
print(f"|a| = {abs(a):.2f}")  # 3-4-5 triangle!
