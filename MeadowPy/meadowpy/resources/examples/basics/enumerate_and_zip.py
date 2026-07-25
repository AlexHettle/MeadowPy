# Enumerate & Zip
# Two handy built-in functions for working with sequences.

# === enumerate() — loop with an index ===
# Instead of tracking an index manually:
fruits = ["apple", "banana", "cherry", "date"]

print("Shopping list:")
for i, fruit in enumerate(fruits, start=1):
    print(f"  {i}. {fruit}")

# === zip() — loop over multiple lists together ===
names = ["Alice", "Bob", "Charlie"]
scores = [95, 87, 92]
grades = ["A", "B+", "A-"]

print("\nStudent results:")
for name, score, grade in zip(names, scores, grades):
    print(f"  {name}: {score} ({grade})")

# zip stops at the shortest list
short = [1, 2]
long = [10, 20, 30, 40]
print(f"\nzip stops early: {list(zip(short, long))}")

# === Combining both ===
tasks = ["Write report", "Fix bug", "Code review"]
owners = ["Alice", "Bob", "Charlie"]

print("\nTask assignments:")
for i, (task, owner) in enumerate(zip(tasks, owners), start=1):
    print(f"  {i}. {task} -> {owner}")

# === Creating a dict from two lists ===
keys = ["name", "age", "city"]
values = ["Alice", 30, "London"]
person = dict(zip(keys, values))
print(f"\nDict from zip: {person}")
